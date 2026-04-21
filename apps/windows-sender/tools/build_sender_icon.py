from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"
PNG_PATH = ASSETS_DIR / "snapbridge-icon.png"
ICO_PATH = ASSETS_DIR / "snapbridge.ico"


def radial_gradient(size: int, inner: tuple[int, int, int], outer: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGBA", (size, size))
    pixels = image.load()
    center = (size - 1) / 2
    max_distance = (2 * (center**2)) ** 0.5
    for y in range(size):
        for x in range(size):
            distance = ((x - center) ** 2 + (y - center) ** 2) ** 0.5
            t = min(1.0, distance / max_distance)
            t = t * t
            color = tuple(int(inner[i] * (1 - t) + outer[i] * t) for i in range(3))
            pixels[x, y] = (*color, 255)
    return image


def build_icon(size: int = 512) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse((52, 64, size - 36, size - 24), fill=(8, 18, 31, 155))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    canvas.alpha_composite(shadow)

    orb = radial_gradient(size, inner=(62, 159, 255), outer=(20, 63, 155))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((42, 42, size - 42, size - 42), fill=255)
    canvas.paste(orb, (0, 0), mask)

    draw = ImageDraw.Draw(canvas)
    draw.ellipse((42, 42, size - 42, size - 42), outline=(227, 242, 255, 255), width=14)
    draw.ellipse((76, 76, size - 76, size - 76), outline=(137, 194, 255, 180), width=8)
    draw.arc((110, 88, size - 124, size - 150), start=212, end=330, fill=(233, 245, 255, 220), width=14)
    draw.arc((112, 170, size - 112, size - 90), start=25, end=155, fill=(146, 206, 255, 190), width=9)

    try:
        font = ImageFont.truetype("segoeuib.ttf", 214)
    except OSError:
        font = ImageFont.load_default()

    glyph = "S"
    bbox = draw.textbbox((0, 0), glyph, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    text_x = (size - text_w) / 2 - bbox[0]
    text_y = (size - text_h) / 2 - bbox[1] - 10

    draw.text((text_x + 8, text_y + 8), glyph, font=font, fill=(11, 24, 41, 130))
    draw.text((text_x, text_y), glyph, font=font, fill=(247, 250, 255, 255))

    draw.ellipse((size - 148, 88, size - 92, 144), fill=(136, 238, 144, 255))
    draw.ellipse((size - 138, 98, size - 102, 134), fill=(198, 255, 203, 215))

    return canvas


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    image = build_icon()
    image.save(PNG_PATH)
    image.save(
        ICO_PATH,
        sizes=[(256, 256), (128, 128), (96, 96), (64, 64), (48, 48), (32, 32), (16, 16)],
    )
    print(f"Saved {PNG_PATH}")
    print(f"Saved {ICO_PATH}")


if __name__ == "__main__":
    main()
