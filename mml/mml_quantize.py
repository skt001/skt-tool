#!/usr/bin/env python3
"""
mml_quantize.py -- MML quantizer and simplifier

Usage:
    Quantize high-resolution MML (rounding note lengths) into a simpler format
    using only {2, 4, 8, 16} note values. Also supports transposition and
    converting C major to a minor scale.
Input/output:
    Input: one MML file (see the format below)
    Output: text such as "O4C8 O4D4 R8" to stdout. Multiple channels are
            separated by blank lines and prefixed with their channel names.
Examples:
    python3 mml_quantize.py song.mml --simple
    python3 mml_quantize.py song.mml --judge
    python3 mml_quantize.py song.mml --transpose -2 --minor natural
Dependencies: Python standard library only

Output modes (choose one; they are mutually exclusive):
  (default) Output simple only if it matches exact for every channel.
            If there is drift, print "LOSSY", do not output MML, and exit with code 1.
  --simple  Rounded quantization; produces compact output that sounds natural.
  --exact   Lossless GCD-based quantization; no rounding (tempo adjustment may be needed).
  --judge   Compare simple and exact per channel and report ok / drift.
            Exit code: 0 = all channels match, 1 = drift detected.

Other options:
  --fill         Append rests to shorter channels to match the longest channel.
                 Applied only to the selected mode (--exact if selected, otherwise simple).
                 With --judge, only simple is padded, so shorter channels are
                 reported as drift.
  --transpose N  Shift all pitches by N semitones (negative = down, positive = up).
  --minor MODE   Convert a C major song to minor (natural / harmonic / melodic).
                 Applied after --transpose.

Input MML format:
  - A line starting at column 1 with one letter followed by a space is treated
    as a channel line; lines with the same letter are concatenated
    (e.g. "A O4 CDE"). Lines beginning with a single note name (e.g. "C D E")
    are also channel lines. If any channel lines are found, all other lines
    are ignored.
    If no channel lines are found, all input lines are combined into one
    channel named "1"; lines starting with "X:" (letter + colon), "@" or "!"
    are ignored.
  - Lines starting with ";", "//", or "#" are comments, except "# Zenlen N",
    which sets the file-wide resolution in ticks per whole note (default: 48).
  - A standalone whitespace-delimited token "C<number>" (e.g. " C96 ") sets
    the channel resolution; it is not a C note. To write a C note with a
    length, set the length separately (e.g. "L4 C") or join it to another
    note (e.g. "C4D4").
  - T / V / S / M / @ followed by a number (tempo, volume, etc.) are ignored.
  - "[...]n" is replaced with one note: the last note inside the brackets
    with length n.
  - Supported commands: O<n>, <, >, L<n>, notes CDEFGAB (with #, +, or -),
    R, dots, and ties "&". Tied notes are treated as one note and use the
    pitch of the first note.
"""

import os
import re
import sys
import argparse
from math import gcd
from fractions import Fraction
from functools import reduce
from pathlib import Path
from typing import List, Tuple, Optional, Dict


# ─────────────────────────────────────────────────────────
# Type definitions
# ─────────────────────────────────────────────────────────

Pitch = Tuple   # ('R', None) or (note_str, octave)
Note  = Tuple   # (Pitch, note_value)  note_value in {2,4,8,16}

STEP_OF = {2: 8, 4: 4, 8: 2, 16: 1}


# ─────────────────────────────────────────────────────────
# Preprocessing
# ─────────────────────────────────────────────────────────

def preprocess(mml: str) -> Tuple[str, int]:
    mml = mml.upper()
    resolution = 48
    m = re.search(r'(?:(?<=\s)|^)C(\d+)(?=\s|$)', mml)
    if m:
        resolution = int(m.group(1))
    mml = re.sub(r'(?:(?<=\s)|^)C\d+(?=\s|$)', '', mml)
    mml = re.sub(r'[TVSM@]\d+', '', mml)

    def extract_top(mo):
        inner, length = mo.group(1), mo.group(2) or ''
        notes = re.findall(r'[A-G][+#\-]?', inner)
        return (notes[-1] + length) if notes else ''

    mml = re.sub(r'\[([^\]]+)\](\d+)?', extract_top, mml)
    return mml, resolution


# ─────────────────────────────────────────────────────────
# Parse into (pitch, ticks)
# ─────────────────────────────────────────────────────────

