"""研究 144：研究 142／143「夜盤大跌 → 隔天開盤做多」的樣本外驗證——夜盤出現前（1998～2017-05）用「美股前一晚大跌」當代理

想法：夜盤出現前，美股大跌的衝擊直接反映在台指期日盤開盤跳空；若「恐慌後隔天反彈」是同一個機制，
那 1998～2017 「美股（S&P500／NDX）前一晚跌 ≥x% → 台指期 D 開盤做多，D 收／D+1 開／D+1 收 出」應該也正。
2017-05 以後另列，並看與「夜盤跌 ≥2%」的重疊。
對照：所有日子同樣進出；同波動度（前 20 日台指期實現波動同十分位、美股 > −1% 的日子）差值 2000 次抽樣 p
資料：GSPC.json、NDX.json（Yahoo）；台指期 tx_daily_ohlc.csv
用法：python -X utf8 backtest/research_144_美股大跌隔天做多_樣本外.py
"""
import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r139", os.path.join(HERE, "research_139_日夜盤報酬拆解.py"))
R139 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R139)
NY = timezone(timedelta(hours=-5))
COST = 3.0


def us(fn):
    r = json.load(open(os.path.join(HERE, fn)))
    c = r["indicators"]["quote"][0]["close"]
    rows = [(datetime.fromtimestamp(t, NY).strftime("%Y-%m-%d"), x) for t, x in zip(r["timestamp"], c) if x]
    return {rows[i][0]: rows[i][1] / rows[i - 1][1] - 1 for i in range(1, len(rows))}


def main():
    dates, day, night, near = R139.load_tx()
    US = {"S&P500": us("GSPC.json"), "NDX": us("NDX.json")}
    rows = []
    for k in range(1, len(dates) - 1):
        d, pd_, d1 = dates[k], dates[k - 1], dates[k + 1]
        m = near[pd_]
        b, pb, b1 = day[d].get(m), day[pd_].get(m), day[d1].get(m)
        if not (b and pb and b1):
            continue
        nb = night[d].get(m)
        x = dict(d=d, o=b[0], c=b[3], o1=b1[0], c1=b1[3], pc=pb[3], n=(nb[3] / nb[0] - 1) if nb and nb[4] >= 1000 else None, us={})
        for nm, s in US.items():
            for back in range(1, 5):
                kk = (datetime.fromisoformat(d) - timedelta(days=back)).strftime("%Y-%m-%d")
                if kk in s:
                    x["us"][nm] = s[kk]
                    break
        rows.append(x)
    rcc = np.array([0.0] + [rows[k]["c"] / rows[k - 1]["c"] - 1 for k in range(1, len(rows))])
    vol = np.array([np.std(rcc[max(1, k - 20):k]) if k > 5 else np.nan for k in range(len(rows))])
    rng = np.random.default_rng(144)
    out = [f"研究 144：美股前一晚大跌 → 台指期 D 開盤做多（{rows[0]['d']}～{rows[-1]['d']}；扣 3 點）", ""]
    exits = {"D收": lambda x: x["c"], "D+1開": lambda x: x["o1"], "D+1收": lambda x: x["c1"]}
    for per, lo, hi in (("1998-2017/05（無夜盤，樣本外）", "1998", "2017-05-15"), ("2017/05-2026（有夜盤）", "2017-05-15", "2099")):
        sub = [i for i, x in enumerate(rows) if lo <= x["d"] < hi]
        vs = vol[sub]
        ok = ~np.isnan(vs)
        qs = np.nanpercentile(vs, np.arange(10, 100, 10))
        dec = np.digitize(vs, qs)
        out.append(f"== {per}，{len(sub)} 天 ==")
        for nm in US:
            u = np.array([rows[i]["us"].get(nm, 0.0) for i in sub])
            for th in (0.02, 0.03):
                sig = ok & (u <= -th)
                ctrl = ok & (u > -0.01)
                parts = []
                for lab, f in exits.items():
                    r = np.array([f(rows[i]) / rows[i]["o"] - 1 - COST / rows[i]["o"] for i in sub])
                    diffs = [r[j] - r[ctrl & (dec == dec[j])].mean() for j in np.where(sig)[0]]
                    null = [np.mean([r[rng.choice(np.where(ctrl & (dec == dec[j]))[0])] - r[ctrl & (dec == dec[j])].mean() for j in np.where(sig)[0]]) for _ in range(1000)]
                    pv = (1 + np.sum(np.array(null) >= np.mean(diffs))) / 1001
                    parts.append(f"{lab} {r[sig].mean():+.2%}/{np.mean(r[sig] > 0):.0%}（同波動差 {np.mean(diffs):+.2%}, p {pv:.3f}）")
                gap = np.mean([rows[i]["o"] / rows[i]["pc"] - 1 for i in np.array(sub)[sig]])
                out.append(f"{nm} 跌≥{th:.0%} {sig.sum():3d} 次（開盤跳空 {gap:+.2%}）：" + "  ".join(parts))
        if lo >= "2017":
            u = np.array([rows[i]["us"].get("S&P500", 0.0) for i in sub])
            nn = np.array([rows[i]["n"] if rows[i]["n"] is not None else 0.0 for i in sub])
            a, b = nn <= -0.02, u <= -0.02
            out.append(f"重疊：夜跌≥2% {a.sum()} 次、S&P 跌≥2% {b.sum()} 次、兩者都 {(a & b).sum()} 次")
        out.append("")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究144_美股大跌隔天做多_樣本外.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
