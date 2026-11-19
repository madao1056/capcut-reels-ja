#!/usr/bin/env python3
"""人物だけを残した透過動画を作る（CapCut の有料「自動削除」の代わり）。

  python3 lib/cutout.py <素材> <src_start> <dur> [-o 出力.mov] [--prores] [--quality fast|balanced|accurate]

macOS 標準の Vision（人物セグメンテーション）で各コマの人物マスクを作り、元の映像に透過として重ねて書き出す。
追加インストール・モデルのダウンロードは不要（Xcode のコマンドラインツールの swiftc を使う）。
初回に lib/native/person_matte.swift をビルドして ~/.cache/capcut-reels-ja/ に置く。

書き出しは HEVC の透過（.mov、4秒で約7MB）。--prores で ProRes 4444（約280MB。HEVC が読めない環境向け）。
どちらも CapCut 9.8.0（Mac）で透過として読まれることを確認済み。
-o を省くと ~/.cache/capcut-reels-ja/cutout/ に、素材・区間ごとに1回だけ作る。
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
