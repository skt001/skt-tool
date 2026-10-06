# skt-tools

個人用の小さなツール集です。各スクリプトは単体で動作します。
`font2png.py` だけ Pillow が必要で、それ以外は標準ライブラリだけで動きます。

## ツール一覧

| ツール | 内容 |
|---|---|
| `ca65/bin2ca65.py` | バイナリファイルを ca65 の `.byte` テーブルに変換する |
| `ca65/ca65_rnd_table.py` | 0〜255 の並べ替え表 (乱数参照テーブル) を ca65 形式で生成する |
| `dungeon/nes_dungeon_sim_grid.py` | NES 風ダンジョン生成シミュレータ (グリッド分割方式) |
| `dungeon/nes_dungeon_sim_aabb.py` | NES 風ダンジョン生成シミュレータ (AABB 拒否法) |
| `font/font2png.py` | フォントから 8x8 タイルの PNG (と対応する txt) を生成する |
| `mml/mml_quantize.py` | MML を {2, 4, 8, 16} 分音符に量子化・簡略化する |

## 必要環境

- Python 3.9 以上
- `font2png.py` のみ Pillow: `pip install pillow`、または `uv run font/font2png.py ...` (依存を自動で導入)

## 使い方

詳しい説明とオプションは、各ツールの `-h` を見てください。

```sh
python3 ca65/bin2ca65.py palette.pal --label PALETTE
python3 ca65/ca65_rnd_table.py 256 --seed 0x12345678
python3 dungeon/nes_dungeon_sim_aabb.py 42
python3 dungeon/nes_dungeon_sim_grid.py --sim
python3 font/font2png.py font.ttf --subset -o out/
python3 mml/mml_quantize.py song.mml --judge
```

ダンジョンのシミュレータは、乱数を 8bit の表引きだけで組んだ NES 相当のものにしています。
シードは 0〜255 で、`--sim` で全 256 シードの統計を集計できます。

## ライセンス

[MIT License](LICENSE)
