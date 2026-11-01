#!/usr/bin/env python3
"""
nes_dungeon_sim_aabb.py -- NES-style dungeon generator (AABB rejection)

Usage:
    Place randomly sized rooms on a 32x30 map without overlap (rejecting
    overlapping placements), connect rooms in coordinate order with L-shaped
    corridors, and print the dungeon as text. Use --sim to summarize all 256
    seeds (connected and isolated rooms, average corridors and doors).
Input/output:
    Input: seed 0-255 (random if omitted) and room-size options
    Output: map and statistics to stdout
Examples:
    python3 nes_dungeon_sim_aabb.py                    # Random seed
    python3 nes_dungeon_sim_aabb.py 42                 # Specify a seed
    python3 nes_dungeon_sim_aabb.py --sim              # Statistics for all 256 seeds
    python3 nes_dungeon_sim_aabb.py --sim --attempt 5  # Fewer rooms for a shallow floor
Dependencies: Python standard library only
"""

import argparse
import os
import random
import sys
from collections import Counter
from pathlib import Path

# =============================================================================
# Constants
# =============================================================================
MAP_W = 32
MAP_H = 30

TILE_EMPTY    = 0
TILE_WALL_H   = 1
TILE_WALL_V   = 2
TILE_FLOOR    = 3
TILE_CORRIDOR = 4
TILE_DOOR     = 5
TILE_STAIR_UP = 6
TILE_STAIR_DN = 7

TILE_CHAR = {
    TILE_EMPTY:    ' ',
    TILE_WALL_H:   '-',
    TILE_WALL_V:   '|',
    TILE_FLOOR:    '.',
    TILE_CORRIDOR: '#',
    TILE_DOOR:     '+',
    TILE_STAIR_UP: '<',
    TILE_STAIR_DN: '>',
}

