"""研究 165：日盤當沖 K 線規則家族（加權指數 1 分 K 近似台指期日盤；待研究 23 馬克羊短線）

資料：backtest/taiex_1min/YYYY.csv.gz（build_taiex_1min.py，證交所 5 秒指數 → 1 分 K，09:00～13:30）
指數 09:00～09:05 個股陸續開盤、指數失真，所以「開盤價」用 09:05 收盤；當沖一律 13:30 前出場（台指期 13:45 收，保守）
成本：每筆來回 3 點（換算成 %：3 ÷ 當天價位）；不留倉

規則（都是當天決定、當天平倉）：
A 開盤區間突破 ORB：09:05～09:05+N 分（N 10／25／55）的高低；之後第一根收盤突破就順勢進，停損＝區間另一側，13:30 出
B 日內動能（Gao 等 2018）：昨收→10:00 報酬的方向 → 13:00 進、13:30 出（最後半小時）；另版 → 10:00 進、13:30 出
C 跳空：09:05 相對昨收跳空 ≥ +x／≤ −x（x 0.5／1%）→ 反向（回補）09:05 進、13:30 出；另版順勢
D 早盤趨勢 → 午盤：09:05→11:00 漲跌 ≥ ±0.5% → 11:00 進，順勢或反向，13:30 出
每條規則多空都做；檢定：每筆淨報酬 sign-flip（2000 次）雙尾 p；家族 Bonferroni（×格數）；分段 2010–14／15–19／20–23／24–26
用法：python -X utf8 backtest/research_165_日內K線當沖家族.py
"""
import csv
import gzip
import io
import os
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "taiex_1min")
COST = 3.0
SEGS = [("2010", "2015"), ("2015", "2020"), ("2020", "2024"), ("2024", "2027")]


def load():
    days = defaultdict(dict)
    for fn in sorted(os.listdir(DIR)):
        if not fn.endswith(".csv.gz"):
            continue
        for r in csv.DictReader(io.TextIOWrapper(gzip.open(os.path.join(DIR, fn)), encoding="utf-8")):
            days[r["date"]][r["time"]] = (float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]))
    out = []
    for d in sorted(days):
        b = days[d]
        if "09:05" not in b or "13:30" not in b or len(b) < 200:
            continue
        out.append((d, b))
    return out


def px(b, t):
    """t 時點（分鐘收盤）價；沒有就往前找"""
    h, m = int(t[:2]), int(t[3:])
    for k in range(10):
        mm = h * 60 + m - k
        key = f"{mm // 60:02d}:{mm % 60:02d}"
        if key in b:
            return b[key][3]
    return None


def times(a, z):
    h, m = int(a[:2]), int(a[3:])
    H, M = int(z[:2]), int(z[3:])
    return [f"{x // 60:02d}:{x % 60:02d}" for x in range(h * 60 + m, H * 60 + M + 1)]


