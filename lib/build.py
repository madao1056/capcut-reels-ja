#!/usr/bin/env python3
"""構成表（spec の JSON）から CapCut の下書きを組む。

  python3 lib/build.py spec.json [--name 下書き名] [--drafts 下書き置き場]

spec の書式（相対パスは spec ファイルの場所から、~ も使える）:
{
  "name": "my_reel", "ratio": "9:16",
  "clips": [ {"file": "a.mp4", "src_start": 3.0, "dur": 1.5,
              "scale": 4.0, "x": 0, "y": -0.27, "volume": 0.7,
              "transition": {"slug": "white-flash", "dur": 0.3}} ],
  "texts": [ {"text": "38cm", "start": 0, "dur": 1.5, "size": 24, "color": "#FFE14D",
              "x": 0, "y": 0.3, "track": "sub", "intro": "pop-up", "intro_dur": 0.25,
              "shadow": 0.6, "keyframes": [ {"property": "scale", "time": 0, "value": 1} ],
              "keyframes_jsonl": "kf.jsonl"} ],
  "audio": [ {"file": "bgm.mp3", "start": 0, "dur": 12.6, "volume": 0.18, "track": "sfx",
              "fade_out": 0.8} ],
  "stroke": {"width": 0.12, "color": "#000000", "bold": true}
}
clips はタイムラインの先頭から順に隙間なく並ぶ。dur を "end" にした audio はクリップ全体の長さになる。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cc  # noqa: E402


def _path(base, p):
    p = os.path.expanduser(p)
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))


def build(spec, base=".", name=None, drafts=None, log=print):
    d = cc.Draft.create(name or spec["name"], ratio=spec.get("ratio", "9:16"), drafts=drafts)
    total = 0.0
    clip_ids = []
    for c in spec.get("clips", []):
        seg = d.add_clip(_path(base, c["file"]), c.get("src_start", 0), c["dur"])
        clip_ids.append(seg)
        total += c["dur"]
        if any(k in c for k in ("scale", "x", "y")):
            d.set_clip([seg], scale=c.get("scale"), x=c.get("x"), y=c.get("y"))
    # 切り替えと音量は、全クリップを並べ終えてから付ける（切り替えは次のクリップとの間に入るため）
    for c, seg in zip(spec.get("clips", []), clip_ids):
        if "volume" in c:
            d.volume(seg, c["volume"])
        if "transition" in c:
            d.transition(seg, c["transition"]["slug"], c["transition"].get("dur", 0.3))

    text_ids = []
    for t in spec.get("texts", []):
        seg = d.add_text(t["text"], t["start"], t["dur"], size=t.get("size", 14), color=t.get("color", "#FFFFFF"),
                         x=t.get("x", 0.0), y=t.get("y", 0.0), track=t.get("track"), align=t.get("align", 1))
        text_ids.append(seg)
        if "shadow" in t:
            d.text_shadow(seg, t["shadow"])
        if t.get("intro") or t.get("outro"):
            d.text_anim(seg, intro=t.get("intro"), intro_dur=t.get("intro_dur", 0.25),
                        outro=t.get("outro"), outro_dur=t.get("outro_dur", 0.25))
        rows = list(t.get("keyframes", []))
        if "keyframes_jsonl" in t:
            rows += [json.loads(l) for l in open(_path(base, t["keyframes_jsonl"])) if l.strip()]
        if rows:
            d.keyframes(seg, rows)

    for a in spec.get("audio", []):
        dur = total if a.get("dur") == "end" else a.get("dur")
        seg = d.add_audio(_path(base, a["file"]), a.get("start", 0), dur, volume=a.get("volume", 1.0),
                          track=a.get("track"))
        if seg and (a.get("fade_in") or a.get("fade_out")):
            d.audio_fade(seg, a.get("fade_in", 0), a.get("fade_out", 0))

    st = spec.get("stroke", {})
    lint = d.finish(stroke_width=st.get("width", 0.12), stroke_color=st.get("color", "#000000"),
                    bold=st.get("bold", True))
    log(f"下書き: {d.path}（映像 {total:.2f} 秒・クリップ {len(clip_ids)}・テキスト {len(text_ids)}）")
    if lint:
        log(lint)
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--name")
    ap.add_argument("--drafts", help="下書き置き場（省略時は CapCut の置き場）")
    a = ap.parse_args()
    spec = json.load(open(a.spec))
    build(spec, base=os.path.dirname(os.path.abspath(a.spec)), name=a.name, drafts=a.drafts)


if __name__ == "__main__":
    main()
