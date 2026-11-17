#!/usr/bin/env python3
"""予告イントロ（teaser-cards）の下書きを組む。

  python3 recipes/teaser-cards/build.py --footage a.mp4 [b.mp4 ...] --cards cards.json
      [--bpm 120] [--beats 1] [--name 下書き名] [--drafts 置き場]

cards.json の例（cards.sample.json）:
{
  "cards": ["新しい", "シリーズが", "{はじまる}", "まもなく"],   # {…} の札だけ白地・黒文字にする
  "title": ["COMING", "SOON"],          # 2語目を差し色にする
  "accent": "#FFD400",
  "sub": "STAY TUNED",                   # 題の下の小さい文字（省略可）
  "script": "Original Series"            # 筆記体の一言（省略可）
}
文字の札と映像を拍に合わせて交互に出し、最後に題で止める。
札の地にする単色の動画は、cards.json と同じフォルダの teaser_assets/ に作る。
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import build  # noqa: E402

CARD_LOOK = {"font": "gothic-heavy", "spacing": 6, "no_shadow": True}
TITLE_LOOK = {"font": "serif-bold", "spacing": 1, "no_shadow": True}
SUB_LOOK = {"font": "gothic", "spacing": 8, "no_shadow": True}
SCRIPT_LOOK = {"font": "script", "no_shadow": True}
END_SECONDS = 2.5


def solid(color, out_dir, dur):
    """単色の縦長動画を作る（札の地）。"""
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, f"solid_{color.lstrip('#')}_{dur:.3f}.mp4")
    if not os.path.exists(p):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        f"color=c=0x{color.lstrip('#')}:s=1080x1920:r=30:d={dur + 0.1:.3f}",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", p], check=True)
    return p


def probe(f):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--footage", nargs="+", required=True)
    ap.add_argument("--cards", required=True)
    ap.add_argument("--bpm", type=float, default=120)
    ap.add_argument("--beats", type=int, default=1, help="札・映像それぞれを何拍出すか")
    ap.add_argument("--name", default="teaser_cards")
    ap.add_argument("--drafts")
    a = ap.parse_args()

    cfg = json.load(open(a.cards))
    step = round(60 / a.bpm * a.beats, 3)
    assets = os.path.join(os.path.dirname(os.path.abspath(a.cards)), "teaser_assets")
    feet = [os.path.abspath(os.path.expanduser(f)) for f in a.footage]
    pos = {f: 0.0 for f in feet}

    clips, texts, t = [], [], 0.0
    for i, card in enumerate(cfg["cards"]):
        inverse = card.startswith("{") and card.endswith("}")
        clips.append({"file": solid("#FFFFFF" if inverse else "#000000", assets, step), "src_start": 0, "dur": step})
        texts.append({"text": card.strip("{}"), "start": t, "dur": step, "size": 10,
                      "color": "#000000" if inverse else "#FFFFFF", "y": 0, "track": "card", "look": CARD_LOOK})
        t += step
        f = feet[i % len(feet)]
        if pos[f] + step > probe(f):
            pos[f] = 0.0
        clips.append({"file": f, "src_start": round(pos[f], 3), "dur": step})
        pos[f] += step
        t += step

    # 最後: 黒地に題（2語目を差し色）、小さい一言、筆記体
    clips.append({"file": solid("#000000", assets, END_SECONDS), "src_start": 0, "dur": END_SECONDS})
    w1, w2 = cfg["title"]
    texts += [{"text": w1, "start": t, "dur": END_SECONDS, "size": 22, "color": "#FFFFFF", "y": 0.12,
               "track": "title", "look": TITLE_LOOK, "intro": "blur", "intro_dur": 0.3},
              {"text": w2, "start": t, "dur": END_SECONDS, "size": 22, "color": cfg.get("accent", "#FFD400"),
               "y": -0.04, "track": "title2", "look": TITLE_LOOK, "intro": "blur", "intro_dur": 0.3}]
    if cfg.get("sub"):
        texts.append({"text": cfg["sub"], "start": round(t + 0.3, 3), "dur": END_SECONDS - 0.3, "size": 6,
                      "color": "#FFFFFF", "y": -0.17, "track": "sub", "look": SUB_LOOK})
    if cfg.get("script"):
        texts.append({"text": cfg["script"], "start": round(t + 0.5, 3), "dur": END_SECONDS - 0.5, "size": 12,
                      "color": "#FFFFFF", "y": -0.3, "track": "script", "look": SCRIPT_LOOK,
                      "intro": "blur", "intro_dur": 0.4})

    spec = {"name": a.name, "ratio": "9:16", "clips": clips, "texts": texts, "stroke": {"width": 0, "bold": False}}
    build.build(spec, base=os.getcwd(), drafts=a.drafts)
    print(f"1拍 {60 / a.bpm:.3f} 秒・全体 {t + END_SECONDS:.2f} 秒")


if __name__ == "__main__":
    main()
