"""研究 36：台指選 P/C 未平倉比用在出場端
A 持有中 P/C ≤ 過去 250 日 q 分位（過度樂觀）且指數 < MA20 → 提早出場
B 碰到出場線（< MA80×0.975）但近 10 日 P/C ≥ 95 分位（下方有支撐）→ 延後出場，改用「跌破近 20 日低點」才出
基準：現行（2002–2026）；A、B 各自與研究 32 的提早進場合併再看一次；平移安慰劑 100 次
用法：python -X utf8 backtest/research_36_PC出場.py
"""
import importlib.util
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r32", os.path.join(HERE, "research_32_PC比提早進場.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
bt = R.bt
DAYS, PX, N, WE = R.DAYS, R.PX, R.N, R.WE
M20, M60, M80 = bt.get_sma(20), R.M60, R.M80


def run(start, end, exit_mode=None, qa=0.05, early=False, real=False):
    r2 = R.R.R2R if real else bt.R2
    PR = R.PR
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, st, pos, pend, stop = 0.0, 0, False, None, 0.0
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (r2[i] if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * 2
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if not WE[i] or i < 260:
            continue
        new = st
        if st == 0:
            if PX[i] > M60[i] * 1.01:
                new = 2
            elif early and any(PR[j] is not None and PR[j] >= 0.95 for j in range(i - 10, i + 1)):
                lo = min(PX[i - 10:i + 1])
                if PX[i] > lo * 1.03:
                    new, stop = 1, lo
        elif st == 1:
            if PX[i] > M60[i] * 1.01:
                new = 2
            elif PX[i] < stop:
                new = 0
        else:
            out = PX[i] < M80[i] * 0.975
            if exit_mode == "A" and PR[i] is not None and PR[i] <= qa and PX[i] < M20[i]:
                out = True
            if exit_mode == "B" and out and any(PR[j] is not None and PR[j] >= 0.95 for j in range(i - 10, i + 1)):
                out = PX[i] < min(PX[i - 20:i])
            new = 0 if out else 2
        st = new
        if (st != 0) != pos:
            pend = st != 0
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def ev(**kw):
    return [run(a, b, **kw) for a, b in R.PER], run(*R.REAL, real=True, **kw)


def placebo(kw, rng, n=100):
    pr = R.PR
    valid = [i for i in range(N) if pr[i] is not None]
    i0 = valid[0]
    seg = pr[i0:]
    real = run("2002-01-01", "2026-12-31", **kw)[0]
    sims = []
    for _ in range(n):
        k = rng.randrange(250, len(seg) - 250)
        R.PR = [None] * i0 + seg[k:] + seg[:k]
        sims.append(run("2002-01-01", "2026-12-31", **kw)[0])
    R.PR = pr
    return (sum(x >= real for x in sims) + 1) / (n + 1)


def main():
    rng = random.Random(21)
    L = ["研究 36：P/C 用在出場（全期 2002- | 前段 | 後段 | 真實）"]
    for nm, kw in (("現行", {}), ("A P/C ≤5 分位＋< MA20 提早出", dict(exit_mode="A", qa=0.05)), ("A P/C ≤10 分位＋< MA20 提早出", dict(exit_mode="A", qa=0.10)),
                   ("B P/C 高時延後出場", dict(exit_mode="B")), ("研究 32 提早進場", dict(early=True)),
                   ("研究 32 提早進＋A(5)", dict(early=True, exit_mode="A", qa=0.05)), ("研究 32 提早進＋B", dict(early=True, exit_mode="B"))):
        rs, rr = ev(**kw)
        p = placebo(kw, rng) if kw else None
        L.append(f"{nm:28s} {R.fmt(rs, rr)}" + (f" | 安慰劑 p {p:.2f}" if p is not None else ""))
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究36_PC出場.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
