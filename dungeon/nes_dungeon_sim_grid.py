#!/usr/bin/env python3
"""
nes_dungeon_sim_grid.py -- NES-style dungeon generator (grid layout)

Usage:
    Divide a 32x30 map into a fixed 4x3 grid, probabilistically create rooms
    in each cell, and probabilistically connect adjacent rooms with L-shaped
    corridors. Use --sim to summarize all 256 seeds (room counts, average
    corridors, and doors).
Input/output:
    Input: seed 0-255 (random if omitted) and room-size options
    Output: map and statistics to stdout
Examples:
    python3 nes_dungeon_sim_grid.py            # Random seed
    python3 nes_dungeon_sim_grid.py 42         # Specify a seed
    python3 nes_dungeon_sim_grid.py --sim      # Statistics for all 256 seeds
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

GRID_W = 4
GRID_H = 3

ROOM_MIN = 4
ROOM_MAX = 8

# Probability is tested by comparing an 8-bit value with a threshold: threshold / 256.
PROB_ROOM = 230   # Probability of creating a room in a cell (about 0.9)
PROB_LINK = 205   # Probability of connecting adjacent rooms (about 0.8)
PROB_HALF = 128   # 1/2

TILE_EMPTY    = ' '
TILE_WALL_H   = '-'
TILE_WALL_V   = '|'
TILE_FLOOR    = '.'
TILE_CORRIDOR = '#'
TILE_DOOR     = '+'
TILE_STAIR_UP = '<'
TILE_STAIR_DN = '>'


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


def chance(rng, threshold):
    """Return True when the 8-bit random value is below threshold (probability threshold/256)."""
    return rng.next() < threshold


def rand_range(rng, lo, hi):
    """Return an integer from lo to hi, inclusive (range width must be at most 255)."""
    return lo + mg_mod(rng.next(), hi - lo + 1)


def rand_index(rng, n):
    """Return an integer from 0 to n-1 (1 <= n <= 65535).

    Since there may be more than 255 candidates, reduce a combined 16-bit value
    using repeated subtraction.
    """
    hi = rng.next()
    lo = rng.next()
    v = (hi << 8) | lo
    while v >= n:
        v -= n
    return v


class Room:
    def __init__(self, x, y, w, h, gx, gy):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.gx = gx
        self.gy = gy
        self.doors = {"N": None, "S": None, "E": None, "W": None}


def make_grid():
    return [[TILE_EMPTY for _ in range(MAP_W)] for _ in range(MAP_H)]


def carve_room(grid, r):
    for y in range(r.y, r.y + r.h):
        for x in range(r.x, r.x + r.w):
            if y == r.y or y == r.y + r.h - 1:
                grid[y][x] = TILE_WALL_H
            elif x == r.x or x == r.x + r.w - 1:
                grid[y][x] = TILE_WALL_V
            else:
                grid[y][x] = TILE_FLOOR


def generate_rooms(grid, rng, minw, minh, maxw, maxh):
    rooms = []
    table = {}
    cell_w = MAP_W // GRID_W
    cell_h = MAP_H // GRID_H

    for gy in range(GRID_H):
        for gx in range(GRID_W):
            if chance(rng, PROB_ROOM):
                max_w = min(maxw, cell_w - 2)
                max_h = min(maxh, cell_h - 2)
                if max_w < minw or max_h < minh:
                    continue

                w = rand_range(rng, minw, max_w)
                h = rand_range(rng, minh, max_h)
                x = gx * cell_w + rand_range(rng, 1, cell_w - w - 1)
                y = gy * cell_h + rand_range(rng, 1, cell_h - h - 1)

                r = Room(x, y, w, h, gx, gy)
                carve_room(grid, r)
                rooms.append(r)
                table[(gx, gy)] = r

    return rooms, table


def get_door(rng, room, direction):
    if room.doors[direction]:
        return room.doors[direction]

    if direction == "E":
        d = (room.x + room.w - 1, rand_range(rng, room.y + 1, room.y + room.h - 2))
    elif direction == "W":
        d = (room.x, rand_range(rng, room.y + 1, room.y + room.h - 2))
    elif direction == "N":
        d = (rand_range(rng, room.x + 1, room.x + room.w - 2), room.y)
    else:
        d = (rand_range(rng, room.x + 1, room.x + room.w - 2), room.y + room.h - 1)

    room.doors[direction] = d
    return d


def door_outside(room, x, y):
    if x == room.x:
        return x - 1, y
    if x == room.x + room.w - 1:
        return x + 1, y
    if y == room.y:
        return x, y - 1
    if y == room.y + room.h - 1:
        return x, y + 1


def dig_corridor(grid, rng, x1, y1, x2, y2):
    x, y = x1, y1
    if chance(rng, PROB_HALF):
        while x != x2:
            if grid[y][x] == TILE_EMPTY:
                grid[y][x] = TILE_CORRIDOR
            x += 1 if x2 > x else -1
        while y != y2:
            if grid[y][x] == TILE_EMPTY:
                grid[y][x] = TILE_CORRIDOR
            y += 1 if y2 > y else -1
    else:
        while y != y2:
            if grid[y][x] == TILE_EMPTY:
                grid[y][x] = TILE_CORRIDOR
            y += 1 if y2 > y else -1
        while x != x2:
            if grid[y][x] == TILE_EMPTY:
                grid[y][x] = TILE_CORRIDOR
            x += 1 if x2 > x else -1


def connect(grid, rng, a, b, direction):
    opposite = {"E": "W", "W": "E", "N": "S", "S": "N"}
    d1 = get_door(rng, a, direction)
    d2 = get_door(rng, b, opposite[direction])

    grid[d1[1]][d1[0]] = TILE_DOOR
    grid[d2[1]][d2[0]] = TILE_DOOR

    o1 = door_outside(a, *d1)
    o2 = door_outside(b, *d2)

    grid[o1[1]][o1[0]] = TILE_CORRIDOR
    grid[o2[1]][o2[0]] = TILE_CORRIDOR

    dig_corridor(grid, rng, o1[0], o1[1], o2[0], o2[1])


def connect_neighbors(grid, rng, table):
    for (gx, gy), r in table.items():
        right = (gx + 1, gy)
        down = (gx, gy + 1)

        if right in table and chance(rng, PROB_LINK):
            connect(grid, rng, r, table[right], "E")
        if down in table and chance(rng, PROB_LINK):
            connect(grid, rng, r, table[down], "S")


def random_floor(grid, rng):
    floors = [(x, y) for y, row in enumerate(grid) for x, c in enumerate(row) if c == TILE_FLOOR]
    return floors[rand_index(rng, len(floors))] if floors else None


def reachable_tiles(grid, start):
    stack = [start]
    visited = {start}
    h = len(grid)
    w = len(grid[0])

    while stack:
        x, y = stack.pop()
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited:
                if grid[ny][nx] in (TILE_FLOOR, TILE_CORRIDOR, TILE_DOOR):
                    visited.add((nx, ny))
                    stack.append((nx, ny))
    return visited


def place_stairs(grid, rng):
    up = random_floor(grid, rng)
    if not up:
        return
    reachable = reachable_tiles(grid, up)
    # Sort by coordinates before choosing so the result does not depend on set iteration order.
    candidates = sorted(p for p in reachable if grid[p[1]][p[0]] == TILE_FLOOR)
    if candidates:
        down = candidates[rand_index(rng, len(candidates))]
        grid[up[1]][up[0]] = TILE_STAIR_UP
        grid[down[1]][down[0]] = TILE_STAIR_DN


def count_tiles(grid, target):
    return sum(row.count(target) for row in grid)


def print_map(grid):
    border = '─' * (MAP_W + 2)
    print('┌' + border + '┐')
    for row in grid:
        print('│ ' + "".join(row) + ' │')
    print('└' + border + '┘')
    print("Legend: space=empty  -=horizontal wall  |=vertical wall  .=floor  #=corridor  +=door  <=up stairs  >=down stairs")


def generate(seed, minw, minh, maxw, maxh):
    rng = RNG(seed)

    grid = make_grid()
    rooms, table = generate_rooms(grid, rng, minw, minh, maxw, maxh)
    connect_neighbors(grid, rng, table)
    place_stairs(grid, rng)

    n_conn = len(rooms)
    n_corr = count_tiles(grid, TILE_CORRIDOR)
    n_door = count_tiles(grid, TILE_DOOR)

    print(f"seed={seed}  rooms={n_conn}  corridors={n_corr} doors={n_door}")
    print(f"  size={minw}-{maxw}x{minh}-{maxh}  grid={GRID_W}x{GRID_H}")
    print_map(grid)


def run_sim(minw, minh, maxw, maxh):
    """Generate rooms and corridors for all 256 seeds and print statistics."""
    conn_counts = Counter()
    corr_total = 0
    door_total = 0
    total = 256

    for seed in range(total):
        rng = RNG(seed)
        grid = make_grid()
        rooms, table = generate_rooms(grid, rng, minw, minh, maxw, maxh)
        connect_neighbors(grid, rng, table)

        n_conn = len(rooms)
        conn_counts[n_conn] += 1
        corr_total += count_tiles(grid, TILE_CORRIDOR)
        door_total += count_tiles(grid, TILE_DOOR)

    print(f"All {total} seeds  size={minw}-{maxw}x{minh}-{maxh}  grid={GRID_W}x{GRID_H}")
    print()
    print(f"{'Connected':>10}  {'Count':>5}  {'Share':>6}  Distribution")
    for n in sorted(conn_counts):
        bar = '█' * (conn_counts[n] * 40 // total)
        print(f"    {n:2d} rooms  {conn_counts[n]:3d}  {conn_counts[n]/total*100:5.1f}%  {bar}")

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
        description='NES-style dungeon generator (grid layout)',
        epilog="""Examples:
  python3 nes_dungeon_sim_grid.py            # Random seed
  python3 nes_dungeon_sim_grid.py 42         # Specify a seed
  python3 nes_dungeon_sim_grid.py --sim      # Statistics for all 256 seeds

Divide the map into a fixed 4x3 grid and probabilistically create rooms and
connect adjacent rooms. The RNG uses only 8-bit lookup tables, like an
NES-style implementation.""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('seed', nargs='?', type=seed_value, default=None, metavar='SEED', help='Random seed, 0-255 (random if omitted)')
    parser.add_argument('--minw', type=int, default=ROOM_MIN, metavar='N', help='Minimum room width, including walls (default: 4)')
    parser.add_argument('--minh', type=int, default=ROOM_MIN, metavar='N', help='Minimum room height, including walls (default: 4)')
    parser.add_argument('--maxw', type=int, default=ROOM_MAX, metavar='N', help='Maximum room width, including walls (default: 8)')
    parser.add_argument('--maxh', type=int, default=ROOM_MAX, metavar='N', help='Maximum room height, including walls (default: 8)')
    parser.add_argument('--sim', action='store_true', help='Collect statistics across all 256 seeds')
    args = parser.parse_args()

    if args.sim:
        run_sim(args.minw, args.minh, args.maxw, args.maxh)
    else:
        seed = args.seed if args.seed is not None else random.randint(0, 255)
        generate(seed, args.minw, args.minh, args.maxw, args.maxh)


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
