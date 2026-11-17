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
  text-look    <draft> --ids ... [--font mincho|gothic|maru|<path>] [--spacing N] [--opacity A]
               [--shadow-color #RRGGBB --shadow-alpha A --shadow-blur P --shadow-distance D] [--no-shadow]
               [--bg-color #RRGGBB --bg-alpha A --bg-radius R] [--kana-scale S] [--curve 角度]
               書体・文字間隔・透け・影・背景・かな縮小・曲線（円弧。360で円）
  text-loop    <draft> --ids ... --slug rotate [--dur 秒]   出ている間くり返す文字の動き（画面の「ループ」）
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


FONT_DIR = "/System/Library/Fonts"
FONT_ALIASES = {"mincho": "ヒラギノ明朝 ProN.ttc", "gothic": "ヒラギノ角ゴシック W6.ttc",
                "gothic-heavy": "ヒラギノ角ゴシック W8.ttc", "maru": "ヒラギノ丸ゴ ProN W4.ttc",
                # 欧文（macOS に元から入っている物）
                "serif-bold": "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
                "script": "/System/Library/Fonts/Supplemental/SnellRoundhand.ttc"}


def font_path(name):
    """別名（mincho 等）かファイルの場所から、実際のフォントファイルの場所を返す。"""
    import unicodedata
    if name in FONT_ALIASES and FONT_ALIASES[name].startswith("/"):
        if not os.path.isfile(FONT_ALIASES[name]):
            die(f"フォントが見つからない: {FONT_ALIASES[name]}")
        return FONT_ALIASES[name]
    if name in FONT_ALIASES:
        want = unicodedata.normalize("NFC", FONT_ALIASES[name])
        for f in os.listdir(FONT_DIR):
            if unicodedata.normalize("NFC", f) == want:
                return os.path.join(FONT_DIR, f)
        die(f"フォントが見つからない: {FONT_ALIASES[name]}")
    p = os.path.expanduser(name)
    if not os.path.isfile(p):
        die(f"フォントのファイルが無い: {p}")
    return p


def _rgb(hexc):
    h = hexc.lstrip("#")
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def _is_kana(ch):
    return "\u3041" <= ch <= "\u309f"  # ひらがな（記号・カタカナは縮めない）


def _split_kana(styles, text, scale):
    """ひらがなだけ文字の大きさを scale 倍にするよう、文字スタイルを区間ごとに分ける。"""
    out = []
    for st in styles:
        a, b = st["range"]
        i = a
        while i < b:
            k = _is_kana(text[i])
            j = i
            while j < b and _is_kana(text[j]) == k:
                j += 1
            seg = json.loads(json.dumps(st))
            seg["range"] = [i, j]
            if k:
                seg["size"] = round(st["size"] * scale, 1)
            out.append(seg)
            i = j
    return out


def cmd_text_look(a):
    # CapCut 9.8 の画面で設定して保存された形に合わせて書く（2026-11-17 に確認）
    d = Draft(a.draft)
    segs = resolve_ids(d.main, a.ids)
    want = {s["material_id"] for t in d.main["tracks"] for s in t["segments"] if s["id"] in segs}
    fpath = font_path(a.font) if a.font else None
    n = 0
    for _, doc in d.each():
        for m in doc.get("materials", {}).get("texts", []):
            if m["id"] not in want:
                continue
            c = json.loads(m["content"])
            styles = c.get("styles", [])
            if fpath:
                m["font_path"] = fpath
                for st in styles:
                    st["font"] = {"path": fpath, "id": ""}
            if a.spacing is not None:
                m["letter_spacing"] = a.spacing / 20   # 画面の「文字」の値 -1 が -0.05
            if a.opacity is not None:
                m["global_alpha"] = a.opacity
            if a.no_shadow:
                m["has_shadow"] = False
                for st in styles:
                    st.pop("shadows", None)
            elif a.shadow_color or a.shadow_alpha is not None:
                col = a.shadow_color or "#000000"
                alpha = 0.5 if a.shadow_alpha is None else a.shadow_alpha
                import math
                ang = a.shadow_angle
                m["check_flag"] = m.get("check_flag", 7) | 16
                m.update(has_shadow=True, shadow_color=col, shadow_alpha=alpha, shadow_distance=a.shadow_distance,
                         shadow_angle=ang, shadow_smoothing=a.shadow_blur / 100 * 3,
                         shadow_point={"x": math.cos(math.radians(ang)) * 0.9, "y": math.sin(math.radians(ang)) * 0.9})
                for st in styles:
                    st["shadows"] = [{"alpha": alpha, "angle": ang, "distance": a.shadow_distance,
                                      "diffuse": a.shadow_blur / 100 / 6,   # 画面の「不鮮明さ」40% が 0.0667
                                      "content": {"render_type": "solid", "solid": {"color": _rgb(col)}},
                                      "thickness_projection_enable": False, "thickness_projection_angle": ang,
                                      "thickness_projection_distance": 0}]
            if a.bg_color:
                m["check_flag"] = m.get("check_flag", 7) | 32 | 16   # 背景を描かせる印（画面で付けると 7→55 になる）
                m.update(background_style=1, background_color=a.bg_color, background_alpha=a.bg_alpha,
                         background_round_radius=a.bg_radius, background_width=a.bg_pad, background_height=a.bg_pad)
            if a.curve:
                # 画面の「曲線」強度（度）。360 で文字が円に並ぶ。背景をオンにすると画面では曲線を選べない
                if a.bg_color or m.get("background_style"):
                    raise SystemExit("曲線と背景は同時に使えません（CapCut の画面でも背景オンだと曲線が選べない）")
                m["text_curve"] = {"enable": True, "angle": float(a.curve)}
                m["check_flag"] = m.get("check_flag", 7) | 128   # 画面で付けると 128 が立つ
            if a.kana_scale and a.kana_scale != 1:
                styles = _split_kana(styles, c["text"], a.kana_scale)
            c["styles"] = styles
            m["content"] = json.dumps(c, ensure_ascii=False)
            n += 1
    d.save()
    print(f"{n // len(d.files)} texts")


def cmd_text_loop(a):
    # capcut-cli の text-anim は入り・出が無いとループだけを付けられないので、画面で付けた形に合わせて書く（2026-11-17 確認）
    import uuid
    r = subprocess.run(["capcut", "enums", "x", "--text-loop-anims"], capture_output=True, text=True)
    hit = [e for e in json.loads(r.stdout or "[]") if e["slug"] == a.slug]
    if not hit:
        die(f"ループの名前 {a.slug} がありません（capcut enums x --text-loop-anims で一覧）")
    e = hit[0]
    d = Draft(a.draft)
    segs = set(resolve_ids(d.main, a.ids))
    entry = {"id": e["resource_id"], "type": "loop", "start": 0, "duration": int(a.dur * 1e6), "path": "",
             "platform": "all", "resource_id": e["resource_id"], "third_resource_id": e["resource_id"],
             "source_platform": 1, "name": e["title"], "category_id": "xunhuan", "category_name": "text",
             "panel": "", "material_type": "sticker", "anim_adjust_params": None, "request_id": ""}
    for _, doc in d.each():
        anims = doc.setdefault("materials", {}).setdefault("material_animations", [])
        byid = {m["id"]: m for m in anims}
        for t in doc.get("tracks", []):
            for sg in t.get("segments", []):
                if sg["id"] not in segs:
                    continue
                refs = sg.setdefault("extra_material_refs", [])
                ma = next((byid[x] for x in refs if x in byid and byid[x].get("type") == "sticker_animation"), None)
                if ma is None:
                    ma = {"id": str(uuid.uuid4()).upper(), "type": "sticker_animation", "multi_language_current": "none",
                          "animations": []}
                    anims.append(ma); byid[ma["id"]] = ma; refs.append(ma["id"])
                ma["animations"] = [x for x in ma.get("animations", []) if x.get("type") != "loop"] + [dict(entry)]
    d.save()
    print(f"{len(segs)} texts: {e['title']} {a.dur}s")


def _attach(d, ids, kind, build_item, replace=lambda m: True):
    """セグメントの extra_material_refs に materials[kind] の項目を付ける（画面で付けた形、2026-11-17 確認）。
    replace(m) が真の既存項目は外してから付け直す。"""
    segs = set(resolve_ids(d.main, ids))
    for _, doc in d.each():
        mats = doc.setdefault("materials", {}).setdefault(kind, [])
        byid = {m["id"]: m for m in mats}
        for t in doc.get("tracks", []):
            for sg in t.get("segments", []):
                if sg["id"] not in segs:
                    continue
                refs = sg.setdefault("extra_material_refs", [])
                old = [x for x in refs if x in byid and replace(byid[x])]
                refs[:] = [x for x in refs if x not in old]
                mats[:] = [m for m in mats if m["id"] not in old]
                item = build_item()
                mats.append(item)
                refs.append(item["id"])
    return segs


BLUR_ID = "7399464929830423813"     # 動画エフェクト → クラシック →「ぼかし」（無料の方）
HSL_ID = "7501974767453474064"
HSL_COLORS = {"red": (1, "#FFE64444"), "orange": (2, "#FFE69444"),       # 画面で8色とも付けて確認（2026-11-17）
              "yellow": (3, "#FFF2F224"), "green": (4, "#FF45E644"),
              "cyan": (5, "#FF45E6E6"), "blue": (6, "#FF4595E6"),
              "purple": (7, "#FF9545E6"), "magenta": (8, "#FFE644E6")}


def _cached(rid, label):
    p = effect_index().get(rid)
    if not p:
        die(f"{label}が手元にありません。CapCut の画面で一度付けて取得してから使ってください（未取得のまま開くと止まることがあります）")
    return p


def cmd_clip_blur(a):
    # capcut-cli の add-effect --bind はエフェクト用の段に置く形で、画面で付けた形（クリップに直接付く）と違う
    import uuid
    path = _cached(BLUR_ID, "ぼかしの効果")
    d = Draft(a.draft)
    item = lambda: {"id": str(uuid.uuid4()).upper(), "effect_id": BLUR_ID, "resource_id": BLUR_ID, "name": "ぼかし",
                    "type": "video_effect", "sub_type": 0, "bind_segment_id": "", "transparent_params": "", "path": path,
                    "value": 1.0, "category_id": "2037709426", "category_name": "クラシック", "platform": "all",
                    "apply_target_type": 0, "source_platform": 1, "version": "", "item_effect_type": 0,
                    "adjust_params": [{"name": "effects_adjust_blur", "value": a.amount, "default_value": 0.5}],
                    "time_range": None, "formula_id": "", "apply_time_range": None, "render_index": 11000,
                    "track_render_index": 0, "common_keyframes": [], "request_id": "", "algorithm_artifact_path": "",
                    "disable_effect_faces": [], "covering_relation_change": 0, "enable_mask": True, "effect_mask": [],
                    "enable_video_mask_stroke": True, "enable_video_mask_shadow": True}
    segs = _attach(d, a.ids, "video_effects", item, lambda m: m.get("resource_id") == BLUR_ID)
    d.save()
    print(f"{len(segs)} clips: ぼかし {a.amount}")


def cmd_clip_hsl(a):
    import uuid
    path = _cached(HSL_ID, "HSL の効果")
    ctype, ccolor = HSL_COLORS[a.color]
    d = Draft(a.draft)
    item = lambda: {"id": str(uuid.uuid4()).upper(), "constant_material_id": str(uuid.uuid4()).upper(),
                    "hsl_color_type": ctype, "hue": int(a.hue), "saturation": int(a.sat), "lightness": int(a.light),
                    "interacting": False, "version": "1", "path": path, "type": "hsl",
                    "lumi_hub_path": os.path.join(path, "lumi_hub_path"), "custom_color": ccolor,
                    "resource_id": HSL_ID, "source_platform": 1}
    segs = _attach(d, a.ids, "hsl", item, lambda m: m.get("hsl_color_type") == ctype)
    d.save()
    print(f"{len(segs)} clips: HSL {a.color} 色合い{a.hue} 彩度{a.sat} 明るさ{a.light}")


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
    s = sp.add_parser("text-look"); s.add_argument("draft"); s.add_argument("--ids", nargs="+", required=True)
    s.add_argument("--font"); s.add_argument("--spacing", type=float); s.add_argument("--opacity", type=float)
    s.add_argument("--shadow-color"); s.add_argument("--shadow-alpha", type=float)
    s.add_argument("--shadow-blur", type=float, default=40); s.add_argument("--shadow-distance", type=float, default=5)
    s.add_argument("--shadow-angle", type=float, default=-45); s.add_argument("--no-shadow", action="store_true")
    s.add_argument("--bg-color"); s.add_argument("--bg-alpha", type=float, default=0.8)
    s.add_argument("--bg-radius", type=float, default=0.0); s.add_argument("--bg-pad", type=float, default=0.14)
    s.add_argument("--kana-scale", type=float); s.add_argument("--curve", type=float)
    s.set_defaults(f=cmd_text_look)
    s = sp.add_parser("text-loop"); s.add_argument("draft"); s.add_argument("--ids", nargs="+", required=True)
    s.add_argument("--slug", required=True); s.add_argument("--dur", type=float, default=0.5)
    s.set_defaults(f=cmd_text_loop)
    s = sp.add_parser("clip-blur"); s.add_argument("draft"); s.add_argument("--ids", nargs="+", required=True)
    s.add_argument("--amount", type=float, default=0.5, help="ぼかしの強さ 0〜1（画面の 0〜100）")
    s.set_defaults(f=cmd_clip_blur)
    s = sp.add_parser("clip-hsl"); s.add_argument("draft"); s.add_argument("--ids", nargs="+", required=True)
    s.add_argument("--color", required=True, choices=list(HSL_COLORS))
    s.add_argument("--hue", type=float, default=0); s.add_argument("--sat", type=float, default=0)
    s.add_argument("--light", type=float, default=0); s.set_defaults(f=cmd_clip_hsl)
    s = sp.add_parser("fix-duration"); s.add_argument("draft"); s.set_defaults(f=cmd_fix_duration)
    s = sp.add_parser("fill-effects"); s.add_argument("draft"); s.set_defaults(f=cmd_fill_effects)
    s = sp.add_parser("info"); s.add_argument("draft"); s.set_defaults(f=cmd_info)
    return p


if __name__ == "__main__":
    a = build_parser().parse_args()
    a.f(a)