# =============================================================================
# RNG (NES-style: 8-bit lookup, XOR, comparison, and subtraction only)
# =============================================================================
# Permutation containing every value from 0x00 to 0xFF exactly once (256 values)
RND_256 = [
    0x96,0x14,0xB2,0x1A,0xAE,0xB8,0x16,0xC9,0xE9,0x8F,0x08,0x80,0x03,0xB6,0x92,0xC2,
    0x27,0xC6,0xB3,0xE2,0xFE,0x3B,0x8D,0x42,0x0C,0x0F,0x45,0xBE,0x74,0x86,0xC0,0xDE,
    0x87,0xE6,0xFD,0xE4,0x4A,0x21,0x7A,0x79,0x95,0x44,0x68,0x3F,0x67,0xE5,0xE3,0x23,
    0xF2,0xD7,0x43,0x09,0x55,0xE1,0x59,0xAA,0x2A,0x9F,0xA2,0x17,0x6C,0xF1,0xAD,0x54,
    0xDD,0x78,0x4C,0x00,0xE7,0x6B,0x3A,0x65,0xFA,0x5E,0x9A,0x36,0x1D,0x69,0xEA,0xC7,
    0xA6,0xAB,0x62,0xB7,0x58,0xEF,0x56,0x41,0xD0,0xC3,0x47,0x18,0x24,0x10,0x39,0x3D,
    0x61,0xDA,0x77,0xA5,0x51,0x8A,0x13,0xD6,0xBB,0x49,0x7E,0x9D,0xD9,0xB4,0xEC,0x83,
    0xF5,0x7C,0xE8,0x3E,0x73,0x46,0xDC,0x2D,0x91,0xF6,0xC4,0x70,0x05,0x4B,0x12,0x84,
    0x6A,0x34,0xED,0xC8,0xF7,0x2C,0x06,0x40,0x2F,0x8C,0x2E,0x81,0xD3,0x35,0xCC,0x6D,
    0xFC,0x8B,0xFF,0x4E,0x25,0x9C,0x0A,0xD4,0x26,0x50,0x37,0x28,0xCA,0x9E,0x4D,0x2B,
    0xC1,0x7B,0xA4,0xC5,0xEB,0xD1,0x20,0xAC,0x66,0xA3,0xBC,0x5B,0x9B,0x71,0x8E,0xF4,
    0x19,0x33,0x1C,0x38,0xB9,0x4F,0xCB,0xBD,0x7F,0x89,0xB1,0xCD,0x57,0x0B,0x85,0xCE,
    0xCF,0x5A,0xA8,0x97,0x5D,0x76,0x07,0x93,0x0D,0x63,0x0E,0xBA,0x53,0x6F,0xDB,0x98,
    0xA1,0x3C,0x99,0xA0,0x94,0x48,0x5C,0x6E,0xD8,0xDF,0x11,0xAF,0xD2,0xF9,0x82,0x52,
    0xF0,0xFB,0x15,0xEE,0x1B,0x88,0x32,0x22,0xB5,0xD5,0xBF,0xF3,0xA7,0x90,0x31,0x1F,
    0xB0,0xE0,0xA9,0x29,0xF8,0x02,0x64,0x04,0x01,0x72,0x1E,0x7D,0x30,0x60,0x75,0x5F,
]
# Contains each value from 0x00 to 0xFF once, except 0x34 (255 values)
RND_255 = [
    0xB9,0x94,0xD6,0x6D,0x73,0xE1,0xFF,0x8C,0xF9,0x0E,0xDC,0x64,0x57,0xF1,0xEC,0x44,
    0x7A,0xE2,0x09,0x1C,0x29,0x37,0x2B,0x91,0x02,0x9C,0xE5,0x76,0x7C,0x1A,0x04,0xE7,
    0x97,0x69,0xFA,0xEA,0x9B,0x28,0xC0,0xA8,0xD1,0xB1,0x74,0xE8,0xB0,0xD5,0xA0,0xBB,
    0x1F,0x22,0xC7,0x0B,0x58,0x06,0x0C,0xFB,0x6F,0x88,0xBA,0xEE,0x4C,0x24,0x81,0xAE,
    0x48,0xDD,0x68,0xEF,0x72,0x9A,0xDA,0x67,0xC5,0xDE,0x3B,0x86,0x54,0x11,0xD3,0x8A,
    0x62,0x2C,0xD9,0x40,0xF8,0xCD,0xF7,0x8D,0x45,0xE6,0x5A,0xBD,0x55,0x65,0x6A,0xBF,
    0x0F,0xA3,0xAA,0xCF,0x8F,0xCA,0x5C,0x6E,0x95,0x30,0x3E,0xDF,0xB3,0x9D,0xE9,0x87,
    0x39,0x0D,0xB5,0x36,0x63,0x51,0xD7,0xFC,0xA7,0x7F,0xC3,0x26,0x4B,0x4D,0xC4,0x77,
    0x0A,0x05,0xA2,0x42,0x19,0x21,0x17,0x4A,0x66,0xC1,0x1B,0x7E,0x59,0xAC,0x49,0xE0,
    0x8E,0xA4,0xD0,0x1E,0x1D,0xFE,0x2D,0x5B,0x83,0xD2,0xD4,0x85,0x52,0x3D,0xA5,0x61,
    0xA1,0xC6,0xB7,0xBC,0x82,0xF3,0x7B,0x4F,0xE3,0xF5,0x32,0xFD,0x6C,0xAB,0x14,0x56,
    0x5D,0x3A,0x75,0x46,0x80,0x33,0x38,0xF6,0x5E,0x16,0x47,0x03,0xED,0x4E,0xB6,0xB8,
    0xF0,0x35,0x53,0x13,0x78,0x18,0x7D,0x60,0xB4,0x93,0x12,0x70,0x79,0x50,0xF2,0x41,
    0x98,0xEB,0xCC,0xBE,0x9F,0x5F,0x3C,0x08,0xE4,0x6B,0xAF,0xD8,0xC8,0xB2,0x3F,0xCB,
    0x20,0x27,0x2A,0x25,0x07,0x92,0x8B,0x2F,0xA9,0xDB,0x71,0x90,0x10,0xC9,0x01,0x00,
    0xC2,0xA6,0x9E,0x43,0x2E,0x89,0xF4,0xAD,0x99,0xCE,0x31,0x23,0x15,0x96,0x84,
]


def mg_mod(a, b):
    """8-bit modulo by repeated subtraction (returns 0 when b is 0)."""
    a, b = a & 0xFF, b & 0xFF
    if b == 0:
        return 0
    while a >= b:
        a = (a - b) & 0xFF
    return a


