import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "images"
ICON_SIZES = (16, 20, 24, 32, 48, 64, 256)


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_generator_writes_complete_deterministic_icon_family(tmp_path):
    from generate_logo import generate_assets

    first, second = tmp_path / "first", tmp_path / "second"
    generate_assets(IMAGES / "logo_master.png", first)
    generate_assets(IMAGES / "logo_master.png", second)
    names = {f"logo_{size}.png" for size in ICON_SIZES} | {"logo.ico"}
    assert {path.name for path in first.iterdir()} == names
    assert {name: _digest(first / name) for name in names} == {
        name: _digest(second / name) for name in names
    }


def test_png_family_dimensions_and_transparent_corners():
    for size in ICON_SIZES:
        with Image.open(IMAGES / f"logo_{size}.png") as image:
            assert image.mode == "RGBA"
            assert image.size == (size, size)
            assert all(image.getpixel(point)[3] == 0 for point in (
                (0, 0), (size - 1, 0), (0, size - 1), (size - 1, size - 1)
            ))


def test_master_is_square_rgba_with_transparent_corners():
    with Image.open(IMAGES / "logo_master.png") as image:
        assert image.mode == "RGBA"
        assert image.width == image.height and image.width >= 256
        assert image.getpixel((0, 0))[3] == 0
        assert image.getpixel((image.width - 1, image.height - 1))[3] == 0


def test_ico_contains_every_required_frame():
    with Image.open(IMAGES / "logo.ico") as icon:
        assert set(icon.ico.sizes()) == {(size, size) for size in ICON_SIZES}


def test_resource_path_uses_meipass(monkeypatch, tmp_path):
    import config

    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert Path(config.resource_path("images/logo_32.png")) == tmp_path / "images" / "logo_32.png"


def test_tray_prefers_32_pixel_logo(monkeypatch, tmp_path):
    import tray

    image_dir = tmp_path / "images"
    image_dir.mkdir()
    Image.new("RGBA", (32, 32), "red").save(image_dir / "logo_32.png")
    Image.new("RGBA", (64, 64), "green").save(image_dir / "logo_64.png")
    requested = []

    def resolve(relative):
        requested.append(relative)
        return str(tmp_path / relative)

    monkeypatch.setattr(tray, "resource_path", resolve)
    assert tray._load_or_create_icon().size == (32, 32)
    assert requested == ["images/logo_32.png"]


def test_tray_menu_uses_russian_labels(monkeypatch):
    import tray

    class MenuItem:
        def __init__(self, text, action, default=False):
            self.text = text

    class Menu:
        def __init__(self, *items):
            self.items = items

    class Icon:
        def __init__(self, name, image, title, menu):
            self.menu = menu

        def run(self):
            pass

        def stop(self):
            pass

    monkeypatch.setattr(tray, "HAS_TRAY", True)
    monkeypatch.setattr(tray, "pystray", SimpleNamespace(Icon=Icon, Menu=Menu, MenuItem=MenuItem))
    monkeypatch.setattr(tray, "_load_or_create_icon", lambda: Image.new("RGBA", (32, 32)))
    icon = tray.TrayIcon(lambda: None, lambda: None)
    icon.start()
    icon._thread.join(timeout=1)
    assert [item.text for item in icon._icon.menu.items] == ["Открыть", "Выход"]


def test_spec_and_gitignore_bindings():
    spec = (ROOT / "dota_auto_accept.spec").read_text(encoding="utf-8")
    for size in ICON_SIZES:
        assert f"images/logo_{size}.png" in spec
    assert "images/logo_master.png" in spec
    assert "('images/logo.ico', 'images')" in spec
    assert "icon='images/logo.ico'" in spec

    patterns = set((ROOT / ".gitignore").read_text(encoding="utf-8").splitlines())
    assert {"*.spec", "!dota_auto_accept.spec", ".superpowers/", ".venv-local/", ".pytest_cache/"} <= patterns
