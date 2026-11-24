"""研究 25：進出場要連續 k 個週五確認（減少假突破／假跌破），歷史＋拔靴路徑
用法：python -X utf8 backtest/research_25_連續確認.py
"""
import importlib.util
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


def sig_confirm(px, we, mi, mo, kin, kout, bi=1.01, bo=0.98, start=260):
    st, cin, cout, out = False, 0, 0, []
    for i in range(len(px)):
        if we[i] and i >= start:
            if st:
                cout = cout + 1 if px[i] < mo[i] * bo else 0
                if cout >= kout:
                    st, cout = False, 0
            else:
                cin = cin + 1 if px[i] > mi[i] * bi else 0
                if cin >= kin:
                    st, cin = True, 0
        out.append(st)
    return out


def boot(kin, kout, bo, paths):
    res = []
    for rets in paths:
        px = [100.0]
        for r in rets:
            px.append(px[-1] * (1 + r))
        mi, mo = R24.sma(px, 60), R24.sma(px, 80)
        we = [i % 5 == 0 for i in range(len(px))]
        sig = sig_confirm(px, we, mi, mo, kin, kout, bo=bo, start=261)
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
            if we[i] and sig[i] != pos:
                pend = sig[i]
        res.append((eq ** (1 / R24.YEARS) - 1, mdd))
    return res


def main():
    mi, mo = bt.get_sma(60), bt.get_sma(80)
    rng = random.Random(7)
    paths = [R24.R.path(rng, 250) for _ in range(500)]
    base = boot(1, 1, 0.98, paths)
    L = ["研究 25：連續 k 週確認（歷史：全期 | 前段 | 後段 | 真實；拔靴：年化中位、P(<-50%)、勝現行比例）"]
    for kin, kout, bo in ((1, 1, 0.98), (2, 1, 0.98), (3, 1, 0.98), (1, 2, 0.98), (1, 3, 0.98), (2, 2, 0.98), (1, 2, 1.0), (1, 2, 0.99), (1, 1, 0.975)):
        r, rr = R11.evaluate(sig_confirm(PX, WE, mi, mo, kin, kout, bo=bo))
        b = boot(kin, kout, bo, paths)
        cs = sorted(x[0] for x in b)
        win = sum(1 for x, y in zip(b, base) if x[0] > y[0] + 1e-12) / 500
        L.append(f"進 {kin} 週／出 {kout} 週 出場線 MA80x{bo}  {R11.fmt(r, rr)} || 拔靴 {cs[250]:6.1%}、P {sum(x[1] < -0.5 for x in b) / 500:5.1%}、勝 {win:5.1%}")
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究25_連續確認.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
