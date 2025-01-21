import json
from typing import ClassVar
from dataclasses import dataclass, field, asdict


@dataclass
class BaseMessage:
    ext: dict
    channel: str = field(init=False)
    id: str = field(init=False)

    _id_counter: ClassVar[int] = 0

    def __post_init__(self):
        self.id = str(self.__class__._id_counter)
        self.__class__._id_counter += 1

    def to_json(self) -> str:
        return json.dumps(asdict(self))

@dataclass
class HandshakeMessage(BaseMessage):
    version: str = "1.0"
    supportedConnectionTypes: list = field(
        default_factory=lambda: [
            "websocket",
            "eventsource",
            "long-polling",
            "cross-origin-long-polling",
            "callback-polling",
        ]
    )

    def __post_init__(self):
        super().__post_init__()
        self.channel = "/meta/handshake"

@dataclass
class ConnectMessage(BaseMessage):
    clientId: str
    connectionType: str = "websocket"

    def __post_init__(self):
        super().__post_init__()
        self.channel = "/meta/connect"

@dataclass
class SubscribeMessage(BaseMessage):
    clientId: str
    subscription: str

    def __post_init__(self):
        super().__post_init__()
        self.channel = "/meta/subscribe"