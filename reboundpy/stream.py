from reboundpy.models import HandshakeMessage, ConnectMessage, SubscribeMessage
import reboundpy.constants as constants

class LiveStreamStats:
    def __init__(self, sports_code, game_id):
        self._sports_code = sports_code
        self._game_id = game_id
        response = _fetch_url(
            f"{constants.BASE_STATS_URL}/{self._game_id}/box_score"
        )
        match = re.search(
            r"livestream_user_id=([^;]+);.*?_stats_session=([^;]+);", response.headers["Set-Cookie"]
        )
        self._livestream_user_id = match.group(1)
        self._websocket_message_ext = {
            "livestream_token": "",
            "livestream_user_id": self._livestream_user_id,
        }
        self._stats_session = match.group(2)
        self._session_cookie = (
            f"livestream_user_id={self._livestream_user_id}; _stats_session={match.group(2)}"
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

    async def _process_messages(self, websocket):
        while True:
            async for message in websocket:
                message = json.loads(message)

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