"""Generate a GitHub social preview image for PolyAgent."""

from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError as exc:  # pragma: no cover - helper script
    raise SystemExit("Pillow is required. Install it with `pip install Pillow`.") from exc

PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = PROJECT_ROOT / "docs" / "images"
OUTPUT_PATH = IMAGE_DIR / "polyagent-social-preview.png"
CANVAS_SIZE = (1280, 640)
BACKGROUND = "#f5f7f4"
INK = "#172033"
SOFT = "#5f6b7a"
ACCENT = "#10a37f"
ACCENT_SOFT = "#d8f3ea"
CARD = "#ffffff"
CARD_BORDER = "#d9e2dc"


def load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def round_corners(image: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, image.size[0], image.size[1]), radius=radius, fill=255)
    rounded = image.copy()
    rounded.putalpha(mask)
    return rounded


def add_card_shadow(base: Image.Image, box: tuple[int, int, int, int], radius: int = 28) -> None:
    shadow = Image.new("RGBA", (box[2] - box[0] + 28, box[3] - box[1] + 28), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle(
        (14, 14, shadow.size[0] - 14, shadow.size[1] - 14),
        radius=radius,
        fill=(23, 32, 51, 28),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    base.alpha_composite(shadow, (box[0] - 14, box[1] - 4))


def paste_card(
    canvas: Image.Image,
    source_path: Path,
    *,
    box: tuple[int, int, int, int],
    radius: int = 28,
) -> None:
    add_card_shadow(canvas, box, radius=radius)
    card = Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), CARD)
    source = Image.open(source_path).convert("RGB")
    source.thumbnail((card.size[0] - 28, card.size[1] - 58))
    offset = ((card.size[0] - source.size[0]) // 2, 14)
    card.paste(source, offset)
    rounded = round_corners(card, radius)
    canvas.alpha_composite(rounded, (box[0], box[1]))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(box, radius=radius, outline=CARD_BORDER, width=2)


def main() -> None:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    canvas = Image.new("RGBA", CANVAS_SIZE, BACKGROUND)
    draw = ImageDraw.Draw(canvas)

    title_font = load_font(54, bold=True)
    subtitle_font = load_font(24)
    badge_font = load_font(20, bold=True)
    body_font = load_font(22)
    caption_font = load_font(18, bold=True)

    badge_text = "PolyAgent v0.1.0"
    badge_x = 54
    badge_y = 52
    badge_padding_x = 20
    badge_padding_y = 11
    badge_bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
    badge_width = (badge_bbox[2] - badge_bbox[0]) + badge_padding_x * 2
    badge_height = (badge_bbox[3] - badge_bbox[1]) + badge_padding_y * 2
    badge_box = (
        badge_x,
        badge_y,
        badge_x + badge_width,
        badge_y + badge_height,
    )
    draw.rounded_rectangle(badge_box, radius=22, fill=ACCENT_SOFT, outline=ACCENT)
    draw.text(
        (badge_x + badge_padding_x, badge_y + badge_padding_y - 1),
        badge_text,
        font=badge_font,
        fill=ACCENT,
    )
    draw.text(
        (54, 130),
        "Multi-Agent Assistant\nfor Knowledge Workflows",
        font=title_font,
        fill=INK,
        spacing=10,
    )
    draw.text(
        (54, 268),
        "Grounded QA, document summarization, formal writing,\nand step-by-step guidance in one workspace.",
        font=subtitle_font,
        fill=SOFT,
        spacing=8,
    )

    bullets = [
        "Grounded retrieval from Markdown knowledge bases",
        "Compound requests routed across multiple agents",
        "Launch-ready README, screenshots, and release docs",
    ]
    top = 360
    for bullet in bullets:
        draw.ellipse((60, top + 9, 72, top + 21), fill=ACCENT)
        draw.text((86, top), bullet, font=body_font, fill=INK)
        top += 54

    cards = [
        (
            (730, 86, 1210, 346),
            IMAGE_DIR / "polyagent-home-desktop-en.png",
            "Desktop workspace",
            (748, 108),
        ),
        (
            (668, 330, 1138, 592),
            IMAGE_DIR / "polyagent-feature-multi-agent-en.png",
            "Multi-agent orchestration",
            (686, 560),
        ),
    ]
    for box, image_path, label, label_position in cards:
        paste_card(canvas, image_path, box=box)
        draw.text(label_position, label, font=caption_font, fill=INK)

    canvas.convert("RGB").save(OUTPUT_PATH, quality=95)
    print(f"Saved social preview to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
