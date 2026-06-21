from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _display_api():
    from engine_events import EngineEvent, EngineState
    from ui_state import display_for

    return display_for, EngineEvent, EngineState


@pytest.mark.parametrize(
    ("state", "action", "tone"),
    [
        ("STOPPED", "Старт", "neutral"),
        ("WAITING", "Стоп", "success"),
        ("DETECTING", "Стоп", "working"),
        ("VERIFYING", "Стоп", "working"),
        ("ACCEPTED", "Стоп", "success"),
        ("FAILED", "Стоп", "danger"),
    ],
)
def test_display_maps_engine_state_to_action_and_tone(state, action, tone):
    display_for, EngineEvent, EngineState = _display_api()
    display = display_for(
        EngineEvent(getattr(EngineState, state), "Заголовок", "Подробности")
    )

    assert display.primary_action == action
    assert display.tone == tone


def test_display_preserves_event_copy():
    display_for, EngineEvent, EngineState = _display_api()
    display = display_for(
        EngineEvent(EngineState.FAILED, "Не удалось принять", "Enter проигнорирован")
    )

    assert display.title == "Не удалось принять"
    assert display.detail == "Enter проигнорирован"


def test_launcher_has_one_main_guard_and_no_legacy_runtime():
    source = (ROOT / "accept_dota.py").read_text(encoding="utf-8")

    assert source.count('if __name__ == "__main__":') == 1
    assert "def find_button(" not in source
    assert "def force_foreground(" not in source
