# capcut-reels-ja

AI（Claude Code）に素材と指示を渡すと、**CapCut デスクトップ版で開ける日本語のショート動画の下書き**ができるスキルです。
テロップ・カット割り・効果音・動きまで入った状態で CapCut が開くので、あとは画面で微調整して書き出すだけです。

- 対応: Mac 版 CapCut 9.8.0（それ以外の版・Windows は未確認）
- 作れるもの: Instagram リール・TikTok・YouTube ショート向けの縦型動画（9:16）
- 中身: 日本語リール向けの共通ルール（テロップ・構成・音・媒体ごとの注意）と、見せ方・構成の型

> CapCut の下書きファイルを外から書き換える、非公式の仕組みです。CapCut の更新で動かなくなることがあります。大事な下書きは必ずコピーを取ってから使ってください。

## できること（例）
- 横長の映像を縦の画面の中央に置き、上下の帯にテロップを入れる
- 結果を先に見せて、「3分前…」から短いカットで山場に持っていく
- カメラに向けて指を開くと、指の間の文字が大きくなる（指先は自動で検出）
- 顔出しで話す動画に、質問ラベル＋明朝の答えの落ち着いたテロップを入れる（影の色は服から自動で取る）
- 文字を円に並べてぐるぐる回す（人物の後ろに回すところは CapCut の画面で切り抜き）
- 飲食・美容・農業・士業などの業種ごとの構成のひな形

## 準備するもの
| もの | 何に使う | 入れ方 |
|---|---|---|
| CapCut デスクトップ版（Mac） | 下書きを開いて仕上げる | 公式サイトから。**自動更新は切っておく** |
| Claude Code | AI に作業を頼む | 公式の案内どおり |
| Node.js（18 以上） | capcut-cli を動かす | 公式サイトか Homebrew |
| capcut-cli | 下書きを読み書きする | `npm install -g capcut-cli` |
| Python 3 | このスキルの道具 | Mac に入っている物でよい |
| ffmpeg（任意） | 素材を調べる・見本の素材を作る | `brew install ffmpeg` |
| uv（任意） | 指先の自動検出（pinch-text） | `brew install uv` |

## 入れ方
1. このリポジトリを Claude Code のスキルの置き場にコピーします。
   ```bash
   git clone https://github.com/madao1056/capcut-reels-ja ~/.claude/skills/capcut-reels-ja
   ```
2. capcut-cli を入れて、動くか確かめます。
   ```bash
   npm install -g capcut-cli
   ```
   ```bash
   capcut --version
   ```
3. CapCut を一度起動して、空のプロジェクトを1つ作って閉じます（下書きの置き場ができます）。

## 試してみる（自分の素材を使わずに）
1. 見本用の素材を作ります（色と図形だけの動画と、合成した音）。
   ```bash
   ~/.claude/skills/capcut-reels-ja/examples/make_assets.sh
   ```
2. **CapCut を終了**してから、見本の下書きを組みます。
   ```bash
   cd ~/.claude/skills/capcut-reels-ja && python3 lib/build.py recipes/result-first/template.json
   ```
3. CapCut を開くと、ホームに `result_first_sample` ができています。開いて再生してみてください。

## 自分の素材で作る
Claude Code に、素材のフォルダと作りたいものを伝えます。

```
~/Movies/素材/新メニュー の動画で、CapCut のリールの下書きを作って。
飲食店の新メニューの紹介。15秒くらい。
```

AI が素材を見て、構成表（カットごとの時間・映像・テロップ）を出してきます。直したい所を伝えて OK したら、下書きができます。

## 気をつけること
- **CapCut が「インターフェースをロード中」のまま開かない時**: CapCut を強制終了して `python3 lib/crj.py fill-effects <下書きのフォルダ>` を流してから開き直します（切り替えや文字の動きの効果を、ネットから取り直そうとして止まっていることがあります）。詳しくは `references/safety.md`
- **CapCut を開いたまま下書きを書かせない**。CapCut の自動保存で変更が消えます（道具は、CapCut の起動中は書き込みを止めます）
- **CapCut の自動更新を切る**。新しい版では、外から書いた下書きを開けないという報告があります
- 素材は `~/Desktop`・`~/Documents`・`~/Downloads` 以外（例: `~/Movies/素材/`）に置くと安全です
- BGM・効果音は、使ってよいと確かめた物だけ使ってください
- 媒体ごとの尺の上限や、画面のどこがボタンに隠れるかは変わることがあります（`references/platforms.md` は 2026年11月時点の調べ）

## 中身
```
SKILL.md        AI が最初に読む要点と型の一覧
references/     共通ルールの詳細（作業の流れ・安全運用・下書きの落とし穴・テロップ・構成・音・媒体）
recipes/        型（1つの見せ方・構成＝1フォルダ）
lib/            capcut-cli で足りない操作を補う道具
examples/       見本用の合成素材を作るスクリプト
```

## 型を足す
`recipes/<名前>/` に README.md（使う場面・構成・素材の条件・変えられる所・作り方・確認のポイント・由来）と recipe.json を置き、`recipes/catalog.json` と SKILL.md の一覧に1行足します。
他人の解説動画から学んだ見せ方は、自分の言葉で一般化して書いてください（文言・画像・出典のアカウントは載せない）。

## 謝辞・ライセンス
- 下書きの読み書きは [capcut-cli](https://github.com/renezander030/capcut-cli)（MIT）を使っています
- CapCut は Bytedance の製品です。このリポジトリは CapCut の公式の物ではありません
- ライセンス: MIT（LICENSE）
