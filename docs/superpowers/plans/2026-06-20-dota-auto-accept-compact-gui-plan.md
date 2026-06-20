# Dota 2 Auto Accept Compact GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a compact tray-first Windows GUI with a circular Dota-themed icon and verified no-focus background match acceptance.

**Architecture:** Keep CustomTkinter, pystray, OpenCV, and pywin32. Separate pure engine state/events from the GUI, serialize acceptance attempts, capture Dota with `PrintWindow`, send Enter only to the Dota window, and verify that the ready-check disappeared before reporting success. Generate a coordinated detailed/small icon family and bind it through one resource loader to Tk, tray, and PyInstaller.

**Tech Stack:** Python 3.12, CustomTkinter, Pillow, pystray, OpenCV, NumPy, pywin32, pytest, PyInstaller.

---

## File map

- Create `requirements-dev.txt`: development-only pytest dependency.
- Create `tests/conftest.py`: shared configuration fixture and Windows test isolation.
- Create `tests/test_config.py`: persisted/default behavior flags.
- Create `tests/test_detector.py`: capture validation and detector guard tests.
- Create `tests/test_engine_events.py`: structured state/event tests.
- Create `tests/test_engine_background.py`: no-focus input, verification, serialization, and minimized-state restoration.
- Create `tests/test_ui_state.py`: pure GUI copy/state mapping tests.
- Create `tests/test_assets.py`: required icon resource and ICO-frame checks.
- Create `tests/test_tray.py`: tray callback behavior without launching a real tray loop.
- Create `engine_events.py`: `EngineState` and `EngineEvent` definitions shared by engine and GUI.
- Create `ui_state.py`: pure mapping from engine events to visible Russian copy and colors.
- Modify `config.py:21-46`: add every engine/UI setting to persisted defaults.
- Modify `detector.py:31-82`: validate captures and guarantee Win32 resource cleanup.
- Modify `engine.py:46-401`: serialized attempts, structured events, no-focus background Enter, post-input verification, and restore-to-minimized behavior.
- Modify `gui.py:1-655`: replace the tabbed 640×740 layout with the approved compact page stack.
- Modify `tray.py:17-78`: use the small icon and Russian menu labels without changing engine state on hide/show.
- Modify `generate_logo.py:1-end`: deterministic detailed/tray PNG and multi-resolution ICO generation from a master image.
- Modify `.gitignore`: keep build artifacts ignored while explicitly tracking `dota_auto_accept.spec`.
- Replace `accept_dota.py:1-305`: remove the appended legacy runtime and leave one clean GUI/CLI launcher.
- Modify `dota_auto_accept.spec:1-end`: bundle all icon variants and set the executable icon.
- Modify `requirements.txt:1-end`: remove duplicate entries while preserving runtime packages.
- Modify `README.md`: document compact startup, tray behavior, and honest background-test limitations.
- Create/update `images/logo_master.png`, `images/logo_16.png`, `images/logo_20.png`, `images/logo_24.png`, `images/logo_32.png`, `images/logo_48.png`, `images/logo_64.png`, `images/logo_256.png`, and `images/logo.ico`.

### Task 1: Test harness and complete persisted defaults

**Files:**
- Create: `requirements-dev.txt`
- Create: `tests/conftest.py`
- Create: `tests/test_config.py`
- Modify: `config.py:21-46`

- [ ] **Step 1: Add the development requirement**

```text
-r requirements.txt
pytest>=8.2,<9
```

- [ ] **Step 2: Add shared test configuration**

```python
# tests/conftest.py
from copy import deepcopy

import pytest

import config


@pytest.fixture
def default_config():
    return deepcopy(config.DEFAULTS)
```

- [ ] **Step 3: Write failing persistence tests**

```python
# tests/test_config.py
import json

import config


def test_background_defaults_are_explicit():
    assert config.DEFAULTS["use_enter"] is True
    assert config.DEFAULTS["switch_focus"] is False
    assert config.DEFAULTS["verify_delay_seconds"] == 0.20
    assert config.DEFAULTS["verify_frames"] == 2
    assert config.DEFAULTS["capture_min_mean"] == 2.0
    assert config.DEFAULTS["capture_min_std"] == 1.0


def test_background_settings_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    saved = dict(config.DEFAULTS)
    saved.update({
        "use_enter": False,
        "switch_focus": False,
        "verify_delay_seconds": 0.35,
        "verify_frames": 3,
    })
    config.save(saved)
    loaded = config.load()
    assert loaded["use_enter"] is False
    assert loaded["switch_focus"] is False
    assert loaded["verify_delay_seconds"] == 0.35
    assert loaded["verify_frames"] == 3
    raw = json.loads((tmp_path / config.APP_NAME / "settings.json").read_text(encoding="utf-8"))
    assert raw["verify_frames"] == 3
```

