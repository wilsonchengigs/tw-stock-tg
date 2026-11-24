"""研究 81（待研究 24）：融資過熱出場後的回補規則
現行：過熱出場後，要等「不過熱」且「站上 MA60×1.01」才進場（2026-06-26 過熱出場 44,572，08-14 才在 45,811 買回）。
變形（只影響「因過熱而出場」的那段空手期；跌破出場線出場的照舊）：
- A 過熱解除（偏離 < y_re）且指數 > MA60×b 就回補，b ∈ {0.98, 1.00}；y_re ∈ {17.5%（無遲滯）, 15%, 12.5%, 10%}
- B 過熱解除且指數仍在出場線（MA80×0.975）之上就回補（等於過熱只是暫停）
新版基準＝出場 2.5%＋融資過熱 250／17.5%；歷史 2002- 三段＋真實；融資偏離平移 100 次安慰劑（看全期）
用法：python -X utf8 backtest/research_81_過熱後回補.py
"""
import importlib.util
import itertools
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r41", os.path.join(HERE, "research_41_總經濾網.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
bt, DAYS, PX, N, WE = R.bt, R.DAYS, R.PX, R.N, R.WE
RR = R.R40.R32.R
DEV = [R.R40.R38.R.ratio_dev(i, 250) if i >= 250 else None for i in range(N)]
TH = 0.175


def run(start, end, mode=None, y_re=TH, b=1.0, dev=DEV, real=False, log=None):
    r2 = RR.R2R if real else bt.R2
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, on, pos, pend, heat_out = 0.0, False, False, None, False
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (r2[i] if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * 2
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if WE[i] and i >= 260:
            d = dev[i]
            hot = d is not None and d > TH
            p = PX[i]
            if on:
                if hot:
                    on, heat_out = False, True
                elif p < R.M80[i] * 0.975:
                    on, heat_out = False, False
            else:
                normal = p > R.M60[i] * 1.01 and not hot
                cool = d is None or d < y_re
                if heat_out and p < R.M80[i] * 0.975:
                    heat_out = False  # 過熱期間已經跌破出場線：回到一般規則
                early = False
                if heat_out and cool:
                    if mode == "A":
                        early = p > R.M60[i] * b
                    elif mode == "B":
                        early = p > R.M80[i] * 0.975
                if normal or early:
                    on, heat_out = True, False
            if on != pos:
                pend = on
                if log is not None:
                    log.append((DAYS[i], "進" if on else "出", round(p)))
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def main():
    rng = random.Random(81)
    L = ["研究 81：融資過熱出場後回補（全期 2002- | 前段 | 後段 | 真實；p＝100 次平移）"]
    base = [run(a, b_) for a, b_ in R.PER]
    L.append("新版基準 " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in base) + f" | 真實 {run(*R.REAL, real=True)[0]:.1%}")
    i0 = next(i for i in range(N) if DEV[i] is not None)
    seg = DEV[i0:]
    variants = [(f"A 偏離 < {y:.1%} 且 > MA60×{b}", dict(mode="A", y_re=y, b=b)) for y, b in itertools.product((0.175, 0.15, 0.125, 0.10), (0.98, 1.0))]
    variants += [(f"B 偏離 < {y:.1%} 且在出場線上", dict(mode="B", y_re=y)) for y in (0.175, 0.15, 0.125, 0.10)]
    for nm, kw in variants:
        rs = [run(a, b_, **kw) for a, b_ in R.PER]
        rr = run(*R.REAL, real=True, **kw)
        sims = []
        for _ in range(100):
            k = rng.randrange(250, len(seg) - 250)
            sh = [None] * i0 + seg[k:] + seg[:k]
            sims.append((run(*R.PER[0], dev=sh, **kw)[0], run(*R.PER[0], dev=sh)[0]))
        # 檢定「回補規則相對於不回補」的增益是否來自真實的融資序列
        gain = rs[0][0] - base[0][0]
        p = (sum(1 for a_, b_ in sims if a_ - b_ >= gain) + 1) / 101
        L.append(f"{nm:26s} " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%} | 增益 {gain:+.1%} p {p:.2f}")
        print(L[-1], flush=True)
    la, lb = [], []
    run("2024-01-01", "2026-12-31", log=la)
    run("2024-01-01", "2026-12-31", mode="B", y_re=0.15, log=lb)
    L.append("\n2024 起進出：新版 " + "、".join(f"{d}{x}{p}" for d, x, p in la) + "\n          B 15% " + "、".join(f"{d}{x}{p}" for d, x, p in lb))
    out = "\n".join(L) + "\n"
    print(L[-2] if len(L) > 1 else "")
    print(L[-1])
    open(os.path.join(HERE, "結果_研究81_過熱後回補.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