class RNG:
    """Read two tables with periods 256 and 255 and return their 8-bit XOR.

    The seed (0-255) sets the initial read positions in both tables.
    """

    def __init__(self, seed):
        self.idx256 = seed & 0xFF
        self.idx255 = mg_mod(seed, 255)

    def next(self):
        v256 = RND_256[self.idx256]
        self.idx256 = (self.idx256 + 1) & 0xFF
        v255 = RND_255[self.idx255]
        self.idx255 += 1
        if self.idx255 >= 255:
            self.idx255 = 0
        return v256 ^ v255


def make_map():
    return [TILE_EMPTY] * (MAP_W * MAP_H)


def put_tile(buf, x, y, tile):
    if 0 <= x < MAP_W and 0 <= y < MAP_H:
        buf[y * MAP_W + x] = tile


def get_tile(buf, x, y):
    if 0 <= x < MAP_W and 0 <= y < MAP_H:
        return buf[y * MAP_W + x]
    return TILE_EMPTY


def count_tile(buf, tile):
    return sum(1 for t in buf if t == tile)


def draw_room(buf, rx, ry, rw, rh):
    for dx in range(rw):
        put_tile(buf, rx + dx, ry, TILE_WALL_H)
        put_tile(buf, rx + dx, ry + rh - 1, TILE_WALL_H)
    for dy in range(1, rh - 1):
        put_tile(buf, rx, ry + dy, TILE_WALL_V)
        put_tile(buf, rx + rw - 1, ry + dy, TILE_WALL_V)
        for dx in range(1, rw - 1):
            put_tile(buf, rx + dx, ry + dy, TILE_FLOOR)


def overlaps(ax, ay, aw, ah, bx, by, bw, bh):
    m = 1
    return not (ax + aw + m <= bx or bx + bw + m <= ax or
                ay + ah + m <= by or by + bh + m <= ay)


def dig_tile(buf, x, y):
    t = get_tile(buf, x, y)
    if t == TILE_EMPTY:
        put_tile(buf, x, y, TILE_CORRIDOR)
    elif t in (TILE_WALL_H, TILE_WALL_V):
        put_tile(buf, x, y, TILE_DOOR)


def dig_h(buf, x0, x1, y):
    if x0 > x1:
        x0, x1 = x1, x0
    for x in range(x0, x1 + 1):
        dig_tile(buf, x, y)


def dig_v(buf, x, y0, y1):
    if y0 > y1:
        y0, y1 = y1, y0
    for y in range(y0, y1 + 1):
        dig_tile(buf, x, y)


def scan_wall_h(buf, x0, x1, y):
    if x0 > x1:
        x0, x1 = x1, x0
    count = 0
    for x in range(x0, x1 + 1):
        if get_tile(buf, x, y) in (TILE_WALL_H, TILE_WALL_V):
            count += 1
    return count


def scan_wall_v(buf, x, y0, y1):
    if y0 > y1:
        y0, y1 = y1, y0
    count = 0
    for y in range(y0, y1 + 1):
        if get_tile(buf, x, y) in (TILE_WALL_H, TILE_WALL_V):
            count += 1
    return count


def room_center(rx, ry, rw, rh):
    return rx + (rw >> 1), ry + (rh >> 1)


def sort_rooms(rooms):
    return sorted(rooms, key=lambda r: r[0] + r[1])


def connect_rooms(buf, connected):
    connected = sort_rooms(connected)
    for i in range(len(connected) - 1):
        ax, ay = room_center(*connected[i])
        bx, by = room_center(*connected[i + 1])

        if ax == bx:
            dig_v(buf, ax, ay, by)
        elif ay == by:
            dig_h(buf, ax, bx, ay)
        else:
            hit_l1 = scan_wall_h(buf, ax, bx, ay) + scan_wall_v(buf, bx, ay, by)
            hit_l2 = scan_wall_v(buf, ax, ay, by) + scan_wall_h(buf, ax, bx, by)

            if hit_l1 <= hit_l2:
                dig_h(buf, ax, bx, ay)
                dig_v(buf, bx, ay, by)
            else:
                dig_v(buf, ax, ay, by)
                dig_h(buf, ax, bx, by)


