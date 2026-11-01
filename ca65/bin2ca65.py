#!/usr/bin/env python3
"""
bin2ca65.py -- Convert a binary file to a ca65 .byte table

Usage:
    Convert binary data such as palettes or fonts into ca65 source code
    (.segment directive, label, and .byte lines).
Input/output:
    Input: one binary file
    Output: text to stdout (redirect it to save to a file)
Examples:
    python3 bin2ca65.py data.bin
    python3 bin2ca65.py palette.pal --label PALETTE
    python3 bin2ca65.py font.chr --segment CHARS --cols 8 > font.inc
Dependencies: Python standard library only
"""

import argparse
import os
import sys
from pathlib import Path


def bin_to_ca65(data: bytes, segment: str, label: str, cols: int = 16) -> str:
    """Convert binary data to a ca65 .byte source string."""
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
    """argparse type: positive integer."""
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("Value must be a positive integer.")
    return value


def main():
    parser = argparse.ArgumentParser(
        prog=Path(__file__).name,
        description="Convert a binary file to ca65 .byte table source on stdout.",
        epilog="""Examples:
  python3 bin2ca65.py data.bin                        # Defaults (RODATA, binary_data)
  python3 bin2ca65.py palette.pal --label PALETTE     # Set the label
  python3 bin2ca65.py font.chr --segment CHARS        # Set the segment
  python3 bin2ca65.py font.chr --cols 8 > font.inc    # Save 8 bytes per line to a file""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", type=Path, help="Input binary file")
    parser.add_argument("--segment", default="RODATA", metavar="NAME", help="Segment name (default: RODATA)")
    parser.add_argument("--label", default="binary_data", metavar="NAME", help="Label name (default: binary_data)")
    parser.add_argument("--cols", type=positive_int, default=16, metavar="N", help="Bytes per output line (default: 16)")

    args = parser.parse_args()

    if not args.file.is_file():
        print(f"Error: File not found: '{args.file}'.", file=sys.stderr)
        sys.exit(1)

    try:
        data = args.file.read_bytes()
    except Exception as e:
        print(f"Error: Could not read file ({e}).", file=sys.stderr)
        sys.exit(1)

    result = bin_to_ca65(data, args.segment, args.label, args.cols)
    print(result)


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
