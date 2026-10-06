#!/usr/bin/env python3
"""
ca65_rnd_table.py -- ca65 向け 乱数参照テーブル (.byte) 生成ツール

用途:
    0x00〜0xFF の全値がちょうど 1 回ずつ現れる 256 バイトの並べ替え表を作り、
    ca65 の .byte 行として出力します。ゲームの乱数参照テーブルなどに使います。
入出力:
    入力: 生成バイト数 (引数)、シード (任意)
    出力: 標準出力に ca65 ソーステキストを書き出します
使用例:
    python3 ca65_rnd_table.py 256
    python3 ca65_rnd_table.py 256 --seed 0x12345678
    python3 ca65_rnd_table.py 512 --label RND_TABLE
依存: Python 3.9 以上 (標準ライブラリのみ)
"""

import argparse
import os
import secrets
import sys
from pathlib import Path


def xorshift32(state: int) -> int:
    """32-bit Xorshift による擬似乱数生成"""
    state ^= (state << 13) & 0xFFFFFFFF
    state ^= (state >> 17) & 0xFFFFFFFF
    state ^= (state << 5) & 0xFFFFFFFF
    return state & 0xFFFFFFFF


def shuffled_0_255(state: int) -> tuple[list[int], int]:
    """
    0〜255 の数値を重複なしで並べ替えた 256 バイトの配列を生成。
    アルゴリズム: Fisher-Yates シャッフル
    """
    arr = list(range(256))
    for i in range(255, 0, -1):
        state = xorshift32(state)
        j = state % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
    return arr, state


def positive_int(text: str) -> int:
    """argparse 用: 1 以上の整数"""
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("1 以上の整数を指定してください")
    return value


def seed_value(text: str) -> int:
    """argparse 用: 1〜0xFFFFFFFF のシード (0 は Xorshift32 が変化しないため不可)"""
    value = int(text, 0)
    if not 1 <= value <= 0xFFFFFFFF:
        raise argparse.ArgumentTypeError(
            "1〜0xFFFFFFFF の範囲で指定してください (0 は Xorshift32 が変化せず乱数にならないため不可)"
        )
    return value


def main():
    parser = argparse.ArgumentParser(
        prog=Path(__file__).name,
        description="ca65 アセンブラ向け 乱数参照テーブル (.byte) 出力ツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
【動作・アルゴリズムの説明】
  1. 32-bit Xorshift32
     高速で周期の長い擬似乱数生成器です。シードを省略した場合は、
     Python の secrets モジュールで 1〜0xFFFFFFFF のシードを自動生成します。

  2. Fisher-Yates (Knuth) シャッフル
     0 から 255 までの値を隙間なく詰めた配列を用意し、末尾から順に乱数位置と
     入れ替えることで「0〜255 の全値がちょうど 1 回ずつ現れる配列」を作ります。
     乱数は「状態 % (i+1)」で範囲に丸めるため、わずかな偏りがあります。
     また 32bit シードで作れる並びは、全 256! 通りのごく一部です。
     (暗号用途には使えません)

  3. ブロック出力
     指定バイト数 (num_bytes) に達するまで、256 バイト単位で新しい並べ替えを作って
     出力します。端数は最後のブロックの先頭から必要な分だけ使います。
     ブロックをまたぐと同じ値が再び現れます。

【使用例】
  python3 ca65_rnd_table.py 256                      # 256 バイトの乱数テーブル
  python3 ca65_rnd_table.py 256 --seed 0x12345678    # シード指定で同じ結果を再現
  python3 ca65_rnd_table.py 512 --label RND_TABLE    # ラベル名・サイズを指定
"""
    )
    parser.add_argument(
        "num_bytes", nargs="?", type=positive_int, default=256,
        help="生成する総バイト数 (既定: 256)"
    )
    parser.add_argument(
        "--seed", type=seed_value, default=None, metavar="HEX/INT",
        help="Xorshift32 用シード。1〜0xFFFFFFFF (例: 0x12345678)。省略時はランダム"
    )
    parser.add_argument(
        "--segment", default="RODATA", metavar="NAME",
        help="出力するセグメント名 (既定: RODATA)"
    )
    parser.add_argument(
        "--label", default=None, metavar="NAME",
        help="出力ラベル名 (既定: RND_<バイト数>)"
    )
    parser.add_argument(
        "--cols", type=positive_int, default=16, metavar="N",
        help="1 行あたりに出力する要素数 (既定: 16)"
    )

    args = parser.parse_args()

    n = args.num_bytes
    state = args.seed if args.seed is not None else secrets.randbelow(0xFFFFFFFF) + 1
    label = args.label or f"RND_{n}"

    print(f'.segment "{args.segment}"')
    print(f"{label}:  ; {n} bytes, seed=0x{state:08X}")

    line = []
    remaining = n
    offset = 0

    while remaining > 0:
        table, state = shuffled_0_255(state)
        take = min(256, remaining)
        end = offset + take - 1
        print(f"    ; block {offset:#06x}-{end:#06x}")

        for b in table[:take]:
            line.append(f"${b:02X}")
            if len(line) == args.cols:
                print("    .byte " + ", ".join(line))
                line = []
        if line:
            print("    .byte " + ", ".join(line))
            line = []

        offset += take
        remaining -= take


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
