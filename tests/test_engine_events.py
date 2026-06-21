from dataclasses import FrozenInstanceError
import threading
from unittest.mock import Mock

import pytest

import engine as engine_module
from engine import AutoAcceptEngine
from engine_events import EngineEvent, EngineState


def test_engine_states_cover_complete_visible_flow():
    assert [state.value for state in EngineState] == [
        "stopped",
        "waiting",
        "detecting",
        "verifying",
        "accepted",
        "failed",
    ]


def test_engine_event_is_frozen_and_carries_structured_status():
    event = EngineEvent(EngineState.WAITING, "Waiting for match", "Hooks active")

    assert event.state is EngineState.WAITING
    assert event.title == "Waiting for match"
    assert event.detail == "Hooks active"
    with pytest.raises(FrozenInstanceError):
        event.detail = "changed"


def test_engine_emits_structured_status_to_callback(default_config):
    received = []
    engine = AutoAcceptEngine(default_config, status_callback=received.append)

    engine._emit(EngineState.DETECTING, "Scanning", "taskbar flash")

    assert received == [
        EngineEvent(EngineState.DETECTING, "Scanning", "taskbar flash")
    ]


def test_request_accept_runs_in_worker_and_rejects_overlap(default_config):
    engine = AutoAcceptEngine(default_config)
    engine._running = True
    started = threading.Event()
    release_worker = threading.Event()

    def blocking_attempt(reason):
        assert reason == "first"
        started.set()
        release_worker.wait(timeout=2)

    engine.try_accept = blocking_attempt

    assert engine.request_accept("first") is True
    assert started.wait(timeout=1) is True
    assert engine.request_accept("overlap") is False

    release_worker.set()
    assert engine._attempt_lock.acquire(timeout=1) is True
    engine._attempt_lock.release()


def test_winapi_callbacks_only_schedule_attempts(monkeypatch, default_config):
    engine = AutoAcceptEngine(default_config)
    engine._running = True
    engine._shellhook_msg = 0xC123
    engine.request_accept = Mock(return_value=True)
    engine.is_dota = Mock(return_value=True)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("capture/detection ran inside a WinAPI callback")

    engine.try_accept = forbidden
    monkeypatch.setattr(engine_module.detector, "grab_window_bgr", forbidden)
    monkeypatch.setattr(engine_module.detector, "grab_screen_bgr", forbidden)
    monkeypatch.setattr(engine_module.detector, "find_button", forbidden)

    flash = engine_module.HSHELL_HIGHBIT | engine_module.HSHELL_REDRAW
    assert engine._wnd_proc(1, engine._shellhook_msg, flash, 123) == 0
    assert engine._wnd_proc(1, engine_module.win32con.WM_TIMER, 1, 0) == 0
    engine._fg_callback(None, None, 123, None, None, None, None)

    assert [call.args[0] for call in engine.request_accept.call_args_list] == [
        "taskbar flash",
        "safety scan",
        "window foreground",
    ]
