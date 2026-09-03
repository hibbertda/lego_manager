"""Generates the printable storage-box labels used when a set is disassembled
for parts storage: cover image in the upper-left corner, name/theme/set
number filling the space below it (left edge to the QR column), and a QR
code linking back to the set's page on the right.

Labels are composed as flat 4in x 2in (landscape) PNGs at 300 DPI so they
print cleanly at true size on standard label stock, and are saved under
SETS_DIR alongside each set's other downloaded assets.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import qrcode
from PIL import Image, ImageDraw, ImageFont
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)

# 4in x 2in landscape at 300 DPI.
LABEL_WIDTH = 1200
LABEL_HEIGHT = 600

_PADDING = 24
_LEFT_PADDING = _PADDING + 20  # a bit of extra breathing room on the left edge
_QR_COL_WIDTH = 380
# The cover image sits in the upper-left corner, sized to use most of the
# remaining space now that only the set name lives in the block below it
# (theme moved under the QR code alongside the set number).
_IMAGE_BOX_WIDTH = 700
_IMAGE_BOX_HEIGHT = 400
_IMAGE_TEXT_GAP = 16
# A solid black border around the whole label, so it doubles as a cut guide
# when printed on sheet label/sticker paper.
_BORDER_WIDTH = 4
# Font sizes (10% larger than the previous revision) for the name / theme /
# set-number text. All label text is bold (simulated via stroke, since
# Pillow's built-in default font has no bold variant of its own).
_NAME_FONT_SIZE = 53
_THEME_FONT_SIZE = 33
_SET_NUMBER_FONT_SIZE = 35
_BOLD_STROKE_WIDTH = 1


def _safe_set_number(set_data: dict[str, Any]) -> str:
    return secure_filename(str(set_data.get("setNumber") or "unknown"))


def label_relpath(set_data: dict[str, Any]) -> str:
    """Path (relative to SETS_DIR) where this set's label image lives.
    Keyed by setID (not just set number) so multiple DB rows that share an
    asset folder — e.g. numbered variants of the same set — each get their
    own label."""
    return os.path.join(_safe_set_number(set_data), f"label_{set_data['setID']}.png")


def get_label_abs_path(set_data: dict[str, Any], sets_dir: str) -> str:
    return os.path.join(sets_dir, label_relpath(set_data))


def label_exists(set_data: dict[str, Any], sets_dir: str) -> bool:
    return os.path.isfile(get_label_abs_path(set_data, sets_dir))


def _set_url(base_url: str, set_id: int) -> str:
    # Deliberately built as a plain string rather than via Flask's url_for,
    # so label generation doesn't need a request/app context and can run
    # from any code path that has a set's data and the configured base URL.
    return f"{base_url}/set/{set_id}"


def _fit_cover_image(
    sets_dir: str, set_data: dict[str, Any], box_w: int, box_h: int
) -> Image.Image:
    """Load and scale the set's first cover image to fit within box_w x
    box_h, preserving aspect ratio and letterboxed on white. Falls back to a
    plain bordered placeholder if there's no image or it can't be read."""
    canvas = Image.new("RGB", (box_w, box_h), "white")
    images = set_data.get("local_images") or []
    if images:
        img_path = os.path.join(sets_dir, images[0])
        try:
            with Image.open(img_path) as img:
                img = img.convert("RGB")
                img.thumbnail((box_w, box_h), Image.LANCZOS)
                canvas.paste(img, ((box_w - img.width) // 2, (box_h - img.height) // 2))
                return canvas
        except (OSError, ValueError):
            logger.warning("Could not open cover image %s for label", img_path)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([4, 4, box_w - 4, box_h - 4], outline="#adb5bd", width=3)
    return canvas


def _make_qr(url: str, box_size: int) -> Image.Image:
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return img.resize((box_size, box_size), Image.NEAREST)


def _text_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # pragma: no cover - Pillow < 10.1 fallback
        return ImageFont.load_default()


def _text_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    stroke_width: int,
) -> float:
    """Width of `text`, approximating the extra width added by a stroke
    (simulated bold) — draw.textlength() itself doesn't accept stroke_width
    in this Pillow version, so it's added on afterward (stroke extends
    ~stroke_width px on each side)."""
    return draw.textlength(text, font=font) + stroke_width * 2


def _draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    x: int,
    y: int,
    max_width: int,
    max_lines: int,
    fill: str = "black",
    line_spacing: int = 6,
    bold: bool = True,
) -> int:
    """Greedy word-wrap `text` into at most `max_lines` lines within
    max_width, ellipsizing the last line if content overflows. Returns the y
    position just below the drawn text, for stacking subsequent fields."""
    stroke_width = _BOLD_STROKE_WIDTH if bold else 0
    words = text.split()
    lines: list[str] = []
    current = ""
    idx = 0
    while idx < len(words) and len(lines) < max_lines:
        candidate = f"{current} {words[idx]}".strip()
        if not current or (
            _text_width(draw, candidate, font, stroke_width) <= max_width
        ):
            current = candidate
            idx += 1
        else:
            lines.append(current)
            current = ""
    if current and len(lines) < max_lines:
        lines.append(current)
        current = ""

    truncated = idx < len(words) or bool(current)
    if truncated and lines:
        last = lines[-1]
        while (
            len(last) > 1
            and _text_width(draw, last + "\u2026", font, stroke_width) > max_width
        ):
            last = last[:-1].rstrip()
        lines[-1] = last + "\u2026"

    for line in lines:
        draw.text(
            (x, y),
            line,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=fill,
        )
        y = (
            int(draw.textbbox((x, y), line, font=font, stroke_width=stroke_width)[3])
            + line_spacing
        )
    return y


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    center_x: int,
    y: int,
    fill: str = "black",
    bold: bool = True,
) -> None:
    """Draw a single line of text horizontally centered on `center_x`."""
    stroke_width = _BOLD_STROKE_WIDTH if bold else 0
    width = _text_width(draw, text, font, stroke_width)
    draw.text(
        (center_x - width / 2, y),
        text,
        font=font,
        fill=fill,
        stroke_width=stroke_width,
        stroke_fill=fill,
    )


def generate_label(
    set_data: dict[str, Any], sets_dir: str, base_url: Optional[str]
) -> Optional[str]:
    """Compose and save this set's storage-box label as a PNG under
    SETS_DIR. Returns the path (relative to SETS_DIR) of the saved label, or
    None if `base_url` isn't configured — a QR code has to encode an
    absolute URL to be worth anything once printed, so label generation is
    skipped entirely rather than producing a broken/local-only code."""
    if not base_url:
        return None
    set_id = set_data.get("setID")
    if set_id is None:
        return None

    canvas = Image.new("RGB", (LABEL_WIDTH, LABEL_HEIGHT), "white")
    draw = ImageDraw.Draw(canvas)

    # Upper-left: cover image (or placeholder box), sized smaller than the
    # full label height so the text block below has more room to breathe.
    cover = _fit_cover_image(sets_dir, set_data, _IMAGE_BOX_WIDTH, _IMAGE_BOX_HEIGHT)
    canvas.paste(cover, (_LEFT_PADDING, _PADDING))

    # Right column: QR code linking to the set's page, sized to fit within
    # both the column width and the label height (minus padding on each
    # side), then centered in that column.
    qr_box = min(LABEL_HEIGHT, _QR_COL_WIDTH) - _PADDING * 2
    qr_img = _make_qr(_set_url(base_url, set_id), qr_box)
    qr_x = LABEL_WIDTH - _QR_COL_WIDTH + (_QR_COL_WIDTH - qr_box) // 2
    qr_y = (LABEL_HEIGHT - qr_box) // 2
    canvas.paste(qr_img, (qr_x, qr_y))

    # Below the QR code: theme, then set number — both centered under it.
    qr_center_x = qr_x + qr_box // 2
    below_qr_y = qr_y + qr_box + 12
    if set_data.get("theme"):
        _draw_centered_text(
            draw,
            set_data["theme"],
            _text_font(_THEME_FONT_SIZE),
            center_x=qr_center_x,
            y=below_qr_y,
            fill="#495057",
        )
        below_qr_y += int(_THEME_FONT_SIZE * 1.3)
    if set_data.get("setNumber"):
        _draw_centered_text(
            draw,
            f"Set #{set_data['setNumber']}",
            _text_font(_SET_NUMBER_FONT_SIZE),
            center_x=qr_center_x,
            y=below_qr_y,
            fill="#495057",
        )

    # Bottom-left: set name, filling the full width from the left edge to
    # the QR column, below the (now much larger) cover image.
    text_x = _LEFT_PADDING
    text_max_w = LABEL_WIDTH - _QR_COL_WIDTH - text_x - _PADDING
    y = _PADDING + _IMAGE_BOX_HEIGHT + _IMAGE_TEXT_GAP
    _draw_wrapped_text(
        draw,
        set_data.get("name") or "Untitled set",
        _text_font(_NAME_FONT_SIZE),
        text_x,
        y,
        text_max_w,
        max_lines=2,
        line_spacing=8,
    )

    # Solid black border around the whole label, doubling as a cut guide
    # when printed on sheet sticker paper. Inset by half the border width so
    # the stroke is fully visible (not clipped by the canvas edge).
    inset = _BORDER_WIDTH // 2
    draw.rectangle(
        [inset, inset, LABEL_WIDTH - 1 - inset, LABEL_HEIGHT - 1 - inset],
        outline="black",
        width=_BORDER_WIDTH,
    )

    rel_path = label_relpath(set_data)
    abs_path = os.path.join(sets_dir, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    canvas.save(abs_path, format="PNG")
    logger.info("Generated storage-box label for set %s at %s", set_id, rel_path)
    return rel_path
