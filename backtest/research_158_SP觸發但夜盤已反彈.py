"""研究 158：S&P 前一晚跌 ≥2% 觸發，但台指期夜盤（同一晚）本身沒大跌／已反彈時，還要不要進場（2017-05～）

分組（只看 S&P 觸發的日子）：夜盤 ≤ −2%（兩者都觸發）／−2%～0／≥ 0（夜盤收紅）
另看「D 開盤跳空」（D 開盤 ÷ 夜盤收盤 − 1）分組
報酬 D 開→D+1 開扣 3 點；同波動度非訊號日對照
用法：python -X utf8 backtest/research_158_SP觸發但夜盤已反彈.py
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


def main():
    dates, day, night, near = R144.R139.load_tx()
    US = R144.us("GSPC.json")
    rows = []
    for k in range(1, len(dates) - 1):
        d, pd_, d1 = dates[k], dates[k - 1], dates[k + 1]
        if d < "2017-05-15":
            continue
        m = near[pd_]
        b, b1, nb = day[d].get(m), day[d1].get(m), night[d].get(m)
        if not (b and b1 and nb) or nb[4] < 1000:
            continue
        u = None
        for back in range(1, 5):
            kk = (datetime.fromisoformat(d) - timedelta(days=back)).strftime("%Y-%m-%d")
            if kk in US:
                u = US[kk]
                break
        nr = nb[3] / nb[0] - 1
        rows.append(dict(sp=u is not None and u <= -0.02, nr=nr, P=nr <= -0.02 or (u is not None and u <= -0.02),
                         gap=b[0] / nb[3] - 1, r=(b1[0] - b[0] - COST) / b[0], c=b[3]))
    n = len(rows)
    cc = np.array([0.0] + [rows[k]["c"] / rows[k - 1]["c"] - 1 for k in range(1, n)])
    vol = np.array([np.std(cc[max(1, k - 20):k]) if k > 5 else np.nan for k in range(n)])
    ok = ~np.isnan(vol)
    dec = np.digitize(vol, np.nanpercentile(vol, np.arange(10, 100, 10)))
    SPs = np.array([x["sp"] for x in rows])
    P = np.array([x["P"] for x in rows])
    NR = np.array([x["nr"] for x in rows])
    G = np.array([x["gap"] for x in rows])
    r = np.array([x["r"] for x in rows])
    rng = np.random.default_rng(158)
    out = ["研究 158：S&P 跌 ≥2% 觸發時，依台指期夜盤本身表現分組（2017-05～）", ""]
    groups = [("夜盤也 ≤−2%（雙觸發）", NR <= -0.02), ("夜盤 −2%～0", (NR > -0.02) & (NR < 0)), ("夜盤收紅 ≥0", NR >= 0),
              ("開盤跳空 ≤−0.5%", G <= -0.005), ("開盤跳空 −0.5%～+0.5%", (G > -0.005) & (G < 0.005)), ("開盤跳空 ≥+0.5%", G >= 0.005)]
    for lab, g in groups:
        idx = np.where(SPs & ok & g)[0]
        if len(idx) < 5:
            out.append(f"{lab:22s} {len(idx)} 次（太少）")
            continue
        pools = {k: np.where(~P & ok & (dec == dec[k]))[0] for k in idx}
        diff = np.mean([r[k] - r[pools[k]].mean() for k in idx])
        null = np.array([np.mean([r[rng.choice(pools[k])] - r[pools[k]].mean() for k in idx]) for _ in range(2000)])
        out.append(f"{lab:22s} {len(idx):3d} 次  每筆 {r[idx].mean():+.2%}  勝率 {np.mean(r[idx] > 0):.0%}  比同波動 {diff:+.2%}（p {(1 + np.sum(null >= diff)) / 2001:.3f}）")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究158_SP觸發但夜盤已反彈.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
