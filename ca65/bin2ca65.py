#!/usr/bin/env python3
"""
bin2ca65.py -- バイナリファイルを ca65 の .byte テーブルに変換する

用途:
    パレットやフォントなどのバイナリを、ca65 アセンブラに取り込めるソース
    (.segment 指定 + ラベル + .byte 行) に変換します。
入出力:
    入力: バイナリファイル 1 つ
    出力: 標準出力にテキストを書き出します (保存はリダイレクトで行います)
使用例:
    python3 bin2ca65.py data.bin
    python3 bin2ca65.py palette.pal --label PALETTE
    python3 bin2ca65.py font.chr --segment CHARS --cols 8 > font.inc
依存: 標準ライブラリのみ
"""

import argparse
import os
import sys
from pathlib import Path


def bin_to_ca65(data: bytes, segment: str, label: str, cols: int = 16) -> str:
    """バイナリデータを ca65 形式の .byte ソースコード文字列に変換する"""
    lines = []
    lines.append(f'.segment "{segment}"')
    lines.append(f"{label}:")

    total = len(data)
    for i in range(0, total, cols):
        if i % 256 == 0:
            end = min(i + 255, total - 1)
            lines.append(f"    ; offset {i:#06x}-{end:#06x}")
        chunk = data[i:i + cols]
        bytes_str = ", ".join(f"${b:02X}" for b in chunk)
        lines.append(f"    .byte {bytes_str}")

    return "\n".join(lines)


def positive_int(text: str) -> int:
    """argparse 用: 1 以上の整数"""
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("1 以上の整数を指定してください")
    return value


def main():
    parser = argparse.ArgumentParser(
        prog=Path(__file__).name,
        description="バイナリファイルを ca65 アセンブラ用の .byte テーブル形式テキストに変換します。"
                    "結果は標準出力に出ます。",
        epilog="""例:
  python3 bin2ca65.py data.bin                        ← 既定値 (RODATA, binary_data)
  python3 bin2ca65.py palette.pal --label PALETTE     ← ラベル指定
  python3 bin2ca65.py font.chr --segment CHARS        ← セグメント指定
  python3 bin2ca65.py font.chr --cols 8 > font.inc    ← 1 行 8 バイトでファイルへ保存""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", type=Path, help="入力バイナリファイル")
    parser.add_argument("--segment", default="RODATA", metavar="NAME", help="セグメント名 (既定: RODATA)")
    parser.add_argument("--label", default="binary_data", metavar="NAME", help="ラベル名 (既定: binary_data)")
    parser.add_argument("--cols", type=positive_int, default=16, metavar="N", help="1 行あたりの出力バイト数 (既定: 16)")

    args = parser.parse_args()

    if not args.file.is_file():
        print(f"エラー: ファイル '{args.file}' が見つかりません。", file=sys.stderr)
        sys.exit(1)

    try:
        data = args.file.read_bytes()
    except Exception as e:
        print(f"エラー: ファイルの読み込みに失敗しました ({e})", file=sys.stderr)
        sys.exit(1)

    result = bin_to_ca65(data, args.segment, args.label, args.cols)
    print(result)


def run():
    try:
        main()
        sys.stdout.flush()
    except BrokenPipeError:
        # 出力先 (head など) が先に閉じた場合は、エラーを出さずに終了する
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(1)


if __name__ == "__main__":
    run()