def parse(mml: str, resolution: int) -> List[Tuple[Pitch, int]]:
    octave = 4
    default_length = 4
    events: List[Tuple[Pitch, int]] = []
    i, n = 0, len(mml)

    def skip():
        nonlocal i
        while i < n and mml[i] in ' \t\n\r':
            i += 1

    def read_int():
        nonlocal i
        s = ''
        while i < n and mml[i].isdigit():
            s += mml[i]
            i += 1
        return int(s) if s else None

    def read_dots():
        nonlocal i
        d = 0
        while i < n and mml[i] == '.':
            d += 1
            i += 1
        return d

    def to_ticks(length, dots):
        t = Fraction(resolution, length)
        cur = t
        for _ in range(dots):
            cur /= 2
            t += cur
        return int(t)

    while i < n:
        skip()
        if i >= n:
            break
        c = mml[i]

        if c == 'O':
            i += 1
            v = read_int()
            if v is not None:
                octave = v

        elif c == '<':
            octave -= 1
            i += 1
        elif c == '>':
            octave += 1
            i += 1

        elif c == 'L':
            i += 1
            v = read_int()
            if v:
                default_length = v

        elif c in 'CDEFGABR':
            is_rest = (c == 'R')
            base = c
            i += 1
            acc = ''
            if not is_rest:
                if i < n and mml[i] in '#+':
                    acc = '+'
                    i += 1
                elif i < n and mml[i] == '-':
                    acc = '-'
                    i += 1

            length = read_int() or default_length
            ticks = to_ticks(length, read_dots())
            pitch: Pitch = ('R', None) if is_rest else (base + acc, octave)

            while i < n:
                skip()
                if i < n and mml[i] == '&':
                    i += 1
                    skip()
                    if i < n and mml[i] in 'CDEFGABR':
                        tb = mml[i]
                        i += 1
                        if tb != 'R' and i < n and mml[i] in '#+-':
                            i += 1  # Ignore the tied note's accidental; keep the first note's pitch.
                        tl = read_int() or default_length
                        ticks += to_ticks(tl, read_dots())
                else:
                    break

            events.append((pitch, ticks))
        else:
            i += 1

    return events


# ─────────────────────────────────────────────────────────
# Shared decomposition and merging
# ─────────────────────────────────────────────────────────

def decompose(steps: int, pitch: Pitch) -> List[Note]:
    result = []
    for val, sz in [(2, 8), (4, 4), (8, 2), (16, 1)]:
        while steps >= sz:
            result.append((pitch, val))
            steps -= sz
    return result


def merge_consecutive(notes: List[Note]) -> List[Note]:
    if not notes:
        return notes
    result, i = [], 0
    while i < len(notes):
        pitch, val = notes[i]
        total = STEP_OF[val]
        j = i + 1
        while j < len(notes) and notes[j][0] == pitch:
            total += STEP_OF[notes[j][1]]
            j += 1
        result.extend(decompose(total, pitch))
        i = j
    return result


def count_steps(notes: List[Note]) -> int:
    return sum(STEP_OF[v] for _, v in notes)


NOTE_SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

def pitch_to_midi(pitch: Pitch) -> Optional[int]:
    note_str, octave = pitch
    if note_str == "R":
        return None
    base = NOTE_SEMITONES[note_str[0]]
    if "+" in note_str:
        base += 1
    elif "-" in note_str:
        base -= 1
    return (octave + 1) * 12 + base


_MIDI_TO_NOTE = {0: 'C', 1: 'C+', 2: 'D', 3: 'D+', 4: 'E', 5: 'F', 6: 'F+', 7: 'G', 8: 'G+', 9: 'A', 10: 'A+', 11: 'B'}

def midi_to_pitch(midi: int) -> Pitch:
    octave = midi // 12 - 1
    note_str = _MIDI_TO_NOTE[midi % 12]
    return (note_str, octave)


def transpose_events(events: List[Tuple[Pitch, int]], semitones: int) -> List[Tuple[Pitch, int]]:
    if semitones == 0:
        return events
    result = []
    for pitch, ticks in events:
        if pitch[0] == 'R':
            result.append((pitch, ticks))
        else:
            midi = pitch_to_midi(pitch)
            result.append((midi_to_pitch(midi + semitones), ticks))
    return result


MINOR_VARIANTS = {
    'natural':  {4, 9, 11},  # E- A- B-
    'harmonic': {4, 9},      # E- A-
    'melodic':  {4},         # E-
}

