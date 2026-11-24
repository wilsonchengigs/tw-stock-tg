"""研究 37：假跌破回補——出場後 W 週內，指數重新站上 MA80×(1+b) 就直接回補（不必等 MA60×1.01）
歷史＋拔靴路徑（研究 24 同路徑）
用法：python -X utf8 backtest/research_37_假跌破回補.py
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
PX, WE, N = bt.PX, bt.WEEK_END, len(bt.PX)


def sig(px, we, m60, m80, W, b, start=260):
    st, since, out = False, 10 ** 9, []
    for i in range(len(px)):
        if we[i] and i >= start:
            if st:
                if px[i] < m80[i] * 0.975:
                    st, since = False, 0
            else:
                since += 1
                if px[i] > m60[i] * 1.01 or (W and since <= W and px[i] > m80[i] * (1 + b)):
                    st = True
        out.append(st)
    return out


def boot(W, b, paths):
    res = []
    for rets in paths:
        px = [100.0]
        for r in rets:
            px.append(px[-1] * (1 + r))
        m60, m80 = R24.sma(px, 60), R24.sma(px, 80)
        we = [i % 5 == 0 for i in range(len(px))]
        s = sig(px, we, m60, m80, W, b, 261)
        eq = peak = 1.0
        mdd, pos, pend = 0.0, False, None
        for i in range(261, len(px)):
            r1 = px[i] / px[i - 1] - 1 + bt.DIV / bt.TD
            eq *= 1 + ((2 * r1 - bt.DRAG / bt.TD) if pos else bt.RC)
            if pend is not None:
                eq *= 1 - bt.COST * 2
                pos, pend = pend, None
            peak = max(peak, eq)
            mdd = min(mdd, eq / peak - 1)
            if we[i] and s[i] != pos:
                pend = s[i]
        res.append((eq ** (1 / R24.YEARS) - 1, mdd))
    return res


def main():
    m60, m80 = bt.get_sma(60), bt.get_sma(80)
    rng = random.Random(7)
    paths = [R24.R.path(rng, 250) for _ in range(300)]
    base = boot(0, 0, paths)
    L = ["研究 37：假跌破回補（歷史：全期 | 前段 | 後段 | 真實；拔靴 300 條：年化中位、P(<-50%)、勝現行）"]
    for W, b in [(0, 0)] + list(itertools.product((2, 4, 8), (0.0, 0.01, 0.02))):
        r, rr = R11.evaluate(sig(PX, WE, m60, m80, W, b))
        bs = base if W == 0 else boot(W, b, paths)
        cs = sorted(x[0] for x in bs)
        win = sum(1 for x, y in zip(bs, base) if x[0] > y[0] + 1e-12) / len(bs)
        L.append(f"{'現行' if W == 0 else f'{W} 週內站上 MA80x{1 + b:.2f} 回補':26s} {R11.fmt(r, rr)} || 拔靴 {cs[150]:6.1%}、P {sum(x[1] < -0.5 for x in bs) / len(bs):5.1%}、勝 {win:5.1%}")
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究37_假跌破回補.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
