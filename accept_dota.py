"""
Авто-принятие матча в Dota 2.

Архитектура (см. обсуждение):
  Триггер  — настоящие события Windows, а не постоянные скриншоты:
             1) HSHELL_FLASH — окно Dota замигало в панели задач (это и есть
                красное мигание, которое ты видишь, когда найден матч);
             2) EVENT_SYSTEM_FOREGROUND — окно Dota вышло на передний план
                (запасной сигнал, если фокус всё-таки переключается).
  Действие — только в момент триггера: один template-match кнопки «ПРИНЯТЬ»
             по эталону images/accept_button.png и клик по ней.

Valve не отдаёт координаты кнопки наружу (Source 2 / Panorama рендерится как
картинка), поэтому поиск кнопки — через OpenCV. Но матчинг запускается НЕ
постоянно, а только когда система уже сказала «матч найден».
Запуск:
    python accept_dota.py            # рабочий режим — ждёт матч
    python accept_dota.py --test     # разово проверить, видит ли кнопку сейчас
    python accept_dota.py --test --click   # то же, но реально кликнуть (для проверки)

Остановка: Ctrl+C в консоли, либо увести курсор в левый верхний угол экрана
(сработает failsafe pyautogui).
"""

import sys
import time
import ctypes
from ctypes import wintypes

import cv2
import numpy as np
import mss
import pyautogui
import win32api
import win32con
import win32gui
import win32process

#
# ── Настройки ────────────────────────────────────────────────────────────────
TEMPLATE_PATH   = "images/accept_button.png"  # эталон кнопки «ПРИНЯТЬ»
MATCH_THRESHOLD = 0.75   # порог уверенности совпадения (0..1). Выше — строже.
RETRY_SECONDS   = 4.0    # сколько искать кнопку после триггера (мигание может
                         # чуть опередить отрисовку попапа)
RETRY_INTERVAL  = 0.25   # пауза между попытками поиска, сек
DEBOUNCE_SECONDS = 8.0   # не реагировать повторно сразу после клика
SAFETY_SCAN_SEC = 2    # фоновый «страховочный» скан раз в N сек (0 = выключить).
                         # Лёгкий: один matchTemplate. Подстраховка на случай,
                         # если событие мигания не придёт.
SCALES = (1.00, 0.95, 1.05, 0.90, 1.10, 0.85, 1.15)  # масштабы для надёжности
                         # на чужом разрешении (эталон снят на 1920×1080)

pyautogui.FAILSAFE = True   # курсор в угол экрана => аварийная остановка
pyautogui.PAUSE = 0.0

# ── Константы WinAPI ─────────────────────────────────────────────────────────
HSHELL_HIGHBIT = 0x8000
HSHELL_REDRAW  = 6                         # HSHELL_FLASH = HSHELL_REDRAW|HIGHBIT
EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_OUTOFCONTEXT   = 0x0000

user32 = ctypes.windll.user32

# ── Загрузка эталона ─────────────────────────────────────────────────────────
_template = cv2.imread(TEMPLATE_PATH, cv2.IMREAD_COLOR)
if _template is None:
    print(f"[!] Не найден эталон кнопки: {TEMPLATE_PATH}")
    sys.exit(1)
_TPL_H, _TPL_W = _template.shape[:2]

_last_action_ts = 0.0


# ── Поиск кнопки и клик ──────────────────────────────────────────────────────
def grab_screen_bgr():
    """Снимок всего экрана как BGR-массив для OpenCV."""
    with mss.mss() as sct:
        mon = sct.monitors[1]          # основной монитор
        shot = sct.grab(mon)
        img = np.asarray(shot)[:, :, :3]   # BGRA -> BGR
        return img, mon["left"], mon["top"]


