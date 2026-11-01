# skt-tool

A collection of small, standalone Python utilities for NES development, fonts, and MML.

[日本語版はこちら](README.ja.md)

## Tools

| Tool | Description |
|---|---|
| [`ca65/bin2ca65.py`](ca65/bin2ca65.py) | Convert a binary file to ca65 `.byte` table source. |
| [`ca65/ca65_rnd_table.py`](ca65/ca65_rnd_table.py) | Generate a ca65 random lookup table containing a shuffled sequence of byte values. |
| [`dungeon/nes_dungeon_sim_grid.py`](dungeon/nes_dungeon_sim_grid.py) | NES-style dungeon generator using a fixed grid layout. |
| [`dungeon/nes_dungeon_sim_aabb.py`](dungeon/nes_dungeon_sim_aabb.py) | NES-style dungeon generator using AABB room placement rejection. |
| [`font/font2png.py`](font/font2png.py) | Generate an 8x8-tile PNG and optional text file from a font. |
| [`mml/mml_quantize.py`](mml/mml_quantize.py) | Quantize and simplify MML to {2, 4, 8, 16} note values. |

## Requirements

- Python 3.9 or later
- Pillow is required only by `font2png.py`. Install it with `python3 -m pip install pillow`, or run the script with [`uv`](https://docs.astral.sh/uv/) to resolve its inline dependency.

## Examples

Run commands from the repository root:

```sh
python3 ca65/bin2ca65.py palette.pal --label PALETTE
python3 ca65/ca65_rnd_table.py 256 --seed 0x12345678
python3 dungeon/nes_dungeon_sim_aabb.py 42
python3 dungeon/nes_dungeon_sim_grid.py --sim
python3 font/font2png.py font.ttf --subset -o out/
python3 mml/mml_quantize.py song.mml --judge
```

For options and detailed usage, run any script with `-h`:

```sh
python3 path/to/script.py -h
```

The dungeon simulators use an NES-style random number generator built from 8-bit lookup tables. Seeds range from 0 to 255; `--sim` reports statistics for all 256 seeds.

## License

MIT. See [LICENSE](LICENSE).
