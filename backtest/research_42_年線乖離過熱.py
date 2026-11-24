"""研究 42：價格面過熱——指數高於 MA240 超過 x 就出場且不進（新版基準：出場 2.5%＋融資過熱）
對照融資過熱：兩者是否重複、能否互補
用法：python -X utf8 backtest/research_42_年線乖離過熱.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r41", os.path.join(HERE, "research_41_總經濾網.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
bt, N, PX = R.bt, R.N, R.PX


def main():
    L = ["研究 42：年線乖離過熱（全期 2002- | 前段 | 後段 | 真實）"]
    base = [R.run(a, b) for a, b in R.PER]
    L.append("新版基準 " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in base) + f" | 真實 {R.run(*R.REAL, real=True)[0]:.1%}")
    for n in (120, 240):
        ma = bt.get_sma(n)
        for x in (0.20, 0.25, 0.30, 0.35, 0.40, 0.50):
            f = [ma[i] is not None and PX[i] > ma[i] * (1 + x) for i in range(N)]
            for mode in ("出場且不進", "只擋進場"):
                kw = dict(block=f, force=f) if mode == "出場且不進" else dict(block=f)
                rs = [R.run(a, b, **kw) for a, b in R.PER]
                rr = R.run(*R.REAL, real=True, **kw)
                days = sum(f[i] for i in range(N) if bt.DAYS[i] >= "2002")
                L.append(f"MA{n} 乖離 > {x:.0%} {mode}（觸發 {days} 天）  " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%}")
                print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究42_年線乖離過熱.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
