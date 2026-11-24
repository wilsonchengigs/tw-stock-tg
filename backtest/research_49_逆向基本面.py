"""研究 49：逆向基本面——基本面最差（出口年增 < 0 或燈號藍燈）時深跌反彈才提早進場
研究 48 的事件研究：深跌時出口年增 < 0 的 16 次，120 日 +21%、上漲 94%。這裡寫成策略驗證，並加平移安慰劑。
規則同研究 48（深跌 ≥ d、從近 10 日低點反彈 3%、停損近期低點、站上 MA60×1.01 轉正常；新版基準含融資濾網）
用法：python -X utf8 backtest/research_49_逆向基本面.py
"""
import importlib.util
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r48", os.path.join(HERE, "research_48_基本面景氣.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
N = R.N


def main():
    rng = random.Random(49)
    L = ["研究 49：逆向基本面提早進場（全期 2002- | 前段 | 後段 | 真實；p＝100 次平移）"]
    base = [R.run(a, b) for a, b in R.R.PER]
    L.append("新版基準 " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in base) + f" | 真實 {R.run(*R.R.REAL, real=True)[0]:.1%}")
    tests = []
    for g in (0.0, -0.05, -0.10):
        tests.append((f"出口年增 < {g:.0%}", R.EX, (lambda v, g=g: v is not None and v < g)))
    for s in (16, 22, 25):
        tests.append((f"燈號 ≤ {s}", R.SC, (lambda v, s=s: v is not None and v <= s)))
    tests.append(("領先指標 6 月下降", R.LD6, (lambda v: v is not None and v < 0)))
    for d in (0.15, 0.20, 0.25):
        for nm, raw, fn in tests:
            flag = [fn(v) for v in raw]
            rs = [R.run(a, b, strong=flag, d=d) for a, b in R.R.PER]
            rr = R.run(*R.R.REAL, real=True, strong=flag, d=d)
            sims = []
            for _ in range(100):
                sh = R.shifted(raw, rng)
                sims.append(R.run(*R.R.PER[0], strong=[fn(v) for v in sh], d=d)[0])
            p = (sum(x >= rs[0][0] for x in sims) + 1) / 101
            L.append(f"深跌 ≥{d:.0%} 且 {nm:14s} " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%} | p {p:.2f}")
            print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究49_逆向基本面.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
