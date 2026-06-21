"""
Core auto-accept engine for Dota 2.

Triggers:
  - HSHELL_FLASH  (taskbar blink when match found)
  - EVENT_SYSTEM_FOREGROUND  (Dota window comes to front)
  - WM_TIMER safety scan  (periodic fallback)

Action: detect accept button → click → optional Telegram notification.
"""

import os
import time
import uuid
import ctypes
from ctypes import wintypes

import cv2
import win32api
import win32con
import win32gui
import win32process

import threading

import config
import detector
import telegram_notifier as tg
from engine_events import EngineEvent, EngineState

# ── WinAPI constants ─────────────────────────────────────────────────────────
HSHELL_HIGHBIT = 0x8000
HSHELL_REDRAW = 6
EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_OUTOFCONTEXT = 0x0000

user32 = ctypes.windll.user32

TEMPLATE_PATH = "images/accept_button.png"
SIGNAL_ENTER_REASONS = frozenset({"taskbar flash", "window foreground"})


class AutoAcceptEngine:
    """Main engine. Controlled by the GUI (start/stop/update_config)."""

    def __init__(self, cfg: dict, log_callback=None, config_callback=None,
                 status_callback=None):
        self.cfg = dict(cfg)
        self._log = log_callback or (lambda msg: print(msg))
        self._status_callback = status_callback
        # config_callback: returns the LIVE config from the GUI (always up-to-date)
        self._get_live_config = config_callback

        # Load template (may be None if file missing — color mode still works)
        self._template = None
        tpl_path = config.resource_path(TEMPLATE_PATH)
        if os.path.isfile(tpl_path):
            self._template = cv2.imread(tpl_path, cv2.IMREAD_COLOR)
            if self._template is not None:
                self._log(f"[*] Template loaded: {self._template.shape[1]}x{self._template.shape[0]}")
            else:
                self._log("[!] Failed to read template image")
        else:
            self._log("[*] No template file — using color-only detection")

        self._last_action_ts = 0.0
        self._last_accept_method = "none"
        self._running = False
        self._hwnd = None
        self._win_event_proc = None
        self._shellhook_msg = None
        self._thread = None
        self._attempt_lock = threading.Lock()

    def _emit(self, state, title, detail=""):
        event = EngineEvent(state, title, detail)
        if self._status_callback:
            self._status_callback(event)
        self._log(
            f"[{state.value}] {title}" + (f" — {detail}" if detail else "")
        )

    def request_accept(self, reason):
        if not self._running or not self._attempt_lock.acquire(blocking=False):
            return False

        def worker():
            try:
                self.try_accept(reason)
            finally:
                self._attempt_lock.release()

        try:
            threading.Thread(
                target=worker,
                daemon=True,
                name="dota-accept-attempt",
            ).start()
        except Exception:
            self._attempt_lock.release()
            raise
        return True

    # ── Dota window helpers ──────────────────────────────────────────────
    @staticmethod
    def _proc_name(hwnd):
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            h = win32api.OpenProcess(
                win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            try:
                path = win32process.GetModuleFileNameEx(h, 0)
            finally:
                win32api.CloseHandle(h)
            return path.lower()
        except Exception:
            return ""

    @staticmethod
    def is_dota(hwnd):
        if not hwnd:
            return False
        title = win32gui.GetWindowText(hwnd) or ""
        if title.strip() == "Dota 2":
            return True
        return "dota2.exe" in AutoAcceptEngine._proc_name(hwnd)

    @staticmethod
    def find_dota_window():
        """Find any Dota 2 window (including minimized ones)."""
        found = []

        def cb(hwnd, _):
            if AutoAcceptEngine.is_dota(hwnd):
                found.append(hwnd)

        win32gui.EnumWindows(cb, None)
        return found[0] if found else None

    @staticmethod
    def _focus_dota(hwnd):
        """Bring Dota forward exactly once after the ready button is detected."""
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.08)
            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
            win32api.keybd_event(
                win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0
            )
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception as exc:
            return False

    @staticmethod
    def _press_enter_foreground():
        try:
            win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
            time.sleep(0.03)
            win32api.keybd_event(
                win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0
            )
            return True
        except Exception:
            return False

    @staticmethod
    def _restore_no_activate(hwnd):
        """Restore a minimized window WITHOUT stealing focus."""
        try:
            if not win32gui.IsIconic(hwnd):
                return True
            placement = win32gui.GetWindowPlacement(hwnd)
            placement = (
                placement[0], 4,  # SW_SHOWNOACTIVATE
                placement[2], placement[3], placement[4],
            )
            win32gui.SetWindowPlacement(hwnd, placement)
            time.sleep(0.15)
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

    # ── Telegram helpers ─────────────────────────────────────────────────
    def _live_cfg(self) -> dict:
        """Get the latest config — uses callback if available, else static copy."""
        if self._get_live_config:
            try:
                return self._get_live_config()
            except Exception:
                pass
        return self.cfg

    def _tg_notify(self, func_name: str, *args):
        """Send a Telegram notification using the shared bot."""
        cfg = self._live_cfg()
        if cfg.get("telegram_enabled") and cfg.get("telegram_chat_id"):
            fn = getattr(tg, func_name, None)
            if fn:
                fn(cfg["telegram_chat_id"], *args,
                   username=cfg.get("telegram_username", ""))

    def _detector_kwargs(self):
        """Build detector parameters from current config."""
        cfg = self._live_cfg()
        return dict(
            use_color=cfg.get("use_color", True),
            use_template=cfg.get("use_template", True),
            threshold=cfg.get("match_threshold", 0.75),
        )

    # ── Core action ──────────────────────────────────────────────────────
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
            use_color=cfg.get("use_color", True),
            use_template=cfg.get("use_template", True),
            threshold=cfg.get("match_threshold", 0.75),
        )
        return confidence >= cfg.get("match_threshold", 0.75)

    def _focus_and_enter(self, hwnd, method, detail):
        """Focus Dota once and send a normal foreground Enter."""
        self._emit(EngineState.VERIFYING, "Принимаю матч", detail)
        if not self._focus_dota(hwnd):
            return False
        time.sleep(0.08)
        accepted = self._press_enter_foreground()
        if accepted:
            self._last_accept_method = method
        return accepted

    def _run_background_attempt(self, hwnd, cfg, reason):
        visual_enabled = bool(
            cfg.get("use_color", True) or cfg.get("use_template", True)
        )
        if visual_enabled:
            deadline = time.time() + float(cfg.get("retry_seconds", 4.0))
            interval = max(0.01, float(cfg.get("retry_interval", 0.25)))
            while self._running and time.time() < deadline:
                image = self._capture_dota(hwnd, cfg)
                if image is not None and self._detect_ready(image, cfg):
                    self._tg_notify("notify_match_found")
                    return self._focus_and_enter(
                        hwnd,
                        "visual-enter",
                        "Кнопка подтверждена распознаванием",
                    )
                time.sleep(interval)

        if cfg.get("use_enter", True) and reason in SIGNAL_ENTER_REASONS:
            return self._focus_and_enter(
                hwnd,
                "signal-enter",
                "Резервный Enter по системному сигналу",
            )
        return False

    def _attempt_with_window_state(self, hwnd, cfg, reason):
        was_minimized = bool(win32gui.IsIconic(hwnd))
        accepted = False
        try:
            if was_minimized and not self._restore_no_activate(hwnd):
                return False
            accepted = self._run_background_attempt(hwnd, cfg, reason)
            return accepted
        except Exception as exc:
            self._log(f"[!] Background attempt error: {exc}")
            return False
        finally:
            if was_minimized and not accepted:
                self._minimize_no_activate(hwnd)

    def try_accept(self, reason: str) -> bool:
        cfg = self._live_cfg()
        now = time.time()
        if now - self._last_action_ts < cfg.get("debounce_seconds", 8.0):
            return False
        dota = self.find_dota_window()
        if not dota:
            self._emit(
                EngineState.WAITING,
                "Ожидаю Dota 2",
                "Окно игры пока не найдено",
            )
            return False
        if reason == "safety scan" and win32gui.IsIconic(dota):
            return False
        self._emit(EngineState.DETECTING, "Проверяю Dota 2", reason)
        if not self._attempt_with_window_state(dota, cfg, reason):
            self._emit(
                EngineState.FAILED,
                "Не удалось принять",
                "Методы принятия не сработали",
            )
            return False
        self._last_action_ts = time.time()
        self._tg_notify("notify_accepted", self._last_accept_method)
        self._emit(
            EngineState.ACCEPTED,
            "Матч принят",
            "Enter отправлен в Dota 2",
        )
        if cfg.get("exit_after_accept"):
            self.stop()
        return True

    # ── WinAPI callbacks ─────────────────────────────────────────────────
    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == self._shellhook_msg:
            code = wparam & 0x7FFF
            is_flash = (wparam & HSHELL_HIGHBIT) and code == HSHELL_REDRAW
            if is_flash and self.is_dota(lparam):
                self.request_accept("taskbar flash")
            return 0
        if msg == win32con.WM_TIMER:
            scan = self._live_cfg().get("safety_scan_sec", 2.0)
            if scan > 0:
                self.request_accept("safety scan")
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _fg_callback(self, hWinEventHook, event, hwnd, idObject,
                     idChild, dwEventThread, dwmsEventTime):
        try:
            if self.is_dota(hwnd):
                self.request_accept("window foreground")
        except Exception:
            pass

    # ── Run / Stop ───────────────────────────────────────────────────────
    def run(self):
        """Blocking — call from a worker thread."""
        self._running = True

        # Use unique class name per engine instance to avoid RegisterClass conflicts
        self._class_name = f"DotaAutoAcceptWnd_{uuid.uuid4().hex[:8]}"

        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._wnd_proc
        wc.lpszClassName = self._class_name
        wc.hInstance = win32api.GetModuleHandle(None)
        try:
            atom = win32gui.RegisterClass(wc)
        except Exception:
            pass  # class may already exist
        self._hwnd = win32gui.CreateWindow(
            atom, "DotaAutoAccept", 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None)

        if user32.RegisterShellHookWindow(self._hwnd):
            self._log("[*] Listening for taskbar flash (HSHELL_FLASH).")
        else:
            self._log("[!] Shell hook registration failed.")

        self._shellhook_msg = win32gui.RegisterWindowMessage("SHELLHOOK")

        WinEventProcType = ctypes.WINFUNCTYPE(
            None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
            wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)
        self._win_event_proc = WinEventProcType(self._fg_callback)
        user32.SetWinEventHook(
            EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND,
            0, self._win_event_proc, 0, 0, WINEVENT_OUTOFCONTEXT)
        self._log("[*] Listening for Dota foreground switch.")

        scan = self.cfg.get("safety_scan_sec", 2.0)
        if scan > 0:
            user32.SetTimer(self._hwnd, 1, int(scan * 1000), None)
            self._log(f"[*] Safety scan every {scan}s.")

        methods = []
        if self.cfg.get("use_color"):
            methods.append("color")
        if self.cfg.get("use_template"):
            methods.append("template")
        if self.cfg.get("use_enter"):
            methods.append("enter")
        self._log(f"[*] Active methods: {', '.join(methods) if methods else 'none'}")
        self._log("[*] Ready. Waiting for match.\n")
        self._emit(EngineState.WAITING, "Ожидаю матч", "Слушатели Windows активны")

        try:
            win32gui.PumpMessages()
        except Exception:
            pass
        self._running = False
        self._emit(EngineState.STOPPED, "Остановлен", "Мониторинг завершён")
        self._log("[*] Engine stopped.")

    def stop(self):
        """Signal the message loop to exit and clean up window."""
        self._running = False
        hwnd = self._hwnd
        if hwnd:
            self._hwnd = None
            # DestroyWindow causes GetMessage to return 0 → PumpMessages exits.
            # PostMessage(WM_QUIT) is unreliable (window-level vs thread-level).
            try:
                win32gui.DestroyWindow(hwnd)
            except Exception:
                pass
            # Schedule UnregisterClass after message loop exits
            class_name = getattr(self, "_class_name", None)
            if class_name:
                def _cleanup():
                    try:
                        win32gui.UnregisterClass(class_name, win32api.GetModuleHandle(None))
                    except Exception:
                        pass
                threading.Thread(target=_cleanup, daemon=True).start()

    @property
    def running(self):
        return self._running

    def update_config(self, cfg: dict):
        """Hot-update settings (takes effect on next trigger)."""
        self.cfg.update(cfg)
