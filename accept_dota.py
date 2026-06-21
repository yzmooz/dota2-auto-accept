"""Windows launcher for Dota 2 Auto Accept."""

import os
import sys
import ctypes


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _acquire_single_instance():
    """Return a process-wide mutex handle, or None when another copy exists."""
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, "Local\\DotaAutoAccept.Singleton")
    if not handle or kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        if handle:
            kernel32.CloseHandle(handle)
        return None
    return handle


def main():
    if "--cli" in sys.argv:
        import config
        from engine import AutoAcceptEngine

        engine = AutoAcceptEngine(config.load())
        try:
            engine.run()
        except KeyboardInterrupt:
            engine.stop()
        return

    from gui import main as gui_main

    gui_main()


if __name__ == "__main__":
    _mutex = _acquire_single_instance()
    if _mutex:
        try:
            main()
        finally:
            ctypes.windll.kernel32.CloseHandle(_mutex)
