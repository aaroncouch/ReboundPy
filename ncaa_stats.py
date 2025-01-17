"""
NCAA Basketball Stats CLI Tool

This script provides a command-line interface (CLI) to retrieve NCAA Basketball game statistics.

Features:
1. List all games by a given date.
2. Retrieve live player statistics for a specific game ID.
3. Support for looping execution to periodically fetch data.

Dependencies:
    - Python 3.x
    - Libraries:
        - requests
        - pandas
        - BeautifulSoup4
        - lxml
        - urllib3

Usage Examples:
    - List all games by date:
        python script.py --list-games-by-date 01/01/2024 --sports-code WBB --division 1

    - Get live player stats by game ID:
        python script.py --get-live-player-stats 12345

    - Loop execution every 30 seconds:
        python script.py --get-live-player-stats 12345 --loop --loop-interval-sec 30

Optional Arguments:
    --sports-code          Specify the sport code (default: WBB).
    --division             NCAA division (default: 1).
    --loop                 Enable looping mode for periodic data retrieval.
    --loop-interval-sec    Interval in seconds for looping mode (default: 30).

"""

import re
import os
import json
import time
import argparse
from typing import Optional, Any, Union
from urllib3.util.retry import Retry

import requests
from requests import Session, Response
from requests.adapters import HTTPAdapter
import pandas as pd
from bs4 import BeautifulSoup
from bs4.element import Tag
import lxml


