#!/usr/bin/env bash
# 見本用の素材を ffmpeg で作る（人物・実写・他人の音源を含まない合成素材）
set -euo pipefail
cd "$(dirname "$0")"; mkdir -p assets; cd assets
ff() { ffmpeg -hide_banner -loglevel error -y "$@"; }
# 横長 10 秒（動く図形＋時刻）と小さな音
ff -f lavfi -i testsrc2=size=1920x1080:rate=30:duration=10 -f lavfi -i sine=frequency=330:duration=10 \
   -af volume=0.2 -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest landscape.mp4
# 縦長 5 秒（色が流れる背景）
ff -f lavfi -i "gradients=size=1080x1920:rate=30:duration=5:speed=0.02" -c:v libx264 -pix_fmt yuv420p portrait.mp4
# BGM（和音 12 秒）・効果音（打つ音・風を切る音）
ff -f lavfi -i "aevalsrc=0.15*sin(2*PI*262*t)+0.12*sin(2*PI*330*t)+0.1*sin(2*PI*392*t):d=12" bgm.wav
ff -f lavfi -i "aevalsrc=0.9*sin(2*PI*90*t)*exp(-12*t):d=0.4" hit.wav
ff -f lavfi -i "anoisesrc=d=0.4:c=pink:a=0.5" -af "afade=t=in:d=0.3,afade=t=out:st=0.3:d=0.1,highpass=f=800" whoosh.wav
ls -1