- [ ] **Step 4: Run the tests and confirm the missing defaults fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_config.py -v`

Expected: `test_background_defaults_are_explicit` fails with `KeyError: 'use_enter'`.

- [ ] **Step 5: Add explicit defaults to `config.DEFAULTS`**

Insert these keys in the behavior/detection sections; keep the existing type-aware loader unchanged:

```python
DEFAULTS = {
    "use_color": True,
    "use_template": True,
    "use_center_click": False,
    "use_enter": True,
    "switch_focus": False,
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
    "telegram_enabled": False,
    "telegram_chat_id": "",
    "telegram_username": "",
    "exit_after_accept": False,
    "start_minimized": False,
    "add_to_autostart": False,
    "window_geometry": "",
}
```

- [ ] **Step 6: Run the tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_config.py -v`

Expected: `2 passed`.

- [ ] **Step 7: Commit only this task**

```powershell
git add -- requirements-dev.txt tests/conftest.py tests/test_config.py config.py
git commit -m "test: establish background acceptance defaults"
```

### Task 2: Reject unusable window captures and clean up Win32 resources

**Files:**
- Create: `tests/test_detector.py`
- Modify: `detector.py:31-82`

- [ ] **Step 1: Write failing capture-validation tests**

```python
# tests/test_detector.py
import numpy as np

import detector


def test_rejects_missing_empty_and_black_captures():
    assert detector.is_usable_capture(None) is False
    assert detector.is_usable_capture(np.empty((0, 0, 3), dtype=np.uint8)) is False
    assert detector.is_usable_capture(np.zeros((120, 160, 3), dtype=np.uint8)) is False


def test_rejects_nearly_uniform_dark_capture():
    image = np.full((120, 160, 3), 2, dtype=np.uint8)
    assert detector.is_usable_capture(image, min_mean=2.0, min_std=1.0) is False


def test_accepts_realistic_capture():
    image = np.zeros((120, 160, 3), dtype=np.uint8)
    image[20:100, 30:130] = (35, 90, 180)
    assert detector.is_usable_capture(image, min_mean=2.0, min_std=1.0) is True
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests/test_detector.py -v`

Expected: collection succeeds and tests fail because `detector.is_usable_capture` does not exist.

- [ ] **Step 3: Add the pure validator**

```python
def is_usable_capture(image, min_mean=2.0, min_std=1.0):
    if image is None or not isinstance(image, np.ndarray):
        return False
    if image.size == 0 or image.ndim != 3 or image.shape[2] < 3:
        return False
    luminance = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
    return float(luminance.mean()) > float(min_mean) and float(luminance.std()) > float(min_std)
```

- [ ] **Step 4: Replace `grab_window_bgr` with guaranteed cleanup**

Use one `try/finally` that initializes `hwnd_dc`, `mfc_dc`, `save_dc`, and `bmp` to `None`, performs `PrintWindow`, returns `(None, 0, 0)` when the result is zero or the image is unusable, and releases each acquired object in reverse order in `finally`. The decision block must be:

```python
printed = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)
if not printed:
    return None, 0, 0

bmp_info = bmp.GetInfo()
bmp_bits = bmp.GetBitmapBits(True)
image = np.frombuffer(bmp_bits, dtype=np.uint8)
image = image.reshape(bmp_info["bmHeight"], bmp_info["bmWidth"], 4)[:, :, :3]
if not is_usable_capture(image):
    return None, 0, 0
return image, rect[0], rect[1]
```

- [ ] **Step 5: Run detector tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_detector.py -v`

Expected: `3 passed`.

- [ ] **Step 6: Commit only detector work**

```powershell
git add -- tests/test_detector.py detector.py
git commit -m "fix: reject invalid Dota window captures"
```

### Task 3: Introduce structured engine events and serialized attempt scheduling

**Files:**
- Create: `engine_events.py`
- Create: `tests/test_engine_events.py`
- Modify: `engine.py:46-80,278-315`

- [ ] **Step 1: Write failing event-model tests**

```python
# tests/test_engine_events.py
from engine_events import EngineEvent, EngineState


def test_engine_event_is_immutable_and_has_detail():
    event = EngineEvent(EngineState.WAITING, "Ожидаю матч", "Shell hook активен")
    assert event.state is EngineState.WAITING
    assert event.title == "Ожидаю матч"
    assert event.detail == "Shell hook активен"


