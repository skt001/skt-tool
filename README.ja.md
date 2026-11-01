# skt-tool

NES 開発、フォント、MML 用の小さな Python ツール集です。各スクリプトは単体で動作します。

[English README](README.md)

## ツール一覧

| ツール | 内容 |
|---|---|
| [`ca65/bin2ca65.py`](ca65/bin2ca65.py) | バイナリファイルを ca65 の `.byte` テーブルに変換します。 |
| [`ca65/ca65_rnd_table.py`](ca65/ca65_rnd_table.py) | バイト値を並べ替えた乱数参照テーブルを ca65 形式で生成します。 |
| [`dungeon/nes_dungeon_sim_grid.py`](dungeon/nes_dungeon_sim_grid.py) | 固定グリッド方式の NES 風ダンジョン生成シミュレーターです。 |
| [`dungeon/nes_dungeon_sim_aabb.py`](dungeon/nes_dungeon_sim_aabb.py) | AABB による部屋配置の棄却方式を使った NES 風ダンジョン生成シミュレーターです。 |
| [`font/font2png.py`](font/font2png.py) | フォントから 8x8 タイルの PNG と任意のテキストファイルを生成します。 |
| [`mml/mml_quantize.py`](mml/mml_quantize.py) | MML を {2, 4, 8, 16} 分音符に量子化・簡略化します。 |

## 必要環境

- Python 3.9 以上
- `font2png.py` のみ Pillow が必要です。`python3 -m pip install pillow` で導入するか、[`uv`](https://docs.astral.sh/uv/) でスクリプトを実行すると、インライン依存関係が解決されます。

## 使用例

リポジトリのルートディレクトリから実行してください。

```sh
python3 ca65/bin2ca65.py palette.pal --label PALETTE
python3 ca65/ca65_rnd_table.py 256 --seed 0x12345678
python3 dungeon/nes_dungeon_sim_aabb.py 42
python3 dungeon/nes_dungeon_sim_grid.py --sim
python3 font/font2png.py font.ttf --subset -o out/
python3 mml/mml_quantize.py song.mml --judge
```

各スクリプトのオプションと詳しい使い方は、`-h` を指定して確認できます。

```sh
python3 path/to/script.py -h
```

ダンジョンシミュレーターは 8bit の参照テーブルを使う NES 風の乱数生成器を使用します。シードは 0〜255 で、`--sim` を指定すると全 256 シードの統計を集計します。

## ライセンス

MIT License — 詳細は [LICENSE](LICENSE) を参照してください。
