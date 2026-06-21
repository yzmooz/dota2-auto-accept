import autostart


def test_set_enabled_writes_current_command(monkeypatch):
    calls = []
    monkeypatch.setattr(autostart, "_set_run_value", lambda value: calls.append(value))
    monkeypatch.setattr(
        autostart,
        "launch_command",
        lambda: '"C:\\App\\DotaAutoAccept.exe"',
    )

    autostart.set_enabled(True)

    assert calls == ['"C:\\App\\DotaAutoAccept.exe"']


def test_set_disabled_removes_run_value(monkeypatch):
    calls = []
    monkeypatch.setattr(autostart, "_delete_run_value", lambda: calls.append(True))

    autostart.set_enabled(False)

    assert calls == [True]


def test_launch_command_uses_frozen_executable(monkeypatch):
    monkeypatch.setattr(autostart.sys, "frozen", True, raising=False)
    monkeypatch.setattr(autostart.sys, "executable", r"C:\App\DotaAutoAccept.exe")

    assert autostart.launch_command() == '"C:\\App\\DotaAutoAccept.exe"'
