import re
import json
import time
import asyncio

import lxml
import websockets
from bs4 import BeautifulSoup

from src.http import fetch_url
import src.constants as constants
from src.helpers import normalize_player_stats, map_player_headers_to_player_fields
from src.models import HandshakeMessage, ConnectMessage, SubscribeMessage, Scoreboard, Player


def _get_scoreboards(box_score_html: str) -> tuple[Scoreboard, Scoreboard]:
    soup = BeautifulSoup(box_score_html, "lxml")
    for index, scoreboard in enumerate(soup.find_all("div", class_="col p-2")):
        team_info = scoreboard.find("span", class_="d-none d-sm-block")
        team_img = scoreboard.find("img")
        player_data_table = scoreboard.find("table", id=lambda x: x and x.startswith("competitor_"))
        table_headers = [th.text.strip() for th in player_data_table.find_all("th")]
        players = []
        for player in player_data_table.find_all("tr"):
            player_data = [td.text.strip() for td in player.find_all("td")]
            if len(player_data) > 0:
                if len(player_data) < len(table_headers):
                    continue
                player_data = normalize_player_stats(dict(zip(table_headers, player_data)))
                player_data = map_player_headers_to_player_fields(Player, player_data)
                players.append(Player(**player_data))

        scoreboard = Scoreboard(
            team_name=team_info.text.strip() if team_info else None,
            team_logo_url=team_img.get("src") if team_img else None,
            players=players,
        )
        if index == 0:
            away_scoreboard = scoreboard
        else:
            home_scoreboard = scoreboard
    return away_scoreboard, home_scoreboard


class LiveStreamStats:
    def __init__(self, sports_code, game_id):
        self._sports_code = sports_code
        self._game_id = game_id
        response = fetch_url(f"{constants.BASE_STATS_URL}/{self._game_id}/box_score")

        # TODO: Add sane loop here for box_score to become available.
        match = re.search(
            r"(?:livestream_user_id=([^;]+);)?(?:.*?_stats_session=([^;]+);)?",
            response.headers["Set-Cookie"],
        )
        # match = None
        # with open("test_box_score.html", "r") as file:
        #     test_html = file.read()
        self.away_scoreboard, self.home_scoreboard = _get_scoreboards(response.text)
        livestream_user_id = match.group(1) if match and match.group(1) else ""
        self._websocket_message_ext = {
            "livestream_token": "",
            "livestream_user_id": livestream_user_id,
        }
        stats_session = match.group(2) if match and match.group(2) else ""
        self._session_cookie = (
            f"livestream_user_id={livestream_user_id}; _stats_session={stats_session}"
        )

    def _handshake(self, websocket):
        message = HandshakeMessage(
            ext=self._websocket_message_ext,
        )
        return websocket.send(message.to_json())

    def _connect(self, websocket):
        message = ConnectMessage(
            clientId=self._client_id,
            ext=self._websocket_message_ext,
        )
        return websocket.send(message.to_json())

    def _subscribe(self, websocket):
        message = SubscribeMessage(
            clientId=self._client_id,
            subscription=f"/{self._sports_code}/box_score/{self._game_id}",
            ext=self._websocket_message_ext,
        )
        return websocket.send(message.to_json())

    async def _refresh_connection(self, websocket):
        while True:
            await asyncio.sleep(constants.WEBSOCKET_REFRESH_SEC)
            await self._connect(websocket)

    def _get_player(self, player_name: str, team_shortname: str) -> Player:
        """Fetch the player object by name and assign team shortname if needed."""
        if self.away_scoreboard.team_shortname == team_shortname:
            return self.away_scoreboard.get_player_by_name(player_name)
        if self.home_scoreboard.team_shortname == team_shortname:
            return self.home_scoreboard.get_player_by_name(player_name)

        # Default fallback
        player = self.away_scoreboard.get_player_by_name(player_name)
        if player:
            self.away_scoreboard.team_shortname = team_shortname
            return player

        player = self.home_scoreboard.get_player_by_name(player_name)
        if player:
            self.home_scoreboard.team_shortname = team_shortname
        return player

    def _parse_plays(self, play_text: str):
        pattern = r"(?P<player_name>[A-Za-z\s]+)\((?P<team_shortname>[A-Za-z]+)\)"
        return re.finditer(pattern, play_text)

    def _process_play_data(self, play_key, play_info):
        play_id = int(play_key.split("_")[1])
        plays_text = play_info.get(f"play_text_{play_id}", "").split(",")
        clock = play_info.get(f"clock_{play_id}", "")
        period = play_info.get(f"period_{play_id}", 0)

        for play_text in plays_text:
            for match in self._parse_plays(play_text):
                player = self._get_player(
                    match.group("player_name").strip(),
                    match.group("team_shortname"),
                )
                if player:
                    player.add_play(play_id, play_text, clock, period)

    async def _process_messages(self, websocket) -> None:
        while True:
            async for raw_message in websocket:
                message = json.loads(raw_message)
                for item in message:
                    if not self._is_relevant_message(item):
                        continue
                    play_data = self._extract_play_data(item)
                    for play_key, play_info in play_data.items():
                        self._process_play_data(play_key, play_info)

    def _is_relevant_message(self, item) -> bool:
        return (
            "channel" in item
            and item["channel"] == f"/{self._sports_code}/box_score/{self._game_id}"
            and "data" in item
            and "chart" not in item
            and "shot_chart" not in item
        )

    def _extract_play_data(self, item):
        return {key: value for key, value in item["data"].items() if key.startswith("play_")}

    async def stream(self):
        async for websocket in websockets.connect(
            "wss://livestream.ncaa.org/stream",
            user_agent_header=constants.USER_AGENT,
            additional_headers={"Cookie": self._session_cookie},
        ):
            try:
                await self._handshake(websocket)
                message = await websocket.recv()
                message = json.loads(message)
                if message[0]["successful"]:
                    self._client_id = message[0]["clientId"]
                await self._connect(websocket)
                await self._subscribe(websocket)
                refresh_task = asyncio.create_task(self._refresh_connection(websocket))
                process_task = asyncio.create_task(self._process_messages(websocket))
                await asyncio.gather(refresh_task, process_task)
            except websockets.ConnectionClosed as ex:
                print(ex)
                continue
