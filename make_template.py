
import os
import sys
import cv2
import numpy as np

OUT = os.path.join("images", "accept_button.png")


def auto_crop(img):
    """Найти зелёную кнопку в центре кадра."""
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (35, 80, 60), (85, 255, 255))
    sub = np.zeros_like(mask)
    cx0, cx1 = int(w * 0.20), int(w * 0.80)
    cy0, cy1 = int(h * 0.30), int(h * 0.80)
    sub[cy0:cy1, cx0:cx1] = mask[cy0:cy1, cx0:cx1]
    cnts, _ = cv2.findContours(sub, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    for c in cnts:
        x, y, bw, bh = cv2.boundingRect(c)
        if bw > 80 and bh > 25 and bw > bh * 1.5 and bw < w * 0.45:
            area = bw * bh
            if best is None or area > best[0]:
                best = (area, x, y, bw, bh)
    return None if best is None else best[1:]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    path = sys.argv[1]
    img = cv2.imread(path)
    if img is None:
        print(f"[!] Не удалось открыть скриншот: {path}")
        sys.exit(1)

    if len(sys.argv) >= 6:
        x, y, bw, bh = map(int, sys.argv[2:6])
    else:
        box = auto_crop(img)
        if box is None:
            print("[!] Зелёную кнопку найти не удалось. Задай область вручную:")
            print("    python make_template.py скрин.png x y w h")
            sys.exit(1)
        x, y, bw, bh = box
        print(f"[*] Кнопка найдена: x={x} y={y} w={bw} h={bh}")

    crop = img[y + 3:y + bh - 3, x + 3:x + bw - 3]
    os.makedirs("images", exist_ok=True)
    cv2.imwrite(OUT, crop)
    print(f"[+] Эталон сохранён: {OUT}  (размер {crop.shape[1]}x{crop.shape[0]})")


if __name__ == "__main__":
    main()
