# 下書き形式の落とし穴

capcut-cli（0.34.0）のまま使うと CapCut 9.8.0 で思った通りにならない所と、`lib/` での直し方。

| 症状 | 原因 | 直し方 |
|---|---|---|
| 並べ替えが反映されない | メイン動画トラックは、開始時刻ではなく配列の順番で詰めて並ぶ | `crj.py reorder`（配列ごと入れ替えて時刻を詰め直す） |
| 切り出した位置ではなく、素材の頭から再生される | `add-video` に長さを渡すと、素材全体の長さがその秒数で登録される | `crj.py add-clip`（長さを渡さず追加して `trim`） |
| 作成済みの下書きを縦長にできない | キャンバスを変えるコマンドが無い | `crj.py set-canvas <draft> 9:16` |
| 拡大率・位置の固定値を設定できない | 静的な拡大・位置のコマンドが無い | `crj.py set-clip <draft> <id> --scale 4 --y -0.27` |
| テキストの拡大キーフレームが効かない | `uniform_scale` で書かれ、9.8.0 は無視する | `crj.py keyframes`（`scale` を `scale_x` と `scale_y` に分けて書く） |
| 縁取り・太字が表示されない | `text-style --border-*` は外側の項目にだけ書く。描画は文字スタイル側を見る | `crj.py text-stroke`（文字スタイルに縁と太字を書く） |
| 並べ替え・移動の後に全体の尺が合わない | 尺が再計算されない | `crj.py fix-duration` |
| 見出しテロップに「速すぎる」警告 | `lint` の日本語の基準が字幕向け（4文字/秒・7秒まで） | 見出しなら無視。字幕なら直す |
| `capcut segments` がエラー | 機械向け出力の不具合 | `-H` を付けて人向け出力で見る |
| CapCut で開くと「インターフェースをロード中」のまま止まる | 切り替え・文字アニメなどの効果の場所が空だと、CapCut がネットから取り直す。その取得が止まると先へ進まない | `crj.py fill-effects`（手元のキャッシュの場所を書く。`build.py` が自動で行う）。手元に無い効果は、CapCut の画面で一度使うとキャッシュされる |
| 簡易プレビューに拡大・テロップが出ない | `render` が拡大を反映せず、文字を描かない | CapCut の画面で確かめる |
| 映像のキーフレームが効かない（素材の途中から使う区間） | capcut-cli は区間の頭から数えた時刻で書くが、9.8.0 は素材の頭から数える。キーフレームが切り出し位置より前にあると見なされ、最後の値のまま止まる | `crj.py keyframes`（映像の区間は、素材の切り出し位置のぶん時刻をずらす） |
| 映像の不透明度のキーフレームを書いても透けない | 画面の「ブレンド」が切れている。入／切は映像の素材の `check_flag` の 8 | `crj.py keyframes`（不透明度を書くと 8 を足す） |
| 透け・影の色・背景の箱・書体を書いても見た目が変わらない | CapCut は影を文字スタイル側（`styles[].shadows`）で描き、背景の箱は素材の `check_flag` の印が無いと描かない | `crj.py text-look`（CapCut の画面で設定して保存された形に合わせて書く） |

本家で直るべきもの（拡大キーフレーム・縁取り・`segments`）は報告する。直ったら `lib/` から外す。

## 座標と大きさ
- 位置は画面の中央が 0、右と上が＋、端が ±1
- 画面の割合（左上 0〜1）の (fx, fy) から換算: `x = (fx − 0.5) × 2`、`y = (0.5 − fy) × 2`
- 横長（16:9）の素材を 9:16 に置くと、拡大率 1 で横幅に合う。縦いっぱいにするには約 3.16 倍
- テキストは 14pt・4文字・拡大率 1 で画面幅の約 1/3（9.8.0 の画面で 1 回測っただけ。文字数・書体で変わる）

## 時間の単位
下書きの中は マイクロ秒（1 秒 = 1,000,000）。capcut-cli には `1.5s` や `1500ms` で渡す。
CapCut は保存のときに音の長さなどを 1/30 秒単位に丸めることがある。

## タイムラインのファイル
- 新しい下書き: `draft_content.json`・`draft_info.json`・`template-2.tmp`
- CapCut で一度開いた下書き: 上に加えて `Timelines/<id>/` の中にも同じものができる
- どれか 1 つだけ書き換えると食い違う。`lib/crj.py` は全部を書き換える

## テキストの見た目（CapCut 9.8.0 の画面で設定して保存された形）
| 画面の設定 | 下書きの中 |
|---|---|
| フォント | 文字スタイル `styles[].font.path` と素材の `font_path`。macOS の書体ファイルを直接指せる（例: ヒラギノ明朝 ProN） |
| 太字 | `styles[].bold`（素材の `bold_width` 0.008） |
| 文字（文字間隔） | 素材の `letter_spacing`。画面の値の 1/20（−1 → −0.05） |
| 不透明度 | 素材の `global_alpha`（85% → 0.85） |
| シャドウ | `styles[].shadows[]`（`alpha`・`distance`・`angle`・`diffuse`＝不鮮明さ%÷600・色）と素材の `has_shadow` ほか。`check_flag` に 16 |
| 背景 | 素材の `background_style` 1・`background_color`・`background_alpha`・`background_round_radius`・`background_width/height`（余白）。`check_flag` に 32 |
| 文字ごとの大きさ | `styles[]` を文字の区間（`range`）ごとに分け、`size` を変える |
| 曲線 | 素材の `text_curve` = `{"enable": true, "angle": 強度の度数}`（360 で円）。`check_flag` に 128。背景と同時には使えない |
| キーフレームのイーズ | `position_y` 等に `easing`（ease-in・ease-out・ease-in-out）を付けると `FreeCurveInOut` と制御点で書かれ、CapCut で効く（text-drop で確認）。`scale` に付けたイーズは直線（`Line`）で書かれた。原因は未確認 |
| クリップのぼかし | 画面で映像に付けると、効果の段ではなく `materials.video_effects` の1件を映像の `extra_material_refs` から指す形（`bind_segment_id` は空）。強さは `adjust_params` の `effects_adjust_blur`（0〜1）。capcut-cli の `add-effect --bind` は効果の段に置く別の形で、画面の形と違う。`crj.py clip-blur` は画面の形で書く |
| HSL | `materials.hsl` に色ごと1件（`hsl_color_type` 1赤・2橙・3黄・4緑・5水色・6青・7紫・8赤紫、`hue`・`saturation`・`lightness` は画面の整数）。映像の `extra_material_refs` から指す。`crj.py clip-hsl` |
| ループ（出ている間くり返す動き） | `material_animations` の `sticker_animation` に `type: "loop"` の1件（`duration` が1周の長さ）。capcut-cli の `text-anim --combo` は入り・出が無いと書けないので `crj.py text-loop` で書く。「回転」は slug `rotate` |
| 段の重なり順 | `tracks` 配列の順番が下から上の重なり順。CapCut は開くたびに、配列の順から各セグメントの `track_render_index` を振り直す。文字も映像も同じ並びで、映像の段を文字の段より後ろに置けば文字の上に描かれる（`crj.py raise-track`）。その並びでは、タイムラインに文字の段が表示されない（描画は正しく、プレビューで文字を選べる。原因は未確認） |
| 透過の動画 | HEVC の透過（`hevc_videotoolbox -alpha_quality`、`.mov`・`hvc1`）も ProRes 4444（`yuva444p10le`）も、重ねる段に置くだけで透過として描かれる。ブレンドなどの設定は要らない（9.8.0 で確認） |
