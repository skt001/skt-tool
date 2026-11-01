#!/usr/bin/env python3
# /// script
# dependencies = [
#     "pillow",
# ]
# ///
"""
font2png.py -- Generate an 8x8-tile PNG (and optional text file) from a font

Usage:
    Arrange font glyphs as 8x8 pixel tiles in 16 columns and save them as a
    1-bit PNG. Includes a built-in 256-character NES-oriented subset (--subset).
Input/output:
    Input: font file (.ttf / .otf)
    Output: <font_name>.png (the PNG is authoritative; glyphs are ordered
            left-to-right in 16 columns)
            Add --txt or --safetxt to also write a matching <font_name>.txt.
            Set the output directory with -o (defaults to the current directory).
            Existing files with the same names are overwritten.
Examples:
    python3 font2png.py font.ttf --subset
    python3 font2png.py font.ttf --ascii --safetxt
    python3 font2png.py font.ttf --sjis -o out/
Dependencies: Pillow (automatically installed with `uv run font2png.py`;
otherwise install with `pip install pillow`)
"""

import os
import sys
import math
import argparse
import unicodedata
from typing import Dict, List, Callable, Optional

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("Error: Pillow is required. Install it with `pip install pillow` or run with `uv run font2png.py ...`.")

# ============================================================
# Built-in subset: 256 characters for a 16x16 NES layout with Shift_JIS single-byte positions.
# ============================================================

SUBSET = (
    # 0x00 - 0x0F (selected symbols 1/2)
    " ─│┌┐└┘├┤┬┴┼×÷⊂⊃"
    # 0x10 - 0x1F (selected symbols 2/2)
    "■□▲△▼▽◆◇○◎●◯★☆♀♂"
    # 0x20 - 0x2F (ASCII symbols and digits)
    " ！＂＃＄％＆＇（）＊＋，－．／"
    # 0x30 - 0x3F (ASCII digits and symbols)
    "０１２３４５６７８９：；＜＝＞？"
    # 0x40 - 0x4F (ASCII uppercase letters)
    "＠ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯ"
    # 0x50 - 0x5F (ASCII uppercase letters and symbols)
    "ＰＱＲＳＴＵＶＷＸＹＺ［￥］＾＿"
    # 0x60 - 0x6F (ASCII lowercase letters)
    "｀ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏ"
    # 0x70 - 0x7F (ASCII lowercase letters and symbols)
    "ｐｑｒｓｔｕｖｗｘｙｚ｛｜｝￣～"
    # 0x80 - 0x8F (Greek letters 1/2)
    "αβγδεζηθικλμνξοπ"
    # 0x90 - 0x9F (Greek letters 2/2, iteration marks, and brackets)
    "ρστυφχψω『』【】〃々㈱㈲"
    # 0xA0 - 0xAF (JIS X 0201 positions: symbols and small kana)
    " 。「」、・をぁぃぅぇぉゃゅょっ"
    # 0xB0 - 0xBF (JIS X 0201 positions: long vowel mark through "so")
    "ーあいうえおかきくけこさしすせそ"
    # 0xC0 - 0xCF (JIS X 0201 positions: "ta" through "ho")
    "たちつてとなにぬねのはひふへほま"
    # 0xD0 - 0xDF (JIS X 0201 positions: "mi" through "n", dakuten marks)
    "みむめもやゆよらりるれろわん゛゜"
    # 0xE0 - 0xEF (general-purpose kanji for NES 1)
    "勇戦魔僧商遊盗賢剣鎧盾兜薬毒指輪"
    # 0xF0 - 0xFF (general-purpose kanji for NES 2)
    "火水風土光無闇炎氷雷力守速命体金"
)

# ============================================================
# Constants
# ============================================================

TILE_W = 8
TILE_H = 8
COLUMNS = 16

CONTROL_MIN = 0x00
CONTROL_MAX = 0x1F
DEL_CODE = 0x7F
MISSING_GLYPH_CHAR = "\u25A1"


# ============================================================
# Glyph detection
# ============================================================

def has_glyph(font: ImageFont.FreeTypeFont, ch: str, cache: Dict[str, bool]) -> bool:
    if ch in cache:
        return cache[ch]
    try:
        mask = font.getmask(ch)
        result = mask.getbbox() is not None
    except (AttributeError, ValueError, OSError, RuntimeError):
        # Treat layout failures for individual glyphs as missing glyphs and continue.
        result = False
    cache[ch] = result
    return result


def is_cp932(ch: str) -> bool:
    try:
        ch.encode("cp932")
        return True
    except UnicodeEncodeError:
        return False


def is_halfwidth(ch: str) -> bool:
    return unicodedata.east_asian_width(ch) in ("Na", "H")


def is_fullwidth(ch: str) -> bool:
    return unicodedata.east_asian_width(ch) in ("F", "W")


# ============================================================
# Tile rendering
# ============================================================

def draw_char_tile(font: ImageFont.FreeTypeFont, ch: str) -> Image.Image:
    tile = Image.new("L", (TILE_W, TILE_H), 0)
    draw = ImageDraw.Draw(tile)

    try:
        bbox = font.getbbox(ch)
        if bbox:
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            x = (TILE_W - w) // 2 - bbox[0]
            y = (TILE_H - h) // 2 - bbox[1]
            draw.text((x, y), ch, fill=255, font=font)
    except (AttributeError, ValueError, OSError, RuntimeError):
        # Leave this tile blank if rendering fails, then continue with the remaining glyphs.
        pass

    return tile


# ============================================================
# Text conversion
# ============================================================

