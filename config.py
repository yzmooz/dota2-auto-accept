"""
Persistent JSON configuration for Dota 2 Auto Accept.
Settings are stored in %APPDATA%/DotaAutoAccept/settings.json
"""

import json
import os

APP_NAME = "DotaAutoAccept"


def _config_dir():
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    return os.path.join(appdata, APP_NAME)


def _config_path():
    return os.path.join(_config_dir(), "settings.json")


DEFAULTS = {
    # Detection — individual method toggles
    "use_color": True,
    "use_template": True,
    "use_center_click": False,
    "use_enter": True,
    "switch_focus": True,
    "focus_mode_configured": False,
    "center_area_pct": 15,
    "match_threshold": 0.75,
    "retry_seconds": 4.0,
    "retry_interval": 0.25,
    "debounce_seconds": 8.0,
    "safety_scan_sec": 2.0,
    "verify_delay_seconds": 0.20,
    "verify_frames": 2,
    "capture_min_mean": 2.0,
    "capture_min_std": 1.0,
    "scales": [1.0, 0.95, 1.05, 0.9, 1.1, 0.85, 1.15],

    # Telegram (bot token hardcoded in telegram_notifier, only chat_id + username stored)
    "telegram_enabled": False,
    "telegram_chat_id": "",
    "telegram_username": "",

    # Behavior
    "exit_after_accept": False,
    "start_minimized": False,
    "add_to_autostart": False,

    # UI state
    "window_geometry": "",
}


def load() -> dict:
    """Load settings from disk, filling missing keys with defaults."""
    path = _config_path()
    cfg = dict(DEFAULTS)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for key, default_val in DEFAULTS.items():
                if key in saved:
                    sv = saved[key]
                    if isinstance(default_val, bool):
                        cfg[key] = bool(sv) if isinstance(sv, (bool, int)) else default_val
                    elif isinstance(default_val, int):
                        cfg[key] = int(sv) if isinstance(sv, (int, float)) else default_val
                    elif isinstance(default_val, float):
                        cfg[key] = float(sv) if isinstance(sv, (int, float)) else default_val
                    elif isinstance(default_val, str):
                        cfg[key] = str(sv) if isinstance(sv, str) else default_val
                    elif isinstance(default_val, list):
                        cfg[key] = list(sv) if isinstance(sv, list) else default_val
                    else:
                        cfg[key] = sv
        except Exception:
            pass
    return cfg


def save(cfg: dict):
    """Persist current settings to disk."""
    d = _config_dir()
    os.makedirs(d, exist_ok=True)
    with open(_config_path(), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def resource_path(rel: str) -> str:
    """Path to bundled resource (works both in dev and PyInstaller .exe)."""
    base = getattr(__import__("sys"), "_MEIPASS",
                   os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)
