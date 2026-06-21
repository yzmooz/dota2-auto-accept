import json

import config


def test_defaults_include_behavior_and_capture_settings(default_config):
    assert default_config["use_enter"] is True
    assert default_config["switch_focus"] is True
    assert default_config["verify_delay_seconds"] == 0.20
    assert default_config["verify_frames"] == 2
    assert default_config["capture_min_mean"] == 2.0
    assert default_config["capture_min_std"] == 1.0


def test_save_and_load_round_trip_new_settings(
    default_config, monkeypatch, tmp_path
):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    expected = {
        "use_enter": False,
        "switch_focus": False,
        "verify_delay_seconds": 0.35,
        "verify_frames": 3,
    }
    default_config.update(expected)

    config.save(default_config)

    loaded = config.load()
    assert {key: loaded[key] for key in expected} == expected

    settings_path = tmp_path / config.APP_NAME / "settings.json"
    raw_settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert raw_settings["verify_frames"] == 3
