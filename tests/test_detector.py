from types import SimpleNamespace
import ctypes

import numpy as np

import detector


CLEANUP_ORDER = [
    "delete_bitmap",
    "delete_save_dc",
    "delete_mfc_dc",
    "release_hwnd_dc",
]


def test_is_usable_capture_rejects_none():
    assert detector.is_usable_capture(None) is False


def test_is_usable_capture_rejects_empty_bgr_image():
    image = np.empty((0, 0, 3), dtype=np.uint8)

    assert detector.is_usable_capture(image) is False


def test_is_usable_capture_rejects_all_black_image():
    image = np.zeros((120, 160, 3), dtype=np.uint8)

    assert detector.is_usable_capture(image) is False


def test_is_usable_capture_rejects_uniform_image_at_mean_threshold():
    image = np.full((120, 160, 3), 2, dtype=np.uint8)

    assert detector.is_usable_capture(image, min_mean=2.0, min_std=1.0) is False


def test_is_usable_capture_accepts_realistic_colored_image():
    image = np.zeros((120, 160, 3), dtype=np.uint8)
    image[20:100, 30:130] = (20, 180, 240)

    assert detector.is_usable_capture(image) is True


def _install_capture_fakes(
    monkeypatch,
    *,
    print_result=1,
    bitmap_read_error=None,
    cleanup_errors=(),
):
    events = []
    cleanup_errors = set(cleanup_errors)

    bgra = np.zeros((120, 160, 4), dtype=np.uint8)
    bgra[20:100, 30:130, :3] = (20, 180, 240)

    class FakeBitmap:
        def CreateCompatibleBitmap(self, mfc_dc, width, height):
            assert mfc_dc is fake_mfc_dc
            assert (width, height) == (160, 120)
            events.append("create_bitmap_storage")

        def GetInfo(self):
            if bitmap_read_error == "info":
                raise RuntimeError("bitmap must not be read after capture failure")
            return {"bmHeight": 120, "bmWidth": 160}

        def GetBitmapBits(self, signed):
            assert signed is True
            if bitmap_read_error == "bits":
                raise RuntimeError("bitmap read failed")
            return bgra.tobytes()

        def GetHandle(self):
            return "bitmap_handle"

    class FakeSaveDC:
        def SelectObject(self, bitmap):
            assert bitmap is fake_bitmap
            events.append("select_bitmap")

        def GetSafeHdc(self):
            return "save_hdc"

        def DeleteDC(self):
            events.append("delete_save_dc")
            if "delete_save_dc" in cleanup_errors:
                raise RuntimeError("save DC cleanup failed")

    class FakeMfcDC:
        def CreateCompatibleDC(self):
            events.append("create_save_dc")
            return fake_save_dc

        def DeleteDC(self):
            events.append("delete_mfc_dc")
            if "delete_mfc_dc" in cleanup_errors:
                raise RuntimeError("MFC DC cleanup failed")

    fake_bitmap = FakeBitmap()
    fake_save_dc = FakeSaveDC()
    fake_mfc_dc = FakeMfcDC()
    hwnd_dc = "window_dc"

    def get_window_rect(hwnd):
        assert hwnd == 123
        return (11, 22, 171, 142)

    def get_window_dc(hwnd):
        assert hwnd == 123
        events.append("get_window_dc")
        return hwnd_dc

    def delete_object(handle):
        assert handle == "bitmap_handle"
        events.append("delete_bitmap")
        if "delete_bitmap" in cleanup_errors:
            raise RuntimeError("bitmap cleanup failed")

    def release_dc(hwnd, dc):
        assert (hwnd, dc) == (123, hwnd_dc)
        events.append("release_hwnd_dc")
        if "release_hwnd_dc" in cleanup_errors:
            raise RuntimeError("window DC cleanup failed")

    fake_win32gui = SimpleNamespace(
        GetWindowRect=get_window_rect,
        GetWindowDC=get_window_dc,
        DeleteObject=delete_object,
        ReleaseDC=release_dc,
    )
    fake_win32ui = SimpleNamespace(
        CreateDCFromHandle=lambda dc: fake_mfc_dc,
        CreateBitmap=lambda: fake_bitmap,
    )

    def print_window(hwnd, hdc, flags):
        assert (hwnd, hdc, flags) == (123, "save_hdc", 2)
        events.append("print_window")
        return print_result

    monkeypatch.setattr(detector, "win32gui", fake_win32gui)
    monkeypatch.setattr(detector, "win32ui", fake_win32ui)
    monkeypatch.setattr(
        ctypes,
        "windll",
        SimpleNamespace(user32=SimpleNamespace(PrintWindow=print_window)),
    )

    return events


def _cleanup_events(events):
    return [event for event in events if event in CLEANUP_ORDER]


def test_grab_window_releases_resources_when_print_window_fails(monkeypatch):
    events = _install_capture_fakes(
        monkeypatch,
        print_result=0,
        bitmap_read_error="info",
    )

    assert detector.grab_window_bgr(123) == (None, 0, 0)
    assert _cleanup_events(events) == CLEANUP_ORDER


def test_grab_window_releases_resources_when_bitmap_read_raises(monkeypatch):
    events = _install_capture_fakes(monkeypatch, bitmap_read_error="bits")

    assert detector.grab_window_bgr(123) == (None, 0, 0)
    assert _cleanup_events(events) == CLEANUP_ORDER


def test_grab_window_continues_cleanup_when_one_cleanup_action_raises(monkeypatch):
    events = _install_capture_fakes(
        monkeypatch,
        print_result=0,
        bitmap_read_error="info",
        cleanup_errors={"delete_bitmap"},
    )

    assert detector.grab_window_bgr(123) == (None, 0, 0)
    assert _cleanup_events(events) == CLEANUP_ORDER
