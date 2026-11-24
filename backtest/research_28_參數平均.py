"""研究 28：參數平均（ensemble）——資金平分給鄰近多組參數各自跑現行規則，降低「參數選擇的運氣」
組合：進場 MA{50,60,70} × 出場 MA{70,80,90}（緩衝固定 1.01／0.98）＝9 組；再加緩衝 {1.0,1.01,1.02}×{0.97,0.98,0.99} 的 27 組版
做法：每組一份子帳戶獨立運作（不互相再平衡），總淨值＝加總；歷史＋拔靴路徑（研究 24 同路徑）
用法：python -X utf8 backtest/research_28_參數平均.py
"""
import importlib.util
import itertools
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

spec = importlib.util.spec_from_file_location("r11", os.path.join(HERE, "research_11_進出場細掃.py"))
R11 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R11)
spec = importlib.util.spec_from_file_location("r24", os.path.join(HERE, "research_24_候選參數拔靴檢驗.py"))
R24 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R24)
PX, WE, N, DAYS = bt.PX, bt.WEEK_END, len(bt.PX), bt.DAYS


def ens_hist(params, key, real=False):
    i0, i1 = R11.IDX[key]
    r2 = R11.R2R if real else bt.R2
    sigs = [R11.signals(*p) for p in params]
    k = len(params)
    eqs, pos, pend = [1 / k] * k, [False] * k, [None] * k
    peak, mdd = 1.0, 0.0
    for i in range(i0, i1 + 1):
        for j in range(k):
            if i > i0:
                eqs[j] *= 1 + (r2[i] if pos[j] else bt.RC)
            if pend[j] is not None:
                eqs[j] *= 1 - bt.COST * 2
                pos[j], pend[j] = pend[j], None
            if WE[i] and sigs[j][i] != pos[j]:
                pend[j] = sigs[j][i]
        e = sum(eqs)
        peak = max(peak, e)
        mdd = min(mdd, e / peak - 1)
    yrs = (i1 - i0) / bt.TD
    return sum(eqs) ** (1 / yrs) - 1, mdd


def ens_boot(params, paths):
    out = []
    for rets in paths:
        px = [100.0]
        for r in rets:
            px.append(px[-1] * (1 + r))
        mas = {n: R24.sma(px, n) for n in {p[0] for p in params} | {p[2] for p in params}}
        k = len(params)
        eqs, on, pos, pend = [1 / k] * k, [False] * k, [False] * k, [None] * k
        peak, mdd = 1.0, 0.0
        for i in range(261, len(px)):
            r1 = px[i] / px[i - 1] - 1 + bt.DIV / bt.TD
            r2 = 2 * r1 - bt.DRAG / bt.TD
            for j, (ein, bi, eo, bo) in enumerate(params):
                eqs[j] *= 1 + (r2 if pos[j] else bt.RC)
                if pend[j] is not None:
                    eqs[j] *= 1 - bt.COST * 2
                    pos[j], pend[j] = pend[j], None
                if i % 5 == 0:
                    on[j] = (not px[i] < mas[eo][i] * bo) if on[j] else (px[i] > mas[ein][i] * bi)
                    if on[j] != pos[j]:
                        pend[j] = on[j]
            e = sum(eqs)
            peak = max(peak, e)
            mdd = min(mdd, e / peak - 1)
        out.append((sum(eqs) ** (1 / R24.YEARS) - 1, mdd))
    return out


def main():
    sets = {
        "現行單一組": [(60, 1.01, 80, 0.98)],
        "9 組（進 50/60/70 × 出 70/80/90）": [(a, 1.01, b, 0.98) for a, b in itertools.product((50, 60, 70), (70, 80, 90))],
        "9 組（緩衝 1.0/1.01/1.02 × 0.97/0.98/0.99）": [(60, a, 80, b) for a, b in itertools.product((1.0, 1.01, 1.02), (0.97, 0.98, 0.99))],
        "27 組（均線 3×3 × 進場緩衝 3）": [(a, c, b, 0.98) for a, b, c in itertools.product((50, 60, 70), (70, 80, 90), (1.0, 1.01, 1.02))],
    }
    rng = random.Random(7)
    paths = [R24.R.path(rng, 250) for _ in range(300)]
    base = ens_boot(sets["現行單一組"], paths)
    L = ["研究 28：參數平均（歷史：全期 | 前段 | 後段 | 真實；拔靴 300 條：年化中位、P(<-50%)、勝現行比例）"]
    for nm, ps in sets.items():
        h = [ens_hist(ps, p) for p in R11.PER]
        rr = ens_hist(ps, R11.REAL, real=True)
        b = base if len(ps) == 1 else ens_boot(ps, paths)
        cs = sorted(x[0] for x in b)
        win = sum(1 for x, y in zip(b, base) if x[0] > y[0] + 1e-12) / len(b)
        L.append(f"{nm:38s} " + " | ".join(f"{c * 100:5.1f}%/{m * 100:6.1f}%" for c, m in h)
                 + f" | 真實 {rr[0] * 100:5.1f}%/{rr[1] * 100:6.1f}% || 拔靴 {cs[len(cs) // 2]:6.1%}、P {sum(x[1] < -0.5 for x in b) / len(b):5.1%}、勝 {win:5.1%}")
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究28_參數平均.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
