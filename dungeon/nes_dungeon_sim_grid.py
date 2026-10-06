#!/usr/bin/env python3
"""
nes_dungeon_sim_grid.py -- NES風ダンジョン生成シミュレータ (グリッド分割方式)

用途:
    32x30 のマップを固定の 4x3 グリッドに分割し、各セルに確率で部屋を作り、
    隣り合う部屋を確率で通路 (L 字) でつないで、ダンジョンを文字で表示します。
    --sim で全 256 シードの統計 (部屋数・通路/扉の平均) を集計できます。
入出力:
    入力: シード 0〜255 (省略時はランダム) と部屋サイズのオプション
    出力: 標準出力にマップと統計を書き出します
使用例:
    python3 nes_dungeon_sim_grid.py            # ランダムシード
    python3 nes_dungeon_sim_grid.py 42         # シード指定
    python3 nes_dungeon_sim_grid.py --sim      # 全 256 シードの統計
依存: 標準ライブラリのみ
"""

import argparse
import os
import random
import sys
from collections import Counter
from pathlib import Path

# =============================================================================
# 定数
# =============================================================================
MAP_W = 32
MAP_H = 30

GRID_W = 4
GRID_H = 3

ROOM_MIN = 4
ROOM_MAX = 8

# 確率は 8bit 乱数との比較 (乱数 < 閾値) で表す。確率 = 閾値 / 256
PROB_ROOM = 230   # セルに部屋を作る確率 (約 0.9)
PROB_LINK = 205   # 隣り合う部屋を通路でつなぐ確率 (約 0.8)
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
# 乱数 (NES 相当: 8bit の表引き・XOR・比較・減算だけで構成)
# =============================================================================
# 0x00〜0xFF を 1 回ずつ含む並べ替え (256 要素)
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
# 0x34 を除く 0x00〜0xFF を 1 回ずつ含む (255 要素)
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
    """8bit の剰余 (減算の繰り返し。b が 0 のときは 0)"""
    a, b = a & 0xFF, b & 0xFF
    if b == 0:
        return 0
    while a >= b:
        a = (a - b) & 0xFF
    return a


class RNG:
    """2 本の表を周期 256 / 255 で読み、XOR した 8bit 値を返す乱数

    seed (0〜255) は 2 本の読み出し位置の初期値を決める。
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
    """8bit 乱数が threshold 未満なら True (確率 threshold/256)"""
    return rng.next() < threshold


def rand_range(rng, lo, hi):
    """lo〜hi (両端を含む) の整数。幅 (hi-lo+1) は 255 以下"""
    return lo + mg_mod(rng.next(), hi - lo + 1)


def rand_index(rng, n):
    """0〜n-1 の整数 (n は 1 以上 65535 以下)。

    候補数が 255 を超えうるので、2 バイトを連結した 16bit 値を減算の繰り返しで剰余にする。
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
    # 集合の走査順に依存しないよう、座標順に並べてから選ぶ
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
    print("凡例:  空  -壁  |壁  .床  #通路  +扉  <上り  >下り")


def generate(seed, minw, minh, maxw, maxh):
    rng = RNG(seed)

    grid = make_grid()
    rooms, table = generate_rooms(grid, rng, minw, minh, maxw, maxh)
    connect_neighbors(grid, rng, table)
    place_stairs(grid, rng)

    n_conn = len(rooms)
    n_corr = count_tiles(grid, TILE_CORRIDOR)
    n_door = count_tiles(grid, TILE_DOOR)

    print(f"seed={seed}  {n_conn}室生成  通路{n_corr} 扉{n_door}")
    print(f"  size={minw}-{maxw}x{minh}-{maxh}  grid={GRID_W}x{GRID_H}")
    print_map(grid)


def run_sim(minw, minh, maxw, maxh):
    """全 256 シードで部屋配置と通路を生成し、統計を表示する"""
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

    print(f"全{total}seed  size={minw}-{maxw}x{minh}-{maxh}  grid={GRID_W}x{GRID_H}")
    print()
    print(f"{'接続室数':>6}  {'件数':>4}  {'割合':>6}  分布")
    for n in sorted(conn_counts):
        bar = '█' * (conn_counts[n] * 40 // total)
        print(f"    {n:2d}室  {conn_counts[n]:3d}件  {conn_counts[n]/total*100:5.1f}%  {bar}")

    print()
    print(f"--- 通路統計 (全{total}seed平均) ---")
    print(f"  通路タイル: {corr_total/total:.1f}  扉タイル: {door_total/total:.1f}")


def seed_value(text):
    """argparse 用: 0〜255 のシード"""
    value = int(text)
    if not 0 <= value <= 255:
        raise argparse.ArgumentTypeError("0〜255 の整数を指定してください")
    return value


def main():
    parser = argparse.ArgumentParser(
        prog=Path(__file__).name,
        description='NES風ダンジョンシミュレータ (グリッド分割方式)',
        epilog="""例:
  python3 nes_dungeon_sim_grid.py            ← ランダムシード
  python3 nes_dungeon_sim_grid.py 42         ← シード指定
  python3 nes_dungeon_sim_grid.py --sim      ← 全256シードの統計

マップを固定グリッド(4x3)に分割し、確率で部屋を生成・隣接接続します。
乱数は 8bit の表引きだけで構成した NES 相当のものです。""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('seed', nargs='?', type=seed_value, default=None, metavar='SEED', help='乱数シード 0〜255 (省略時はランダム)')
    parser.add_argument('--minw', type=int, default=ROOM_MIN, metavar='N', help='部屋幅の最小値 壁込み (既定: 4)')
    parser.add_argument('--minh', type=int, default=ROOM_MIN, metavar='N', help='部屋高さの最小値 壁込み (既定: 4)')
    parser.add_argument('--maxw', type=int, default=ROOM_MAX, metavar='N', help='部屋幅の最大値 壁込み (既定: 8)')
    parser.add_argument('--maxh', type=int, default=ROOM_MAX, metavar='N', help='部屋高さの最大値 壁込み (既定: 8)')
    parser.add_argument('--sim', action='store_true', help='全256シードを網羅して統計を集計')
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
        # 出力先 (head など) が先に閉じた場合は、エラーを出さずに終了する
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(1)


if __name__ == '__main__':
    run()