def place_stairs(buf, rng, connected):
    n = len(connected)
    if n == 0:
        return

    def rand_floor_pos(rng, rx, ry, rw, rh):
        while True:
            x = rx + 1 + mg_mod(rng.next(), 32)
            y = ry + 1 + mg_mod(rng.next(), 32)
            if x <= rx + rw - 2 and y <= ry + rh - 2:
                return x, y

    i = mg_mod(rng.next(), n)
    rx, ry, rw, rh = connected[i]
    sx, sy = rand_floor_pos(rng, rx, ry, rw, rh)
    put_tile(buf, sx, sy, TILE_STAIR_UP)

    if n == 1:
        while True:
            dx, dy = rand_floor_pos(rng, rx, ry, rw, rh)
            if (dx, dy) != (sx, sy):
                break
        put_tile(buf, dx, dy, TILE_STAIR_DN)
    else:
        j = mg_mod(rng.next(), n - 1)
        if j >= i:
            j += 1
        rx, ry, rw, rh = connected[j]
        dx, dy = rand_floor_pos(rng, rx, ry, rw, rh)
        put_tile(buf, dx, dy, TILE_STAIR_DN)


def place_rooms(rng, buf, minw, minh, maxw, maxh, attempts):
    rooms = []
    fail = 0
    while fail < attempts:
        rw = minw + mg_mod(rng.next(), maxw - minw + 1)
        rh = minh + mg_mod(rng.next(), maxh - minh + 1)

        x_range = MAP_W - rw
        y_range = MAP_H - rh
        rx = mg_mod(rng.next(), x_range) if x_range > 0 else 0
        ry = mg_mod(rng.next(), y_range) if y_range > 0 else 0

        if any(overlaps(rx, ry, rw, rh, ex, ey, ew, eh) for ex, ey, ew, eh in rooms):
            fail += 1
            continue

        rooms.append((rx, ry, rw, rh))
        if buf is not None:
            draw_room(buf, rx, ry, rw, rh)
        fail = 0
    return rooms


def generate(seed, minw, minh, maxw, maxh, attempts, maxroom):
    rng = RNG(seed)
    buf = make_map()

    rooms = place_rooms(rng, buf, minw, minh, maxw, maxh, attempts)
    connected = rooms[:maxroom]
    isolated  = rooms[maxroom:]

    connect_rooms(buf, connected)
    place_stairs(buf, rng, connected)

    n_conn = len(connected)
    n_iso  = len(isolated)
    n_all  = len(rooms)
    n_corr = count_tile(buf, TILE_CORRIDOR)
    n_door = count_tile(buf, TILE_DOOR)

    if n_iso > 0:
        label = f"{n_conn} connected + {n_iso} isolated (total {n_all})"
    elif n_all == 1:
        label = "Great Hall"
    else:
        label = f"{n_all} rooms"

    print(f"seed={seed}  {label}  corridors={n_corr} doors={n_door}")
    print(f"  size={minw}-{maxw}x{minh}-{maxh}  attempt={attempts}  maxroom={maxroom}")

    print_map(buf)


def print_map(buf):
    border = '─' * (MAP_W + 2)
    print('┌' + border + '┐')
    for y in range(MAP_H):
        row = '│ '
        for x in range(MAP_W):
            row += TILE_CHAR[get_tile(buf, x, y)]
        row += ' │'
        print(row)
    print('└' + border + '┘')
    print("Legend: space=empty  -=horizontal wall  |=vertical wall  .=floor  #=corridor  +=door  <=up stairs  >=down stairs")


