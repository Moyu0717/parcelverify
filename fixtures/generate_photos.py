"""
ParcelVerify - Fixture Photo Generator

Generates 12 placeholder parcel photos as colored JPEGs with text labels.
These are real image files that produce valid SHA-256 and pHash values.

Run: python fixtures/generate_photos.py
"""

from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont

# Output directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = SCRIPT_DIR  # Save directly in fixtures/

# 12 photo configurations: different colors and labels
PHOTOS = [
    {"name": "photo_001.jpg", "color": (220, 60, 60), "label": "PV-DEMO-001\nHandoff\nSEAL-07"},
    {"name": "photo_002.jpg", "color": (60, 120, 220), "label": "PV-DEMO-001\nSeal Detail\nSEAL-07"},
    {"name": "photo_003.jpg", "color": (60, 180, 80), "label": "PV-DEMO-001\nWeight Scale\n1850g"},
    {"name": "photo_004.jpg", "color": (180, 160, 60), "label": "PV-DEMO-001\nPOD\nSigned"},
    {"name": "photo_005.jpg", "color": (160, 80, 200), "label": "PV-SHIP-002\nDispatch\nSEAL-12"},
    {"name": "photo_006.jpg", "color": (80, 200, 200), "label": "PV-SHIP-003\nHandoff\nSEAL-21"},
    {"name": "photo_007.jpg", "color": (220, 160, 60), "label": "PV-SHIP-005\nSeal Check\nSEAL-33"},
    {"name": "photo_008.jpg", "color": (60, 80, 160), "label": "PV-SHIP-008\nPOD\nRecipient"},
    {"name": "photo_009.jpg", "color": (200, 100, 80), "label": "PV-SHIP-012\nWeight\n2100g"},
    {"name": "photo_010.jpg", "color": (100, 200, 120), "label": "PV-SHIP-015\nPackage\nCondition OK"},
    {"name": "photo_011.jpg", "color": (160, 120, 80), "label": "PV-SHIP-020\nRepackaging\nApproved"},
    {"name": "photo_012.jpg", "color": (80, 160, 220), "label": "PV-SHIP-025\nHandoff\nSEAL-44"},
]

# Image dimensions (640x480 = 0.307 MP, well under 20 MP limit)
IMG_WIDTH = 640
IMG_HEIGHT = 480


def _get_font(size: int = 28) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try to load a TrueType font, fall back to default."""
    try:
        return ImageFont.truetype("arial.ttf", size)
    except (OSError, IOError):
        return ImageFont.load_default()


def generate_photo(config: dict) -> str:
    """Generate a single placeholder photo."""
    img = Image.new("RGB", (IMG_WIDTH, IMG_HEIGHT), config["color"])
    draw = ImageDraw.Draw(img)

    # Draw a border rectangle
    border_color = tuple(max(0, c - 60) for c in config["color"])
    draw.rectangle(
        [10, 10, IMG_WIDTH - 10, IMG_HEIGHT - 10],
        outline=border_color,
        width=3,
    )

    # Draw label text centered
    font = _get_font(28)
    lines = config["label"].split("\n")
    y = IMG_HEIGHT // 2 - len(lines) * 20
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (IMG_WIDTH - text_width) // 2
        # Draw text with contrast color
        text_color = (255, 255, 255) if sum(config["color"]) < 400 else (0, 0, 0)
        draw.text((x, y), line, fill=text_color, font=font)
        y += 40

    # Save
    path = os.path.join(OUTPUT_DIR, config["name"])
    img.save(path, "JPEG", quality=85)
    return path


def generate_all() -> list[str]:
    """Generate all fixture photos."""
    paths = []
    for config in PHOTOS:
        path = generate_photo(config)
        paths.append(path)
        print(f"Generated: {path}")
    return paths


if __name__ == "__main__":
    paths = generate_all()
    print(f"\nGenerated {len(paths)} fixture photos in {OUTPUT_DIR}")
