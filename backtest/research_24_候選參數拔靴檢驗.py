"""研究 24：把研究 11 的候選參數放到拔靴路徑上檢驗（同研究 20 的路徑，區塊 250 天，500 條 20 年）
看候選是否在「另一種歷史」裡也比現行好，而不只是剛好適合 1998～2026 這一條路徑
用法：python -X utf8 backtest/research_24_候選參數拔靴檢驗.py
"""
import importlib.util
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r20", os.path.join(HERE, "research_20_拔靴降險比較.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
bt = R.bt
TD, YEARS = R.TD, R.YEARS


def sma(px, k):
    n = len(px)
    out, s = [None] * n, 0.0
    for i in range(n):
        s += px[i]
        if i >= k:
            s -= px[i - k]
        if i >= k - 1:
            out[i] = s / k
    return out


def run(px, mas, p):
    ein, bi, eo, bo = p
    mi, mo = mas[ein], mas[eo]
    eq = peak = 1.0
    mdd, on, pos, pend = 0.0, False, False, None
    for i in range(261, len(px)):
        r1 = px[i] / px[i - 1] - 1 + bt.DIV / TD
        eq *= 1 + ((2 * r1 - bt.DRAG / TD) if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * 2
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if i % 5 == 0:
            on = (not px[i] < mo[i] * bo) if on else (px[i] > mi[i] * bi)
            if on != pos:
                pend = on
    return eq ** (1 / YEARS) - 1, mdd


def main():
    rng = random.Random(7)
    paths = [R.path(rng, 250) for _ in range(500)]
    cands = [(60, 1.01, 80, 0.98), (60, 1.01, 80, 0.975), (60, 1.01, 86, 0.975), (60, 1.01, 90, 0.975), (60, 1.01, 90, 0.98),
             (60, 1.0, 90, 0.98), (60, 1.0, 80, 0.98), (55, 1.005, 90, 0.98), (60, 1.01, 100, 0.98), (60, 1.01, 70, 0.98)]
    res = {p: [] for p in cands}
    for rets in paths:
        px = [100.0]
        for r in rets:
            px.append(px[-1] * (1 + r))
        mas = {k: sma(px, k) for k in (55, 60, 70, 80, 86, 90, 100)}
        for p in cands:
            res[p].append(run(px, mas, p))
    base = res[cands[0]]
    L = ["研究 24：候選參數在拔靴路徑上的表現（500 條 20 年、區塊 250 天）"]
    for p in cands:
        cs = [r[0] for r in res[p]]
        ms = [r[1] for r in res[p]]
        win = sum(1 for a, b in zip(res[p], base) if a[0] > b[0] + 1e-12) / 500
        L.append(f"進 MA{p[0]}x{p[1]}／出 MA{p[2]}x{p[3]:<6} 年化中位 {R.q(cs, .5):6.1%}（平均 {sum(cs) / 500:6.1%}） | 回檔中位 {R.q(ms, .5):6.1%}"
                 f" | P(<-50%) {sum(m < -0.5 for m in ms) / 500:5.1%} | 勝現行路徑比例 {win:5.1%}")
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究24_候選參數拔靴檢驗.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