def test_engine_states_cover_visible_flow():
    assert [state.value for state in EngineState] == [
        "stopped", "waiting", "detecting", "verifying", "accepted", "failed"
    ]
```

- [ ] **Step 2: Verify the import fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_engine_events.py -v`

Expected: collection fails with `ModuleNotFoundError: No module named 'engine_events'`.

- [ ] **Step 3: Create the event model**

```python
# engine_events.py
from dataclasses import dataclass
from enum import Enum


class EngineState(str, Enum):
    STOPPED = "stopped"
    WAITING = "waiting"
    DETECTING = "detecting"
    VERIFYING = "verifying"
    ACCEPTED = "accepted"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class EngineEvent:
    state: EngineState
    title: str
    detail: str = ""
```

- [ ] **Step 4: Add event emission and non-overlapping scheduling to the engine**

Extend `AutoAcceptEngine.__init__` with `status_callback=None`, store `_status_callback`, and initialize `_attempt_lock = threading.Lock()`. Add:

```python
def _emit(self, state, title, detail=""):
    event = EngineEvent(state, title, detail)
    if self._status_callback:
        self._status_callback(event)
    self._log(f"[{state.value}] {title}" + (f" — {detail}" if detail else ""))

def request_accept(self, reason):
    if not self._running or not self._attempt_lock.acquire(blocking=False):
        return False

    def worker():
        try:
            self.try_accept(reason)
        finally:
            self._attempt_lock.release()

    threading.Thread(target=worker, daemon=True, name="dota-accept-attempt").start()
    return True
```

Import `EngineEvent` and `EngineState`, replace callback calls to `try_accept(...)` in `_wnd_proc` and `_fg_callback` with `request_accept(...)`, and emit `WAITING` after hooks are installed and `STOPPED` when the loop exits.

- [ ] **Step 5: Add a scheduling regression test**

```python
def test_request_accept_rejects_overlap(monkeypatch, default_config):
    from engine import AutoAcceptEngine

    engine = AutoAcceptEngine(default_config)
    engine._running = True
    assert engine._attempt_lock.acquire(blocking=False) is True
    try:
        assert engine.request_accept("test") is False
    finally:
        engine._attempt_lock.release()
```

- [ ] **Step 6: Run event and scheduling tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_engine_events.py -v`

Expected: all tests pass.

- [ ] **Step 7: Commit the event boundary**

```powershell
git add -- engine_events.py tests/test_engine_events.py engine.py
git commit -m "refactor: serialize engine acceptance events"
```

### Task 4: Verify background Enter without focus stealing

**Files:**
- Create: `tests/test_engine_background.py`
- Modify: `engine.py:111-148,179-275`

- [ ] **Step 1: Write failing verification and restoration tests**

```python
# tests/test_engine_background.py
from unittest.mock import Mock

from engine import AutoAcceptEngine


def make_engine(default_config):
    engine = AutoAcceptEngine(default_config)
    engine._running = True
    engine._template = None
    return engine


def test_verify_requires_two_consecutive_missing_frames(monkeypatch, default_config):
    engine = make_engine(default_config)
    engine._capture_dota = Mock(side_effect=[object(), object()])
    engine._detect_ready = Mock(side_effect=[False, False])
    monkeypatch.setattr("engine.time.sleep", lambda _: None)
    assert engine._verify_ready_check_gone(123, default_config) is True
    assert engine._detect_ready.call_count == 2


def test_verify_fails_when_button_remains(monkeypatch, default_config):
    engine = make_engine(default_config)
    engine._capture_dota = Mock(return_value=object())
    engine._detect_ready = Mock(return_value=True)
    monkeypatch.setattr("engine.time.sleep", lambda _: None)
    assert engine._verify_ready_check_gone(123, default_config) is False


def test_minimized_window_is_restored_after_exception(monkeypatch, default_config):
    engine = make_engine(default_config)
    monkeypatch.setattr("engine.win32gui.IsIconic", lambda _: True)
    engine._restore_no_activate = Mock(return_value=True)
    engine._minimize_no_activate = Mock()
    engine._run_background_attempt = Mock(side_effect=RuntimeError("capture failed"))
    assert engine._attempt_with_window_state(123, default_config) is False
    engine._minimize_no_activate.assert_called_once_with(123)


