"""System tray integration for Dota Auto Accept."""

import threading

from config import resource_path

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None
    Image = None
    ImageDraw = None


HAS_TRAY = pystray is not None and Image is not None


def _load_or_create_icon():
    """Prefer the tray-optimized frame and safely fall back to a drawn icon."""
    if Image is None:
        return None

    for relative_path in ("images/logo_32.png", "images/logo_64.png"):
        try:
            with Image.open(resource_path(relative_path)) as opened:
                return opened.convert("RGBA")
        except (OSError, ValueError):
            continue

    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((2, 2, size - 3, size - 3), fill=(30, 30, 46, 255))
    draw.polygon(
        ((13, 34), (19, 28), (29, 39), (47, 20), (53, 26), (29, 49)),
        fill=(55, 220, 92, 255),
    )
    return image


class TrayIcon:
    """System tray icon with show and quit commands."""

    def __init__(self, on_show_window, on_quit):
        self._on_show = on_show_window
        self._on_quit = on_quit
        self._icon = None
        self._thread = None

    def start(self):
        if not HAS_TRAY:
            return
        image = _load_or_create_icon()
        if image is None:
            return
        self._icon = pystray.Icon(
            "DotaAutoAccept",
            image,
            "Dota 2 Auto Accept",
            menu=pystray.Menu(
                pystray.MenuItem("Открыть", self._show, default=True),
                pystray.MenuItem("Выход", self._quit),
            ),
        )
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self):
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass

    def _show(self, icon=None, item=None):
        self._on_show()

    def _quit(self, icon=None, item=None):
        self.stop()
        self._on_quit()
