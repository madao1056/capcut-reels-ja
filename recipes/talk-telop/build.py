#!/usr/bin/env python3
"""顔出しトークのテロップ（talk-telop）の下書きを組む。

  python3 recipes/talk-telop/build.py --video talk.mov --captions captions.json \\
      [--src-start 0] [--dur 秒] [--name 下書き名] [--drafts 置き場] [--shadow-color #RRGGBB]

captions.json の例（時刻はクリップの頭からの秒。label は省略可。同じ label が続く間はラベルを出したままにする）:
[
  {"start": 0.0, "end": 2.5, "label": "文字色", "text": "基本は白"},
  {"start": 2.5, "end": 5.0, "label": "フォント", "text": "明朝の太字にする"}
]
影の色を省略すると、映像の胸元（服）の色を取って使う。
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import build  # noqa: E402

MAX_LINE = 15        # 1行の文字数
MAX_LINES = 2        # 3行以上にしない
NO_LINE_HEAD = set("、。，．・：；？！ー）」』】ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮ")

# 位置（画面の縦の真ん中のすぐ下に答え、その真上にラベル）
ANSWER_Y = -0.14     # 画面の上から約57%（1行のとき）
LABEL_GAP = 0.13     # 答えの1行目の上端からラベルまで
LINE_H = 0.075       # 答え（18）の1行の高さの半分（座標の単位）

ANSWER_LOOK = {"font": "mincho", "spacing": -1, "opacity": 0.85, "shadow_alpha": 0.5, "kana_scale": 0.8}
LABEL_LOOK = {"font": "gothic", "bg_color": "#333333", "bg_alpha": 0.7, "bg_radius": 0.3, "bg_pad": 0.18,
              "no_shadow": True}


def _is_kanji(ch):
    return "\u4e00" <= ch <= "\u9fff" or ch in "々〆"


def _cut_rank(text, i):
    """i 文字目の前で改行するときの良さ。0=句読点・助詞のあと、1=かな→漢字の切れ目、None=不可。"""
    a, b = text[i - 1], text[i]
    if b in NO_LINE_HEAD:
        return None
    if a in "、。！？」』）":
        return 0
    if a in "のはをがにでともへやか" and not (a in "でとかやへもに" and "\u3041" <= b <= "\u309f"):
        return 0                            # 助詞のあと（で・と・か等の次がかなだと言葉の途中のことが多い）
    if not _is_kanji(a) and _is_kanji(b):
        return 1                            # 送りがなの途中で切れることがあるので後回し
    return None


def wrap(text):
    """15文字を超えたら、真ん中に近い言葉の切れ目で2行にする。3行以上にはしない。"""
    if "\n" in text:
        lines = text.split("\n")
    elif len(text) <= MAX_LINE:
        lines = [text]
    else:
        ok = [i for i in range(1, len(text)) if len(text) - i <= MAX_LINE and i <= MAX_LINE]
        cands = [i for i in ok if _cut_rank(text, i) == 0] or [i for i in ok if _cut_rank(text, i) == 1]
        if not cands:
            cands = [i for i in range(1, len(text)) if len(text) - i <= MAX_LINE and i <= MAX_LINE
                     and text[i] not in NO_LINE_HEAD]
        if not cands:
            raise SystemExit(f"{MAX_LINE}文字×{MAX_LINES}行に収まりません。分けてください: {text}")
        mid = len(text) / 2
        cut = min(cands, key=lambda i: abs(i - mid))
        lines = [text[:cut], text[cut:]]
    if len(lines) > MAX_LINES or any(len(l) > MAX_LINE for l in lines):
        raise SystemExit(f"{MAX_LINE}文字×{MAX_LINES}行に収まりません。分けてください: {text}")
    return "\n".join(lines)


def shirt_color(video, t):
    """映像の胸元（下の中央）の平均色を #RRGGBB で返す。少し暗くして影に使う。"""
    vf = "crop=iw*0.5:ih*0.18:iw*0.25:ih*0.72,scale=1:1"
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", video, "-frames:v", "1", "-vf", vf,
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    if r.returncode or len(r.stdout) < 3:
        return "#222222"
    return "#" + "".join(f"{int(c * 0.7):02X}" for c in r.stdout[:3])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--captions", required=True)
    ap.add_argument("--src-start", type=float, default=0.0)
    ap.add_argument("--dur", type=float)
    ap.add_argument("--size", type=float, default=18, help="答えの文字の大きさ（CapCut の数値）")
    ap.add_argument("--shadow-color")
    ap.add_argument("--name", default="talk_telop")
    ap.add_argument("--drafts")
    a = ap.parse_args()

    video = os.path.abspath(os.path.expanduser(a.video))
    caps = json.load(open(a.captions))
    dur = a.dur or max(c["end"] for c in caps)
    shadow = a.shadow_color or shirt_color(video, a.src_start + dur / 2)

    texts = []
    # 答え: 項目ごとに差し替え、ふわっと出す。2行のときは下へ伸ばし、1行目の位置をそろえる
    for c in caps:
        body = wrap(c["text"])
        c["_lines"] = body.count("\n") + 1
        texts.append({"text": body, "start": c["start"], "dur": round(c["end"] - c["start"], 3),
                      "size": a.size, "y": round(ANSWER_Y - (c["_lines"] - 1) * LINE_H, 3), "intro": "blur", "intro_dur": 0.4,
                      "look": {**ANSWER_LOOK, "shadow_color": shadow}})
    # ラベル: 同じラベルが続く間は出したまま
    run = None
    for c in caps + [{"label": None, "start": dur, "end": dur}]:
        lab = c.get("label")
        if run and lab == run["text"] and abs(c["start"] - (run["start"] + run["dur"])) < 1e-6:
            run["dur"] = round(c["end"] - run["start"], 3)
            continue
        if run:
            texts.append(run)
        run = {"text": lab, "start": c["start"], "dur": round(c["end"] - c["start"], 3), "size": round(a.size * 0.6),
               "y": round(ANSWER_Y + LABEL_GAP, 3), "track": "label", "look": LABEL_LOOK} if lab else None

    spec = {"name": a.name, "ratio": "9:16",
            "clips": [{"file": video, "src_start": a.src_start, "dur": dur}],
            "texts": texts,
            "stroke": {"width": 0, "bold": True}}
    build.build(spec, base=os.getcwd(), drafts=a.drafts)
    print(f"影の色: {shadow}")


if __name__ == "__main__":
    main()