def test_background_path_never_uses_global_input(monkeypatch, default_config):
    import engine as engine_module

    engine = make_engine(default_config)
    monkeypatch.setattr("engine.win32gui.IsIconic", lambda _: False)
    foreground = Mock()
    monkeypatch.setattr(engine_module.win32gui, "SetForegroundWindow", foreground)
    engine._run_background_attempt = Mock(return_value=True)
    assert engine._attempt_with_window_state(123, default_config) is True
    foreground.assert_not_called()


def test_failed_verification_never_sends_accepted_notification(default_config):
    engine = make_engine(default_config)
    engine.find_dota_window = Mock(return_value=123)
    engine._attempt_with_window_state = Mock(return_value=False)
    engine._tg_notify = Mock()
    assert engine.try_accept("test") is False
    accepted_calls = [call for call in engine._tg_notify.call_args_list if call.args[0] == "notify_accepted"]
    assert accepted_calls == []
    assert engine._last_action_ts == 0.0
```

- [ ] **Step 2: Run tests and verify missing helpers fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_engine_background.py -v`

Expected: failures name `_verify_ready_check_gone`, `_attempt_with_window_state`, and `_run_background_attempt`.

- [ ] **Step 3: Make background input return a real result**

```python
@staticmethod
def _press_enter_background(hwnd):
    try:
        win32gui.PostMessage(hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
        time.sleep(0.03)
        win32gui.PostMessage(hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, 0)
        return True
    except Exception:
        return False

@staticmethod
def _minimize_no_activate(hwnd):
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        return True
    except Exception:
        return False
```

- [ ] **Step 4: Add capture/detection and stable verification helpers**

```python
def _capture_dota(self, hwnd, cfg):
    image, _, _ = detector.grab_window_bgr(hwnd)
    if not detector.is_usable_capture(
        image,
        cfg.get("capture_min_mean", 2.0),
        cfg.get("capture_min_std", 1.0),
    ):
        return None
    return image

def _detect_ready(self, image, cfg):
    if image is None:
        return False
    confidence, _, _, _ = detector.find_button(
        image,
        self._template,
        cfg.get("scales"),
        **self._detector_kwargs(),
    )
    return confidence >= cfg.get("match_threshold", 0.75)

def _verify_ready_check_gone(self, hwnd, cfg):
    required = max(1, int(cfg.get("verify_frames", 2)))
    delay = max(0.0, float(cfg.get("verify_delay_seconds", 0.20)))
    missing = 0
    for _ in range(required + 1):
        if delay:
            time.sleep(delay)
        image = self._capture_dota(hwnd, cfg)
        if image is None:
            return False
        if self._detect_ready(image, cfg):
            missing = 0
        else:
            missing += 1
            if missing >= required:
                return True
    return False
```

- [ ] **Step 5: Replace the false-positive success path**

Implement `_run_background_attempt(hwnd, cfg)` so each retry captures the Dota window, detects the ready-check, sends only background Enter, emits `VERIFYING`, and returns true only after `_verify_ready_check_gone`. Implement `_attempt_with_window_state` with `was_minimized = win32gui.IsIconic(hwnd)` and a `finally` block that calls `_minimize_no_activate(hwnd)` when `was_minimized` is true. `try_accept` must call this method, set `_last_action_ts`, send Telegram accepted notification, and emit `ACCEPTED` only on true; on timeout it emits `FAILED` and does not update debounce time.

Use this complete window-state wrapper:

```python
def _attempt_with_window_state(self, hwnd, cfg):
    was_minimized = bool(win32gui.IsIconic(hwnd))
    try:
        if was_minimized and not self._restore_no_activate(hwnd):
            return False
        return self._run_background_attempt(hwnd, cfg)
    except Exception as exc:
        self._log(f"[!] Background attempt error: {exc}")
        return False
    finally:
        if was_minimized:
            self._minimize_no_activate(hwnd)
```

The success branch must be exactly guarded as follows:

```python
accepted = self._attempt_with_window_state(dota, cfg)
if not accepted:
    self._emit(EngineState.FAILED, "Не удалось принять", "Dota не подтвердила фоновый Enter")
    return False
self._last_action_ts = time.time()
self._tg_notify("notify_accepted", "background-enter")
self._emit(EngineState.ACCEPTED, "Матч принят", "Без переключения фокуса")
if cfg.get("exit_after_accept"):
    self.stop()
return True
```

Remove `force_foreground`, global `pyautogui.press`, and mouse-click calls from the default acceptance path. Do not use screen capture when Dota is not the foreground window.
For `WM_TIMER`, call `request_accept("safety scan")` directly; do not capture or detect inside the message-window callback.

