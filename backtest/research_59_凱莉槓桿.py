"""研究 59：凱莉（Kelly）最適槓桿——依馬克羊「超過凱莉建議的下注尺度，長期翻倍速度反而下降」
對現行趨勢策略（出場 2.5%；拔靴路徑不含融資濾網，歷史含）掃描在場槓桿 0.5～4x，看：
- 長期成長率（年化，等同對數報酬平均）在哪個槓桿最大＝凱莉最適
- 中位數與最差 5% 路徑的年化、P(回檔 < -50%)、P(破產：回檔 < -90%)
槓桿 L 的日報酬＝L×(指數+配息) − (L−1)×1% 內扣（現實中 >2x 要用台指期，內扣近似資金成本）
用法：python -X utf8 backtest/research_59_凱莉槓桿.py
"""
import importlib.util
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r41", os.path.join(HERE, "research_41_總經濾網.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
spec = importlib.util.spec_from_file_location("r24", os.path.join(HERE, "research_24_候選參數拔靴檢驗.py"))
R24 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R24)
bt, DAYS, PX, N, WE, HOT = R.bt, R.DAYS, R.PX, R.N, R.WE, R.HOT
LEVS = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0)


def hist(lev, start, end):
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, on, pos, pend = 0.0, False, False, None
    for i in range(i0, i1 + 1):
        if i > i0:
            r1 = bt.R1[i]
            eq *= 1 + ((lev * r1 - max(lev - 1, 0) * bt.DRAG / bt.TD) if pos else bt.RC)
            eq = max(eq, 1e-9)
        if pend is not None:
            eq *= 1 - bt.COST * lev
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if WE[i] and i >= 260:
            on = (not (PX[i] < R.M80[i] * 0.975 or HOT[i])) if on else (PX[i] > R.M60[i] * 1.01 and not HOT[i])
            if on != pos:
                pend = on
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def boot(lev, paths):
    out = []
    for rets in paths:
        px = [100.0]
        for r in rets:
            px.append(px[-1] * (1 + r))
        m60, m80 = R24.sma(px, 60), R24.sma(px, 80)
        eq = peak = 1.0
        mdd, on, pos, pend = 0.0, False, False, None
        for i in range(261, len(px)):
            r1 = px[i] / px[i - 1] - 1 + bt.DIV / bt.TD
            eq *= 1 + ((lev * r1 - max(lev - 1, 0) * bt.DRAG / bt.TD) if pos else bt.RC)
            eq = max(eq, 1e-9)
            if pend is not None:
                eq *= 1 - bt.COST * lev
                pos, pend = pend, None
            peak = max(peak, eq)
            mdd = min(mdd, eq / peak - 1)
            if i % 5 == 0:
                on = (not px[i] < m80[i] * 0.975) if on else (px[i] > m60[i] * 1.01)
                if on != pos:
                    pend = on
        out.append((eq ** (1 / R24.YEARS) - 1, mdd))
    return out


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def main():
    rng = random.Random(7)
    paths = [R24.R.path(rng, 250) for _ in range(500)]
    L = ["研究 59：凱莉最適槓桿（現行趨勢策略，在場槓桿 L）",
         "歷史（含融資濾網）：全期 2002- | 前段 -2012 | 後段 2013- ；拔靴 500 條 20 年（區塊 250 天）：年化中位、最差 5%、P(回檔<-50%)、P(回檔<-90%)"]
    for lev in LEVS:
        h = [hist(lev, a, b) for a, b in R.PER]
        b = boot(lev, paths)
        cs = [x[0] for x in b]
        ms = [x[1] for x in b]
        L.append(f"{lev:.1f}x  " + " | ".join(f"{c:6.1%}/{m:6.1%}" for c, m in h)
                 + f" || 拔靴 中位 {q(cs, .5):6.1%}、最差 5% {q(cs, .05):6.1%}、P50 {sum(m < -0.5 for m in ms) / 500:4.0%}、P90 {sum(m < -0.9 for m in ms) / 500:4.0%}")
        print(L[-1], flush=True)
    out = "\n".join(L) + "\n"
    open(os.path.join(HERE, "結果_研究59_凱莉槓桿.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
