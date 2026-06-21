from copy import deepcopy

import pytest

import config
import gui


@pytest.fixture
def app(monkeypatch):
    cfg = deepcopy(config.DEFAULTS)
    cfg["focus_mode_configured"] = True
    monkeypatch.setattr(gui.config, "load", lambda: deepcopy(cfg))
    monkeypatch.setattr(gui.config, "save", lambda value: None)
    monkeypatch.setattr(gui, "HAS_TRAY", False)
    monkeypatch.setattr(gui.tg, "start_background_listener", lambda callback: None)
    monkeypatch.setattr(gui.tg, "stop_background_listener", lambda: None)
    instance = gui.App()
    instance.update()
    yield instance
    if instance.winfo_exists():
        instance.destroy()


def test_settings_page_exposes_full_enter_based_controls(app, monkeypatch):
    assert (gui.WINDOW_W, gui.WINDOW_H) == (500, 700)
    assert gui.FONT_BODY_SIZE >= 12
    assert gui.FONT_CAPTION_SIZE >= 11
    assert tuple(app._nav_buttons) == (
        "Главная",
        "Журнал",
        "Telegram",
        "Настройки",
    )
    assert all(button.cget("width") <= 110 for button in app._nav_buttons.values())
    assert hasattr(app, "sld_threshold")
    assert hasattr(app, "sld_scan")
    assert hasattr(app, "sld_retry")
    assert hasattr(app, "sld_debounce")
    assert hasattr(app, "var_start_minimized")
    assert hasattr(app, "var_autostart")
    assert hasattr(app, "var_enter")
    assert not hasattr(app, "var_switch_focus")
    assert not hasattr(app, "sld_center_area")
    assert "зелёную кнопку" in app.lbl_color_method_help.cget("text")
    assert "эталонным изображением" in app.lbl_template_method_help.cget("text")
    assert "системному сигналу" in app.lbl_signal_method_help.cget("text")
    assert "нажимает Enter" in app.lbl_home_description.cget("text")
    telegram_help = app.lbl_telegram_help.cget("text")
    assert "@dota2_auto_accept_bot" in telegram_help
    assert "/start" in telegram_help
    assert "Chat ID" in telegram_help

    settings_page = app._pages["Настройки"]
    lift_calls = []
    settings_page.lift = lambda: lift_calls.append("settings")
    app._nav_buttons["Настройки"].invoke()
    assert lift_calls == ["settings"]
    assert app._nav_buttons["Настройки"].cget("fg_color") == gui.C_RED

    app.var_color.set(False)
    app.var_template.set(True)
    app.var_enter.set(False)
    app.var_exit.set(True)
    app.var_start_minimized.set(True)
    app.var_autostart.set(True)
    app.sld_threshold.set(0.64)
    app.sld_scan.set(3.0)
    app.sld_retry.set(7.0)
    app.sld_debounce.set(12.0)

    cfg = app._collect_config()

    assert cfg["use_color"] is False
    assert cfg["use_template"] is True
    assert cfg["use_enter"] is False
    assert cfg["use_center_click"] is False
    assert cfg["switch_focus"] is True
    assert cfg["exit_after_accept"] is True
    assert cfg["match_threshold"] == 0.64
    assert cfg["safety_scan_sec"] == 3.0
    assert cfg["retry_seconds"] == 7.0
    assert cfg["debounce_seconds"] == 12.0
    assert cfg["start_minimized"] is True
    assert cfg["add_to_autostart"] is True

    created_engines = []

    class DelayedEngine:
        running = False

        def __init__(self, *args, **kwargs):
            self.stop_calls = 0
            created_engines.append(self)

        def run(self):
            return None

        def stop(self):
            self.stop_calls += 1

    class DormantThread:
        def start(self):
            return None

    monkeypatch.setattr(gui, "AutoAcceptEngine", DelayedEngine)
    monkeypatch.setattr(
        gui.threading,
        "Thread",
        lambda *args, **kwargs: DormantThread(),
    )

    assert app.btn_toggle.cget("text") == "Старт"
    assert app.btn_toggle.cget("fg_color") == gui.C_GREEN

    app.var_color.set(False)
    app.var_template.set(False)
    app.var_enter.set(False)
    app._toggle_engine()
    assert created_engines == []
    assert app.lbl_status.cget("text") == "Выберите метод принятия"

    app.var_enter.set(True)
    app._toggle_engine()
    assert app.btn_toggle.cget("text") == "Стоп"
    assert app.btn_toggle.cget("fg_color") == gui.C_RED

    app._toggle_engine()
    assert len(created_engines) == 1
    assert created_engines[0].stop_calls == 1
    assert app.btn_toggle.cget("text") == "Старт"
    assert app.btn_toggle.cget("fg_color") == gui.C_GREEN