def _fetch_url(
    url: str,
    retries: int = 3,
    backoff_factor: float = 0.3,
    status_forcelist: tuple = (500, 502, 504),
    timeout: int = 30,
    params: Optional[dict[Any, Any]] = None,
) -> Response:
    """
    Fetches a URL using requests with retries and exception handling.

    Args:
        url                (str): The URL to fetch.
        retries            (int): The number of retry attempts (default is 3).
        backoff_factor   (float): A backoff factor to apply between attempts (default is 0.3).
        status_forcelist (tuple): A set of HTTP status codes to retry (default is (500, 502, 504)).
        timeout            (int): The timeout in seconds for the request (default is 5).

    Returns:
        Response object if the request is successful.
        None if all retries fail or an exception occurs.
    """
    try:
        session = Session()
        retries = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        response = session.get(
            url,
            params=params,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ( "
                    "KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None


def _normalize_player_stats(player_data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalizes player statistics by converting numeric strings to integers,
    replacing empty strings with zeros, and substituting '*' with 1.

    Args:
        player_data (dict[Any, Any]): A dictionary containing player statistics.

    Returns:
        dict[Any, Any]: A new dictionary with normalized values.
    """
    normalized = {}
    for key, value in player_data.items():
        if isinstance(value, str):
            if value.isdigit():
                normalized[key] = int(value)
            # Replace empty strings with zero
            elif value == "":
                normalized[key] = 0
            # Replace '*' with 1
            elif value == "*":
                normalized[key] = 1
            # Keep other strings as-is
            else:
                normalized[key] = value
        else:
            # Preserve non-string values as-is
            normalized[key] = value
    return normalized


def _livestream_scoreboards_soup(
    date: str, sports_code: str, division: int, conference_id: Optional[int] = None
) -> BeautifulSoup:
    """Fetches and parses the NCAA livestream scoreboards page for a specific date and sport.

    Args:
        date          (str): The game date in the format "MM/DD/YYYY".
        sports_code   (str): The sports code (e.g., "MBB" for Men's Basketball).
        division      (int): The NCAA division (e.g., 1, 2, or 3).
        conference_id (int): The ID of the conference. Defaults to None.

    Returns:
        BeautifulSoup: Parsed HTML content of the livestream scoreboards page.
    """
    params = {
        "utf8": "%E2%9C%93",
        "sport_code": sports_code,
        "academic_year": date.split("/")[-1],
        "division": division,
        "game_date": date,
        "commit": "Submit",
    }
    if conference_id is not None:
        params["conference_id"] = conference_id
    response = _fetch_url(
        "https://stats.ncaa.org/contests/livestream_scoreboards",
        params=params,
    )

    return BeautifulSoup(response.text, "lxml")


def _get_href_id(element: Tag, split_index: int) -> str | None:
    """Extracts a specific part of the href attribute from an HTML element.

    Args:
        element     (Tag): The HTML tag element to extract from.
        split_index (int): The index to split the href by "/" and retrieve.

    Returns:
         str: The extracted part of the href attribute, or None if an href isn't found.
    """
    return element.get("href", "").split("/")[split_index] if element else None


def _get_text(element: Tag) -> str | None:
    """Extracts and strips the text content from an HTML element.

    Args:
        element (Tag): The HTML tag element to extract text from.

    Returns:
        str: The stripped text content, or None if a bad element is given.
    """
    return element.text.strip() if element else None


def get_days_scoreboard(
    date: str, sports_code: str, division: int, conference_id: Optional[int] = None
) -> pd.DataFrame:
    """
    Retrieves the scoreboard data for games on a specified date.

    Args:
        date          (str): The date of the games in 'mm/dd/yyyy' format.
        sports_code   (str): The sport code (e.g., 'WBB' for women's basketball).
        division      (int): NCAA division number (e.g., 1, 2, or 3).
        conference_id (int): NCCA conference number (e.g. 30022, 14825 or 834)

    Returns:
        pd.DataFrame: DataFrame containing the scoreboard data for the specified date.
    """
    soup = _livestream_scoreboards_soup(date, sports_code, division, conference_id)
    data_array = []

    # Process each game table
    for table in soup.find_all("table"):
        # Extract metadata for each gam
        box_info = table.find(
            "a", target=lambda x: x and x.startswith("box_score_"), class_="skipMask"
        )
        live_box_info = table.find("a", target="LIVE_BOX_SCORE", class_="skipMask")
        if live_box_info:
            box_info = live_box_info
        time_info = table.find("div", class_="col-6 p-0")
        period_info = table.find("span", id=lambda x: x and x.startswith("period_"))
        clock_info = table.find("span", id=lambda x: x and x.startswith("clock_"))
        attendance_info = table.find("div", class_="col p-0 text-right")
        attendance = None
        if attendance_info and "Attend:" in attendance_info.text:
            attendance = attendance_info.text.replace("Attend:", "").strip()
        period_scores = table.find("table", id=lambda x: x and x.startswith("linescore_"))
        if period_scores is None:
            continue
        period_scores = period_scores.find_all("td")
        data = {
            "game_id": _get_href_id(box_info, split_index=-2),
            "match_time": _get_text(time_info),
            "match_period": _get_text(period_info),
            "match_clock": _get_text(clock_info),
            "attendance": attendance,
        }
        rows = table.find_all("tr", id=lambda x: x and x.startswith("contest_"))
        # Extract team data
        for index, row in enumerate(rows):
            venue = "away" if index == 0 else "home"
            team_img = row.find("img")
            team_info = row.find("a", class_="skipMask")
            period_scores = table.find("table", id=lambda x: x and x.startswith("linescore_"))
            period_scores = period_scores.find_all("td")
            final_score_info = row.find("div", id=lambda x: x and x.startswith("score_"))
            # Period scores are stored in slices of the list: 0-3 for "away" and 4-7 for "home"
            start_index = index * 4  # 0 for away, 4 for home
            period_scores_dict = {
                f"{venue}_period_{i+1}_score": (
                    period_scores[start_index + i].text
                    if start_index + i < len(period_scores)
                    else None
                )
                for i in range(4)  # 4 periods per team
            }
            data.update(
                {
                    f"{venue}_name": _get_text(team_info),
                    f"{venue}_id": _get_href_id(team_info, split_index=-1),
                    f"{venue}_logo_url": team_img.get("src") if team_img else None,
                    **period_scores_dict,
                    f"{venue}_final_score": _get_text(final_score_info),
                }
            )
        if data:
            data_array.append(data)
    return pd.DataFrame(data_array)


def get_live_player_stats(game_id: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Retrieves live player statistics from the give game ID.

    Args:
        game_id (int): The unique identifier of the basketball game you want to retrieve stats for.

    Returns:
        tuple: Returns a tuple of Dataframes where the first is the away team's stats and the
               second is the home team's stats.
    """
    response = _fetch_url(
        f"https://stats.ncaa.org/contests/livestream_scoreboards/{game_id}/box_score",
    )
    soup = BeautifulSoup(response.text, "lxml")
    for index, scoreboard in enumerate(soup.find_all("div", class_="col p-2")):
        team_info = scoreboard.find("span", class_="d-none d-sm-block")
        team_img = scoreboard.find("img")
        player_data_table = scoreboard.find("table", id=lambda x: x and x.startswith("competitor_"))
        table_headers = [th.text.strip() for th in player_data_table.find_all("th")]
        team_data = []
        for player in player_data_table.find_all("tr"):
            aggregate_column = False
            player_data = [td.text.strip() for td in player.find_all("td")]
            if len(player_data) > 0:
                if len(player_data) < len(table_headers):
                    aggregate_column = True
                    player_data[1:1] = [None] * 4
                player_data = _normalize_player_stats(dict(zip(table_headers, player_data)))
                player_data["team_name"] = team_info.text.strip() if team_info else None
                player_data["team_logo_url"] = team_img.get("src") if team_img else None
                if aggregate_column:
                    team_data.insert(0, player_data)
                else:
                    team_data.append(player_data)
        if index == 0:
            away_data_array = team_data
        else:
            home_data_array = team_data
    return pd.DataFrame(away_data_array), pd.DataFrame(home_data_array)


def main() -> None:
    """
    Main function to parse command-line arguments and execute the appropriate actions based on input.
    """
    parser = argparse.ArgumentParser(
        description="Simple CLI tool for getting NCAA Basketball game stats."
    )

    # Define mutually exclusive arguments
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--list-games-by-date",
        type=str,
        help=(
            "List all of the games, and their IDs, by the given date in mm/dd/yyyy format. "
            "A single CSV file will be written to disk as <date>.csv."
        ),
    )
    group.add_argument(
        "--get-live-player-stats",
        type=int,
        help=(
            "Gets the live game stats of the given game ID as a CSV file written to disk. "
            "Two CSV files will be written to disk, away.csv and home.csv."
        ),
    )
    # Additional optional arguments
    parser.add_argument(
        "--sports-code",
        type=str,
        help="The sports code to use when looking up games by date.",
        choices=["WBB", "MBB"],
        default="WBB",
    )
    parser.add_argument(
        "--division",
        type=int,
        help="The NCAA division to use when looking up games by date.",
        default=1,
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Specify this flag if you want to peform your action in a loop.",
    )
    parser.add_argument(
        "--loop-interval-sec",
        type=int,
        help="Specify the amount of time, in seconds, to wait in between each loop.",
        default=30,
    )

    args, unknown_args = parser.parse_known_args()

    # I didn't want to have to maintain all of the IDs for the conferences and their
    # corresponding names. So I'm scraping them from the source. I didn't want to be abusive
    # and poll for the correct ID all the time so I'm opting to write them all to disk.
    conferences = {}
    conferences_filename = f"{args.sports_code}_d{args.division}_conf_ids.json"
    if not os.path.exists(conferences_filename) and args.list_games_by_date:
        soup = _livestream_scoreboards_soup(
            date=args.list_games_by_date, sports_code=args.sports_code, division=args.division
        )
        options = soup.find("select", id="conference_id_select", class_="chosen-select")
        conferences = {
            option.text.strip(): int(option.get("value"))
            for option in options.find_all("option")
            if option.get("value")
        }
        with open(conferences_filename, "w") as file:
            json.dump(conferences, file)
    # There's already a conference ID file on disk matching the scoreboard criteria given.
    elif os.path.exists(conferences_filename) and args.list_games_by_date:
        with open(conferences_filename, "r") as file:
            conferences = json.load(file)

    parser.add_argument(
        "--conference",
        type=str,
        help="The name of the conference to use when looking up games by date.",
        choices=list(conferences.keys()),
    )

    args = parser.parse_args()

    while True:
        try:
            if args.list_games_by_date:
                data = get_days_scoreboard(
                    date=args.list_games_by_date,
                    sports_code=args.sports_code,
                    division=args.division,
                    conference_id=conferences.get(args.conference, None),
                )
                # Default filename based on date
                filename = f"{args.list_games_by_date.replace('/', '-')}.csv"
                data.to_csv(filename, index=False)

            # Handle the 'get-live-player-stats' option
            elif args.get_live_player_stats:
                away_data, home_data = get_live_player_stats(game_id=args.get_live_player_stats)
                filename = f"{args.get_live_player_stats}.csv"
                away_data.to_csv("away.csv", index=False)
                home_data.to_csv("home.csv", index=False)
        except Exception as e:
            print(f"Error executing: {e}")

        if not args.loop:
            break
        time.sleep(args.loop_interval_sec)


if __name__ == "__main__":
    main()
