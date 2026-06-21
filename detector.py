"""
Multi-method accept-button detector for Dota 2.

Methods:
  template  — classic multi-scale cv2.matchTemplate (needs bundled PNG)
  color     — resolution-independent green-button HSV mask
  combined  — runs both, picks the best confidence (default)
"""

import cv2
import numpy as np
import mss
import win32gui
import win32ui
import win32con

# ── Green-button HSV ranges (Dota 2 accept button specifically) ─────────────
# The Dota 2 accept button is a bright neon/saturated green.
# Tighter than generic green to avoid false positives (e.g. Steam buttons).
# The real filtering power comes from the search ROI + center_score.
GREEN_LOW  = np.array([35, 90, 80])
GREEN_HIGH = np.array([80, 255, 255])

# Approximate aspect ratio of the Dota 2 accept button (w/h ≈ 3.5–4.5)
BTN_ASPECT_MIN = 2.8
BTN_ASPECT_MAX = 5.5
BTN_MIN_AREA_RATIO = 0.004   # min button area / screen area
BTN_MAX_AREA_RATIO = 0.07    # max button area / screen area


def grab_screen_bgr():
    """Full-screen capture → BGR numpy array + monitor offset."""
    with mss.mss() as sct:
        mon = sct.monitors[1]  # primary monitor
        shot = sct.grab(mon)
        img = np.asarray(shot)[:, :, :3]  # BGRA → BGR
        return img, mon["left"], mon["top"]


def is_usable_capture(image, min_mean=2.0, min_std=1.0):
    if image is None or not isinstance(image, np.ndarray):
        return False
    if image.size == 0 or image.ndim != 3 or image.shape[2] < 3:
        return False
    luminance = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
    return float(luminance.mean()) > float(min_mean) and float(luminance.std()) > float(min_std)


def grab_window_bgr(hwnd):
    """
    Capture a specific window using Win32 PrintWindow.
    Works even when the window is behind other windows (not minimized).
    Returns (BGR numpy array, window_left, window_top) or (None, 0, 0).
    """
    if not hwnd:
        return None, 0, 0

    hwnd_dc = None
    mfc_dc = None
    save_dc = None
    bmp = None

    try:
        rect = win32gui.GetWindowRect(hwnd)
        w = rect[2] - rect[0]
        h = rect[3] - rect[1]
        if w <= 0 or h <= 0:
            return None, 0, 0

        hwnd_dc = win32gui.GetWindowDC(hwnd)
        if not hwnd_dc:
            hwnd_dc = None
            return None, 0, 0
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(mfc_dc, w, h)
        save_dc.SelectObject(bmp)

        # PW_RENDERFULLCONTENT = 2 → uses DWM composition, captures even obscured windows
        import ctypes
        if not ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2):
            return None, 0, 0

        bmp_info = bmp.GetInfo()
        bmp_bits = bmp.GetBitmapBits(True)

        img = np.frombuffer(bmp_bits, dtype=np.uint8)
        img = img.reshape(bmp_info['bmHeight'], bmp_info['bmWidth'], 4)
        img = img[:, :, :3]  # drop alpha channel

        if not is_usable_capture(img):
            return None, 0, 0

        return img, rect[0], rect[1]
    except Exception:
        return None, 0, 0
    finally:
        if bmp is not None:
            try:
                win32gui.DeleteObject(bmp.GetHandle())
            except Exception:
                pass
        if save_dc is not None:
            try:
                save_dc.DeleteDC()
            except Exception:
                pass
        if mfc_dc is not None:
            try:
                mfc_dc.DeleteDC()
            except Exception:
                pass
        if hwnd_dc is not None:
            try:
                win32gui.ReleaseDC(hwnd, hwnd_dc)
            except Exception:
                pass


