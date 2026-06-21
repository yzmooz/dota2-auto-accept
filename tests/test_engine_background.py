from unittest.mock import Mock

import pytest

import engine as engine_module
from engine import AutoAcceptEngine


def make_engine(default_config, **overrides):
    cfg = dict(default_config)
    cfg.update(overrides)
    engine = AutoAcceptEngine(cfg, log_callback=lambda _message: None)
    engine._running = True
    engine._template = None
    return engine, cfg


def test_no_focus_before_visual_button_is_detected(monkeypatch, default_config):
    engine, cfg = make_engine(default_config, use_enter=False)
    engine._capture_dota = Mock(return_value=object())
    engine._detect_ready = Mock(return_value=False)
    engine._focus_dota = Mock()
    monkeypatch.setattr(engine_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        engine_module.time,
        "time",
        Mock(side_effect=[0.0, 0.0, 5.0]),
    )

    assert engine._run_background_attempt(123, cfg, "taskbar flash") is False
    engine._focus_dota.assert_not_called()


def test_visual_detection_always_focuses_then_presses_enter(
    monkeypatch, default_config
):
    engine, cfg = make_engine(
        default_config,
        switch_focus=False,
        use_enter=False,
    )
    engine._capture_dota = Mock(return_value=object())
    engine._detect_ready = Mock(return_value=True)
    engine._focus_dota = Mock(return_value=True)
    engine._press_enter_foreground = Mock(return_value=True)
    engine._press_enter_background = Mock()
    monkeypatch.setattr(engine_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(engine_module.time, "time", Mock(side_effect=[0.0, 0.0]))

    assert engine._run_background_attempt(123, cfg, "taskbar flash") is True
    engine._focus_dota.assert_called_once_with(123)
    engine._press_enter_foreground.assert_called_once_with()
    engine._press_enter_background.assert_not_called()
    assert engine._last_accept_method == "visual-enter"


@pytest.mark.parametrize("reason", ["taskbar flash", "window foreground"])
def test_trusted_signal_falls_back_to_enter_after_visual_timeout(
    monkeypatch, default_config, reason
):
    engine, cfg = make_engine(default_config, use_enter=True)
    engine._capture_dota = Mock(return_value=object())
    engine._detect_ready = Mock(return_value=False)
    engine._focus_dota = Mock(return_value=True)
    engine._press_enter_foreground = Mock(return_value=True)
    monkeypatch.setattr(engine_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        engine_module.time,
        "time",
        Mock(side_effect=[0.0, 0.0, 5.0]),
    )

    assert engine._run_background_attempt(123, cfg, reason) is True
    engine._focus_dota.assert_called_once_with(123)
    engine._press_enter_foreground.assert_called_once_with()
    assert engine._last_accept_method == "signal-enter"


def test_safety_scan_never_uses_signal_enter_fallback(monkeypatch, default_config):
    engine, cfg = make_engine(default_config, use_enter=True)
    engine._capture_dota = Mock(return_value=object())
    engine._detect_ready = Mock(return_value=False)
    engine._focus_dota = Mock()
    engine._press_enter_foreground = Mock()
    monkeypatch.setattr(engine_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        engine_module.time,
        "time",
        Mock(side_effect=[0.0, 0.0, 5.0]),
    )

    assert engine._run_background_attempt(123, cfg, "safety scan") is False
    engine._focus_dota.assert_not_called()
    engine._press_enter_foreground.assert_not_called()


def test_enter_only_mode_handles_trusted_signal_without_capture(
    monkeypatch, default_config
):
    engine, cfg = make_engine(
        default_config,
        use_color=False,
        use_template=False,
        use_enter=True,
    )
    engine._capture_dota = Mock()
    engine._focus_dota = Mock(return_value=True)
    engine._press_enter_foreground = Mock(return_value=True)
    monkeypatch.setattr(engine_module.time, "sleep", lambda _seconds: None)

    assert engine._run_background_attempt(123, cfg, "taskbar flash") is True
    engine._capture_dota.assert_not_called()
    engine._focus_dota.assert_called_once_with(123)
    engine._press_enter_foreground.assert_called_once_with()


def test_minimized_safety_scan_does_not_restore_or_focus(
    monkeypatch, default_config
):
    engine, _ = make_engine(default_config)
    engine.find_dota_window = Mock(return_value=123)
    engine._attempt_with_window_state = Mock()
    monkeypatch.setattr(engine_module.win32gui, "IsIconic", lambda _hwnd: True)
    monkeypatch.setattr(engine_module.time, "time", lambda: 100.0)

    assert engine.try_accept("safety scan") is False
    engine._attempt_with_window_state.assert_not_called()


def test_failed_minimized_attempt_restores_minimized_state(default_config, monkeypatch):
    engine, cfg = make_engine(default_config)
    monkeypatch.setattr(engine_module.win32gui, "IsIconic", lambda _hwnd: True)
    engine._restore_no_activate = Mock(return_value=True)
    engine._run_background_attempt = Mock(return_value=False)
    engine._minimize_no_activate = Mock(return_value=True)

    assert engine._attempt_with_window_state(123, cfg, "taskbar flash") is False
    engine._minimize_no_activate.assert_called_once_with(123)


def test_successful_enter_leaves_dota_foreground(default_config, monkeypatch):
    engine, cfg = make_engine(default_config)
    monkeypatch.setattr(engine_module.win32gui, "IsIconic", lambda _hwnd: True)
    engine._restore_no_activate = Mock(return_value=True)
    engine._run_background_attempt = Mock(return_value=True)
    engine._minimize_no_activate = Mock()

    assert engine._attempt_with_window_state(123, cfg, "taskbar flash") is True
    engine._minimize_no_activate.assert_not_called()
