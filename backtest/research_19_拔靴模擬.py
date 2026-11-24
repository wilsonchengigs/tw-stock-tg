"""研究 19：區塊拔靴（block bootstrap）模擬，估計現行策略的風險分布

做法：把 1997～2026 加權指數日報酬切成平均長度 L 天的區塊（stationary bootstrap，Politis & Romano 1994），
隨機重組成 500 條 20 年的「另一種歷史」，在每條路徑上跑：
- 0050 買進持有、正2 買進持有、現行策略（2x）、現行策略 1.5x
記錄年化、最大回檔，回報：回檔超過 50% 的機率、跑輸 0050 的機率、年化分位數。
限制：區塊重組會打斷長期趨勢（例如 2000、2008 的長空頭被切碎），所以 L 用 60／120／250 天三種看敏感度
用法：python -X utf8 backtest/research_19_拔靴模擬.py
"""
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
DIV, DRAG = bt.DIV, bt.DRAG


def path(rng, L):
    out = []
    i = rng.randrange(T)
    while len(out) < LEN:
        out.append(RET[i])
        i += 1
        if i >= T or rng.random() < 1 / L:
            i = rng.randrange(T)
    return out


def simulate(rets):
    px = [100.0]
    for r in rets:
        px.append(px[-1] * (1 + r))
    n = len(px)
    s60 = s80 = 0.0
    m60, m80 = [None] * n, [None] * n
    for i in range(n):
        s60 += px[i]
        s80 += px[i]
        if i >= 60:
            s60 -= px[i - 60]
        if i >= 80:
            s80 -= px[i - 80]
        if i >= 59:
            m60[i] = s60 / 60
        if i >= 79:
            m80[i] = s80 / 80
    res = {}
    for name, lev, rule in (("0050", 1, False), ("正2", 2, False), ("現行 2x", 2, True), ("現行 1.5x", 1.5, True)):
        eq = peak = 1.0
        mdd, on, pos, pend = 0.0, False, False, None
        for i in range(261, n):
            r1 = px[i] / px[i - 1] - 1 + DIV / TD
            rl = lev * r1 - (lev - 1) * DRAG / TD
            if rule:
                eq *= 1 + (rl if pos else bt.RC)
                if pend is not None:
                    eq *= 1 - bt.COST * lev
                    pos, pend = pend, None
                if i % 5 == 0:
                    on = (not px[i] < m80[i] * 0.98) if on else (px[i] > m60[i] * 1.01)
                    if on != pos:
                        pend = on
            else:
                eq *= 1 + rl
            peak = max(peak, eq)
            mdd = min(mdd, eq / peak - 1)
        res[name] = (eq ** (1 / YEARS) - 1, mdd)
    return res


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def main():
    L = [f"研究 19：區塊拔靴模擬（500 條 {YEARS} 年路徑；年化分位數 5%/50%/95%；最大回檔中位數與 5% 最差；P(回檔<-50%)；P(年化輸 0050)）"]
    for Lb in (60, 120, 250):
        rng = random.Random(42 + Lb)
        sims = [simulate(path(rng, Lb)) for _ in range(500)]
        L.append(f"\n== 平均區塊長度 {Lb} 天 ==")
        for k in ("0050", "正2", "現行 2x", "現行 1.5x"):
            cs = [s[k][0] for s in sims]
            ms = [s[k][1] for s in sims]
            lose = sum(1 for s in sims if s[k][0] < s["0050"][0]) / len(sims)
            p50 = sum(1 for m in ms if m < -0.5) / len(sims)
            L.append(f"{k:10s} 年化 {q(cs, .05):6.1%} / {q(cs, .5):6.1%} / {q(cs, .95):6.1%} | 回檔中位 {q(ms, .5):6.1%}、最差 5% {q(ms, .05):6.1%}"
                     f" | P(回檔<-50%) {p50:5.1%} | P(輸 0050) {lose:5.1%}")
            print(L[-1], flush=True)
    out = "\n".join(L) + "\n"
    open(os.path.join(HERE, "結果_研究19_拔靴模擬.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()


def lev_sweep():
    """平均區塊 250 天，現行規則在不同槓桿下的風險（同一批路徑）"""
    rng = random.Random(7)
    paths = [path(rng, 250) for _ in range(500)]
    L = ["\n== 槓桿掃描（區塊 250 天，同一批 500 條路徑；現行進出場規則）=="]
    for lev in (1.0, 1.25, 1.5, 1.75, 2.0):
        cs, ms, b0 = [], [], []
        for p in paths:
            px = [100.0]
            for r in p:
                px.append(px[-1] * (1 + r))
            n = len(px)
            s60 = s80 = 0.0
            m60, m80 = [None] * n, [None] * n
            for i in range(n):
                s60 += px[i]; s80 += px[i]
                if i >= 60:
                    s60 -= px[i - 60]
                if i >= 80:
                    s80 -= px[i - 80]
                if i >= 59:
                    m60[i] = s60 / 60
                if i >= 79:
                    m80[i] = s80 / 80
            eq = peak = 1.0
            mdd, on, pos, pend = 0.0, False, False, None
            e0 = 1.0
            for i in range(261, n):
                r1 = px[i] / px[i - 1] - 1 + DIV / TD
                e0 *= 1 + r1
                eq *= 1 + ((lev * r1 - (lev - 1) * DRAG / TD) if pos else bt.RC)
                if pend is not None:
                    eq *= 1 - bt.COST * lev
                    pos, pend = pend, None
                if i % 5 == 0:
                    on = (not px[i] < m80[i] * 0.98) if on else (px[i] > m60[i] * 1.01)
                    if on != pos:
                        pend = on
                peak = max(peak, eq)
                mdd = min(mdd, eq / peak - 1)
            cs.append(eq ** (1 / YEARS) - 1)
            ms.append(mdd)
            b0.append(e0 ** (1 / YEARS) - 1)
        p50 = sum(1 for m in ms if m < -0.5) / len(ms)
        p40 = sum(1 for m in ms if m < -0.4) / len(ms)
        lose = sum(1 for c, b in zip(cs, b0) if c < b) / len(cs)
        L.append(f"{lev:.2f}x 年化中位 {q(cs, .5):6.1%}（5% {q(cs, .05):6.1%}） | 回檔中位 {q(ms, .5):6.1%}、最差 5% {q(ms, .05):6.1%}"
                 f" | P(<-40%) {p40:5.1%} | P(<-50%) {p50:5.1%} | P(輸 0050) {lose:5.1%}")
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究19_拔靴模擬.txt"), "a", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    lev_sweep()
