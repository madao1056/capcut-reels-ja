"""指先の検出結果から、指の間の文字のキーフレームを作る。

- 冒頭〜follow_from 秒: 文字は小さいまま、その時点の指先の位置に固定（指のほうが寄ってくる）
- follow_from〜bang_at 秒: 位置は固定のまま、大きさだけ指の開きに合わせて育てる。指を戻しても縮めない
- bang_at 秒から: 加速しながら特大へ（ギュイン）→ 少し行き過ぎて戻る
- 検出結果が無いときは、x, y の位置で小→中へ一定の速さで育てる（見本・試し用）

時刻はすべてクリップの頭からの秒。fingers の t は元素材の秒なので src_start を引いて合わせる。
"""
import json

BASE_W = 0.33        # 文字 scale=1 の幅（画面幅に対する割合。14pt・4文字で実測）
FIT = 0.85           # 指先の横幅の何割に文字を収めるか
MIN_S, MAX_S = 0.25, 1.3
PEAK, SETTLE = 2.45, 2.25   # ギュインの行き過ぎ・落ち着く大きさ
RISE, BACK = 0.35, 0.10     # ギュインの加速にかける秒・戻りにかける秒


def _samples(fingers, src_start, follow_from, bang_at, step=0.1):
    rows = {round(r["t"], 2): r for r in fingers if "mid" in r}
    out = []
    t = follow_from
    while t < bang_at - 1e-6:
        r = rows.get(round(src_start + t, 2))
        if r:
            dx = abs(r["thumb"][0] - r["index"][0])
            s = min(MAX_S, max(MIN_S, FIT * dx / BASE_W))
            out.append([round(t, 2), s, (r["mid"][0] - 0.5) * 2, (0.5 - r["mid"][1]) * 2])
        t += step
    return out


def _smooth(rows):
    if len(rows) < 3:
        return rows
    sm = [rows[0]]
    for i in range(1, len(rows) - 1):
        sm.append([rows[i][0]] + [round(sum(rows[j][k] for j in (i - 1, i, i + 1)) / 3, 3) for k in (1, 2, 3)])
    sm.append(rows[-1])
    return sm


def make(fingers=None, src_start=0.0, follow_from=0.6, bang_at=2.6, x=0.0, y=0.0):
    """キーフレームの行（crj keyframes に渡す形）を返す。"""
    if fingers:
        sm = _smooth(_samples(fingers, src_start, follow_from, bang_at))
    else:
        sm = []
    if not sm:  # 検出なし: 一定の速さで育てる
        n = max(2, int((bang_at - follow_from) / 0.1))
        sm = [[round(follow_from + (bang_at - follow_from) * i / n, 2), MIN_S + (1.0 - MIN_S) * i / n, x, y]
              for i in range(n + 1)]
    ax, ay = sm[0][2], sm[0][3]
    peak = MIN_S
    rows = [[0.0, MIN_S, ax, ay]]
    for t, s, _, _ in sm:
        if t <= 0:
            continue
        peak = max(peak, s)   # 縮めない
        rows.append([t, peak, ax, ay])

    out = []

    def kf(prop, t, v, easing=None):
        d = {"property": prop, "time": f"{t:.2f}s", "value": round(v, 3)}
        if easing:
            d["easing"] = easing
        out.append(d)

    for t, s, px, py in rows:
        if t >= bang_at:
            break
        for p, v in (("scale_x", s), ("scale_y", s), ("position_x", px), ("position_y", py)):
            kf(p, t, v)
    last = rows[-1][1]
    for p in ("scale_x", "scale_y"):
        kf(p, bang_at, last, "ease-in")
    for p in ("scale_x", "scale_y"):
        kf(p, bang_at + RISE, PEAK, "ease-out")
    for p in ("scale_x", "scale_y"):
        kf(p, bang_at + RISE + BACK, SETTLE)
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fingers", help="track_fingers.py の出力（JSONL）")
    ap.add_argument("--src-start", type=float, default=0.0)
    ap.add_argument("--follow-from", type=float, default=0.6)
    ap.add_argument("--bang-at", type=float, default=2.6)
    ap.add_argument("--x", type=float, default=0.0)
    ap.add_argument("--y", type=float, default=0.0)
    a = ap.parse_args()
    fingers = [json.loads(l) for l in open(a.fingers) if l.strip()] if a.fingers else None
    for r in make(fingers, a.src_start, a.follow_from, a.bang_at, a.x, a.y):
        print(json.dumps(r))
