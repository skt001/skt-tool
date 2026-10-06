#!/usr/bin/env python3
"""
mml_quantize.py -- MML の量子化・簡略化ツール

用途:
    高解像度な MML を {2, 4, 8, 16} 分音符だけで書いたシンプルな形式に
    量子化 (丸め) します。移調と、C メジャーから短調への変換もできます。
入出力:
    入力: MML ファイル 1 つ (入力の書式は下記)
    出力: 標準出力に "O4C8 O4D4 R8" のような形式で書き出します
          (複数チャンネルのときは、チャンネルごとに空行で区切り、先頭にチャンネル名が付きます)
使用例:
    python3 mml_quantize.py song.mml --simple
    python3 mml_quantize.py song.mml --judge
    python3 mml_quantize.py song.mml --transpose -2 --minor natural
依存: 標準ライブラリのみ

出力モード (どれか 1 つ。同時には指定できません):
  (無指定)  simple と exact が全チャンネルで一致したときだけ simple を出力します。
            差分 (drift) があるときは "LOSSY" と表示し、MML は出力せず終了コード 1 で終了します。
  --simple  丸めクオンタイズ。人間の耳に自然でコンパクトな出力になります。
  --exact   GCD ベースの無失真クオンタイズ。丸めません (必要に応じてテンポ調整が要ります)。
  --judge   チャンネルごとに simple と exact を比較し、ok / drift をレポートします。
            終了コード: 0 = 全チャンネル一致, 1 = ドリフトあり

その他のオプション:
  --fill         短いチャンネルの末尾に休符を足して、最長チャンネルに揃えます。
                 選んだモード (--exact なら exact、それ以外は simple) の側にだけ適用されます。
                 --judge と併用すると simple 側だけが揃えられるため、短いチャンネルは
                 drift と判定されます。
  --transpose N  全ピッチを N 半音シフトします (負数 = 下げる, 正数 = 上げる)。
  --minor MODE   C メジャーの曲を短調に変換します (natural / harmonic / melodic)。
                 --transpose の適用後に実行されます。

入力 MML の書式:
  - 行頭 (先頭に空白を置かない) が「英字 1 文字 + 空白」の行は、その英字をチャンネル名とする
    行として扱い、同じ名前の行は連結します (例: "A O4 CDE")。単独の音名で始まる行
    ("C D E" など) もチャンネル行になるので注意してください。
    チャンネル行が 1 つでもあると、チャンネル行以外の行は無視されます。
    チャンネル行が 1 つも無いときは、全行をまとめて 1 チャンネル (名前 "1") として扱い、
    "X:" (英字 + コロン) や "@" "!" で始まる行は無視します。
  - ";" "//" "#" で始まる行はコメントです。ただし "# Zenlen N" はファイル全体の解像度
    (全音符あたりの tick 数, 既定 48) の指定です。
  - 空白で区切られた単独のトークン "C<数字>" (例: " C96 ") は音符 C ではなく、
    そのチャンネルの解像度の指定として扱われます。長さ付きの C を書くときは、
    "L4 C" のように長さを別に指定するか、"C4D4" のように他の音符と続けてください。
  - T / V / S / M / @ + 数字 (テンポ・音量など) は無視されます。
  - "[...]n" は、括弧内の最後の音名だけを残し、長さ n を付けた 1 音に置き換えます。
  - 使えるコマンド: O<n> < > L<n> 音符 CDEFGAB (# + - 付き) R, 付点, タイ "&"。
    タイでつないだ音は 1 つの音として扱い、高さは最初の音を使います。
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
# 型定義
# ─────────────────────────────────────────────────────────

Pitch = Tuple   # ('R', None) または (note_str, octave)
Note  = Tuple   # (Pitch, note_value)  note_value in {2,4,8,16}

STEP_OF = {2: 8, 4: 4, 8: 2, 16: 1}


# ─────────────────────────────────────────────────────────
# 前処理
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
# パース → (pitch, ticks)
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
                            i += 1  # タイ先の臨時記号は読み飛ばす (高さは最初の音を使う)
                        tl = read_int() or default_length
                        ticks += to_ticks(tl, read_dots())
                else:
                    break

            events.append((pitch, ticks))
        else:
            i += 1

    return events


# ─────────────────────────────────────────────────────────
# 分解・マージ共通
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
# クオンタイズ処理
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
# フォーマット
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
# ファイル読み込み・解析
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
# 変換パイプライン
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
# main
# ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog=Path(__file__).name,
        description='MML Quantizer & Simplifier ({2,4,8,16} 分音符への量子化)。'
                    '出力モードは --simple / --exact / --judge のどれか 1 つ (無指定は下記)。',
        epilog="""無指定の動作:
  simple と exact が全チャンネルで一致したときだけ simple を出力します。
  差分 (drift) があるときは "LOSSY" と表示して終了コード 1 で終了します。

例:
  python3 mml_quantize.py song.mml --simple
  python3 mml_quantize.py song.mml --exact --fill
  python3 mml_quantize.py song.mml --judge
  python3 mml_quantize.py song.mml --transpose -2 --minor natural

入力 MML の書式 (チャンネル行, C<数字> が解像度指定になる点など) は、
このファイルの先頭の説明を参照してください。""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('file', type=Path, help='入力 MML ファイルパス')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--simple', action='store_true', help='丸めクオンタイズで出力 (人間の耳に自然でコンパクト)')
    mode.add_argument('--exact',  action='store_true', help='GCD ベースの無失真クオンタイズで出力')
    mode.add_argument('--judge',  action='store_true', help='チャンネルごとに simple と exact を比較し ok/drift を表示 (終了コード 0=全一致, 1=ドリフトあり)')
    parser.add_argument('--fill',   action='store_true', help='短いチャンネルの末尾に休符を足して長さを揃える (選んだモード側にだけ適用。--judge では simple 側のみ)')
    parser.add_argument('--transpose', type=int, default=0, metavar='N', help='指定半音数だけ移調 (正=上, 負=下)')
    parser.add_argument('--minor', choices=['natural', 'harmonic', 'melodic'], default=None, help='C メジャーを短調に変換 (--transpose の後に適用)')

    args = parser.parse_args()

    if not args.file.is_file():
        print(f"エラー: ファイル '{args.file}' が見つかりません。", file=sys.stderr)
        sys.exit(1)

    try:
        channel_entries_raw, file_res = read_file(args.file)
    except Exception as e:
        print(f"エラー: ファイルの読み込みに失敗しました ({e})", file=sys.stderr)
        sys.exit(1)

    channel_entries = [(lbl, mml, file_res) for lbl, mml in channel_entries_raw]
    results, unit = convert_all(channel_entries, transpose=args.transpose, minor=args.minor)

    # --fill の独立適用ロジック
    if args.fill:
        if args.exact:
            results = apply_fill(results, 'exact')
        else:
            results = apply_fill(results, 'simple')

    # --judge モード
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

    # オプション未指定時: ドリフト検証後に simple 出力
    drifts = [r['label'] or '1' for r in results
              if format_output(r['simple_notes']) != format_output(r['exact_notes'])]

    if drifts:
        print(f"LOSSY: チャンネル {', '.join(drifts)} で simple と exact に差分が発生しました。")
        print("--simple または --exact を明示して実行してください (必要に応じて --fill を併用)。")
        sys.exit(1)

    print_mode('simple')


def run():
    try:
        main()
        sys.stdout.flush()
    except BrokenPipeError:
        # 出力先 (head など) が先に閉じた場合は、エラーを出さずに終了する
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(1)


if __name__ == '__main__':
    run()