- [ ] **Step 6: Run engine tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_engine_events.py tests/test_engine_background.py -v`

Expected: all tests pass and the mocked `SetForegroundWindow` has zero calls.

- [ ] **Step 7: Commit verified background acceptance**

```powershell
git add -- tests/test_engine_background.py engine.py
git commit -m "fix: verify no-focus background acceptance"
```

### Task 5: Generate and bind the circular icon family

**Files:**
- Modify: `generate_logo.py:1-end`
- Modify: `tray.py:17-78`
- Modify: `dota_auto_accept.spec:1-end`
- Modify: `.gitignore`
- Create/update: `images/logo_master.png`, `images/logo_16.png`, `images/logo_20.png`, `images/logo_24.png`, `images/logo_32.png`, `images/logo_48.png`, `images/logo_64.png`, `images/logo_256.png`, `images/logo.ico`
- Create: `tests/test_assets.py`

- [ ] **Step 1: Generate the approved master mark with `imagegen`**

Use the supplied `Z:\Downloads\ChatGPT Image 20 июн. 2026 г., 07_47_32.png` as a style/composition reference, not an edit target. Use this prompt:

```text
Use case: logo-brand
Asset type: Windows desktop app icon master
Primary request: Create an original circular Dota-inspired auto-accept emblem: a bold red carved stone rune as the primary mass and a luminous green acceptance check crossing the lower-right quadrant.
Input image: supplied image is a style and composition reference only.
Composition: centered circular medallion, generous safe margin, strong silhouette readable at 32 px.
Style: polished game utility icon, restrained 3D depth, crisp edges, minimal particles.
Background: dark circular medallion; perfectly flat solid #ff00ff outside the circle for removal.
Constraints: no text, no square tile, no watermark, no tiny floating details, no thin lines; do not place #ff00ff inside the medallion.
```

Copy the selected generated file into `images/logo_master-keyed.png`, run the imagegen chroma-key removal helper to produce `images/logo_master.png`, and inspect it at original size before continuing.

- [ ] **Step 2: Write failing asset tests**

```python
# tests/test_assets.py
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "images"


def test_required_icon_files_exist():
    for size in (16, 20, 24, 32, 48, 64, 256):
        assert (IMAGES / f"logo_{size}.png").is_file()
    assert (IMAGES / "logo.ico").is_file()


def test_png_icons_have_transparent_corners():
    for size in (16, 32, 64, 256):
        with Image.open(IMAGES / f"logo_{size}.png") as image:
            rgba = image.convert("RGBA")
            assert rgba.size == (size, size)
            assert rgba.getpixel((0, 0))[3] == 0


def test_ico_contains_small_and_large_frames():
    with Image.open(IMAGES / "logo.ico") as image:
        sizes = image.info.get("sizes", set())
        assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= sizes


def test_resource_path_uses_pyinstaller_root(monkeypatch, tmp_path):
    import sys

    import config

    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    expected = tmp_path / "images" / "logo_32.png"
    assert Path(config.resource_path("images/logo_32.png")) == expected
```

- [ ] **Step 3: Replace `generate_logo.py` with deterministic resizing**

The script must load `images/logo_master.png`, fit it to a square, sharpen and increase contrast slightly for sizes 32 and below, preserve alpha, write every PNG size, and save one ICO:

```python
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


ROOT = Path(__file__).resolve().parent
IMAGES = ROOT / "images"
SIZES = (16, 20, 24, 32, 48, 64, 256)


def render_icon(master, size):
    icon = ImageOps.fit(master.convert("RGBA"), (size, size), Image.Resampling.LANCZOS)
    if size <= 32:
        rgb = icon.convert("RGB")
        rgb = ImageEnhance.Contrast(rgb).enhance(1.18)
        rgb = ImageEnhance.Color(rgb).enhance(1.10)
        rgb = rgb.filter(ImageFilter.UnsharpMask(radius=0.8, percent=170, threshold=2))
        rgb.putalpha(icon.getchannel("A"))
        icon = rgb
    return icon


def main():
    master_path = IMAGES / "logo_master.png"
    with Image.open(master_path) as source:
        master = source.convert("RGBA")
    rendered = {size: render_icon(master, size) for size in SIZES}
    for size, image in rendered.items():
        image.save(IMAGES / f"logo_{size}.png", optimize=True)
    rendered[256].save(
        IMAGES / "logo.ico",
        format="ICO",
        sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)],
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Generate and inspect outputs**

Run: `.venv\Scripts\python.exe generate_logo.py`

Run: `.venv\Scripts\python.exe -m pytest tests/test_assets.py -v`

Expected: `3 passed`; visual inspection shows a transparent corner and a recognizable red rune/green check at 16, 32, and 256 px.