def to_minor_events(events: List[Tuple[Pitch, int]], variant: str) -> List[Tuple[Pitch, int]]:
    targets = MINOR_VARIANTS[variant]
    result = []
    for pitch, ticks in events:
        if pitch[0] == 'R':
            result.append((pitch, ticks))
        else:
            midi = pitch_to_midi(pitch)
            if midi % 12 in targets:
                result.append((midi_to_pitch(midi - 1), ticks))
            else:
                result.append((pitch, ticks))
    return result


def pitch_label(pitch: Pitch) -> str:
    return f"O{pitch[1]}{pitch[0]}"

def pitch_range(events):
    pitches = [(pitch_to_midi(p), p) for p, _ in events if p[0] != "R"]
    if not pitches:
        return None, None
    lo = min(pitches, key=lambda x: x[0])[1]
    hi = max(pitches, key=lambda x: x[0])[1]
    return pitch_label(lo), pitch_label(hi)


# ─────────────────────────────────────────────────────────
# Quantization
# ─────────────────────────────────────────────────────────

def simple_quantize(events: List[Tuple[Pitch, int]], resolution: int) -> List[Note]:
    step_size = resolution / 16
    notes = []
    for pitch, ticks in events:
        steps = round(ticks / step_size)
        if steps <= 0:
            continue
        notes.extend(decompose(steps, pitch))
    return merge_consecutive(notes)


