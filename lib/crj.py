#!/usr/bin/env python3
"""crj — capcut-cli で足りない操作を補う道具（CapCut デスクトップ版 9.8.0 / Mac で確認）。

下書きの読み書きの土台は capcut-cli（https://github.com/renezander030/capcut-cli）。
ここでは capcut-cli だけでは起きる落とし穴を避けるための操作だけを持つ。

  add-clip     <draft> <file> <src_start> <dur>      メイン動画トラックの末尾に、元素材の一部を足す
  reorder      <draft> <seg-id>...                    メイン動画トラックを指定順に並べ替え、隙間なく詰める
  set-canvas   <draft> <9:16|1:1|4:5|16:9|WxH>        キャンバスの比率・解像度を変える
  set-clip     <draft> <seg-id>... --scale S [--x X] [--y Y]   拡大率・位置の固定値
  keyframes    <draft> <seg-id>   (stdin: JSONL)      キーフレームを書く（scale は scale_x と scale_y に分ける）
  text-stroke  <draft> [--ids ...] [--width W] [--color #RRGGBB] [--no-bold]   縁取り・太字
  fix-duration <draft>                                下書き全体の尺を、最後のセグメントの終わりに合わせる
  fill-effects <draft>                                切り替え・文字アニメなどの効果に、手元のキャッシュの場所を書く
  info         <draft>                                書き込み対象のファイルと、CapCut の起動状態を表示

seg-id は先頭8文字でもよい。CapCut の下書き置き場（~/Movies/CapCut）への書き込みは、CapCut の起動中は止める。書き込み前に各ファイルを <name>.crjbak に控える。
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

TIMELINE_NAMES = ("draft_content.json", "draft_info.json", "template-2.tmp")
CANVAS_PRESETS = {"9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350), "16:9": (1920, 1080), "3:4": (1080, 1440)}


def die(msg):
    print(f"crj: {msg}", file=sys.stderr)
    sys.exit(1)


STORE_ROOTS = [os.path.expanduser("~/Movies/CapCut"), os.path.expanduser("~/Movies/JianyingPro")]


def in_store(path):
    return any(os.path.abspath(path).startswith(r) for r in STORE_ROOTS)


def capcut_running():
    return subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0


def timeline_files(draft):
    """下書きのタイムラインを持つファイル（直下と Timelines/ の中）をすべて返す。"""
    paths = [os.path.join(draft, n) for n in TIMELINE_NAMES]
    for sub in glob.glob(os.path.join(draft, "Timelines", "*")):
        paths += [os.path.join(sub, n) for n in TIMELINE_NAMES]
    out = []
    for p in paths:
        if not os.path.isfile(p):
            continue
        try:
            doc = json.load(open(p))
        except (ValueError, UnicodeDecodeError):
            continue  # 暗号化・別形式は触らない
        if isinstance(doc, dict) and "tracks" in doc:
            out.append(p)
    if not out:
        die(f"タイムラインのファイルが見つからない: {draft}")
    return out


class Draft:
    def __init__(self, path, write=True):
        self.path = os.path.abspath(os.path.expanduser(path))
        if write and in_store(self.path) and capcut_running():
            die("CapCut が起動中です。終了（⌘Q）してから実行してください")
        self.files = timeline_files(self.path)
        self.docs = {p: json.load(open(p)) for p in self.files}

    def each(self):
        return self.docs.items()

    @property
    def main(self):
        return self.docs[self.files[0]]

    def save(self):
        for p, doc in self.docs.items():
            shutil.copy2(p, p + ".crjbak")
            tmp = p + ".crjtmp"
            with open(tmp, "w") as f:
                json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, p)


def main_video_track(doc):
    for t in doc.get("tracks", []):
        if t.get("type") == "video":
            return t
    return None


def resolve_ids(doc, prefixes):
    all_ids = [s["id"] for t in doc.get("tracks", []) for s in t.get("segments", [])]
    out = []
    for p in prefixes:
        hits = [i for i in all_ids if i.startswith(p)]
        if len(hits) != 1:
            die(f"セグメント {p} が{'見つからない' if not hits else '複数ある'}")
        out.append(hits[0])
    return out


def end_of(doc):
    ends = [s["target_timerange"]["start"] + s["target_timerange"]["duration"]
            for t in doc.get("tracks", []) for s in t.get("segments", [])]
    return max(ends) if ends else 0


def fix_duration_doc(doc):
    doc["duration"] = end_of(doc)


# ---------- commands ----------

def cmd_add_clip(a):
    d = Draft(a.draft)
    track = main_video_track(d.main)
    pos = 0
    if track and track["segments"]:
        last = max(track["segments"], key=lambda s: s["target_timerange"]["start"])
        pos = last["target_timerange"]["start"] + last["target_timerange"]["duration"]
    # 長さを渡さない: 渡すと素材全体の長さがその秒数で登録され、trim の開始位置が範囲外になる
    r = subprocess.run(["capcut", "add-video", d.path, a.file, f"{pos / 1e6}s"], capture_output=True, text=True)
    if r.returncode:
        die(r.stderr or r.stdout)
    seg = json.loads(r.stdout)["segment_id"]
    r = subprocess.run(["capcut", "trim", d.path, seg, str(a.src_start), str(a.dur), "-q"], capture_output=True, text=True)
    if r.returncode:
        die(r.stderr or r.stdout)
    print(seg)


def cmd_reorder(a):
    d = Draft(a.draft)
    ids = resolve_ids(d.main, a.ids)
    for _, doc in d.each():
        track = main_video_track(doc)
        segs = {s["id"]: s for s in track["segments"]}
        if set(ids) != set(segs):
            die("メイン動画トラックの全セグメントを、並べたい順に指定してください")
        # CapCut はメイン動画トラックを配列の順番で詰めて並べるので、配列ごと入れ替える
        track["segments"] = [segs[i] for i in ids]
        pos = 0
        for s in track["segments"]:
            s["target_timerange"]["start"] = pos
            pos += s["target_timerange"]["duration"]
        fix_duration_doc(doc)
    d.save()
    print("ok")


def cmd_set_canvas(a):
    d = Draft(a.draft)
    if a.ratio in CANVAS_PRESETS:
        w, h = CANVAS_PRESETS[a.ratio]
        label = a.ratio
    elif "x" in a.ratio:
        w, h = (int(v) for v in a.ratio.split("x"))
        label = "original"
    else:
        die(f"比率は {', '.join(CANVAS_PRESETS)} か WxH")
    for _, doc in d.each():
        doc.setdefault("canvas_config", {}).update(width=w, height=h, ratio=label)
    d.save()
    print(f"{w}x{h}")


def cmd_set_clip(a):
    d = Draft(a.draft)
    ids = set(resolve_ids(d.main, a.ids))
    n = 0
    for _, doc in d.each():
        for t in doc["tracks"]:
            for s in t["segments"]:
                if s["id"] in ids:
                    clip = s.setdefault("clip", {})
                    if a.scale is not None:
                        clip["scale"] = {"x": a.scale, "y": a.scale}
                    tr = clip.setdefault("transform", {"x": 0, "y": 0})
                    if a.x is not None:
                        tr["x"] = a.x
                    if a.y is not None:
                        tr["y"] = a.y
                    n += 1
    d.save()
    print(f"{n // len(d.files)} segments")


def cmd_keyframes(a):
    if in_store(a.draft) and capcut_running():
        die("CapCut が起動中です。終了（⌘Q）してから実行してください")
    out = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        k = json.loads(line)
        # uniform_scale は CapCut 9.8 で効かない。scale_x と scale_y に分けて書く
        if k["property"] in ("scale", "uniform_scale"):
            for p in ("scale_x", "scale_y"):
                out.append(json.dumps({**k, "property": p}))
        else:
            out.append(json.dumps(k))
    r = subprocess.run(["capcut", "keyframe", a.draft, a.id, "--batch"], input="\n".join(out) + "\n",
                       capture_output=True, text=True)
    if r.returncode:
        die(r.stderr or r.stdout)
    print(r.stdout.strip())


def cmd_text_stroke(a):
    d = Draft(a.draft)
    hexc = a.color.lstrip("#")
    rgb = [int(hexc[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    want = None
    if a.ids:
        segs = resolve_ids(d.main, a.ids)
        want = {s["material_id"] for t in d.main["tracks"] for s in t["segments"] if s["id"] in segs}
    n = 0
    for _, doc in d.each():
        for m in doc.get("materials", {}).get("texts", []):
            if want is not None and m["id"] not in want:
                continue
            c = json.loads(m["content"])
            # CapCut 9.8 は描画に content.styles[] を使う（外側の border_* だけでは表示されない）
            for st in c.get("styles", []):
                st["bold"] = a.bold
                if a.width > 0:
                    st["strokes"] = [{"alpha": 1, "width": a.width,
                                      "content": {"render_type": "solid", "solid": {"alpha": 1, "color": rgb}}}]
                else:
                    st.pop("strokes", None)
            m["content"] = json.dumps(c, ensure_ascii=False)
            n += 1
    d.save()
    print(f"{n // len(d.files)} texts")


def cmd_fix_duration(a):
    d = Draft(a.draft)
    for _, doc in d.each():
        fix_duration_doc(doc)
    d.save()
    print(f"{end_of(d.main) / 1e6:.3f}s")


EFFECT_CACHE = os.path.expanduser("~/Movies/CapCut/User Data/Cache/effect")
DRAFT_STORE = os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft")


def _effect_nodes(o):
    """materials の中で、resource_id と path を持つもの（切り替え・アニメ・エフェクト等）を全部返す。"""
    if isinstance(o, dict):
        if "resource_id" in o and ("path" in o or "effect_id" in o):
            yield o
        for v in o.values():
            yield from _effect_nodes(v)
    elif isinstance(o, list):
        for v in o:
            yield from _effect_nodes(v)


def effect_index():
    """resource_id → 手元のキャッシュの場所。CapCut が保存した下書きと、キャッシュのフォルダ名から集める。"""
    idx = {}
    for f in glob.glob(os.path.join(DRAFT_STORE, "*", "draft_info.json")) + \
            glob.glob(os.path.join(DRAFT_STORE, "*", "Timelines", "*", "draft_info.json")):
        try:
            doc = json.load(open(f))
        except (ValueError, UnicodeDecodeError, OSError):
            continue
        for n in _effect_nodes(doc.get("materials", {})):
            if n.get("resource_id") and n.get("path") and os.path.isdir(n["path"]):
                idx.setdefault(n["resource_id"], n["path"])
    for d in glob.glob(os.path.join(EFFECT_CACHE, "*")):
        rid = os.path.basename(d)
        if rid in idx:
            continue
        subs = [s for s in glob.glob(os.path.join(d, "*")) if os.path.isdir(s) and not s.endswith("_tmp")]
        if len(subs) == 1:
            idx[rid] = subs[0]
    return idx


def cmd_fill_effects(a):
    # CapCut は効果の場所が空だとネットから取り直し、取得が止まると「読み込み中」のまま開けなくなる
    d = Draft(a.draft)
    idx = effect_index()
    filled, missing = set(), set()
    for _, doc in d.each():
        for n in _effect_nodes(doc.get("materials", {})):
            rid = n.get("resource_id")
            if not rid or (n.get("path") and os.path.isdir(n["path"])):
                continue
            if rid in idx:
                n["path"] = idx[rid]
                filled.add(rid)
            else:
                missing.add(f"{n.get('name') or ''}({rid})")
    d.save()
    print(json.dumps({"filled": len(filled), "missing": sorted(missing)}, ensure_ascii=False))


def cmd_info(a):
    d = Draft(a.draft, write=False)
    print(json.dumps({
        "capcut_running": capcut_running(),
        "timeline_files": [os.path.relpath(p, d.path) for p in d.files],
        "canvas": d.main.get("canvas_config"),
        "duration_s": d.main.get("duration", 0) / 1e6,
        "segments": sum(len(t["segments"]) for t in d.main["tracks"]),
    }, ensure_ascii=False, indent=1))


def build_parser():
    p = argparse.ArgumentParser(prog="crj", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("add-clip"); s.add_argument("draft"); s.add_argument("file")
    s.add_argument("src_start", type=float); s.add_argument("dur", type=float); s.set_defaults(f=cmd_add_clip)
    s = sp.add_parser("reorder"); s.add_argument("draft"); s.add_argument("ids", nargs="+"); s.set_defaults(f=cmd_reorder)
    s = sp.add_parser("set-canvas"); s.add_argument("draft"); s.add_argument("ratio"); s.set_defaults(f=cmd_set_canvas)
    s = sp.add_parser("set-clip"); s.add_argument("draft"); s.add_argument("ids", nargs="+")
    s.add_argument("--scale", type=float); s.add_argument("--x", type=float); s.add_argument("--y", type=float)
    s.set_defaults(f=cmd_set_clip)
    s = sp.add_parser("keyframes"); s.add_argument("draft"); s.add_argument("id"); s.set_defaults(f=cmd_keyframes)
    s = sp.add_parser("text-stroke"); s.add_argument("draft"); s.add_argument("--ids", nargs="*")
    s.add_argument("--width", type=float, default=0.12); s.add_argument("--color", default="#000000")
    s.add_argument("--no-bold", dest="bold", action="store_false"); s.set_defaults(f=cmd_text_stroke)
    s = sp.add_parser("fix-duration"); s.add_argument("draft"); s.set_defaults(f=cmd_fix_duration)
    s = sp.add_parser("fill-effects"); s.add_argument("draft"); s.set_defaults(f=cmd_fill_effects)
    s = sp.add_parser("info"); s.add_argument("draft"); s.set_defaults(f=cmd_info)
    return p


if __name__ == "__main__":
    a = build_parser().parse_args()
    a.f(a)