- [ ] **Step 5: Bind the tray and package icons**

Change `tray._load_or_create_icon` to prefer `logo_32.png`, then `logo_64.png`. Keep a generated fallback only for missing-resource resilience. Add every generated PNG and `logo.ico` to `datas` in `dota_auto_accept.spec`; keep `icon='images/logo.ico'` in `EXE`.
Add `!dota_auto_accept.spec` immediately after the existing `*.spec` rule in `.gitignore` so the project build recipe is tracked while arbitrary local spec files remain ignored. Add `.superpowers/` to ignore visual-companion session files.

- [ ] **Step 6: Commit icon assets and bindings**

```powershell
git add -- .gitignore generate_logo.py tray.py dota_auto_accept.spec tests/test_assets.py images/logo_master.png images/logo_16.png images/logo_20.png images/logo_24.png images/logo_32.png images/logo_48.png images/logo_64.png images/logo_256.png images/logo.ico
git commit -m "feat: add circular Dota auto-accept icon"
```

### Task 6: Build the compact page-stack GUI

**Files:**
- Create: `ui_state.py`
- Create: `tests/test_ui_state.py`
- Modify: `gui.py:1-655`

- [ ] **Step 1: Write failing pure UI-state tests**

```python
# tests/test_ui_state.py
from engine_events import EngineEvent, EngineState
from ui_state import display_for


def test_stopped_copy_uses_start_action():
    display = display_for(EngineEvent(EngineState.STOPPED, "Остановлен"))
    assert display.primary_action == "Старт"
    assert display.tone == "neutral"


def test_waiting_copy_uses_stop_action():
    display = display_for(EngineEvent(EngineState.WAITING, "Ожидаю матч"))
    assert display.primary_action == "Стоп"
    assert display.tone == "success"


def test_failure_preserves_engine_action():
    display = display_for(EngineEvent(EngineState.FAILED, "Не удалось принять", "Enter проигнорирован"))
    assert display.primary_action == "Стоп"
    assert display.detail == "Enter проигнорирован"
    assert display.tone == "danger"
```

- [ ] **Step 2: Create the pure display mapping**

```python
# ui_state.py
from dataclasses import dataclass

from engine_events import EngineEvent, EngineState


@dataclass(frozen=True, slots=True)
class DisplayState:
    title: str
    detail: str
    primary_action: str
    tone: str


def display_for(event):
    running = event.state is not EngineState.STOPPED
    tone = {
        EngineState.STOPPED: "neutral",
        EngineState.WAITING: "success",
        EngineState.DETECTING: "working",
        EngineState.VERIFYING: "working",
        EngineState.ACCEPTED: "success",
        EngineState.FAILED: "danger",
    }[event.state]
    return DisplayState(
        title=event.title,
        detail=event.detail,
        primary_action="Стоп" if running else "Старт",
        tone=tone,
    )
```

- [ ] **Step 3: Run the UI-state tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ui_state.py -v`

Expected: `3 passed`.

- [ ] **Step 4: Replace the tab shell with a compact page stack**

Set `WINDOW_W, WINDOW_H = 460, 600`, `ctk.set_appearance_mode("light")`, and use the approved palette:

```python
C_BG = "#F4F1EB"
C_SURFACE = "#FAF8F3"
C_BORDER = "#DEDAD2"
C_TEXT = "#191B1F"
C_MUTED = "#76736D"
C_GREEN = "#4C9B64"
C_GREEN_SOFT = "#E6F3E9"
C_RED = "#B83B35"
C_DANGER_SOFT = "#F7E7E5"
```

Build four peer frames in one `page_host`: `home`, `journal`, `telegram`, and `settings`. `_show_page(name)` calls `tkraise()` and updates the three bottom navigation button styles. The home frame contains the 72 px icon, status title/detail, one full-width start/stop button, latest-event card, and a compact “background/no focus” indicator. Keep existing Telegram and settings controls on their respective frames with a `CTkScrollableFrame`.

The required navigation method is:

```python
def _show_page(self, name):
    self._pages[name].tkraise()
    for key, button in self._nav_buttons.items():
        selected = key == name
        button.configure(
            fg_color=C_TEXT if selected else "transparent",
            text_color="white" if selected else C_MUTED,
        )
```

- [ ] **Step 5: Wire structured engine status to Tk safely**

Pass `status_callback=self._on_engine_event` when creating `AutoAcceptEngine`. The callback must marshal to Tk and update all status widgets through `display_for`:

```python
def _on_engine_event(self, event):
    self.after(0, lambda current=event: self._apply_engine_event(current))