def exact_quantize(events: List[Tuple[Pitch, int]], unit: int) -> List[Note]:
    notes = []
    for pitch, ticks in events:
        if ticks <= 0:
            continue
        notes.extend(decompose(ticks // unit, pitch))
    return merge_consecutive(notes)


# ─────────────────────────────────────────────────────────
# Formatting
# ─────────────────────────────────────────────────────────

def format_output(notes: List[Note]) -> str:
    parts = []
    for pitch, val in notes:
        if pitch[0] == 'R':
            parts.append(f"R{val}")
        else:
            note_str, octave = pitch
            parts.append(f"O{octave}{note_str}{val}")
    return ' '.join(parts)


# ─────────────────────────────────────────────────────────
# File loading and parsing
# ─────────────────────────────────────────────────────────

def read_file(path: Path) -> Tuple[List[Tuple[str, str]], int]:
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines()

    resolution = 48
    for line in lines:
        m = re.match(r'#\s*Zenlen\s+(\d+)', line, re.IGNORECASE)
        if m:
            resolution = int(m.group(1))
            break

    pmd_re = re.compile(r'^([A-Z])\s+(.*)', re.IGNORECASE)
    channels: Dict[str, List[str]] = {}
    order: List[str] = []
    is_pmd = False

    for line in lines:
        s = line.rstrip()
        stripped = s.lstrip()
        if not stripped or stripped.startswith(';') or stripped.startswith('//') or stripped.startswith('#'):
            continue
        m = pmd_re.match(s)
        if m:
            is_pmd = True
            label = m.group(1).upper()
            if label not in channels:
                channels[label] = []
                order.append(label)
            channels[label].append(m.group(2))

    if is_pmd:
        return [(lbl, ' '.join(channels[lbl])) for lbl in order], resolution

    mml_lines = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith(';') or s.startswith('//') or s.startswith('#'):
            continue
        if re.match(r'^[A-Z]:', s) or s.startswith('@') or s.startswith('!'):
            continue
        mml_lines.append(s)
    return [('1', ' '.join(mml_lines))], resolution


# ─────────────────────────────────────────────────────────
# Conversion pipeline
# ─────────────────────────────────────────────────────────

def convert_all(channel_entries: List[Tuple[str, str, int]], transpose: int = 0, minor: str = None) -> Tuple[List[dict], int]:
    all_events = []
    parsed = []

    for label, mml, res in channel_entries:
        cleaned, inline_res = preprocess(mml)
        resolution = inline_res if inline_res != 48 else res
        events = parse(cleaned, resolution)
        if transpose:
            events = transpose_events(events, transpose)
        if minor:
            events = to_minor_events(events, minor)
        parsed.append((label, events, resolution))
        all_events.extend(events)

    all_ticks = [t for _, t in all_events if t > 0]
    unit = reduce(gcd, all_ticks) if all_ticks else 1

    results = []
    for label, events, resolution in parsed:
        simple_notes = simple_quantize(events, resolution)
        exact_notes = exact_quantize(events, unit)
        lo, hi = pitch_range(events)
        results.append({
            'label':        label,
            'simple_notes': simple_notes,
            'exact_notes':  exact_notes,
            'simple_steps': count_steps(simple_notes),
            'exact_steps':  count_steps(exact_notes),
            'lo':           lo,
            'hi':           hi,
        })

    return results, unit


def apply_fill(results: List[dict], mode: str) -> List[dict]:
    key = f'{mode}_notes'
    key_steps = f'{mode}_steps'
    max_steps = max(r[key_steps] for r in results)
    for r in results:
        diff = max_steps - r[key_steps]
        if diff > 0:
            r[key] = r[key] + decompose(diff, ('R', None))
            r[key_steps] = max_steps
    return results


# ─────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog=Path(__file__).name,
        description='MML Quantizer & Simplifier (quantize to {2,4,8,16} note values). '
                    'Choose one output mode: --simple / --exact / --judge (or see the default below).',
        epilog="""Default behavior:
  Output simple only if it matches exact for every channel.
  If there is drift, print "LOSSY" and exit with code 1.

Examples:
  python3 mml_quantize.py song.mml --simple
  python3 mml_quantize.py song.mml --exact --fill
  python3 mml_quantize.py song.mml --judge
  python3 mml_quantize.py song.mml --transpose -2 --minor natural

For the input MML format (including channel lines and C<number> resolution
tokens), see the description at the top of this file.""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('file', type=Path, help='Path to input MML file')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--simple', action='store_true', help='Use rounded quantization (compact, natural-sounding output)')
    mode.add_argument('--exact',  action='store_true', help='Use lossless GCD-based quantization')
    mode.add_argument('--judge',  action='store_true', help='Compare simple and exact per channel; show ok/drift (exit 0=match, 1=drift)')
    parser.add_argument('--fill',   action='store_true', help='Append rests to shorter channels (applies only to selected mode; simple only with --judge)')
    parser.add_argument('--transpose', type=int, default=0, metavar='N', help='Transpose by this many semitones (positive=up, negative=down)')
    parser.add_argument('--minor', choices=['natural', 'harmonic', 'melodic'], default=None, help='Convert C major to minor (applied after --transpose)')

    args = parser.parse_args()

    if not args.file.is_file():
        print(f"Error: File not found: '{args.file}'.", file=sys.stderr)
        sys.exit(1)

    try:
        channel_entries_raw, file_res = read_file(args.file)
    except Exception as e:
        print(f"Error: Could not read file ({e}).", file=sys.stderr)
        sys.exit(1)

    channel_entries = [(lbl, mml, file_res) for lbl, mml in channel_entries_raw]
    results, unit = convert_all(channel_entries, transpose=args.transpose, minor=args.minor)

    # Apply --fill independently to the selected mode.
    if args.fill:
        if args.exact:
            results = apply_fill(results, 'exact')
        else:
            results = apply_fill(results, 'simple')

    # --judge mode
    if args.judge:
        ok = True
        for r in results:
            drift = format_output(r['simple_notes']) != format_output(r['exact_notes'])
            label = f"{r['label']}  " if r['label'] else ""
            status = 'drift' if drift else 'ok'
            lo = r['lo'] or '-'
            hi = r['hi'] or '-'
            print(f"{label}simple={r['simple_steps']}  exact={r['exact_steps']}  lo={lo}  hi={hi}  {status}")
            if drift:
                ok = False
        sys.exit(0 if ok else 1)

    multi = len(results) > 1

    def print_mode(mode):
        for i, r in enumerate(results):
            if i > 0:
                print()
            out = format_output(r[f'{mode}_notes'])
            print(f"{r['label']} {out}" if multi and r['label'] else out)

    if args.simple:
        print_mode('simple')
        return

    if args.exact:
        print_mode('exact')
        return

    # Default mode: validate drift before outputting simple.
    drifts = [r['label'] or '1' for r in results
              if format_output(r['simple_notes']) != format_output(r['exact_notes'])]

    if drifts:
        print(f"LOSSY: simple and exact differ on channel(s): {', '.join(drifts)}.")
        print("Specify --simple or --exact (and optionally --fill) to continue.")
        sys.exit(1)

    print_mode('simple')


def run():
    try:
        main()
        sys.stdout.flush()
    except BrokenPipeError:
        # Exit quietly if the output consumer (such as `head`) closes the pipe first.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(1)


if __name__ == '__main__':
    run()
