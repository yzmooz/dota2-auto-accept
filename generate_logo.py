"""Build the Dota Auto Accept icon family from one RGBA master image."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


ICON_SIZES = (16, 20, 24, 32, 48, 64, 256)
ROOT = Path(__file__).resolve().parent
DEFAULT_IMAGE_DIR = ROOT / "images"
DEFAULT_MASTER = DEFAULT_IMAGE_DIR / "logo_master.png"


def prepare_master(source_path: str | Path, master_path: str | Path) -> Path:
    """Copy the supplied square artwork while making its outer circle transparent."""
    source_path = Path(source_path)
    master_path = Path(master_path)

    with Image.open(source_path) as opened:
        image = opened.convert("RGBA")

    side = min(image.size)
    left = (image.width - side) // 2
    top = (image.height - side) // 2
    image = image.crop((left, top, left + side, top + side))

    # Supersampling keeps the circular edge smooth while guaranteeing clear corners.
    scale = 4
    mask = Image.new("L", (side * scale, side * scale), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((1, 1, side * scale - 2, side * scale - 2), fill=255)
    mask = mask.resize((side, side), Image.Resampling.LANCZOS)
    image.putalpha(mask)

    master_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(master_path, format="PNG", optimize=True, compress_level=9)
    return master_path


def _render(master: Image.Image, size: int) -> Image.Image:
    icon = master.resize((size, size), Image.Resampling.LANCZOS)

    if size <= 32:
        # Tray-sized frames need stronger local separation than the large artwork.
        alpha = icon.getchannel("A")
        rgb = icon.convert("RGB")
        rgb = ImageEnhance.Contrast(rgb).enhance(1.28)
        rgb = ImageEnhance.Color(rgb).enhance(1.18)
        rgb = rgb.filter(ImageFilter.UnsharpMask(radius=0.7, percent=180, threshold=2))
        icon = Image.merge("RGBA", (*rgb.split(), alpha))

    return icon


def generate_assets(master_path: str | Path = DEFAULT_MASTER,
                    output_dir: str | Path = DEFAULT_IMAGE_DIR) -> tuple[Path, ...]:
    """Generate deterministic PNG frames and a multi-frame Windows icon."""
    master_path = Path(master_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(master_path) as opened:
        master = opened.convert("RGBA")
    if master.width != master.height:
        raise ValueError("logo master must be square")

    frames = {size: _render(master, size) for size in ICON_SIZES}
    paths = []
    for size in ICON_SIZES:
        path = output_dir / f"logo_{size}.png"
        frames[size].save(path, format="PNG", optimize=True, compress_level=9)
        paths.append(path)

    ico_path = output_dir / "logo.ico"
    frames[256].save(
        ico_path,
        format="ICO",
        sizes=[(size, size) for size in ICON_SIZES],
        append_images=[frames[size] for size in ICON_SIZES if size != 256],
    )
    paths.append(ico_path)
    return tuple(paths)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        help="optional source artwork used to rebuild logo_master.png")
    parser.add_argument("--master", type=Path, default=DEFAULT_MASTER)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_IMAGE_DIR)
    args = parser.parse_args()

    if args.source:
        prepare_master(args.source, args.master)
    generate_assets(args.master, args.output_dir)


if __name__ == "__main__":
    main()