def _apply_engine_event(self, event):
    display = display_for(event)
    self._last_event = event
    self.lbl_status.configure(text=display.title)
    self.lbl_detail.configure(text=display.detail or "Dota 2 можно держать свёрнутой")
    self.btn_toggle.configure(text=display.primary_action)
    self.lbl_latest.configure(text=display.title)
    self.lbl_latest_detail.configure(text=display.detail)
```

Initialize with `EngineEvent(EngineState.STOPPED, "Остановлен", "Нажмите «Старт» для мониторинга")`. Do not start the engine in `__init__`, even when legacy `start_minimized` is present; normal launch always shows the stopped home page. Keep the setting only for backward-compatible loading until a later migration removes it.

- [ ] **Step 6: Preserve tray behavior and engine state**

`_on_close` calls `withdraw()` only. `_show_window` calls `deiconify()` and `lift()` but never starts/stops the engine. `_real_quit` stops Telegram and the engine, stops the tray, saves config, and destroys the root.

- [ ] **Step 7: Run pure tests and manually inspect the GUI**

Run: `.venv\Scripts\python.exe -m pytest tests/test_ui_state.py -v`

Run: `.venv\Scripts\python.exe accept_dota.py`

Expected: a 460×600 light compact window opens stopped; no engine log appears until Start; bottom navigation stays within the window; closing hides to tray; restoring preserves state.

- [ ] **Step 8: Commit the compact GUI**

```powershell
git add -- ui_state.py tests/test_ui_state.py gui.py
git commit -m "feat: replace GUI with compact tray layout"
```

### Task 7: Clean launcher, runtime requirements, tray labels, and packaging

**Files:**
- Replace: `accept_dota.py:1-305`
- Modify: `tray.py:41-78`
- Modify: `requirements.txt:1-end`
- Modify: `README.md`
- Create: `tests/test_tray.py`

- [ ] **Step 1: Add a launcher regression test**

```python
# append to tests/test_assets.py
def test_launcher_has_one_main_guard():
    source = (ROOT / "accept_dota.py").read_text(encoding="utf-8")
    assert source.count('if __name__ == "__main__":') == 1
    assert "def find_button(" not in source
    assert "def force_foreground(" not in source
```

- [ ] **Step 2: Confirm the current appended legacy runtime fails the test**

Run: `.venv\Scripts\python.exe -m pytest tests/test_assets.py::test_launcher_has_one_main_guard -v`

Expected: FAIL because `accept_dota.py` has two main guards and legacy detection functions.

- [ ] **Step 3: Replace the launcher with one entry path**

```python
"""Windows launcher for Dota 2 Auto Accept."""

import os
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    if "--cli" in sys.argv:
        import config
        from engine import AutoAcceptEngine

        engine = AutoAcceptEngine(config.load())
        try:
            engine.run()
        except KeyboardInterrupt:
            engine.stop()
    else:
        from gui import main as gui_main

        gui_main()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Clean runtime requirements and tray strings**

Use one occurrence of each runtime package in `requirements.txt`: `opencv-python`, `numpy`, `mss`, `pyautogui`, conditional `pywin32`, `customtkinter`, `Pillow`, `pystray`, and `pyinstaller`. Change tray labels to `Открыть` and `Выход`; keep the default/double-click action on `Открыть`.

Create callback tests that do not start pystray:

```python
# tests/test_tray.py
from tray import TrayIcon


def test_show_only_invokes_show_callback():
    calls = []
    tray = TrayIcon(lambda: calls.append("show"), lambda: calls.append("quit"))
    tray._show()
    assert calls == ["show"]


def test_quit_stops_icon_then_invokes_quit(monkeypatch):
    calls = []
    tray = TrayIcon(lambda: calls.append("show"), lambda: calls.append("quit"))
    monkeypatch.setattr(tray, "stop", lambda: calls.append("stop"))
    tray._quit()
    assert calls == ["stop", "quit"]
```

- [ ] **Step 5: Update README behavior claims**

Document that launch starts stopped, close hides to tray, acceptance is attempted with background Enter and verified before notification, and real minimized behavior still requires a live ready-check test on the target machine. Remove any claim that all resolutions or minimized states are guaranteed without that test.

Use this exact behavior text in the primary usage section:

