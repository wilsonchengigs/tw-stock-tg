"""研究 520：盤中第 2 頭較低＋破頸線做空的出場時間
- 型態：|跳空|>0.3%、0.25×ADR20、E2、12:00 前進場（研究 519 不設 VIX 開關的版本），另列 VIX≥18 子集
- 出場：進場後 30／60／120 分、12:00、13:00、13:30 收盤、隔天 09:05（加權 1 分 K，隔夜跳空算進去）
- 成本 3 點；兩段（2010～2017／2018～）
用法：python -X utf8 backtest/research_520_pattern_exit_time.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_511_higher_low as R
from research_514_pattern_regime import yahoo


def main():
    gaps = R.tx_gaps(); days = R.load_days(); adr = R.adr20(days)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix)); ds = sorted(days)
    nxt = {a: b for a, b in zip(ds, ds[1:])}

    def vprev(d):
        i = np.searchsorted(vk, d) - 1
        return vix[vk[i]] if i >= 0 else 0
    S = [s for s in R.setups(days, gaps, adr, -1, "相對", 0.25, "E2") if s["minute"] <= 180 and abs(s["gap"]) > 0.003]
    EX = ["+30分", "+60分", "+120分", "12:00", "13:00", "13:30", "隔天09:05"]
    res = {k: [] for k in EX}; meta = []
    for s in S:
        a = days[s["day"]]; m = a[:, 0].astype(int); c = a[:, 3]
        i0 = int(np.searchsorted(m, s["minute"])); e = c[i0]
        def at(mm):
            j = min(int(np.searchsorted(m, mm)), len(c) - 1)
            return c[j] if mm > s["minute"] else None
        px = {"+30分": at(s["minute"] + 30), "+60分": at(s["minute"] + 60), "+120分": at(s["minute"] + 120),
              "12:00": at(180), "13:00": at(240), "13:30": c[-1]}
        nd = nxt.get(s["day"])
        if nd:
            b = days[nd]; j = int(np.searchsorted(b[:, 0], 5)); px["隔天09:05"] = b[j, 3]
        else:
            px["隔天09:05"] = None
        for k in EX:
            x = px[k] if px[k] is not None else c[-1]
            res[k].append((e - x) / e * 100 - 3 / e * 100)
        meta.append((s["day"] < R.SPLIT, vprev(s["day"]) >= 18))
    ins = np.array([x[0] for x in meta]); hv = np.array([x[1] for x in meta])
    out = [__doc__, f"共 {len(S)} 筆（VIX≥18 {hv.sum()} 筆）"]
    for k in EX:
        p = np.array(res[k])
        f = lambda q: f"{q.mean():+.3f}%（≈{q.mean()*390:+4.0f} 點）t {q.mean()/(q.std(ddof=1)/np.sqrt(len(q))):+.2f}"
        out.append(f"  {k:8s} 全部 {f(p)} 勝率 {(p>0).mean()*100:.0f}%｜內 {p[ins].mean():+.3f} 外 {p[~ins].mean():+.3f}｜VIX≥18 {f(p[hv])}｜標準差 {p.std():.2f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究520_型態出場時間.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