# ── Template matching ───────────────────────────────────────────────────────
def find_button_template(screen_bgr, template, scales, threshold):
    """Multi-scale matchTemplate. Returns (conf, cx, cy) or (0, None, None)."""
    if template is None:
        return 0.0, None, None
    tpl_h, tpl_w = template.shape[:2]
    sh, sw = screen_bgr.shape[:2]
    best = (0.0, None, None)
    for s in scales:
        w, h = int(tpl_w * s), int(tpl_h * s)
        if w < 10 or h < 10 or w > sw or h > sh:
            continue
        tpl = cv2.resize(template, (w, h), interpolation=cv2.INTER_AREA)
        res = cv2.matchTemplate(screen_bgr, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val > best[0]:
            best = (max_val, max_loc[0] + w // 2, max_loc[1] + h // 2)
    return best


# ── Color-based detection ───────────────────────────────────────────────────
def find_button_color(screen_bgr):
    """
    Find the Dota 2 accept button by HSV colour mask.
    Tightly tuned to the specific neon green of the Dota 2 «Принять» popup.
    Resolution-independent — works on any screen size.
    Returns (confidence, cx, cy).
    """
    sh, sw = screen_bgr.shape[:2]
    screen_area = sh * sw

    hsv = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, GREEN_LOW, GREEN_HIGH)

    # Restrict search to center region where the Dota 2 match popup appears.
    # The «ВАША ИГРА ГОТОВА» popup is always in the middle of the screen.
    roi_mask = np.zeros_like(mask)
    x0, x1 = int(sw * 0.25), int(sw * 0.75)
    y0, y1 = int(sh * 0.30), int(sh * 0.75)
    roi_mask[y0:y1, x0:x1] = mask[y0:y1, x0:x1]

    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    roi_mask = cv2.morphologyEx(roi_mask, cv2.MORPH_CLOSE, kernel)
    roi_mask = cv2.morphologyEx(roi_mask, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(roi_mask, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)

    best = None
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        if bh < 20 or bw < 50:
            continue
        aspect = bw / bh
        if not (BTN_ASPECT_MIN <= aspect <= BTN_ASPECT_MAX):
            continue
        area = bw * bh
        area_ratio = area / screen_area
        if not (BTN_MIN_AREA_RATIO <= area_ratio <= BTN_MAX_AREA_RATIO):
            continue

        # Compute fill ratio — real buttons are solid green rectangles
        sub_mask = roi_mask[y:y + bh, x:x + bw]
        fill = cv2.countNonZero(sub_mask) / area
        if fill < 0.60:
            continue

        # Check how close the button centre is to the screen centre.
        # The Dota 2 accept popup is always centred.
        btn_cx = x + bw / 2
        btn_cy = y + bh / 2
        screen_cx = sw / 2
        screen_cy = sh / 2
        dist_x = abs(btn_cx - screen_cx) / (sw / 2)  # 0 = centre, 1 = edge
        dist_y = abs(btn_cy - screen_cy) / (sh / 2)
        center_score = max(0, 1.0 - (dist_x + dist_y))  # higher = closer to centre

        # Confidence: fill ratio + aspect closeness to ~4.0 + center position
        aspect_score = 1.0 - min(abs(aspect - 4.0) / 2.5, 1.0)
        conf = 0.40 * fill + 0.25 * aspect_score + 0.35 * center_score
        if best is None or conf > best[0]:
            cx = x + bw // 2
            cy = y + bh // 2
            best = (conf, cx, cy)

    if best is None:
        return 0.0, None, None
    return best


# ── Combined detector ───────────────────────────────────────────────────────
def find_button(screen_bgr, template=None, scales=None,
                use_color=True, use_template=True,
                threshold=0.75):
    """
    Unified entry point.  Template and HSV colour run together, best wins.
    Returns (conf, cx, cy, method_used).
    """
    if scales is None:
        scales = [1.0, 0.95, 1.05, 0.9, 1.1, 0.85, 1.15]

    best = (0.0, None, None, "none")

    # Template matching
    if use_template and template is not None:
        t_conf, t_cx, t_cy = find_button_template(
            screen_bgr, template, scales, threshold)
        if t_conf > best[0]:
            best = (t_conf, t_cx, t_cy, "template")

    # HSV colour detection
    if use_color:
        c_conf, c_cx, c_cy = find_button_color(screen_bgr)
        if c_conf > best[0]:
            best = (c_conf, c_cx, c_cy, "color")

    return best