```markdown
## Поведение приложения

- После запуска открывается компактное окно; мониторинг выключен.
- Нажмите «Старт», чтобы начать ожидание матча.
- Крестик скрывает приложение в системный трей. Состояние мониторинга не меняется.
- Двойной щелчок по значку в трее возвращает окно.
- «Выход» в меню трея полностью завершает приложение.

## Принятие без переключения фокуса

Программа восстанавливает свёрнутое окно Dota 2 без активации, распознаёт ready-check через `PrintWindow`, отправляет Enter непосредственно окну игры и повторно проверяет, что ready-check исчез. Уведомление «матч принят» отправляется только после этой проверки.

Source 2 может игнорировать оконные сообщения ввода на отдельных конфигурациях. Поэтому работу со свёрнутой Dota необходимо подтвердить во время реального ready-check на целевом компьютере. Программа не переключает фокус автоматически и не сообщает ложный успех, если фоновый Enter не сработал.
```

- [ ] **Step 6: Run launcher and syntax checks**

Run: `.venv\Scripts\python.exe -m pytest tests/test_assets.py::test_launcher_has_one_main_guard tests/test_tray.py -v`

Run: `.venv\Scripts\python.exe -m compileall -q accept_dota.py config.py detector.py engine.py engine_events.py gui.py tray.py ui_state.py`

Expected: test passes and compileall exits 0.

- [ ] **Step 7: Commit launcher/package cleanup**

```powershell
git add -- accept_dota.py tray.py requirements.txt README.md tests/test_assets.py tests/test_tray.py
git commit -m "chore: clean launcher and runtime packaging"
```

### Task 8: Full verification, packaged build, and live Dota check

**Files:**
- Modify only files required by failures found in this task.

- [ ] **Step 1: Run the complete automated suite**

Run: `.venv\Scripts\python.exe -m pytest -v`

Expected: all tests pass with no skipped background-state tests.

- [ ] **Step 2: Run syntax and import verification**

Run: `.venv\Scripts\python.exe -m compileall -q .`

Run: `.venv\Scripts\python.exe -c "import config, detector, engine, engine_events, gui, tray, ui_state; print('imports ok')"`

Expected: compileall exits 0 and output is `imports ok`.

- [ ] **Step 3: Inspect all icon sizes**

Open `images/logo_16.png`, `images/logo_32.png`, and `images/logo_256.png`. Confirm transparent corners, a readable red rune, a distinct green check, and no opaque square halo.

- [ ] **Step 4: Exercise GUI/tray lifecycle**

Run: `.venv\Scripts\python.exe accept_dota.py`

Confirm: initial state stopped; Start changes to waiting; close hides to tray; tray double-click restores without changing running state; Stop returns to stopped; tray Exit terminates without launching the legacy CLI.

- [ ] **Step 5: Run a safe no-click background diagnostic**

With Dota running behind another application, execute a focused diagnostic that calls `find_dota_window`, `_restore_no_activate` only if needed, `detector.grab_window_bgr`, and `detector.is_usable_capture`, then restores the original minimized state. Record the foreground HWND before and after and require equality. Do not send Enter in this diagnostic.

Expected: Dota window found, usable capture true, foreground HWND unchanged, original minimized state restored.

- [ ] **Step 6: Build the executable**

Run: `.venv\Scripts\pyinstaller.exe dota_auto_accept.spec --clean --noconfirm`

Expected: `dist\DotaAutoAccept.exe` is created without missing-resource warnings.

- [ ] **Step 7: Verify the packaged executable**

Launch `dist\DotaAutoAccept.exe`. Confirm the detailed icon appears in Explorer/taskbar/title bar, the small icon is legible in the tray, the compact GUI opens stopped, and tray Exit terminates the process.

- [ ] **Step 8: Perform the real minimized ready-check test**

Start monitoring, begin Dota matchmaking, minimize Dota, and keep another harmless application foreground. During the ready-check, record the engine journal and verify all four conditions: the foreground application never changes, the ready-check disappears, Dota returns to minimized state, and Telegram success (when enabled) is sent only after verification.

If Source 2 ignores background `WM_KEYDOWN`, preserve the failed result and logs; do not enable focus stealing. Report that strict no-focus acceptance is not supported by the current Dota/input configuration instead of claiming success.

- [ ] **Step 9: Run final regression suite after any verification fixes**

Run: `.venv\Scripts\python.exe -m pytest -v`

Expected: all tests pass.

- [ ] **Step 10: Close verification cleanly**

If every check passed without source changes, create no additional commit. If a check failed, return to the task that owns that component, add one focused failing test there, apply the smallest fix, rerun that task's exact tests, and use that task's explicit `git add -- ...` file list. Never stage `build/`, `dist/`, `.superpowers/`, settings files, tokens, or unrelated user changes.