def convert_safetxt(ch: str, font: ImageFont.FreeTypeFont, glyph_cache: Dict[str, bool]) -> str:
    code = ord(ch)

    if CONTROL_MIN <= code <= CONTROL_MAX:
        return chr(0x2400 + code)

    if code == DEL_CODE:
        return chr(0x2421)

    if not has_glyph(font, ch, glyph_cache):
        return MISSING_GLYPH_CHAR

    return ch


def build_text(chars: List[str], columns: int, transform: Optional[Callable[[str], str]] = None) -> str:
    lines = []
    current = []

    for i, ch in enumerate(chars):
        if transform:
            ch = transform(ch)

        current.append(ch)

        if (i + 1) % columns == 0:
            lines.append("".join(current))
            current = []

    if current:
        lines.append("".join(current))

    return "\n".join(lines)


# ============================================================
# Main processing
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        prog=os.path.basename(__file__),
        description="Generate an 8x8-tile PNG from a font. The PNG defines the glyph order; "
                    "any optional text output matches it one-to-one.\n"
                    "Choose at most one character set option (--ascii, etc.). "
                    "Defaults to --glyphs.",
        epilog="""Examples:
  python3 font2png.py font.ttf --subset            # Built-in 256-character NES subset
  python3 font2png.py font.ttf --ascii --safetxt   # ASCII and a display-safe text file
  python3 font2png.py font.ttf --sjis -o out/      # Shift_JIS characters to out/""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    txt_group = parser.add_mutually_exclusive_group()
    txt_group.add_argument(
        "--txt", action="store_true",
        help="Write a text file in the same order as the PNG (no substitutions; control characters are preserved)"
    )
    txt_group.add_argument(
        "--safetxt", action="store_true",
        help="Write a display-safe text file in the same order as the PNG "
             "(control characters become control pictures; missing glyphs become □ (U+25A1))"
    )

    parser.add_argument("fontfile", help="Input font file (.ttf / .otf)")
    parser.add_argument(
        "-o", "--output-dir", default=".", metavar="DIR",
        help="Output directory (default: current directory; created if missing)"
    )

    charset = parser.add_mutually_exclusive_group()
    charset.add_argument("--ascii", action="store_true", help="Characters U+0000-U+007F")
    charset.add_argument("--sjis", action="store_true", help="Characters representable in CP932 (Shift_JIS)")
    charset.add_argument("--glyphs", action="store_true", help="All characters with glyphs in the font (default)")
    charset.add_argument("--fullwidth", action="store_true", help="Full-width characters (East Asian Width F/W)")
    charset.add_argument("--halfwidth", action="store_true", help="Half-width characters (East Asian Width Na/H)")
    charset.add_argument("--all", action="store_true", help="All BMP characters (U+0000-U+FFFF)")
    charset.add_argument("--subset", action="store_true", help="Built-in 256-character NES subset")

    return parser.parse_args()


def select_chars(args, font: ImageFont.FreeTypeFont, glyph_cache: Dict[str, bool]) -> List[str]:
    # UTF-16 surrogate code points are not Unicode scalar values and cannot be
    # encoded in UTF-8. Exclude them from every generated character sequence.
    def chars_in_range(start: int, stop: int) -> List[str]:
        return [chr(i) for i in range(start, stop) if not 0xD800 <= i <= 0xDFFF]

    if args.subset:
        return list(SUBSET)
    if args.ascii:
        return chars_in_range(0, 0x80)
    if args.sjis:
        return [ch for ch in chars_in_range(0, 0x10000) if is_cp932(ch)]
    if args.fullwidth:
        return [ch for ch in chars_in_range(0, 0x10000) if is_fullwidth(ch)]
    if args.halfwidth:
        return [ch for ch in chars_in_range(0, 0x10000) if is_halfwidth(ch)]
    if args.all:
        return chars_in_range(0, 0x10000)
    return [ch for ch in chars_in_range(0, 0x10000) if has_glyph(font, ch, glyph_cache)]


def main():
    args = parse_args()

    font_path = args.fontfile
    font_name = os.path.splitext(os.path.basename(font_path))[0]

    try:
        # Single glyphs rendered into 8x8 tiles need no complex text layout.
        # Select BASIC explicitly to avoid RAQM layout failures.
        font = ImageFont.truetype(font_path, 8, layout_engine=ImageFont.Layout.BASIC)
    except Exception as e:
        print(f"Error: Could not load font file '{font_path}' ({e}).", file=sys.stderr)
        sys.exit(1)

    glyph_cache: Dict[str, bool] = {}
    chars = select_chars(args, font, glyph_cache)

    total = len(chars)
    rows = math.ceil(total / COLUMNS) if total > 0 else 1

    canvas = Image.new("L", (COLUMNS * TILE_W, rows * TILE_H), 0)

    for index, ch in enumerate(chars):
        col = index % COLUMNS
        row = index // COLUMNS
        x = col * TILE_W
        y = row * TILE_H
        tile = draw_char_tile(font, ch)
        canvas.paste(tile, (x, y))

    canvas = canvas.point(lambda p: 255 if p > 128 else 0, mode="1")

    os.makedirs(args.output_dir, exist_ok=True)
    png_name = os.path.join(args.output_dir, f"{font_name}.png")
    canvas.save(png_name)

    if args.txt or args.safetxt:
        if args.txt:
            text_data = build_text(chars, COLUMNS)
        else:
            text_data = build_text(
                chars,
                COLUMNS,
                transform=lambda ch: convert_safetxt(ch, font, glyph_cache)
            )

        txt_name = os.path.join(args.output_dir, f"{font_name}.txt")
        with open(txt_name, "w", encoding="utf-8", newline="") as f:
            f.write(text_data)

        print(f"Generated: {png_name}, {txt_name}")
    else:
        print(f"Generated: {png_name}")

    print(f"Character count: {total}")


if __name__ == "__main__":
    main()
