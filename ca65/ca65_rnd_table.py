#!/usr/bin/env python3
"""
ca65_rnd_table.py -- Generate ca65 random lookup tables (.byte)

Usage:
    Create a 256-byte permutation containing every value from 0x00 to 0xFF exactly once
    and print it as ca65 .byte lines. Useful for game random lookup tables.
Input/output:
    Input: output size (argument) and optional seed
    Output: ca65 source text to stdout
Examples:
    python3 ca65_rnd_table.py 256
    python3 ca65_rnd_table.py 256 --seed 0x12345678
    python3 ca65_rnd_table.py 512 --label RND_TABLE
Dependencies: Python 3.9+ (standard library only)
"""

import argparse
import os
import secrets
import sys
from pathlib import Path


def xorshift32(state: int) -> int:
    """Generate a pseudorandom value using 32-bit Xorshift."""
    state ^= (state << 13) & 0xFFFFFFFF
    state ^= (state >> 17) & 0xFFFFFFFF
    state ^= (state << 5) & 0xFFFFFFFF
    return state & 0xFFFFFFFF


def shuffled_0_255(state: int) -> tuple[list[int], int]:
    """
    Generate a 256-byte permutation of values 0 through 255.
    Algorithm: Fisher-Yates shuffle.
    """
    arr = list(range(256))
    for i in range(255, 0, -1):
        state = xorshift32(state)
        j = state % (i + 1)
        arr[i], arr[j] = arr[j], arr[i]
    return arr, state


def positive_int(text: str) -> int:
    """argparse type: positive integer."""
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("Value must be a positive integer.")
    return value


def seed_value(text: str) -> int:
    """argparse type: seed from 1 to 0xFFFFFFFF (zero is invalid for Xorshift32)."""
    value = int(text, 0)
    if not 1 <= value <= 0xFFFFFFFF:
        raise argparse.ArgumentTypeError(
            "Seed must be between 1 and 0xFFFFFFFF (zero produces no variation with Xorshift32)."
        )
    return value


def main():
    parser = argparse.ArgumentParser(
        prog=Path(__file__).name,
        description="Generate a random lookup table as ca65 .byte source.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Operation and algorithm:
  1. 32-bit Xorshift32
     A fast pseudorandom generator with a long period. If no seed is provided,
     a seed from 1 to 0xFFFFFFFF is generated with Python's secrets module.

  2. Fisher-Yates (Knuth) shuffle
     Start with an array containing every value from 0 to 255, then swap each
     element from the end with a random position. This creates a permutation
     containing each value exactly once. Using state % (i+1) introduces slight
     modulo bias. A 32-bit seed can produce only a tiny fraction of all 256!
     possible permutations. This is not suitable for cryptographic use.

  3. Block output
     Generate and output new 256-byte permutations until the requested
     num_bytes is reached. Use only the required prefix of the final block.
     Values may repeat across blocks.

Examples:
  python3 ca65_rnd_table.py 256                      # 256-byte random table
  python3 ca65_rnd_table.py 256 --seed 0x12345678    # Reproducible output
  python3 ca65_rnd_table.py 512 --label RND_TABLE    # Set label and size
"""
    )
    parser.add_argument(
        "num_bytes", nargs="?", type=positive_int, default=256,
        help="Total number of bytes to generate (default: 256)"
    )
    parser.add_argument(
        "--seed", type=seed_value, default=None, metavar="HEX/INT",
        help="Xorshift32 seed, 1 to 0xFFFFFFFF (e.g. 0x12345678); random if omitted"
    )
    parser.add_argument(
        "--segment", default="RODATA", metavar="NAME",
        help="Output segment name (default: RODATA)"
    )
    parser.add_argument(
        "--label", default=None, metavar="NAME",
        help="Output label (default: RND_<byte_count>)"
    )
    parser.add_argument(
        "--cols", type=positive_int, default=16, metavar="N",
        help="Values per output line (default: 16)"
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
        # Exit quietly if the output consumer (such as `head`) closes the pipe first.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(1)


if __name__ == "__main__":
    run()
