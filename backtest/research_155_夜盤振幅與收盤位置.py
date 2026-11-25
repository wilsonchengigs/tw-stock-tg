"""研究 155：夜盤振幅（高−低）與收盤位置——P 沒觸發時，夜盤劇烈震盪本身有沒有資訊

夜盤振幅＝(高−低)/開 ≥ 2／3%；收盤位置 CLV＝(收−低)/(高−低)：收在低檔（<0.25）／高檔（>0.75）／中間
報酬：D 開盤→D+1 開盤做多，扣 3 點；只看 P（夜盤或 S&P 跌 ≥2%）沒觸發的日子；同波動度對照；2017-05～
用法：python -X utf8 backtest/research_155_夜盤振幅與收盤位置.py
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
        m = near[pd_]
        b, b1, nb = day[d].get(m), day[d1].get(m), night[d].get(m)
        if not (b and b1 and nb) or nb[4] < 1000 or d < "2017-05-15":
            continue
        u = None
        for back in range(1, 5):
            kk = (datetime.fromisoformat(d) - timedelta(days=back)).strftime("%Y-%m-%d")
            if kk in US:
                u = US[kk]
                break
        o, h, lo, c = nb[:4]
        nr = c / o - 1
        P = nr <= -0.02 or (u is not None and u <= -0.02)
        rng_ = (h - lo) / o
        clv = (c - lo) / (h - lo) if h > lo else 0.5
        rows.append(dict(P=P, rng=rng_, clv=clv, nr=nr, r=(b1[0] - b[0] - COST) / b[0], c=b[3]))
    n = len(rows)
    cc = np.array([0.0] + [rows[k]["c"] / rows[k - 1]["c"] - 1 for k in range(1, n)])
    vol = np.array([np.std(cc[max(1, k - 20):k]) if k > 5 else np.nan for k in range(n)])
    ok = ~np.isnan(vol)
    dec = np.digitize(vol, np.nanpercentile(vol, np.arange(10, 100, 10)))
    P = np.array([x["P"] for x in rows])
    R = np.array([x["rng"] for x in rows])
    C = np.array([x["clv"] for x in rows])
    r = np.array([x["r"] for x in rows])
    rng = np.random.default_rng(155)
    ctrl = ok & ~P & (R < 0.01)
    out = [f"研究 155：夜盤振幅與收盤位置（P 沒觸發的日子；2017-05～，{n} 天）", "對照＝P 沒觸發且夜盤振幅 <1% 的同波動度日子", ""]
    for th in (0.02, 0.03):
        for lab, g in (("收在低檔 <0.25", C < 0.25), ("中間", (C >= 0.25) & (C <= 0.75)), ("收在高檔 >0.75", C > 0.75)):
            msk = ok & ~P & (R >= th) & g
            idx = np.where(msk)[0]
            if len(idx) < 5:
                out.append(f"振幅≥{th:.0%} {lab} {len(idx)} 次")
                continue
            pools = {k: np.where(ctrl & (dec == dec[k]))[0] for k in idx}
            idx = [k for k in idx if len(pools[k])]
            diff = np.mean([r[k] - r[pools[k]].mean() for k in idx])
            null = np.array([np.mean([r[rng.choice(pools[k])] - r[pools[k]].mean() for k in idx]) for _ in range(2000)])
            pv = min((1 + np.sum(null >= diff)) / 2001, (1 + np.sum(null <= diff)) / 2001) * 2
            out.append(f"振幅≥{th:.0%} {lab:12s} {len(idx):3d} 次  做多每筆 {r[idx].mean():+.2%}  勝率 {np.mean(r[idx] > 0):.0%}  比同波動 {diff:+.2%}（雙尾 p {min(pv, 1):.3f}，Bonferroni×6 {min(1, pv * 6):.3f}）")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究155_夜盤振幅與收盤位置.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
