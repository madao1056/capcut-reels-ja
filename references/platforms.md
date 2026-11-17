# 媒体ごとの尺・安全領域

2026-11-17 に調べた。媒体の決まりはよく変わるので、投稿前にアプリの画面で確かめる。
「公式」は各社のヘルプ・公式ブログで確かめた物、「第三者」は解説サイトの数値（近似）。

## 共通
- 書き出しは縦 9:16・1080×1920（CapCut の 9:16 の初期値）。3媒体とも縦長の短い動画として扱われる
- 3媒体とも、普通の投稿向けの安全領域の数値は公式に見つからなかった。下の数値は目安

## 尺
| 媒体 | 上限 | 区分 |
|---|---|---|
| YouTube ショート | 3分まで（正方形か縦長で3分以内ならショート扱い） | 公式 |
| Instagram リール | 3分まで投稿できる地域が広がっている。3分を超えると新しい人へのおすすめに載りにくいという説明がある | 公式（本文を直接読めず、検索の要約経由。未確認扱い） |
| TikTok | アップロードは最大10分〜60分の記述が混在 | 公式だが現行の上限は未確認 |

- 「伸びやすい尺」の公式な数値は無い。言いたいことが言えたら終わる（structure.md）
- YouTube の広告では、フィードで流れるのは最初の60秒という説明がある（公式・広告向け）

## 画面の隠れる所（1080×1920 の目安）
| 媒体 | 上 | 下 | 右 | 区分 |
|---|---|---|---|---|
| Instagram リール | 約15%（約290px） | 約10%（約190px）＋説明文 | ボタン列 | 第三者 |
| TikTok | 約120〜200px | 約250〜370px | 約120〜160px | 第三者。公式は広告向けの型紙だけ配布 |
| YouTube ショート | 未確認 | 未確認 | ボタン列（いいね・コメント・共有） | ボタンがある事だけ公式 |

迷ったら、テロップと見せたい物を **縦の中央 6割・横の中央 8割** に収める（3媒体の目安の内側。自分で決めた余裕込みの値）。
座標にすると、y は −0.6〜＋0.6、x は −0.8〜＋0.8（右のボタン列にかかる所は避ける）。

## 一覧（グリッド）での見え方
- Instagram のプロフィールの一覧は 3:4 で表示される（2025年に変更。第三者の報道経由）。9:16 の動画は上下が切れるので、表紙にしたい絵と文字は縦の中央に置く
- TikTok・YouTube の表紙の切り方は未確認

## 出典
- YouTube: support.google.com/youtube/answer/15424877、/answer/12779649、/answer/10059070、support.google.com/google-ads/answer/16041697
- Instagram: help.instagram.com/225190788256708、about.instagram.com/features/reels、creators.instagram.com/blog
- TikTok: tiktok.com/creators/creator-portal（Creating videos longer than one minute）、developers.tiktok.com/doc/content-posting-api-media-transfer-guide、ads.tiktok.com/help/article/tiktok-auction-in-feed-ads
- 第三者（目安の数値）: postfa.st、planoly.com、trymypost.com ほか
