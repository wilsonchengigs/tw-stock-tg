"""研究 548：在場＋高 VIX 隔夜（研究 546）的滾動前進與抱幾夜
(a) 滾動前進：每年只用過去挑 VIX 門檻 {20,22,25,28,30,不做}（過去合計最大，至少 30 夜），2005～ 逐年
(b) 抱 1／2／3 夜（第 n 天 08:45 出；中間日盤也抱）與「只抱夜、白天不抱」連續 n 夜，成本每進出一次 3 點
用法：python -X utf8 backtest/research_548_overnight_wf_hold.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138
from research_544_overnight_vs_day import load


def main():
    b = load(); ds = sorted(b)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    sig = {}
    for p in ds:
        j = np.searchsorted(vk, p) - 1; i = np.searchsorted(keys, p) - 1
        if j >= 0 and i >= 0:
            sig[p] = (st[keys[i]], vix[vk[j]])
    one = {}
    for p, d in zip(ds, ds[1:]):
        if b[p][1] == b[d][1]:
            one[p] = b[d][2] / b[p][3] - 1 - 3 / b[p][3]
    out = [__doc__]
    TH = [20, 22, 25, 28, 30, 999]
    picks = []; got = []
    for y in range(2005, 2027):
        ys = str(y); best = None
        for th in TH:
            past = [one[p] for p in one if p[:4] < ys and sig.get(p, (0, 0))[0] == 1 and sig[p][1] >= th]
            if th != 999 and len(past) < 30:
                continue
            sc = sum(past) if th != 999 else 0.0
            if best is None or sc > best[0]:
                best = (sc, th)
        th = best[1]; picks.append(f"{y}:{th if th<999 else '不做'}")
        got += [one[p] for p in one if p[:4] == ys and sig.get(p, (0, 0))[0] == 1 and sig[p][1] >= th]
    g = np.array(got) * 100
    out.append("(a) 每年挑到：" + " ".join(picks))
    out.append(f"    樣本外 {len(g)} 夜 每夜 {g.mean():+.3f}% t {g.mean()/(g.std(ddof=1)/np.sqrt(len(g))):+.2f} 合計 {g.sum():+.1f}%")
    fx = np.array([one[p] for p in one if p >= "2005" and sig.get(p, (0, 0))[0] == 1 and sig[p][1] >= 28]) * 100
    out.append(f"    對照 固定 28（2005～）：{len(fx)} 夜 每夜 {fx.mean():+.3f}% 合計 {fx.sum():+.1f}%")
    out.append("(b) 抱幾夜（門檻 28）：")
    for n in (1, 2, 3):
        r1 = []; r2 = []
        for k, p in enumerate(ds[:-n]):
            if sig.get(p, (0, 0))[0] != 1 or sig[p][1] < 28:
                continue
            seq = ds[k:k + n + 1]
            if len(set(b[x][1] for x in seq)) > 1:
                continue
            r1.append(b[seq[-1]][2] / b[p][3] - 1 - 3 / b[p][3])
            r2.append(np.prod([b[seq[q + 1]][2] / b[seq[q]][3] for q in range(n)]) - 1 - n * 3 / b[p][3])
        r1 = np.array(r1) * 100; r2 = np.array(r2) * 100
        out.append(f"   {n} 夜：連抱（含中間日盤）每筆 {r1.mean():+.3f}% t {r1.mean()/(r1.std(ddof=1)/np.sqrt(len(r1))):+.2f}｜只抱夜 {r2.mean():+.3f}% t {r2.mean()/(r2.std(ddof=1)/np.sqrt(len(r2))):+.2f}（{len(r1)} 筆，訊號重疊）")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究548_隔夜滾動前進.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
