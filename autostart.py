"""Windows per-user autostart registration for Dota Auto Accept."""

import os
import sys
import winreg


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "DotaAutoAccept"


def launch_command() -> str:
    """Return the command Windows should run at user logon."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    launcher = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accept_dota.py")
    return f'"{sys.executable}" "{launcher}"'


def _set_run_value(command: str) -> None:
    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER,
        RUN_KEY,
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)


def _delete_run_value() -> None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        pass


def set_enabled(enabled: bool) -> None:
    """Enable or disable launch at Windows sign-in for the current user."""
    if enabled:
        _set_run_value(launch_command())
    else:
        _delete_run_value()
