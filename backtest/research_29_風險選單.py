"""研究 29：風險選單——槓桿 1.25～2x × 出場線（MA80×0.98 現行／×0.975 建議），歷史＋拔靴
槓桿用「00631L 與 0050 混合」實現：1.5x＝50% 00631L＋50% 0050；1.25x＝25%＋75%；1.75x＝75%＋25%（出場時全部轉現金）
拔靴：500 條 20 年、區塊 250 天（研究 20／24 同產生方式）
用法：python -X utf8 backtest/research_29_風險選單.py
"""
import importlib.util
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402
import data  # noqa: E402

spec = importlib.util.spec_from_file_location("r24", os.path.join(HERE, "research_24_候選參數拔靴檢驗.py"))
R24 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R24)
DAYS, PX, WE, N = bt.DAYS, bt.PX, bt.WEEK_END, len(bt.DAYS)
PER = [("1998-01-01", "2026-12-31"), ("1998-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31")]
_, l1, l2 = data.series()


def real_ret(src, sim):
    px = [src.get(d, (None, None))[1] for d in DAYS]
    out, lp = [0.0], None
    for i in range(1, N):
        out.append(px[i] / lp - 1 if (px[i] and lp) else sim[i])
        if px[i]:
            lp = px[i]
    return out


R1R, R2R = real_ret(l1, bt.R1), real_ret(l2, bt.R2)


def hist(lev, bo, start, end, real=False):
    r1, r2 = (R1R, R2R) if real else (bt.R1, bt.R2)
    w2 = lev - 1
    mi, mo = bt.get_sma(60), bt.get_sma(80)
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(DAYS) if d <= end)
    eq = peak = 1.0
    mdd, on, pos, pend = 0.0, False, False, None
    b0 = 1.0
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + ((w2 * r2[i] + (1 - w2) * r1[i]) if pos else bt.RC)
            b0 *= 1 + r1[i]
        if pend is not None:
            eq *= 1 - bt.COST * lev
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if WE[i] and i >= 260:
            on = (not PX[i] < mo[i] * bo) if on else (PX[i] > mi[i] * 1.01)
            if on != pos:
                pend = on
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, b0 ** (1 / yrs) - 1


def boot(lev, bo, paths):
    out = []
    for rets in paths:
        px = [100.0]
        for r in rets:
            px.append(px[-1] * (1 + r))
        mi, mo = R24.sma(px, 60), R24.sma(px, 80)
        eq = peak = b0 = 1.0
        mdd, on, pos, pend = 0.0, False, False, None
        for i in range(261, len(px)):
            r1 = px[i] / px[i - 1] - 1 + bt.DIV / bt.TD
            b0 *= 1 + r1
            eq *= 1 + ((lev * r1 - (lev - 1) * bt.DRAG / bt.TD) if pos else bt.RC)
            if pend is not None:
                eq *= 1 - bt.COST * lev
                pos, pend = pend, None
            peak = max(peak, eq)
            mdd = min(mdd, eq / peak - 1)
            if i % 5 == 0:
                on = (not px[i] < mo[i] * bo) if on else (px[i] > mi[i] * 1.01)
                if on != pos:
                    pend = on
        out.append((eq ** (1 / R24.YEARS) - 1, mdd, b0 ** (1 / R24.YEARS) - 1))
    return out


def main():
    rng = random.Random(7)
    paths = [R24.R.path(rng, 250) for _ in range(500)]
    L = ["研究 29：風險選單（歷史 全期 | 前段 | 後段 | 真實 2015-09～；拔靴 500 條：年化中位、回檔中位、P(回檔<-50%)、P(輸 0050)）",
         "對照 0050 長抱：全期 8.6%/-64.6%、真實 20.2%/-33.8%"]
    for lev, mix in ((1.25, "00631L 25%＋0050 75%"), (1.5, "00631L 50%＋0050 50%"), (1.75, "00631L 75%＋0050 25%"), (2.0, "00631L 100%")):
        for bo in (0.98, 0.975):
            h = [hist(lev, bo, a, b) for a, b in PER]
            rr = hist(lev, bo, "2015-09-01", "2026-12-31", real=True)
            b = boot(lev, bo, paths)
            cs = sorted(x[0] for x in b)
            ms = sorted(x[1] for x in b)
            L.append(f"{lev:.2f}x（{mix}）出 MA80x{bo:<5} " + " | ".join(f"{c * 100:5.1f}%/{m * 100:6.1f}%" for c, m, _ in h)
                     + f" | 真實 {rr[0] * 100:5.1f}%/{rr[1] * 100:6.1f}% || 拔靴 {cs[250]:6.1%}、{ms[250]:6.1%}、P {sum(x[1] < -0.5 for x in b) / 500:5.1%}、輸 {sum(x[0] < x[2] for x in b) / 500:5.1%}")
            print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究29_風險選單.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
