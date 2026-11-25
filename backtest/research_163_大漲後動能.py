"""研究 163：夜盤大漲（或 S&P 大漲）後的動能——D 開盤做多、抱到 D+3／D+5 收盤

研究 143 附帶：夜盤漲 ≥2% 隔天做空 D+3 -1.35%、D+5 -1.82%（＝做多賺）。這裡正式檢驗：
觸發：夜盤近月 開→收 ≥ +x 或 S&P 前一晚 ≥ +x（x 2／3%）；1998–2017 只有 S&P（樣本外）
報酬：D 開盤 → D+1 開／D+3 收／D+5 收，扣 3 點；同波動度對照（非觸發日）1000 次；12 格 Bonferroni
另看 v3 在場／空手分組
用法：python -X utf8 backtest/research_163_大漲後動能.py
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
R138 = R144.R139.R138
COST = 3.0


def main():
    dates, day, night, near = R144.R139.load_tx()
    US = R144.us("GSPC.json")
    V3 = dict(zip(R138.DAYS, R138.ST))
    rows = []
    for k in range(1, len(dates) - 6):
        d, pd_ = dates[k], dates[k - 1]
        m = near[pd_]
        b = day[d].get(m)
        ex = [day[dates[k + j]].get(m) for j in (1, 3, 5)]
        if not b or not all(ex):
            continue
        nb = night[d].get(m)
        nr = (nb[3] / nb[0] - 1) if nb and nb[4] >= 1000 else 0.0
        u = 0.0
        for back in range(1, 5):
            kk = (datetime.fromisoformat(d) - timedelta(days=back)).strftime("%Y-%m-%d")
            if kk in US:
                u = US[kk]
                break
        o = b[0]
        rows.append(dict(d=d, nr=nr, u=u, v3=V3.get(pd_), c=b[3],
                         r=[(ex[0][0] - o - COST) / o, (ex[1][3] - o - COST) / o, (ex[2][3] - o - COST) / o]))
    n = len(rows)
    cc = np.array([0.0] + [rows[k]["c"] / rows[k - 1]["c"] - 1 for k in range(1, n)])
    vol = np.array([np.std(cc[max(1, k - 20):k]) if k > 5 else np.nan for k in range(n)])
    ok = ~np.isnan(vol)
    dec = np.digitize(vol, np.nanpercentile(vol, np.arange(10, 100, 10)))
    NR = np.array([x["nr"] for x in rows])
    U = np.array([x["u"] for x in rows])
    R = np.array([x["r"] for x in rows])
    on = np.array([x["v3"] == 1 for x in rows])
    rng = np.random.default_rng(163)
    out = ["研究 163：夜盤或 S&P 大漲後 D 開盤做多（動能）", ""]
    for per, lo, hi in (("1998～2017-05（S&P，樣本外）", "1998", "2017-05-15"), ("2017-05～（夜盤或 S&P）", "2017-05-15", "2099")):
        inp = np.array([lo <= x["d"] < hi for x in rows])
        out.append(f"== {per} ==")
        for th in (0.02, 0.03):
            sig = ((NR >= th) | (U >= th)) & ok & inp
            ctrl = ok & inp & (NR < 0.01) & (U < 0.01) & (NR > -0.01) & (U > -0.01)
            for lab, g in (("全部", np.ones(n, bool)), ("v3 在場", on), ("v3 空手", ~on)):
                idx = np.where(sig & g)[0]
                if len(idx) < 5:
                    out.append(f"漲≥{th:.0%} {lab} {len(idx)} 次")
                    continue
                pools = {k: np.where(ctrl & (dec == dec[k]))[0] for k in idx}
                idx = [k for k in idx if len(pools[k])]
                parts = []
                for j, nm in enumerate(("D+1開", "D+3收", "D+5收")):
                    diff = np.mean([R[k, j] - R[pools[k], j].mean() for k in idx])
                    null = np.array([np.mean([R[rng.choice(pools[k]), j] - R[pools[k], j].mean() for k in idx]) for _ in range(1000)])
                    pv = (1 + np.sum(null >= diff)) / 1001
                    parts.append(f"{nm} {R[idx, j].mean():+.2%}/{np.mean(R[idx, j] > 0):.0%}（超額 {diff:+.2%}, p {pv:.3f}）")
                out.append(f"漲≥{th:.0%} {lab:6s} {len(idx):3d} 次  " + "  ".join(parts))
        out.append("")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究163_大漲後動能.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
