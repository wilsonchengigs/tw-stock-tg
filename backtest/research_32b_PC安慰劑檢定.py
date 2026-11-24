"""研究 32b：P/C 提早進場的安慰劑檢定（placebo / circular-shift test）
把 P/C 百分位序列整段循環平移（位移 ≥ 250 個交易日），保留 P/C 本身的自相關與觸發頻率，但打斷它和股價的時間對應。
若真實序列的成績明顯好過大多數平移序列，才代表 P/C 本身有資訊；否則好處來自「提早進場＋停損」機制或運氣。
用法：python -X utf8 backtest/research_32b_PC安慰劑檢定.py
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
N = R.N
valid = [i for i in range(N) if R.PR[i] is not None]
i_first = valid[0]
seg = R.PR[i_first:]
M = len(seg)


def with_pr(pr, **kw):
    old = R.PR
    R.PR = pr
    try:
        return R.run("2002-01-01", "2026-12-31", **kw)[0]
    finally:
        R.PR = old


def main():
    rng = random.Random(3)
    L = ["研究 32b：P/C 提早進場安慰劑檢定（200 次循環平移，位移 250 日～總長-250 日；看全期 2002～2026 年化）"]
    base = R.run("2002-01-01", "2026-12-31")[0]
    L.append(f"現行（不提早進場）：{base:.1%}")
    for cfg in (dict(q=0.95, L=10, c=0.03, T=13), dict(q=0.95, L=20, c=0.03, T=13), dict(q=0.99, L=10, c=0.03, T=13), dict(q=0.90, L=10, c=0.03, T=13)):
        for lev in (2.0, 1.0):
            real = R.run("2002-01-01", "2026-12-31", lev_early=lev, **cfg)[0]
            sims = []
            for _ in range(200):
                k = rng.randrange(250, M - 250)
                sh = seg[k:] + seg[:k]
                pr = [None] * i_first + sh
                sims.append(with_pr(pr, lev_early=lev, **cfg))
            sims.sort()
            p = (sum(1 for x in sims if x >= real) + 1) / (len(sims) + 1)
            L.append(f"{cfg} 早進 {lev:.0f}x：真實 P/C {real:.1%}｜平移 中位 {sims[100]:.1%}、90 分位 {sims[180]:.1%}、最高 {sims[-1]:.1%}｜p＝{p:.3f}")
            print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究32b_PC安慰劑檢定.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
