"""型（recipes）から使う下書き操作の薄い包み。capcut-cli と crj を呼ぶ。

    import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "lib"))
    import cc
    d = cc.Draft.create("my_reel", ratio="9:16")
    seg = d.add_clip("a.mp4", src_start=3.0, dur=1.5)
    t = d.add_text("38cm", start=0, dur=1.5, size=24, color="#FFE14D", y=0.3)
    d.finish()
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CRJ = [sys.executable, os.path.join(HERE, "crj.py")]
STORE = os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft")


def _run(cmd, stdin=None):
    r = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"{' '.join(map(str, cmd[:3]))} 失敗: {(r.stderr or r.stdout).strip()}")
    return r.stdout.strip()


def _json(cmd, stdin=None):
    return json.loads(_run(cmd, stdin))


def _sec(v):
    if isinstance(v, str) and v.endswith("s"):
        return v
    return f"{float(v)}s"


def capcut_running():
    return subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0


class Draft:
    def __init__(self, path):
        self.path = path

    @classmethod
    def create(cls, name, ratio="9:16", drafts=None):
        drafts = os.path.expanduser(drafts) if drafts else STORE
        path = os.path.join(drafts, name)
        if drafts == STORE and capcut_running():
            raise SystemExit("CapCut が起動中です。終了（⌘Q）してから実行してください")
        if os.path.exists(path):
            raise SystemExit(f"同じ名前の下書きがあります: {path}（別の名前を指定してください）")
        cmd = ["capcut", "init", name, "--ratio", ratio, "-q"]
        if drafts != STORE:
            cmd += ["--drafts", drafts]
        _run(cmd)
        return cls(path)

    # --- 映像 ---
    def add_clip(self, file, src_start, dur):
        return _run(CRJ + ["add-clip", self.path, os.path.abspath(os.path.expanduser(file)), str(src_start), str(dur)])

    def set_clip(self, ids, scale=None, x=None, y=None):
        cmd = CRJ + ["set-clip", self.path, *ids]
        for k, v in (("--scale", scale), ("--x", x), ("--y", y)):
            if v is not None:
                cmd += [k, str(v)]
        _run(cmd)

    def transition(self, seg, slug, dur=0.3):
        _run(["capcut", "transition", self.path, seg, slug, "--duration", _sec(dur), "-q"])

    def volume(self, seg, level):
        _run(["capcut", "volume", self.path, seg, str(level), "-q"])

    # --- 文字 ---
    def add_text(self, text, start, dur, size=14, color="#FFFFFF", x=0.0, y=0.0, track=None, align=1):
        cmd = ["capcut", "add-text", self.path, _sec(start), _sec(dur), text, "--font-size", str(size),
               "--color", color, "--align", str(align), "--x", str(x), "--y", str(y)]
        if track:
            cmd += ["--track-name", track]
        return _json(cmd)["segment_id"]

    def text_anim(self, seg, intro=None, intro_dur=0.25, outro=None, outro_dur=0.25):
        cmd = ["capcut", "text-anim", self.path, seg, "-q"]
        if intro:
            cmd += ["--intro", intro, "--intro-duration", _sec(intro_dur)]
        if outro:
            cmd += ["--outro", outro, "--outro-duration", _sec(outro_dur)]
        _run(cmd)

    def text_shadow(self, seg, alpha=0.5):
        _run(["capcut", "text-style", self.path, seg, "--shadow", "--shadow-alpha", str(alpha), "-q"])

    def keyframes(self, seg, rows):
        """rows: [{"property": "scale"|"position_x"|..., "time": 秒, "value": 値, "easing": 任意}]"""
        lines = "\n".join(json.dumps({**r, "time": _sec(r["time"])}) for r in rows) + "\n"
        _run(CRJ + ["keyframes", self.path, seg], stdin=lines)

    def text_border(self, seg, width=0.08, color="#000000", shadow_alpha=None):
        cmd = ["capcut", "text-style", self.path, seg, "--border-width", str(width), "--border-color", color, "-q"]
        if shadow_alpha is not None:
            cmd += ["--shadow", "--shadow-alpha", str(shadow_alpha)]
        _run(cmd)

    # --- 音 ---
    def add_audio(self, file, start, dur=None, volume=1.0, track=None):
        cmd = ["capcut", "add-audio", self.path, os.path.abspath(os.path.expanduser(file)), _sec(start)]
        if dur is not None:
            cmd.append(_sec(dur))
        cmd += ["--volume", str(volume)]
        if track:
            cmd += ["--track-name", track]
        return _json(cmd).get("segment_id")

    def audio_fade(self, seg, fade_in=0.0, fade_out=0.0):
        cmd = ["capcut", "audio-fade", self.path, seg, "-q"]
        if fade_in:
            cmd += ["--fade-in", str(fade_in)]
        if fade_out:
            cmd += ["--fade-out", str(fade_out)]
        _run(cmd)

    # --- 仕上げ ---
    def finish(self, stroke_width=0.12, stroke_color="#000000", bold=True):
        """縁取り・太字を全テキストに書き、尺を直し、素材を登録して検査する。"""
        cmd = CRJ + ["text-stroke", self.path, "--width", str(stroke_width), "--color", stroke_color]
        if not bold:
            cmd.append("--no-bold")
        _run(cmd)
        _run(CRJ + ["fix-duration", self.path])
        eff = json.loads(_run(CRJ + ["fill-effects", self.path]))
        if eff["missing"]:
            print("注意: 手元に無い効果があります。CapCut で開くとネットから取りに行き、取得が止まると開けません: "
                  + ", ".join(eff["missing"]), file=sys.stderr)
        if os.path.abspath(self.path).startswith(STORE):  # CapCut の一覧に載せる登録は置き場の中だけ
            _run(["capcut", "register", self.path, "--materials", "--apply", "-q"])
        r = subprocess.run(["capcut", "lint", self.path, "-H"], capture_output=True, text=True)
        return r.stdout.strip()
