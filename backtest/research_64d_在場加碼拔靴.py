"""研究 64d：在場時爆量收黑加碼（研究 64b）的拔靴風險檢驗

方法：平穩區塊拔靴（平均區塊 250 天，同研究 19／20／24），500 條 20 年路徑；每天的指數報酬附上「當天是否爆量收黑」
     （證交所成交金額 ≥k × 前 20 日均且收黑，在真實歷史上算好），一起重組，讓訊號與其後幾天的反彈留在同一區塊
策略：現行 MA60×1.01 進／MA80×0.975 出、2x（拔靴不含融資濾網，同研究 59）；加碼：在場時遇訊號，當天收盤加 a 倍抱 H 天
報表：年化中位、最差 5% 年化、P(回檔 < -50%)、P(回檔 < -60%)、加碼版勝過現行的路徑比例
用法：python -X utf8 backtest/research_64d_在場加碼拔靴.py
"""
import importlib.util
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r64", os.path.join(HERE, "research_64_爆量收黑加碼現行策略.py"))
r64 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r64)
bt, PX, N, VR = r64.bt, r64.PX, r64.N, r64.VR
YEARS, LEN = 20, 20 * 245


def sma(px, k):
    out, s = [None] * len(px), 0.0
    for i in range(len(px)):
        s += px[i]
        if i >= k:
            s -= px[i - k]
        if i >= k - 1:
            out[i] = s / k
    return out


def run(rets, sigs, add, H):
    px = [100.0]
    for r in rets:
        px.append(px[-1] * (1 + r))
    m60, m80 = sma(px, 60), sma(px, 80)
    eq = peak = 1.0
    mdd, on, lev, pend, extra, until = 0.0, False, 0.0, None, 0.0, -1
    for i in range(261, len(px)):
        r1 = px[i] / px[i - 1] - 1 + bt.DIV / bt.TD
        L = lev + extra
        eq *= 1 + ((L * r1 - max(L - 1, 0) * bt.DRAG / bt.TD) if L > 0 else bt.RC)
        eq = max(eq, 1e-9)
        if pend is not None:
            eq *= 1 - bt.COST * abs(pend - lev)
            lev, pend = pend, None
            if lev == 0:
                extra, until = 0.0, -1
        if i % 5 == 0:
            on = (not px[i] < m80[i] * 0.975) if on else (px[i] > m60[i] * 1.01)
            want = 2.0 if on else 0.0
            if want != lev:
                pend = want
        if extra and i >= until:
            extra, until = 0.0, -1
        if add and lev == 2.0 and pend is None and not extra and sigs[i - 1]:
            extra, until = add, i + H
            eq *= 1 - 0.0001 * add
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
    return eq ** (1 / YEARS) - 1, mdd


def main():
    i0 = next(i for i, d in enumerate(r64.DAYS) if d >= "1998-09-01")
    RET = [PX[i] / PX[i - 1] - 1 for i in range(i0, N)]
    SIG = {k: [bool(VR[i] is not None and VR[i] >= k and PX[i] < PX[i - 1]) for i in range(i0, N)] for k in (1.3, 1.5)}
    T = len(RET)
    rng = random.Random(64)
    paths = []
    for _ in range(500):
        idx, i = [], rng.randrange(T)
        while len(idx) < LEN:
            idx.append(i)
            i += 1
            if i >= T or rng.random() < 1 / 250:
                i = rng.randrange(T)
        paths.append(idx)
    L = ["研究 64d：在場加碼拔靴（500 條 20 年、平均區塊 250 天；不含融資濾網）",
         "格式：年化中位／最差 5% 年化／P(回檔<-50%)／P(回檔<-60%)／勝過現行的路徑比例"]
    base = [run([RET[j] for j in p], [False] * LEN, 0, 0) for p in paths]

    def summary(res):
        cs = sorted(r[0] for r in res)
        return (cs[250], cs[25], sum(r[1] < -0.5 for r in res) / 500, sum(r[1] < -0.6 for r in res) / 500)

    b = summary(base)
    L.append(f"\n現行             {b[0]:6.1%}  {b[1]:6.1%}  {b[2]:4.0%}  {b[3]:4.0%}")
    for k, add, H in ((1.5, 0.5, 5), (1.5, 1.0, 5), (1.5, 0.5, 10), (1.5, 1.0, 10), (1.3, 0.5, 10), (1.3, 1.0, 10)):
        res = [run([RET[j] for j in p], [SIG[k][j] for j in p], add, H) for p in paths]
        s = summary(res)
        win = sum(r[0] > bb[0] for r, bb in zip(res, base)) / 500
        L.append(f"k{k} 加{add}x 抱{H:2d}天  {s[0]:6.1%}  {s[1]:6.1%}  {s[2]:4.0%}  {s[3]:4.0%}   {win:4.0%}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究64d_在場加碼拔靴.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
