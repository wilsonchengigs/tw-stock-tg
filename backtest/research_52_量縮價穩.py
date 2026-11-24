"""研究 52：「量縮價穩」打底（台股常見說法）
量縮：近 20 日平均成交金額 ÷ 近 250 日平均 ≤ v；價穩：近 k 週沒有創 60 日新低；深跌：距 250 日高點 ≥ d
空手時三者成立且收盤 > 近 20 日低點 ×1.03 → 提早進場（停損近 20 日低點、站上 MA60×1.01 轉正常）
新版基準；安慰劑：成交金額比值序列循環平移 100 次
用法：python -X utf8 backtest/research_52_量縮價穩.py
"""
import importlib.util
import itertools
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r48", os.path.join(HERE, "research_48_基本面景氣.py"))
R48 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R48)
spec = importlib.util.spec_from_file_location("r30", os.path.join(HERE, "research_30_底部爆量.py"))
R30 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R30)
R, bt, PX, N, DAYS = R48.R, R48.bt, R48.PX, R48.N, R48.DAYS
VOL = R30.VOL


def ratio20_250():
    out = [None] * N
    s20 = s250 = 0.0
    q20, q250 = [], []
    for i, v in enumerate(VOL):
        if v is None:
            continue
        q20.append(v)
        q250.append(v)
        s20 += v
        s250 += v
        if len(q20) > 20:
            s20 -= q20.pop(0)
        if len(q250) > 250:
            s250 -= q250.pop(0)
        if len(q250) == 250:
            out[i] = (s20 / 20) / (s250 / 250)
    return out


VR = ratio20_250()


def flag_of(vr, v, k, d):
    lo60 = [min(PX[max(0, i - 59):i + 1]) for i in range(N)]
    out = []
    for i in range(N):
        if vr[i] is None or i < 300:
            out.append(False)
            continue
        stable = all(lo60[j] < PX[j] or j < i - k * 5 for j in range(i - k * 5, i + 1)) and min(PX[i - k * 5:i + 1]) > lo60[i - k * 5] * 0.999
        out.append(vr[i] <= v and stable and min(PX[i - 20:i + 1]) / R48.HI[i] - 1 <= -d)
    return out


def main():
    rng = random.Random(52)
    L = ["研究 52：量縮價穩提早進場（全期 2002- | 前段 | 後段 | 真實；p＝100 次平移）"]
    base = [R48.run(a, b) for a, b in R.PER]
    L.append("新版基準 " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in base))
    for v, k, d in itertools.product((0.6, 0.7, 0.8), (2, 4), (0.15, 0.25)):
        flag = flag_of(VR, v, k, d)
        rs = [R48.run(a, b, strong=flag, d=0.0) for a, b in R.PER]
        rr = R48.run(*R.REAL, real=True, strong=flag, d=0.0)
        sims = []
        for _ in range(100):
            sims.append(R48.run(*R.PER[0], strong=flag_of(R48.shifted(VR, rng), v, k, d), d=0.0)[0])
        p = (sum(x >= rs[0][0] for x in sims) + 1) / 101
        L.append(f"量 ≤ {v:.0%} 均量、{k} 週不破底、深跌 ≥{d:.0%}（觸發 {sum(flag)} 天）  " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs)
                 + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%} | p {p:.2f}")
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究52_量縮價穩.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
