#!/usr/bin/env python3
"""指の間の文字（pinch-text）の下書きを組む。

  python3 recipes/pinch-text/build.py --video hand.mov --src-start 2.6 --dur 3.4 --text 情報解禁 \\
      [--follow-from 0.6] [--bang-at 2.6] [--fingers fingers.jsonl | --track] [--x 0 --y 0] \\
      [--whoosh a.mp3] [--impact b.mp3] [--name 下書き名] [--drafts 置き場]

--track で指先を自動検出する（uv と MediaPipe を使う。初回はダウンロードあり）。
--fingers も --track も無ければ、--x --y の位置で一定の速さで育てる（見本・試し用）。
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "lib"))
sys.path.insert(0, os.path.join(HERE, "tools"))
import build  # noqa: E402
import gen_keyframes  # noqa: E402


def track(video, start, end):
    cmd = ["uv", "run", "--python", "3.11", "--with", "mediapipe==0.10.14", "--with", "opencv-python",
           "python", os.path.join(HERE, "tools", "track_fingers.py"), video, str(start), str(end)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"指先の検出に失敗: {r.stderr.strip()[-500:]}")
    return [json.loads(l) for l in r.stdout.splitlines() if l.startswith("{")]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--src-start", type=float, default=0.0)
    ap.add_argument("--dur", type=float, required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--size", type=float, default=14)
    ap.add_argument("--color", default="#FFFFFF")
    ap.add_argument("--follow-from", type=float, default=0.6, help="文字が育ち始める秒（クリップの頭から）")
    ap.add_argument("--bang-at", type=float, help="ギュインと特大にする秒（省略時は終わりの0.8秒前）")
    ap.add_argument("--fingers")
    ap.add_argument("--track", action="store_true")
    ap.add_argument("--x", type=float, default=0.0)
    ap.add_argument("--y", type=float, default=0.0)
    ap.add_argument("--whoosh", help="ギュインに合わせる効果音")
    ap.add_argument("--impact", help="特大になり切る瞬間の効果音")
    ap.add_argument("--name", default="pinch_text")
    ap.add_argument("--drafts")
    a = ap.parse_args()

    video = os.path.abspath(os.path.expanduser(a.video))
    bang = a.bang_at if a.bang_at is not None else round(a.dur - 0.8, 2)
    fingers = None
    if a.fingers:
        fingers = [json.loads(l) for l in open(a.fingers) if l.strip()]
    elif a.track:
        fingers = track(video, a.src_start, a.src_start + a.dur)
    kfs = gen_keyframes.make(fingers, a.src_start, a.follow_from, bang, a.x, a.y)

    audio = []
    if a.whoosh:
        audio.append({"file": a.whoosh, "start": max(0, bang - 0.1), "volume": 0.7, "track": "sfx"})
    if a.impact:
        audio.append({"file": a.impact, "start": bang + gen_keyframes.RISE, "volume": 0.9, "track": "sfx2"})
    spec = {
        "name": a.name, "ratio": "9:16",
        "clips": [{"file": video, "src_start": a.src_start, "dur": a.dur}],
        "texts": [{"text": a.text, "start": 0, "dur": a.dur, "size": a.size, "color": a.color,
                   "x": a.x, "y": a.y, "shadow": 0.5, "keyframes": kfs}],
        "audio": audio,
        "stroke": {"width": 0.12, "color": "#000000"},
    }
    build.build(spec, base=os.getcwd(), drafts=a.drafts)


if __name__ == "__main__":
    main()
