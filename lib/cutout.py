#!/usr/bin/env python3
"""人物だけを残した透過動画を作る（CapCut の有料「自動削除」の代わり）。

  python3 lib/cutout.py <素材> <src_start> <dur> [-o 出力.mov] [--prores] [--quality fast|balanced|accurate]

macOS 標準の Vision（人物セグメンテーション）で各コマの人物マスクを作り、元の映像に透過として重ねて書き出す。
追加インストール・モデルのダウンロードは不要（Xcode のコマンドラインツールの swiftc を使う）。
初回に lib/native/person_matte.swift をビルドして ~/.cache/capcut-reels-ja/ に置く。

書き出しは HEVC の透過（.mov、4秒で約7MB）。--prores で ProRes 4444（約280MB。HEVC が読めない環境向け）。
どちらも CapCut 9.8.0（Mac）で透過として読まれることを確認済み。
-o を省くと ~/.cache/capcut-reels-ja/cutout/ に、素材・区間ごとに1回だけ作る。
freeze() は1コマで止める部品（背景の .mp4 と、紙の質感の縁を付けた人物の透過 .mov）を作る（型 freeze-intro）。
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.expanduser("~/.cache/capcut-reels-ja")
SWIFT_SRC = os.path.join(ROOT, "lib", "native", "person_matte.swift")


def _binary():
    exe = os.path.join(CACHE, "person_matte")
    if os.path.exists(exe) and os.path.getmtime(exe) >= os.path.getmtime(SWIFT_SRC):
        return exe
    if sys.platform != "darwin" or not shutil.which("swiftc"):
        raise SystemExit("人物の切り抜きには macOS と swiftc（xcode-select --install）が要ります")
    os.makedirs(CACHE, exist_ok=True)
    subprocess.run(["swiftc", "-O", SWIFT_SRC, "-o", exe], check=True)
    return exe


def _probe(src):
    """回転を反映した表示サイズと、コマの速さ（fps）。"""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,avg_frame_rate:stream_side_data=rotation:stream_tags=rotate",
                        "-of", "json", src], capture_output=True, text=True, check=True)
    s = json.loads(r.stdout)["streams"][0]
    w, h = s["width"], s["height"]
    rot = int(float(s.get("tags", {}).get("rotate", 0) or 0))
    for sd in s.get("side_data_list", []):
        rot = int(float(sd.get("rotation", rot)))
    if abs(rot) % 180 == 90:
        w, h = h, w
    n, d = s.get("avg_frame_rate", "30/1").split("/")
    fps = float(n) / float(d) if float(d) else 30.0
    return w, h, round(fps, 3)


def cutout(src, src_start, dur, out=None, prores=False, quality="balanced"):
    """src の [src_start, src_start+dur) を、人物だけ残した透過 .mov にして、そのパスを返す。"""
    src = os.path.abspath(os.path.expanduser(src))
    if out is None:
        key = hashlib.sha1(f"{src}|{os.path.getmtime(src)}|{src_start}|{dur}|{prores}|{quality}".encode()).hexdigest()[:16]
        out = os.path.join(CACHE, "cutout", f"{os.path.splitext(os.path.basename(src))[0]}_{key}.mov")
        if os.path.exists(out):
            return out
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    w, h, fps = _probe(src)
    # マスクは半分の大きさで作れば十分（ふちは書き出し時にぼかす）
    mw, mh = (w // 2) // 2 * 2, (h // 2) // 2 * 2
    exe = _binary()
    with tempfile.TemporaryDirectory() as td:
        fr, mk = os.path.join(td, "f"), os.path.join(td, "m")
        os.makedirs(fr)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(src_start), "-t", str(dur), "-i", src,
                        "-vf", f"fps={fps},scale={mw}:{mh}", os.path.join(fr, "%05d.png")], check=True)
        subprocess.run([exe, fr, mk, quality], check=True)
        fmt = "yuva444p10le" if prores else "bgra"
        graph = (f"[0:v]fps={fps},scale={w}:{h},format={fmt}[v];"
                 f"[1:v]scale={w}:{h},gblur=sigma=1.5,format=gray[m];[v][m]alphamerge[o]")
        enc = (["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"] if prores else
               ["-c:v", "hevc_videotoolbox", "-alpha_quality", "0.75", "-b:v", "12M", "-tag:v", "hvc1"])
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(src_start), "-t", str(dur), "-i", src,
                        "-framerate", str(fps), "-i", os.path.join(mk, "%05d.png"),
                        "-filter_complex", graph, "-map", "[o]", "-an", *enc, out], check=True)
    return out


def freeze(src, at, hold, out_dir=None, border=0.018, paper="#F7F3EA", shadow=0.35, bg_dim=0.08, bg_blur=3.0,
           quality="accurate"):
    """src の at 秒のコマで止める部品を作る。(背景の .mp4, 縁取りした人物の透過 .mov) を返す。
    border は縁の太さ（画面の短い辺に対する割合）。縁は paper の色に細かいざらつきを足した紙の質感。
    背景は少し暗く・ぼかして、手前の人物を浮かせる（bg_dim=0・bg_blur=0 でそのまま）。"""
    src = os.path.abspath(os.path.expanduser(src))
    key = hashlib.sha1(f"{src}|{os.path.getmtime(src)}|{at}|{hold}|{border}|{paper}|{shadow}|{bg_dim}|{bg_blur}|"
                       f"{quality}".encode()).hexdigest()[:16]
    out_dir = out_dir or os.path.join(CACHE, "freeze")
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, f"{os.path.splitext(os.path.basename(src))[0]}_{key}")
    bg, fg = base + "_bg.mp4", base + "_cut.mov"
    if os.path.exists(bg) and os.path.exists(fg):
        return bg, fg
    w, h, fps = _probe(src)
    r = max(2, round(min(w, h) * border))
    exe = _binary()
    with tempfile.TemporaryDirectory() as td:
        fr, mk = os.path.join(td, "f"), os.path.join(td, "m")
        os.makedirs(fr)
        frame = os.path.join(fr, "00001.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(at), "-i", src, "-frames:v", "1", frame], check=True)
        subprocess.run([exe, fr, mk, quality], check=True)
        mask = os.path.join(mk, "00001.png")
        # 人物のふち（少しぼかす）、縁（ぼかしてから二値にして膨らませる）、影（縁をずらしてぼかす）
        sd = max(2, r // 2)
        graph = (f"[1:v]scale={w}:{h},format=gray,split=2[m0][m1];"
                 f"[m0]gblur=sigma=1.5[ma];"
                 f"[m1]gblur=sigma={r / 1.6:.2f},lut=y='if(gt(val,10),255,0)',gblur=sigma=1.2,split=2[mb][ms];"
                 f"[0:v]format=rgba[f];[f][ma]alphamerge[person];"
                 f"color=c={paper}:s={w}x{h},noise=alls=14:allf=t,format=rgba[pp];[pp][mb]alphamerge[edge];"
                 f"color=c=black:s={w}x{h},format=rgba[sk];[ms]gblur=sigma={sd}[msb];[sk][msb]alphamerge,"
                 f"colorchannelmixer=aa={shadow}[sh];"
                 f"color=c=black@0:s={w}x{h},format=rgba[cv];"
                 f"[cv][sh]overlay=x={sd}:y={sd}:format=auto[c1];[c1][edge]overlay=format=auto[c2];"
                 f"[c2][person]overlay=format=auto,format=rgba[o]")
        still = os.path.join(td, "cut.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", frame, "-i", mask, "-filter_complex", graph,
                        "-map", "[o]", "-frames:v", "1", still], check=True)
        shutil.copy(still, base + "_cut.png")   # 確認用
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(fps), "-t", str(hold),
                        "-i", still, "-vf", "format=bgra", "-c:v", "hevc_videotoolbox", "-alpha_quality", "0.75",
                        "-b:v", "12M", "-tag:v", "hvc1", fg], check=True)
        look = [f"eq=brightness={-bg_dim}:saturation={1 - bg_dim * 2}"] if bg_dim else []
        look += [f"gblur=sigma={bg_blur}"] if bg_blur else []
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(fps), "-t", str(hold),
                        "-i", frame, "-vf", ",".join(look + ["format=yuv420p"]), "-c:v", "libx264", "-crf", "16",
                        bg], check=True)
    return bg, fg


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("src_start", type=float)
    ap.add_argument("dur", type=float)
    ap.add_argument("-o", "--out")
    ap.add_argument("--prores", action="store_true")
    ap.add_argument("--quality", default="balanced", choices=["fast", "balanced", "accurate"])
    a = ap.parse_args()
    print(cutout(a.src, a.src_start, a.dur, a.out, a.prores, a.quality))


if __name__ == "__main__":
    main()
