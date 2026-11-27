"""研究 523：三條日內順勢規則比較與合併（保守出場 13:25，另列 13:30）
- PAT：513 型態做空（|跳空|>0.3%、第 2 頭較低＋破頸線、0.25×ADR20、12:00 前）
- D30：09:05→10:30 漲跌 ≥0.5% → 10:30 順勢；D11：同 11:00
- E：盤中第一次漲跌 ≥1%（相對 09:05，13:00 前）→ 順勢
- 合併：一天最多 1 口，取當天最早出現的訊號
點數＝報酬×當天 09:05 指數；每點 50 元（小台）；成本 3 點；全部／VIX≥18 版
用法：python -X utf8 backtest/research_523_intraday_compare.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_511_higher_low as R
import research_522_intraday_trend_robust as M
from research_514_pattern_regime import yahoo


def sigs(days1, days5, gaps, adr, cm):
    """{規則: {date: (進場分鐘, 方向, 報酬)}}"""
    out = {"PAT": {}, "D30": {}, "D11": {}, "E": {}}
    for s in R.setups(days5, gaps, adr, -1, "相對", 0.25, "E2"):
        if s["minute"] <= 180 and abs(s["gap"]) > 0.003:
            a = days1[s["day"]]; e = M.at(a, s["minute"]); c = M.at(a, cm)
            out["PAT"][s["day"]] = (s["minute"], -1, -(c / e - 1) - 3 / e)
    for d, a in days1.items():
        o = M.at(a, 5)
        for k, T in (("D30", 90), ("D11", 120)):
            tr = M.at(a, T) / o - 1
            if abs(tr) >= 0.005:
                sd = 1 if tr > 0 else -1; e = M.at(a, T)
                out[k][d] = (T, sd, sd * (M.at(a, cm) / e - 1) - 3 / e)
        for mm, cl in a:
            if 6 <= mm <= 240 and abs(cl / o - 1) >= 0.01:
                sd = 1 if cl > o else -1
                out["E"][d] = (int(mm), sd, sd * (M.at(a, cm) / cl - 1) - 3 / cl)
                break
    return out


def report(name, lst, px):
    lst = sorted(lst)
    pts = np.array([r * px[d] for d, r in lst])
    eq = np.cumsum(pts); dd = (eq - np.maximum.accumulate(np.concatenate([[0], eq]))[1:]).min()
    yrs = {}
    for (d, _), p in zip(lst, pts):
        yrs[d[:4]] = yrs.get(d[:4], 0) + p
    rec = [p for (d, _), p in zip(lst, pts) if d >= "2024"]
    return (f"  {name:14s} {len(pts):5d} 筆（{len(pts)/17:4.1f}/年）每筆 {pts.mean():+5.1f} 點 t {pts.mean()/(pts.std(ddof=1)/np.sqrt(len(pts))):+.2f} 合計 {pts.sum():+7.0f} 點"
            f"（小台 {pts.sum()*50/1e4:+.0f} 萬）回檔 {dd:6.0f} 點｜正的年 {sum(1 for v in yrs.values() if v>0)}/{len(yrs)}｜2024～ 每筆 {np.mean(rec):+.0f} 點")


def main():
    days1 = M.load_idx(); days5 = R.load_days(); gaps = R.tx_gaps(); adr = R.adr20(days5)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    vhi = {d: vix[vk[np.searchsorted(vk, d) - 1]] >= 18 for d in days1}
    px = {d: M.at(a, 5) for d, a in days1.items()}
    out = [__doc__]
    for cm, lab in ((265, "13:25 出"), (270, "13:30 出")):
        S = sigs(days1, days5, gaps, adr, cm)
        out.append(f"\n===== {lab} =====")
        for gate in (False, True):
            out.append(f" [{'VIX≥18' if gate else '全部日子'}]")
            for k in ("PAT", "D30", "D11", "E"):
                lst = [(d, v[2]) for d, v in S[k].items() if (vhi[d] or not gate)]
                out.append(report(k, lst, px))
            for combo in (("D30", "E"), ("PAT", "D30", "E"), ("PAT", "D11", "E")):
                merged = {}
                for k in combo:
                    for d, v in S[k].items():
                        if (vhi[d] or not gate) and (d not in merged or v[0] < merged[d][0]):
                            merged[d] = v
                out.append(report("+".join(combo), [(d, v[2]) for d, v in merged.items()], px))
        # 重疊
        if cm == 265:
            ks = ["PAT", "D30", "D11", "E"]
            out.append(" 重疊（同一天都有訊號的天數／方向相同比例）：")
            for i in range(4):
                for j in range(i + 1, 4):
                    a, b = S[ks[i]], S[ks[j]]; both = set(a) & set(b)
                    same = np.mean([a[d][1] == b[d][1] for d in both]) if both else float("nan")
                    out.append(f"   {ks[i]}×{ks[j]}：{len(both)} 天（{ks[i]} 的 {len(both)/len(a)*100:.0f}%）同方向 {same*100:.0f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究523_日內規則比較.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
