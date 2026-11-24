"""研究 84：依策略自身交易結果調整槓桿（連虧降 1x，賺一筆恢復 2x）
動機：研究 83 新版 2010～2016 反覆被洗，水下 83 個月。
規則：每筆交易（進場到出場）結束時記錄盈虧；最近 m 筆都虧（m ∈ {1,2,3}）→ 下一次進場只押 lev_low（1x 或 1.5x），直到出現一筆賺錢的交易
新版基準（含融資濾網）；歷史三段＋真實＋拔靴 300 條（不含融資濾網）；並列出 2010～2016 的逐筆交易
用法：python -X utf8 backtest/research_84_連虧降槓桿.py
"""
import importlib.util
import itertools
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
RR = R.R40.R32.R


def core(px, we, m60, m80, hot, r1, m, lev_low, i0, i1, log=None, days=None):
    eq = peak = 1.0
    mdd, on, lev, pend, streak, ent_eq, cur_lev = 0.0, False, 0.0, None, 0, 1.0, 2.0
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + ((lev * r1[i] - max(lev - 1, 0) * bt.DRAG / bt.TD) if lev > 0 else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * abs(pend - lev)
            if lev > 0 and pend == 0:  # 一筆交易結束
                win = eq > ent_eq
                streak = 0 if win else streak + 1
                if log is not None:
                    log.append((days[i], f"出場 {eq / ent_eq - 1:+.1%}（{lev:.1f}x）"))
            if lev == 0 and pend > 0:
                ent_eq = eq
            lev, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if we[i] and i >= 261:
            h = hot[i] if hot else False
            new_on = (not (px[i] < m80[i] * 0.975 or h)) if on else (px[i] > m60[i] * 1.01 and not h)
            if new_on and not on:
                cur_lev = lev_low if (m and streak >= m) else 2.0
            on = new_on
            t = cur_lev if on else 0.0
            if t != lev:
                pend = t
    return eq, mdd


R1 = [0.0] + [bt.R1[i] for i in range(1, N)]
R1R = RR.R1R


def hist(m, lev_low, start, end, real=False, log=None):
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    r1 = R1R if real else R1
    eq, mdd = core(PX, WE, R.M60, R.M80, HOT, r1, m, lev_low, i0, i1, log, DAYS)
    return eq ** (bt.TD / (i1 - i0)) - 1, mdd


def boot(m, lev_low, paths):
    out = []
    for rets in paths:
        px = [100.0]
        for r in rets:
            px.append(px[-1] * (1 + r))
        r1 = [0.0] + [px[i] / px[i - 1] - 1 + bt.DIV / bt.TD for i in range(1, len(px))]
        we = [i % 5 == 0 for i in range(len(px))]
        eq, mdd = core(px, we, R24.sma(px, 60), R24.sma(px, 80), None, r1, m, lev_low, 261, len(px) - 1)
        out.append((eq ** (1 / R24.YEARS) - 1, mdd))
    return out


def main():
    rng = random.Random(7)
    paths = [R24.R.path(rng, 250) for _ in range(300)]
    b0 = boot(0, 2.0, paths)
    L = ["研究 84：連虧降槓桿（歷史 全期 2002- | 前段 | 後段 | 真實；2010-2016；拔靴：年化中位、P(<-50%)、勝新版）"]
    for m, low in [(0, 2.0)] + list(itertools.product((1, 2, 3), (1.0, 1.5))):
        rs = [hist(m, low, a, b) for a, b in R.PER]
        rr = hist(m, low, *R.REAL, real=True)
        mid = hist(m, low, "2010-01-01", "2016-12-31")
        b = b0 if m == 0 else boot(m, low, paths)
        cs = sorted(x[0] for x in b)
        win = sum(1 for x, y in zip(b, b0) if x[0] > y[0] + 1e-12) / len(b)
        nm = "新版（不調整）" if m == 0 else f"連虧 {m} 筆 → {low}x"
        L.append(f"{nm:14s} " + " | ".join(f"{c:.1%}/{mm:.1%}" for c, mm in rs) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%} | 2010-16 {mid[0]:.1%}/{mid[1]:.1%} || 拔靴 {cs[150]:.1%}、P {sum(x[1] < -0.5 for x in b) / len(b):.0%}、勝 {win:.0%}")
        print(L[-1], flush=True)
    log = []
    hist(0, 2.0, "2009-06-01", "2017-03-01", log=log)
    L.append("\n新版 2009-06～2017-03 逐筆：" + "、".join(f"{d} {x}" for d, x in log))
    out = "\n".join(L) + "\n"
    print(L[-1])
    open(os.path.join(HERE, "結果_研究84_連虧降槓桿.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
