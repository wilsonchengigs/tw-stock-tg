"""研究 148：候選 6 連續觸發——前幾個交易日已觸發過時，這次還有沒有效（崩跌期訊號會群聚，如 2026-11-20、11-23、11-25）

訊號同研究 145（夜盤或 S&P 跌 ≥2%）；報酬＝D 08:45 開盤進、D+1 08:45 開盤出、扣 3 點；2017-05～（夜盤）與 1998～2017（S&P 代理）
分組：前 1／3／5 個交易日內有無觸發；第幾次（叢集內序號：1、2、3+；叢集＝間隔 ≤5 個交易日）
對照：同波動度（前 20 日實現波動同十分位）非訊號日，2000 次抽樣單尾 p
用法：python -X utf8 backtest/research_148_恐慌連續觸發.py
"""
import importlib.util
import os
import sys
from datetime import datetime, timedelta

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r144", os.path.join(HERE, "research_144_美股大跌隔天做多_樣本外.py"))
R144 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R144)
COST = 3.0


def build():
    dates, day, night, near = R144.R139.load_tx()
    US = R144.us("GSPC.json")
    rows = []
    for k in range(1, len(dates) - 1):
        d, pd_, d1 = dates[k], dates[k - 1], dates[k + 1]
        m = near[pd_]
        b, b1 = day[d].get(m), day[d1].get(m)
        if not (b and b1):
            continue
        nb = night[d].get(m)
        nr = (nb[3] / nb[0] - 1) if nb and nb[4] >= 1000 else None
        u = None
        for back in range(1, 5):
            kk = (datetime.fromisoformat(d) - timedelta(days=back)).strftime("%Y-%m-%d")
            if kk in US:
                u = US[kk]
                break
        sig = (nr is not None and nr <= -0.02) or (u is not None and u <= -0.02)
        rows.append(dict(d=d, sig=sig, r=(b1[0] - b[0] - COST) / b[0], c=b[3]))
    return rows


def main():
    rows = build()
    n = len(rows)
    cc = np.array([0.0] + [rows[k]["c"] / rows[k - 1]["c"] - 1 for k in range(1, n)])
    vol = np.array([np.std(cc[max(1, k - 20):k]) if k > 5 else np.nan for k in range(n)])
    ok = ~np.isnan(vol)
    dec = np.digitize(vol, np.nanpercentile(vol, np.arange(10, 100, 10)))
    sig = np.array([x["sig"] for x in rows])
    r = np.array([x["r"] for x in rows])
    ctrl = ~sig & ok
    seq = np.zeros(n, int)
    last = -99
    for k in range(n):
        if sig[k]:
            seq[k] = seq[last] + 1 if k - last <= 5 else 1
            last = k
    rng = np.random.default_rng(148)
    out = [f"研究 148：恐慌隔天做多 連續觸發（{rows[0]['d']}～{rows[-1]['d']}）", ""]
    for per, lo, hi in (("2017-05～（夜盤或 S&P）", "2017-05-15", "2099"), ("1998～2017-05（S&P 代理）", "1998", "2017-05-15")):
        inp = np.array([lo <= x["d"] < hi for x in rows])
        out.append(f"== {per}：訊號 {(sig & inp).sum()} 次，全部每筆 {r[sig & inp].mean():+.2%}／勝率 {np.mean(r[sig & inp] > 0):.0%} ==")
        groups = []
        for L in (1, 3, 5):
            prev = np.array([sig[max(0, k - L):k].any() for k in range(n)])
            groups += [(f"前 {L} 天內有觸發", prev), (f"前 {L} 天內沒觸發", ~prev)]
        groups += [("叢集第 1 次", seq == 1), ("叢集第 2 次", seq == 2), ("叢集第 3 次以上", seq >= 3)]
        for lab, g in groups:
            msk = sig & inp & g & ok
            idx = np.where(msk)[0]
            if len(idx) < 5:
                out.append(f"{lab:14s} {len(idx)} 次（太少）")
                continue
            pools = {k: np.where(ctrl & inp & (dec == dec[k]))[0] for k in idx}
            diff = np.mean([r[k] - r[pools[k]].mean() for k in idx])
            null = np.array([np.mean([r[rng.choice(pools[k])] - r[pools[k]].mean() for k in idx]) for _ in range(2000)])
            pv = (1 + np.sum(null >= diff)) / 2001
            out.append(f"{lab:14s} {len(idx):3d} 次  每筆 {r[msk].mean():+.2%}  勝率 {np.mean(r[msk] > 0):.0%}  最差 {r[msk].min():+.2%}  比同波動 {diff:+.2%}（p {pv:.3f}）")
        out.append("")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究148_恐慌連續觸發.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
