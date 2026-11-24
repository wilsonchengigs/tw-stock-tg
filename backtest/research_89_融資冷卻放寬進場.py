"""研究 89：融資冷卻時放寬進場（融資過熱濾網的反面）
想法：融資÷指數 遠低於 250 日均（散戶槓桿已退場）時，進場線從 MA60×1.01 放寬到 MA60×b（或 MA(m)×1.00），讓進場早一點
規則：v3（strategy_v3），只改空手時的進場條件：偏離 < −c 或 z < −zc 時，用放寬的進場線
參數：c ∈ {10, 15, 20%}（或 z < −1.5／−2）、放寬線 ∈ {MA60×1.00, MA60×0.98, MA40×1.00}
平移安慰劑 100 次（看全期）
用法：python -X utf8 backtest/research_89_融資冷卻放寬進場.py
"""
import importlib.util
import itertools
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("v3", os.path.join(HERE, "strategy_v3.py"))
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)
bt, DAYS, PX, N, WE = V.bt, V.DAYS, V.PX, V.N, V.WE
M40 = bt.get_sma(40)


def run(start, end, cool=None, line=None, real=False, cdev=None, cz=None):
    """cdev／cz：只用來判斷「冷卻」的序列（安慰劑時平移它們；過熱判斷永遠用真實序列）"""
    dev, z = V.DEV, V.Z
    cdev = cdev or dev
    cz = cz or z
    r2 = V.R2R if real else bt.R2
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, st, heat_out, pos, pend = 0.0, 0, False, False, None
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (r2[i] if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * 2
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if WE[i] and i >= 260:
            d_, z_ = dev[i], z[i]
            hot = d_ is not None and (d_ > 0.175 or z_ > 2.0)
            p = PX[i]
            above = p >= V.M80[i] * 0.975
            if st == 0:
                if heat_out and not above:
                    heat_out = False
                cooled = d_ is None or (d_ < 0.125 and z_ <= 2.0)
                entry = p > V.M60[i] * 1.01
                if cool:
                    kind, thr = cool
                    cd, cz_ = cdev[i], cz[i]
                    is_cool = cd is not None and ((cd < -thr) if kind == "dev" else (cz_ < -thr))
                    if is_cool:
                        if line == "MA60x1.00":
                            entry = entry or p > V.M60[i]
                        elif line == "MA60x0.98":
                            entry = entry or p > V.M60[i] * 0.98
                        elif line == "MA40x1.00":
                            entry = entry or p > M40[i]
                if (entry and not hot) or (heat_out and cooled and above):
                    st, heat_out = 1, False
            elif hot:
                st, heat_out = 0, True
            elif not above:
                st, heat_out = 0, False
            if (st == 1) != pos:
                pend = st == 1
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def shifted(x, k):
    i0 = next(i for i in range(N) if x[i] is not None)
    seg = x[i0:]
    return [None] * i0 + seg[k:] + seg[:k]


def main():
    rng = random.Random(89)
    L = ["研究 89：融資冷卻放寬進場（v3 基準；全期 2002- | 前段 | 後段 | 真實；p＝100 次平移，只平移冷卻判斷）"]
    base = [run(a, b) for a, b in V.PER]
    L.append("v3 " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in base) + f" | 真實 {run(*V.REAL, real=True)[0]:.1%}")
    i0 = next(i for i in range(N) if V.DEV[i] is not None)
    M = N - i0
    for cool, line in itertools.product((("dev", 0.10), ("dev", 0.15), ("dev", 0.20), ("z", 1.5), ("z", 2.0)), ("MA60x1.00", "MA60x0.98", "MA40x1.00")):
        rs = [run(a, b, cool, line) for a, b in V.PER]
        rr = run(*V.REAL, cool, line, real=True)
        sims = []
        for _ in range(100):
            k = rng.randrange(250, M - 250)
            sims.append(run(*V.PER[0], cool, line, cdev=shifted(V.DEV, k), cz=shifted(V.Z, k))[0])
        p = (sum(x >= rs[0][0] for x in sims) + 1) / 101
        nm = f"{'偏離 <' if cool[0] == 'dev' else 'z <'} -{cool[1]:g} 時 {line}"
        L.append(f"{nm:26s} " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%} | p {p:.2f}")
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究89_融資冷卻放寬進場.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
