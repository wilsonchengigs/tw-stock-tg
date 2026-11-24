"""研究 20：在拔靴路徑上比較「降風險的方法」誰比較有效率

研究 19 顯示現行 2x 在重組歷史中 P(回檔 < -50%) 約 74%。降風險的方法：
- 固定降槓桿（1.25～1.75x）
- 波動目標：在場時槓桿 = min(2, 目標 / 近 20 日年化波動)，週五調整（歷史回測研究 05 G 類報酬掉很多，但在拔靴路徑上的尾部風險可能不同）
- 帳戶回落降槓桿：淨值距高點 > 25% 時改 1x
比較同一批 500 條路徑（區塊 250 天）：年化中位、P(< -50%)、P(< -40%)
用法：python -X utf8 backtest/research_20_拔靴降險比較.py
"""
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

PX = bt.PX
RET = [PX[i] / PX[i - 1] - 1 for i in range(1, len(PX))]
T = len(RET)
YEARS, TD = 20, bt.TD
LEN = YEARS * TD + 260


def path(rng, L):
    out, i = [], rng.randrange(T)
    while len(out) < LEN:
        out.append(RET[i])
        i += 1
        if i >= T or rng.random() < 1 / L:
            i = rng.randrange(T)
    return out


def prep(rets):
    px = [100.0]
    for r in rets:
        px.append(px[-1] * (1 + r))
    n = len(px)
    def sma(k):
        out, s = [None] * n, 0.0
        for i in range(n):
            s += px[i]
            if i >= k:
                s -= px[i - k]
            if i >= k - 1:
                out[i] = s / k
        return out
    lr = [0.0] + [math.log(px[i] / px[i - 1]) for i in range(1, n)]
    vol = [None] * n
    s = s2 = 0.0
    for i in range(n):
        s += lr[i]; s2 += lr[i] ** 2
        if i >= 20:
            s -= lr[i - 20]; s2 -= lr[i - 20] ** 2
        if i >= 20:
            var = max(s2 / 20 - (s / 20) ** 2, 0)
            vol[i] = math.sqrt(var * TD)
    return px, sma(60), sma(80), vol


def run(pp, lev_fn):
    px, m60, m80, vol = pp
    n = len(px)
    eq = peak = 1.0
    mdd, on, lev, pend = 0.0, False, 0.0, None
    for i in range(261, n):
        r1 = px[i] / px[i - 1] - 1 + bt.DIV / TD
        eq *= 1 + ((lev * r1 - max(lev - 1, 0) * bt.DRAG / TD) if lev > 0 else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * abs(pend - lev)
            lev, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if i % 5 == 0:
            on = (not px[i] < m80[i] * 0.98) if on else (px[i] > m60[i] * 1.01)
            t = lev_fn(i, vol, eq / peak - 1) if on else 0.0
            if abs(t - lev) > 0.2 or (t == 0) != (lev == 0):
                pend = t
    return eq ** (1 / YEARS) - 1, mdd


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def main():
    rng = random.Random(7)
    pps = [prep(path(rng, 250)) for _ in range(500)]
    methods = [(f"固定 {l}x", (lambda l: lambda i, v, dd: l)(l)) for l in (1.25, 1.5, 1.75, 2.0)]
    for tgt in (0.20, 0.25, 0.30, 0.35):
        methods.append((f"波動目標 {tgt:.0%}（上限 2x）", (lambda t: lambda i, v, dd: min(2.0, t / v[i]) if v[i] else 1.0)(tgt)))
    for th in (0.15, 0.20, 0.25, 0.30):
        methods.append((f"回落 > {th:.0%} 改 1x", (lambda th: lambda i, v, dd: 1.0 if dd < -th else 2.0)(th)))
    L = ["研究 20：拔靴路徑上的降風險方法比較（500 條 20 年、區塊 250 天）"]
    for nm, fn in methods:
        res = [run(pp, fn) for pp in pps]
        cs, ms = [r[0] for r in res], [r[1] for r in res]
        L.append(f"{nm:22s} 年化中位 {q(cs, .5):6.1%}（5% {q(cs, .05):6.1%}） | 回檔中位 {q(ms, .5):6.1%}、最差 5% {q(ms, .05):6.1%}"
                 f" | P(<-40%) {sum(m < -0.4 for m in ms) / 500:5.1%} | P(<-50%) {sum(m < -0.5 for m in ms) / 500:5.1%}")
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究20_拔靴降險比較.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
