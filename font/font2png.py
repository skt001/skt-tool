#!/usr/bin/env python3
# /// script
# dependencies = [
#     "pillow",
# ]
# ///
"""
font2png.py -- フォントファイルから 8x8 タイルの PNG (と対応する txt) を生成する

用途:
    フォントの文字を 8x8 ピクセルのタイルとして 16 列に並べ、2 値の PNG にします。
    ファミコン用のフォント画像を作る用途を想定し、NES 向けの 256 文字サブセット
    (--subset) を内蔵しています。
入出力:
    入力: フォントファイル (.ttf / .otf)
    出力: <フォント名>.png (PNG が正で、文字は左上から右へ 16 列ずつ並ぶ)
          --txt / --safetxt を付けると、PNG と 1 対 1 に対応する <フォント名>.txt も出力
          出力先は -o で指定 (省略時はカレントディレクトリ)。同名のファイルは上書きされます。
使用例:
    python3 font2png.py font.ttf --subset
    python3 font2png.py font.ttf --ascii --safetxt
    python3 font2png.py font.ttf --sjis -o out/
依存: Pillow (uv run font2png.py なら自動導入。それ以外は pip install pillow)
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
    sys.exit("エラー: Pillow が必要です。`pip install pillow` するか、`uv run font2png.py ...` で実行してください。")

# ============================================================
# サブセット定義（NES 16x16 / Shift_JIS 1バイト位置対応 256文字）
# ============================================================

SUBSET = (
    # 0x00 - 0x0F (厳選記号 1/2)
    " ─│┌┐└┘├┤┬┴┼×÷⊂⊃"
    # 0x10 - 0x1F (厳選記号 2/2)
    "■□▲△▼▽◆◇○◎●◯★☆♀♂"
    # 0x20 - 0x2F (ASCII 記号・数字)
    " ！＂＃＄％＆＇（）＊＋，－．／"
    # 0x30 - 0x3F (ASCII 数字・記号)
    "０１２３４５６７８９：；＜＝＞？"
    # 0x40 - 0x4F (ASCII 英大文字)
    "＠ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯ"
    # 0x50 - 0x5F (ASCII 英大文字・記号)
    "ＰＱＲＳＴＵＶＷＸＹＺ［￥］＾＿"
    # 0x60 - 0x6F (ASCII 英小文字)
    "｀ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏ"
    # 0x70 - 0x7F (ASCII 英小文字・記号)
    "ｐｑｒｓｔｕｖｗｘｙｚ｛｜｝￣～"
    # 0x80 - 0x8F (ギリシャ文字 1/2)
    "αβγδεζηθικλμνξοπ"
    # 0x90 - 0x9F (ギリシャ文字 2/2・踊り字・括弧)
    "ρστυφχψω『』【】〃々㈱㈲"
    # 0xA0 - 0xAF (JIS X 0201位置: 記号・小文字)
    " 。「」、・をぁぃぅぇぉゃゅょっ"
    # 0xB0 - 0xBF (JIS X 0201位置: ーあ〜そ)
    "ーあいうえおかきくけこさしすせそ"
    # 0xC0 - 0xCF (JIS X 0201位置: たち〜ほ)
    "たちつてとなにぬねのはひふへほま"
    # 0xD0 - 0xDF (JIS X 0201位置: み〜ん・濁点)
    "みむめもやゆよらりるれろわん゛゜"
    # 0xE0 - 0xEF (NES用 汎用漢字 1)
    "勇戦魔僧商遊盗賢剣鎧盾兜薬毒指輪"
    # 0xF0 - 0xFF (NES用 汎用漢字 2)
    "火水風土光無闇炎氷雷力守速命体金"
)

# ============================================================
# 定数定義
# ============================================================

TILE_W = 8
TILE_H = 8
COLUMNS = 16

CONTROL_MIN = 0x00
CONTROL_MAX = 0x1F
DEL_CODE = 0x7F
MISSING_GLYPH_CHAR = "\u25A1"


# ============================================================
# 文字判定
# ============================================================

def has_glyph(font: ImageFont.FreeTypeFont, ch: str, cache: Dict[str, bool]) -> bool:
    if ch in cache:
        return cache[ch]
    try:
        mask = font.getmask(ch)
        result = mask.getbbox() is not None
    except (AttributeError, ValueError, OSError):
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
# タイル描画
# ============================================================

def draw_char_tile(font: ImageFont.FreeTypeFont, ch: str) -> Image.Image:
    tile = Image.new("L", (TILE_W, TILE_H), 0)
    draw = ImageDraw.Draw(tile)

    bbox = font.getbbox(ch)
    if bbox:
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (TILE_W - w) // 2 - bbox[0]
        y = (TILE_H - h) // 2 - bbox[1]
        draw.text((x, y), ch, fill=255, font=font)

    return tile


# ============================================================
# テキスト変換
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
# メイン処理
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        prog=os.path.basename(__file__),
        description="フォントファイルから 8x8 タイルの PNG を生成します。"
                    "PNG の並びが基準で、txt を出力する場合も PNG と 1 対 1 に対応します。\n"
                    "文字集合のオプション (--ascii など) はどれか 1 つだけ指定できます。"
                    "省略した場合は --glyphs と同じです。",
        epilog="""例:
  python3 font2png.py font.ttf --subset            ← NES 向け 256 文字サブセット
  python3 font2png.py font.ttf --ascii --safetxt   ← ASCII と、表示できる txt も出力
  python3 font2png.py font.ttf --sjis -o out/      ← Shift_JIS 文字を out/ に出力""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    txt_group = parser.add_mutually_exclusive_group()
    txt_group.add_argument(
        "--txt", action="store_true",
        help="PNG と同じ並びの txt を出力します (置換なし。制御文字もそのまま出力)"
    )
    txt_group.add_argument(
        "--safetxt", action="store_true",
        help="PNG と同じ並びの、表示しても安全な txt を出力します "
             "(制御文字は制御文字記号に、グリフの無い文字は □ (U+25A1) に置換)"
    )

    parser.add_argument("fontfile", help="入力フォントファイル (.ttf / .otf)")
    parser.add_argument(
        "-o", "--output-dir", default=".", metavar="DIR",
        help="出力先ディレクトリ (既定: カレントディレクトリ。無ければ作成)"
    )

    charset = parser.add_mutually_exclusive_group()
    charset.add_argument("--ascii", action="store_true", help="U+0000〜U+007F の文字")
    charset.add_argument("--sjis", action="store_true", help="CP932 (Shift_JIS) で表せる文字")
    charset.add_argument("--glyphs", action="store_true", help="フォントがグリフを持つ全文字 (既定)")
    charset.add_argument("--fullwidth", action="store_true", help="East Asian Width が全角 (F/W) の文字のみ")
    charset.add_argument("--halfwidth", action="store_true", help="East Asian Width が半角 (Na/H) の文字のみ")
    charset.add_argument("--all", action="store_true", help="BMP の全文字 (U+0000〜U+FFFF)")
    charset.add_argument("--subset", action="store_true", help="内蔵の NES 向け 256 文字サブセット")

    return parser.parse_args()


def select_chars(args, font: ImageFont.FreeTypeFont, glyph_cache: Dict[str, bool]) -> List[str]:
    if args.subset:
        return list(SUBSET)
    if args.ascii:
        return [chr(i) for i in range(0x80)]
    if args.sjis:
        return [chr(i) for i in range(0x10000) if is_cp932(chr(i))]
    if args.fullwidth:
        return [chr(i) for i in range(0x10000) if is_fullwidth(chr(i))]
    if args.halfwidth:
        return [chr(i) for i in range(0x10000) if is_halfwidth(chr(i))]
    if args.all:
        return [chr(i) for i in range(0x10000)]
    return [chr(i) for i in range(0x10000) if has_glyph(font, chr(i), glyph_cache)]


def main():
    args = parse_args()

    font_path = args.fontfile
    font_name = os.path.splitext(os.path.basename(font_path))[0]

    try:
        font = ImageFont.truetype(font_path, 8)
    except Exception as e:
        print(f"エラー: フォントファイル '{font_path}' を読み込めません ({e})", file=sys.stderr)
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

        print(f"生成: {png_name}, {txt_name}")
    else:
        print(f"生成: {png_name}")

    print(f"文字数: {total}")


if __name__ == "__main__":
    main()
