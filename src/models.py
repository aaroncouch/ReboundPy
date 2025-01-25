import re
import json
from typing import ClassVar, Union
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


@dataclass
class Play:
    play_id: int
    play_text: str
    clock: str
    period: int


@dataclass
class Player:
    name: str = field(metadata={"header": "Name"})
    number: int = field(metadata={"header": "#"})
    position: str = field(metadata={"header": "Pos"})
    starter: int = field(metadata={"header": "Starter"})
    on_court: int = field(metadata={"header": "On Court"})
    minutes_played: str = field(default="0:00", metadata={"header": "MP"})
    field_goals_made: int = field(
        default=0,
        metadata={
            "header": "FGM",
            "regex": r"(jump shot|layup).*made",
        },
    )
    field_goals_attempted: int = field(
        default=0,
        metadata={
            "header": "FGA",
            "regex": r"free throw.*missed|made",
        },
    )
    three_point_field_goals_made: int = field(
        default=0,
        metadata={
            "header": "3FGM",
            "regex": r"3pt.*made",
        },
    )
    three_point_field_goals_attempted: int = field(
        default=0,
        metadata={
            "header": "3FGA",
            "regex": r"3pt.*missed|made",
        },
    )
    free_throws_made: int = field(
        default=0,
        metadata={
            "header": "FTM",
            "regex": r"free throw.*made",
        },
    )
    free_throws_attempted: int = field(
        default=0,
        metadata={
            "header": "FTA",
            "regex": r"free throw.*missed|made",
        },
    )
    points: int = field(default=0, metadata={"header": "PTS"})
    offensive_rebounds: int = field(default=0, metadata={"header": "ORebs"})
    defensive_rebounds: int = field(default=0, metadata={"header": "DRebs"})
    total_rebounds: int = field(default=0, metadata={"header": "Rebs"})
    assists: int = field(default=0, metadata={"header": "A"})
    turnovers: int = field(default=0, metadata={"header": "TO", "regex": r"turnover.*"})
    steals: int = field(default=0, metadata={"header": "S"})
    blocks: int = field(default=0, metadata={"header": "B"})
    fouls: int = field(default=0, metadata={"header": "F", "regex": r"foul.*"})
    disqualifications: int = field(default=0, metadata={"header": "DQ"})
    technical_fouls: int = field(default=0, metadata={"header": "TFoul"})
    plays: list[Play] = field(default_factory=list)

    def add_play(self, play_id: int, play_text: str, clock: str, period: int) -> Play:
        existing_play = next(
            (
                play
                for play in self.plays
                if play.play_id == play_id
                and play_text == play_text
                and clock == clock
                and period == period
            ),
            None,
        )
        if existing_play:
            return existing_play
        new_play = Play(
            play_id=play_id,
            play_text=play_text,
            clock=clock,
            period=period,
        )
        self._update_stats_from_play(new_play.play_text)
        self.plays.append(new_play)
        return new_play

    def _update_stats_from_play(self, play_text: str) -> None:
        matched = False

        for field_name, field_meta in self.__dataclass_fields__.items():
            regex = field_meta.metadata.get("regex")
            if regex and re.search(regex, play_text, re.IGNORECASE):
                # Increment the metric
                current_value = getattr(self, field_name)
                setattr(self, field_name, current_value + 1)

                matched = True  # A match was found for this play_text

        if not matched:
            print(f"Unmatched play text: {play_text}")


@dataclass
class Scoreboard:
    team_name: str = field(metadata={"header": "Team Name"})
    team_logo_url: str = field(metadata={"header": "Team Logo URL"})
    players: list[Player]
    team_shortname: str = field(default=None)

    def get_player_by_name(self, name: str) -> Union[Player, None]:
        return next((player for player in self.players if player.name == name), None)