def run_sim(minw, minh, maxw, maxh, attempt, maxroom):
    """Generate rooms and corridors for all 256 seeds and print statistics."""
    conn_counts = Counter()
    iso_counts  = Counter()
    corr_total  = 0
    door_total  = 0
    total = 256

    for seed in range(total):
        rng = RNG(seed)
        buf = make_map()
        rooms = place_rooms(rng, buf, minw, minh, maxw, maxh, attempt)
        connected = sort_rooms(rooms[:maxroom])
        connect_rooms(buf, connected)

        n_conn = len(connected)
        n_iso  = len(rooms) - n_conn
        conn_counts[n_conn] += 1
        iso_counts[n_iso]   += 1
        corr_total += count_tile(buf, TILE_CORRIDOR)
        door_total += count_tile(buf, TILE_DOOR)

    print(f"All {total} seeds  size={minw}-{maxw}x{minh}-{maxh}  attempt={attempt}  maxroom={maxroom}")
    print()

    print(f"{'Connected':>10}  {'Count':>5}  {'Share':>6}  Distribution")
    for n in sorted(conn_counts):
        bar = '█' * (conn_counts[n] * 40 // total)
        print(f"    {n:2d} rooms  {conn_counts[n]:3d}  {conn_counts[n]/total*100:5.1f}%  {bar}")
    print()

    print(f"{'Isolated':>10}  {'Count':>5}  {'Share':>6}  Distribution")
    for n in sorted(iso_counts):
        bar = '█' * (iso_counts[n] * 40 // total)
        print(f"    {n:2d} rooms  {iso_counts[n]:3d}  {iso_counts[n]/total*100:5.1f}%  {bar}")

    total_iso = sum(n * c for n, c in iso_counts.items())
    has_iso   = sum(c for n, c in iso_counts.items() if n > 0)
    print(f"  → {has_iso}/{total} maps ({has_iso/total*100:.0f}%) have isolated rooms; average {total_iso/total:.1f} rooms/map")

    print()
    print(f"--- Corridor statistics (average across {total} seeds) ---")
    print(f"  Corridor tiles: {corr_total/total:.1f}  Door tiles: {door_total/total:.1f}")


def seed_value(text):
    """argparse type: seed from 0 to 255."""
    value = int(text)
    if not 0 <= value <= 255:
        raise argparse.ArgumentTypeError("Seed must be an integer from 0 to 255.")
    return value


def main():
    parser = argparse.ArgumentParser(
        prog=Path(__file__).name,
        description='NES-style dungeon generator (AABB rejection)',
        epilog="""Examples:
  python3 nes_dungeon_sim_aabb.py                    # Random seed
  python3 nes_dungeon_sim_aabb.py 42                 # Specify a seed
  python3 nes_dungeon_sim_aabb.py --sim              # Statistics for all 256 seeds
  python3 nes_dungeon_sim_aabb.py --sim --attempt 5  # Shallow floor (fewer rooms)

Randomly place non-overlapping rooms (rejecting overlaps) and connect them in
coordinate order with L-shaped corridors. Each corridor checks both possible
routes in advance and uses the one that crosses fewer walls.
The RNG uses only 8-bit lookup tables, like an NES-style implementation.""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('seed', nargs='?', type=seed_value, default=None, metavar='SEED', help='Random seed, 0-255 (random if omitted)')
    parser.add_argument('--minw', type=int, default=4, metavar='N', help='Minimum room width, including walls (default: 4)')
    parser.add_argument('--minh', type=int, default=4, metavar='N', help='Minimum room height, including walls (default: 4)')
    parser.add_argument('--maxw', type=int, default=16, metavar='N', help='Maximum room width, including walls (default: 16)')
    parser.add_argument('--maxh', type=int, default=16, metavar='N', help='Maximum room height, including walls (default: 16)')
    parser.add_argument('--attempt', type=int, default=80, metavar='N', help='Consecutive failed placement attempts allowed; reset after success (default: 80)')
    parser.add_argument('--maxroom', type=int, default=8, metavar='N', help='Maximum rooms to connect; additional rooms remain isolated (default: 8)')
    parser.add_argument('--sim', action='store_true', help='Collect statistics across all 256 seeds')
    args = parser.parse_args()

    args.minw    = max(4, min(args.minw, MAP_W))
    args.minh    = max(3, min(args.minh, MAP_H))
    args.maxw    = max(args.minw, min(args.maxw, MAP_W))
    args.maxh    = max(args.minh, min(args.maxh, MAP_H))
    args.attempt = max(1, args.attempt)
    args.maxroom = max(1, args.maxroom)

    if args.sim:
        run_sim(args.minw, args.minh, args.maxw, args.maxh, args.attempt, args.maxroom)
    else:
        seed = args.seed if args.seed is not None else random.randint(0, 255)
        generate(seed, args.minw, args.minh, args.maxw, args.maxh, args.attempt, args.maxroom)


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