def trades(days):
    """回傳 {規則名: [(date, 淨報酬)]}"""
    T = defaultdict(list)
    prev_close = None
    for d, b in days:
        o, c = px(b, "09:05"), px(b, "13:30")
        cost = COST / o
        # A ORB
        for N in (10, 25, 55):
            rng = times("09:05", f"{(9 * 60 + 5 + N) // 60:02d}:{(9 * 60 + 5 + N) % 60:02d}")
            hs = [b[t][1] for t in rng if t in b]
            ls = [b[t][2] for t in rng if t in b]
            if not hs:
                continue
            hi, lo = max(hs), min(ls)
            side, entry, stop = 0, None, None
            for t in times(rng[-1], "13:29")[1:]:
                if t not in b:
                    continue
                cl = b[t][3]
                if side == 0:
                    if cl > hi:
                        side, entry, stop = 1, cl, lo
                    elif cl < lo:
                        side, entry, stop = -1, cl, hi
                elif (side == 1 and cl <= stop) or (side == -1 and cl >= stop):
                    T[f"A ORB{N} 順勢"].append((d, side * (cl / entry - 1) - cost))
                    side = 9
                    break
            if side in (1, -1):
                T[f"A ORB{N} 順勢"].append((d, side * (c / entry - 1) - cost))
        if prev_close:
            # B 日內動能
            r1 = px(b, "10:00") / prev_close - 1
            s = 1 if r1 > 0 else -1
            T["B 昨收→10:00 方向 → 最後半小時"].append((d, s * (c / px(b, "13:00") - 1) - cost))
            T["B 昨收→10:00 方向 → 10:00～收"].append((d, s * (c / px(b, "10:00") - 1) - cost))
            # C 跳空
            g = o / prev_close - 1
            for x in (0.005, 0.01):
                if abs(g) >= x:
                    s = 1 if g > 0 else -1
                    T[f"C 跳空≥{x:.1%} 回補"].append((d, -s * (c / o - 1) - cost))
                    T[f"C 跳空≥{x:.1%} 順勢"].append((d, s * (c / o - 1) - cost))
        # D 早盤趨勢 → 午盤
        m11 = px(b, "11:00")
        tr = m11 / o - 1
        if abs(tr) >= 0.005:
            s = 1 if tr > 0 else -1
            T["D 早盤±0.5% → 午盤順勢"].append((d, s * (c / m11 - 1) - cost))
            T["D 早盤±0.5% → 午盤反向"].append((d, -s * (c / m11 - 1) - cost))
        # E 盤中急跌逆勢：從 09:05 起第一次收盤跌（漲）≥ x → 下一分鐘收盤價進反向，13:30 出
        for x in (0.01, 0.015, 0.02):
            for t in times("09:06", "13:00"):
                if t in b:
                    ch = b[t][3] / o - 1
                    if ch <= -x:
                        T[f"E 盤中跌≥{x:.1%} 逆勢做多"].append((d, c / b[t][3] - 1 - cost))
                        break
                    if ch >= x:
                        T[f"E 盤中漲≥{x:.1%} 逆勢做空"].append((d, -(c / b[t][3] - 1) - cost))
                        break
        # F 最後一小時順勢：09:05→12:30 方向（|漲跌| ≥0.3%）→ 12:30 進、13:30 出
        m1230 = px(b, "12:30")
        tr2 = m1230 / o - 1
        if abs(tr2) >= 0.003:
            s = 1 if tr2 > 0 else -1
            T["F 尾盤一小時順勢"].append((d, s * (c / m1230 - 1) - cost))
        prev_close = c
    return T


def signflip(x, rng):
    x = np.asarray(x)
    m = x.mean()
    sims = np.array([(x * rng.choice((-1, 1), len(x))).mean() for _ in range(2000)])
    return (1 + np.sum(np.abs(sims) >= abs(m))) / 2001


def main():
    days = load()
    T = trades(days)
    K = len(T)
    rng = np.random.default_rng(165)
    out = [f"研究 165：日盤當沖 K 線家族（加權指數 1 分 K，{days[0][0]}～{days[-1][0]}，{len(days)} 天；每筆扣 3 點）",
           f"家族 {K} 條規則，Bonferroni＝p×{K}", ""]
    for nm, tr in T.items():
        v = np.array([x[1] for x in tr])
        p = signflip(v, rng)
        seg = "  ".join(f"{a[2:]}–{str(int(z) - 1)[2:]} {np.mean([x[1] for x in tr if a <= x[0] < z]) if any(a <= x[0] < z for x in tr) else 0:+.3%}"
                        for a, z in SEGS)
        out.append(f"{nm:28s} {len(v):5d} 筆  每筆 {v.mean():+.3%}  勝率 {np.mean(v > 0):.0%}  p {p:.3f}（Bonf {min(1, p * K):.3f}）  ｜{seg}")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究165_日內K線當沖家族.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
