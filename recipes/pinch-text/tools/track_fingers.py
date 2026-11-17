"""動画から親指と人差し指の先の位置を一定間隔で取り出す（MediaPipe Hands）。
出力: 1行1サンプルの JSON（t=元素材の秒、thumb/index=画面割合 0〜1、gap=指先の距離、mid=指先の中点）
使い方: uv run --python 3.11 --with mediapipe==0.10.14 --with opencv-python python track_fingers.py <video> <start> <end> [step=0.1]
"""
import json
import sys

import cv2
import mediapipe as mp

path, t0, t1 = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
step = float(sys.argv[4]) if len(sys.argv) > 4 else 0.1

cap = cv2.VideoCapture(path)
hands = mp.solutions.hands.Hands(static_image_mode=True, max_num_hands=1, min_detection_confidence=0.4)
t = t0
while t <= t1 + 1e-6:
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, frame = cap.read()
    if not ok:
        break
    h, w = frame.shape[:2]
    res = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    row = {"t": round(t, 2), "w": w, "h": h}
    if res.multi_hand_landmarks:
        lm = res.multi_hand_landmarks[0].landmark
        th, ix = lm[4], lm[8]
        row.update(
            thumb=[round(th.x, 3), round(th.y, 3)],
            index=[round(ix.x, 3), round(ix.y, 3)],
            mid=[round((th.x + ix.x) / 2, 3), round((th.y + ix.y) / 2, 3)],
            gap=round(((th.x - ix.x) ** 2 + ((th.y - ix.y) * h / w) ** 2) ** 0.5, 3),
        )
    print(json.dumps(row))
    t += step
