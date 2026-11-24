"""研究 82（待研究 25）：出場緩衝依波動調整
現行固定：跌破 MA80×(1−2.5%) 出場。改成 緩衝＝k × σ，σ＝近 n 日日報酬標準差 × √n_h（把日波動換成約 n_h 日的波動），
高波動時放寬（避免被正常震盪洗出）、低波動時收緊；另加上下限 [1%, 6%]。
參數：n ∈ {20, 60}，n_h ∈ {5, 10}，k ∈ {0.5, 0.75, 1.0, 1.25, 1.5}
新版基準（進場 MA60×1.01、融資過熱）；歷史三段＋真實＋拔靴 300 條（不含融資濾網）
用法：python -X utf8 backtest/research_82_波動出場緩衝.py
"""
import importlib.util
import itertools
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r41", os.path.join(HERE, "research_41_總經濾網.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
spec = importlib.util.spec_from_file_location("r24", os.path.join(HERE, "research_24_候選參數拔靴檢驗.py"))
R24 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R24)
bt, DAYS, PX, N, WE, HOT = R.bt, R.DAYS, R.PX, R.N, R.WE, R.HOT
RR = R.R40.R32.R


def vol_arr(px, n):
    lr = [0.0] + [math.log(px[i] / px[i - 1]) for i in range(1, len(px))]
    out, s, s2 = [None] * len(px), 0.0, 0.0
    for i in range(len(px)):
        s += lr[i]
        s2 += lr[i] ** 2
        if i >= n:
            s -= lr[i - n]
            s2 -= lr[i - n] ** 2
        if i >= n:
            out[i] = math.sqrt(max(s2 / n - (s / n) ** 2, 0))
    return out


def band_fn(vol, k, nh):
    if k is None:
        return lambda i: 0.025
    return lambda i: 0.025 if vol[i] is None else min(0.06, max(0.01, k * vol[i] * math.sqrt(nh)))


def core(px, we, m60, m80, hot, band, i0, i1, r2):
    eq = peak = 1.0
    mdd, on, pos, pend = 0.0, False, False, None
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (r2[i] if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * 2
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if we[i] and i >= 261:
            h = hot[i] if hot else False
            on = (not (px[i] < m80[i] * (1 - band(i)) or h)) if on else (px[i] > m60[i] * 1.01 and not h)
            if on != pos:
                pend = on
    return eq, mdd


def hist(n, nh, k, start, end, real=False):
    r2 = RR.R2R if real else bt.R2
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq, mdd = core(PX, WE, R.M60, R.M80, HOT, band_fn(vol_arr(PX, n), k, nh), i0, i1, r2)
    return eq ** (bt.TD / (i1 - i0)) - 1, mdd


def boot(n, nh, k, paths):
    out = []
    for rets in paths:
        px = [100.0]
        for r in rets:
            px.append(px[-1] * (1 + r))
        r2 = [0.0] + [2 * (px[i] / px[i - 1] - 1 + bt.DIV / bt.TD) - bt.DRAG / bt.TD for i in range(1, len(px))]
        we = [i % 5 == 0 for i in range(len(px))]
        eq, mdd = core(px, we, R24.sma(px, 60), R24.sma(px, 80), None, band_fn(vol_arr(px, n), k, nh), 261, len(px) - 1, r2)
        out.append((eq ** (1 / R24.YEARS) - 1, mdd))
    return out


def main():
    rng = random.Random(7)
    paths = [R24.R.path(rng, 250) for _ in range(300)]
    b0 = boot(20, 5, None, paths)
    v20 = vol_arr(PX, 20)
    L = ["研究 82：出場緩衝依波動調整（歷史 全期 2002- | 前段 | 後段 | 真實；拔靴 300 條：年化中位、P(<-50%)、勝固定 2.5%）",
         f"參考：近 20 日日波動 × √5 的中位數 {sorted(x for x in v20 if x)[len([x for x in v20 if x]) // 2] * math.sqrt(5):.2%}（固定緩衝 2.5% 約等於 k≈1）"]
    for n, nh, k in [(20, 5, None)] + list(itertools.product((20, 60), (5, 10), (0.5, 0.75, 1.0, 1.25, 1.5))):
        rs = [hist(n, nh, k, a, b) for a, b in R.PER]
        rr = hist(n, nh, k, *R.REAL, real=True)
        b = b0 if k is None else boot(n, nh, k, paths)
        cs = sorted(x[0] for x in b)
        win = sum(1 for x, y in zip(b, b0) if x[0] > y[0] + 1e-12) / len(b)
        nm = "固定 2.5%（新版）" if k is None else f"n={n} ×√{nh} k={k}"
        L.append(f"{nm:18s} " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%} || 拔靴 {cs[150]:.1%}、P {sum(x[1] < -0.5 for x in b) / len(b):.0%}、勝 {win:.0%}")
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究82_波動出場緩衝.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
