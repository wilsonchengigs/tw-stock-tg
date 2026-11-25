"""研究 160：S&P 觸發改用波動調整（z＝當日報酬 ÷ 前 20 日標準差）vs 固定 −2%

只看「夜盤沒觸發」的日子（S&P 分支本身的資訊；夜盤分支不變）
門檻：固定 −2%（現行）／z ≤ −2.0／−2.5／−3.0／「−2% 且 z ≤ −2」／「−1.5% 且 z ≤ −2.5」
報酬 D 開→D+1 開扣 3 點；同波動度（台指期）對照 1000 次；兩段 1998–2017-05（S&P 唯一觸發，樣本外）、2017-05～
用法：python -X utf8 backtest/research_160_SP波動調整觸發.py
"""
import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r144", os.path.join(HERE, "research_144_美股大跌隔天做多_樣本外.py"))
R144 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R144)
COST = 3.0


def sp_z():
    r = json.load(open(os.path.join(HERE, "GSPC.json")))
    c = r["indicators"]["quote"][0]["close"]
    ny = timezone(timedelta(hours=-5))
    rows = [(datetime.fromtimestamp(t, ny).strftime("%Y-%m-%d"), x) for t, x in zip(r["timestamp"], c) if x]
    ret = [rows[i][1] / rows[i - 1][1] - 1 for i in range(1, len(rows))]
    out = {}
    for i in range(21, len(ret)):
        sd = np.std(ret[i - 20:i])
        out[rows[i + 1][0]] = (ret[i], ret[i] / sd if sd > 0 else 0.0)
    return out


def main():
    dates, day, night, near = R144.R139.load_tx()
    Z = sp_z()
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
            if kk in Z:
                u = Z[kk]
                break
        rows.append(dict(d=d, nsig=nr is not None and nr <= -0.02, ret=u[0] if u else 0.0, z=u[1] if u else 0.0,
                         r=(b1[0] - b[0] - COST) / b[0], c=b[3]))
    n = len(rows)
    cc = np.array([0.0] + [rows[k]["c"] / rows[k - 1]["c"] - 1 for k in range(1, n)])
    vol = np.array([np.std(cc[max(1, k - 20):k]) if k > 5 else np.nan for k in range(n)])
    ok = ~np.isnan(vol)
    dec = np.digitize(vol, np.nanpercentile(vol, np.arange(10, 100, 10)))
    NS = np.array([x["nsig"] for x in rows])
    RT = np.array([x["ret"] for x in rows])
    ZZ = np.array([x["z"] for x in rows])
    r = np.array([x["r"] for x in rows])
    rules = {"固定 −2%（現行）": RT <= -0.02, "z ≤ −2.0": ZZ <= -2.0, "z ≤ −2.5": ZZ <= -2.5, "z ≤ −3.0": ZZ <= -3.0,
             "−2% 且 z ≤ −2": (RT <= -0.02) & (ZZ <= -2), "−1.5% 且 z ≤ −2.5": (RT <= -0.015) & (ZZ <= -2.5)}
    anyrule = np.zeros(n, bool)
    for v in rules.values():
        anyrule |= v
    rng = np.random.default_rng(160)
    out = ["研究 160：S&P 分支 固定門檻 vs 波動調整（夜盤沒觸發的日子）", ""]
    for per, lo, hi in (("1998～2017-05（樣本外）", "1998", "2017-05-15"), ("2017-05～", "2017-05-15", "2099")):
        inp = np.array([lo <= x["d"] < hi for x in rows])
        ctrl = ok & inp & ~anyrule & ~NS & (RT > -0.01)
        out.append(f"== {per} ==")
        for lab, g in rules.items():
            idx = np.where(g & ~NS & ok & inp)[0]
            if len(idx) < 5:
                out.append(f"{lab:18s} {len(idx)} 次")
                continue
            pools = {k: np.where(ctrl & (dec == dec[k]))[0] for k in idx}
            idx = [k for k in idx if len(pools[k])]
            diff = np.mean([r[k] - r[pools[k]].mean() for k in idx])
            null = np.array([np.mean([r[rng.choice(pools[k])] - r[pools[k]].mean() for k in idx]) for _ in range(1000)])
            out.append(f"{lab:18s} {len(idx):3d} 次  每筆 {r[idx].mean():+.2%}  勝率 {np.mean(r[idx] > 0):.0%}  比同波動 {diff:+.2%}（p {(1 + np.sum(null >= diff)) / 1001:.3f}）")
        out.append("")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究160_SP波動調整觸發.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
