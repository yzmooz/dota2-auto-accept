from dataclasses import dataclass
from enum import Enum


class EngineState(str, Enum):
    STOPPED = "stopped"
    WAITING = "waiting"
    DETECTING = "detecting"
    VERIFYING = "verifying"
    ACCEPTED = "accepted"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class EngineEvent:
    state: EngineState
    title: str
    detail: str = ""
