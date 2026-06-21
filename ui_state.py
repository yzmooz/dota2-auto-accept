"""Pure presentation mapping for structured engine events."""

from dataclasses import dataclass

from engine_events import EngineEvent, EngineState


@dataclass(frozen=True, slots=True)
class DisplayState:
    title: str
    detail: str
    primary_action: str
    tone: str


def display_for(event: EngineEvent) -> DisplayState:
    tone = {
        EngineState.STOPPED: "neutral",
        EngineState.WAITING: "success",
        EngineState.DETECTING: "working",
        EngineState.VERIFYING: "working",
        EngineState.ACCEPTED: "success",
        EngineState.FAILED: "danger",
    }[event.state]
    return DisplayState(
        title=event.title,
        detail=event.detail,
        primary_action="Старт" if event.state is EngineState.STOPPED else "Стоп",
        tone=tone,
    )