def find_button(screen_bgr):
    """Мультимасштабный matchTemplate. Возвращает (conf, cx, cy) лучшего совпадения."""
    best = (0.0, None, None)
    for s in SCALES:
        w, h = int(_TPL_W * s), int(_TPL_H * s)
        if w < 10 or h < 10 or w > screen_bgr.shape[1] or h > screen_bgr.shape[0]:
            continue
        tpl = cv2.resize(_template, (w, h), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(screen_bgr, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val > best[0]:
            best = (max_val, max_loc[0] + w // 2, max_loc[1] + h // 2)
    return best


def force_foreground(hwnd):
    """Попытаться вывести окно вперёд (обходим блокировку фокуса нажатием ALT)."""
    try:
        win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
        win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass


def try_accept(reason):
    """Найти кнопку и кликнуть. Вызывается по триггеру. С дебаунсом."""
    global _last_action_ts
    now = time.time()
    if now - _last_action_ts < DEBOUNCE_SECONDS:
        return False

    deadline = now + RETRY_SECONDS
    while time.time() < deadline:
        screen, ox, oy = grab_screen_bgr()
        conf, cx, cy = find_button(screen)
        if conf >= MATCH_THRESHOLD:
            sx, sy = ox + cx, oy + cy
            print(f"[+] Кнопка найдена ({reason}), уверенность {conf:.2f} -> клик ({sx},{sy})")
            dota = find_dota_window()
            if dota:
                force_foreground(dota)
                time.sleep(0.05)
            saved = win32api.GetCursorPos()
            pyautogui.click(sx, sy)
            try:
                win32api.SetCursorPos(saved)   # вернуть курсор на место
            except Exception:
                pass
            _last_action_ts = time.time()
            return True
        time.sleep(RETRY_INTERVAL)

    print(f"[-] Триггер ({reason}), но кнопку не нашёл (порог {MATCH_THRESHOLD}).")
    return False


# ── Определение окна Dota ────────────────────────────────────────────────────
def _proc_name(hwnd):
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        h = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        try:
            path = win32process.GetModuleFileNameEx(h, 0)
        finally:
            win32api.CloseHandle(h)
        return path.lower()
    except Exception:
        return ""


def is_dota(hwnd):
    if not hwnd:
        return False
    title = (win32gui.GetWindowText(hwnd) or "")
    if title.strip() == "Dota 2":
        return True
    return "dota2.exe" in _proc_name(hwnd)


def find_dota_window():
    """Найти top-level окно Dota среди видимых (для вывода вперёд)."""
    found = []

    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and is_dota(hwnd):
            found.append(hwnd)
    win32gui.EnumWindows(cb, None)
    return found[0] if found else None


# ── Слой событий Windows ─────────────────────────────────────────────────────
_SHELLHOOK_MSG = win32gui.RegisterWindowMessage("SHELLHOOK")

# держим ссылку на callback, иначе GC его соберёт и будет краш
_win_event_proc = None


def _wnd_proc(hwnd, msg, wparam, lparam):
    if msg == _SHELLHOOK_MSG:
        code = wparam & 0x7FFF
        is_flash = (wparam & HSHELL_HIGHBIT) and code == HSHELL_REDRAW
        if is_flash and is_dota(lparam):
            try_accept("мигание в таскбаре")
        return 0
    if msg == win32con.WM_TIMER and SAFETY_SCAN_SEC > 0:
        # лёгкий страховочный скан
        screen, ox, oy = grab_screen_bgr()
        conf, cx, cy = find_button(screen)
        if conf >= MATCH_THRESHOLD:
            try_accept("страховочный скан")
        return 0
    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


def _foreground_callback(hWinEventHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
    if is_dota(hwnd):
        try_accept("окно вышло вперёд")


def run():
    global _win_event_proc

    # 1) скрытое message-only окно для шелл-хука
    wc = win32gui.WNDCLASS()
    wc.lpfnWndProc = _wnd_proc
    wc.lpszClassName = "DotaAutoAcceptWnd"
    wc.hInstance = win32api.GetModuleHandle(None)
    atom = win32gui.RegisterClass(wc)
    hwnd = win32gui.CreateWindow(atom, "DotaAutoAccept", 0, 0, 0, 0, 0,
                                 0, 0, wc.hInstance, None)

    if not user32.RegisterShellHookWindow(hwnd):
        print("[!] Не удалось зарегистрировать шелл-хук (мигание ловиться не будет).")
    else:
        print("[*] Слушаю мигание окна Dota в панели задач (HSHELL_FLASH).")

    # 2) хук на выход окна вперёд
    WinEventProcType = ctypes.WINFUNCTYPE(
        None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
        wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)
    _win_event_proc = WinEventProcType(_foreground_callback)
    user32.SetWinEventHook(EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND,
                           0, _win_event_proc, 0, 0, WINEVENT_OUTOFCONTEXT)
    print("[*] Слушаю переключение фокуса на Dota (EVENT_SYSTEM_FOREGROUND).")

    # 3) страховочный таймер
    if SAFETY_SCAN_SEC > 0:
        user32.SetTimer(hwnd, 1, int(SAFETY_SCAN_SEC * 1000), None)
        print(f"[*] Страховочный скан каждые {SAFETY_SCAN_SEC} сек.")

    print("[*] Готов. Жду матч. Остановка: Ctrl+C или курсор в левый верхний угол.\n")
    try:
        win32gui.PumpMessages()
    except KeyboardInterrupt:
        print("\n[*] Остановлено.")


def test(do_click=False):
    """Разовая проверка: видит ли скрипт кнопку прямо сейчас."""
    screen, ox, oy = grab_screen_bgr()
    conf, cx, cy = find_button(screen)
    print(f"Уверенность совпадения: {conf:.3f} (порог {MATCH_THRESHOLD})")
    if cx is not None:
        print(f"Кнопка по центру экрана в точке: ({ox+cx}, {oy+cy})")
    if conf >= MATCH_THRESHOLD:
        print("=> Кнопка распознана.")
        if do_click:
            pyautogui.click(ox + cx, oy + cy)
            print("=> Клик выполнен.")
    else:
        print("=> Кнопка не распознана (открой ready-check или проверь эталон).")


if __name__ == "__main__":
    if "--test" in sys.argv:
        test(do_click="--click" in sys.argv)
    else:
        run()
