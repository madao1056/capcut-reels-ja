#!/usr/bin/env python3
"""決めポーズで止める自己紹介（freeze-intro）の下書きを組む。

  python3 recipes/freeze-intro/build.py --video me.mov --freeze-at 5.0 --name-text はしぐち \\
      [--role-text 動画編集の人] [--play 2.0] [--hold 3.0] [--zoom 1.12] [--border 0.018] \\
      [--shutter a.mp3] [--name 下書き名] [--drafts 置き場]

動画を --play 秒だけ流し、--freeze-at のコマで止める。止めたコマは
  下: 少し暗く・ぼかした背景（止めたコマそのもの）
  上: 人物だけを切り抜き、紙の質感の白い縁と影を付けた静止画（透過の .mov）。ゆっくり寄る
  文字: 名前（大）と肩書き（小）
人物の切り抜きは macOS 標準の Vision（lib/cutout.py）。
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
import build  # noqa: E402
import cutout  # noqa: E402


def slow_out(v0, v1, dur, steps=6):
    """出だしが速く、終わりがゆっくりの寄り（スローアウト）。scale のイーズは CapCut で直線になるので点を刻む。"""
    rows = []
    for i in range(steps + 1):
        t = i / steps
        e = 1 - (1 - t) ** 3
        rows.append({"property": "scale", "time": round(dur * t, 3), "value": round(v0 + (v1 - v0) * e, 4)})
    return rows


def spec_for(a):
    if a.freeze_at < a.play:
        raise SystemExit("--freeze-at は --play 以上にしてください（止める前に流す秒数が足りません）")
    bg, fg = cutout.freeze(a.video, a.freeze_at, a.hold, border=a.border)
    start = round(a.freeze_at - a.play, 3)
    clips = []
    if a.play > 0:
        clips.append({"file": os.path.abspath(a.video), "src_start": start, "dur": a.play})
    clips.append({"file": bg, "src_start": 0, "dur": a.hold})
    texts = [{"text": a.name_text, "start": a.play + 0.25, "dur": a.hold - 0.25, "size": 22, "color": "#FFFFFF",
              "y": -0.55, "intro": "pop-up", "intro_dur": 0.3, "look": {"font": "gothic-heavy"}}]
    if a.role_text:
        texts.append({"text": a.role_text, "start": a.play + 0.45, "dur": a.hold - 0.45, "size": 10,
                      "color": "#FFFFFF", "y": -0.68, "track": "role", "intro": "pop-up", "intro_dur": 0.3,
                      "look": {"bg_color": "#222222", "bg_alpha": 0.75, "bg_radius": 0.3}})
    spec = {"name": a.name or "freeze_intro", "ratio": "9:16", "clips": clips,
            "overlays": [{"file": fg, "at": a.play, "dur": a.hold, "track": "freeze",
                          "keyframes": slow_out(1.0, a.zoom, a.hold)}],
            "texts": texts, "stroke": {"width": 0.1, "color": "#000000", "bold": True}}
    if a.shutter:
        spec["audio"] = [{"file": os.path.abspath(a.shutter), "start": max(0, a.play - 0.05), "volume": 0.8,
                          "track": "sfx"}]
    return spec


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--freeze-at", type=float, required=True, help="止めるコマ（素材の頭からの秒）")
    ap.add_argument("--name-text", required=True)
    ap.add_argument("--role-text")
    ap.add_argument("--play", type=float, default=2.0, help="止める前に流す秒数（0 で止めた所から始める）")
    ap.add_argument("--hold", type=float, default=3.0, help="止めておく秒数")
    ap.add_argument("--zoom", type=float, default=1.12, help="止めている間に寄る倍率")
    ap.add_argument("--border", type=float, default=0.018, help="縁の太さ（画面の短い辺に対する割合）")
    ap.add_argument("--shutter", help="止める瞬間に鳴らす音（シャッター音など）")
    ap.add_argument("--name")
    ap.add_argument("--drafts")
    a = ap.parse_args()
    build.build(spec_for(a), base=os.getcwd(), drafts=a.drafts)


if __name__ == "__main__":
    main()
