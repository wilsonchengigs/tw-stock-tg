"""研究 151：候選 6 的 (A) 星期幾差異（週一＝跨週末）(B) 不用期貨、改用 00631L 現股的版本

(A) 訊號日 D 的星期；同波動度對照（研究 148 的 build）
(B) 00631L：D 開盤買、D+1 開盤賣（Yahoo 開盤價；股票成本：手續費 0.1425%×2 打 6 折＋證交稅 0.1%（ETF）≈ 0.27%）
    另版 D 開盤買、D 收盤賣（現股當沖，證交稅減半 0.05%）；2015-10～（00631L 早期錯價排除）
    與台指期同天比較（台指期報酬×2 對應正2 曝險）
用法：python -X utf8 backtest/research_151_恐慌星期與00631L版.py
"""
import importlib.util
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r148", os.path.join(HERE, "research_148_恐慌連續觸發.py"))
R148 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R148)
STOCK_COST, DAYTRADE_COST = 0.0027, 0.0022


def l631():
    r = json.load(open(os.path.join(HERE, "00631L.TW.json")))
    q = r["indicators"]["quote"][0]
    tw = timezone(timedelta(hours=8))
    out = {}
    for t, o, c in zip(r["timestamp"], q["open"], q["close"]):
        if o and c and o > 0:
            out[datetime.fromtimestamp(t, tw).strftime("%Y-%m-%d")] = (o, c)
    return out


def main():
    rows = R148.build()
    n = len(rows)
    cc = np.array([0.0] + [rows[k]["c"] / rows[k - 1]["c"] - 1 for k in range(1, n)])
    vol = np.array([np.std(cc[max(1, k - 20):k]) if k > 5 else np.nan for k in range(n)])
    ok = ~np.isnan(vol)
    dec = np.digitize(vol, np.nanpercentile(vol, np.arange(10, 100, 10)))
    sig = np.array([x["sig"] for x in rows])
    r = np.array([x["r"] for x in rows])
    wd = np.array([date.fromisoformat(x["d"]).weekday() for x in rows])
    rng = np.random.default_rng(151)
    out = ["研究 151：恐慌隔天做多 (A) 星期幾 (B) 00631L 現股版", ""]
    for per, lo, hi in (("2017-05～", "2017-05-15", "2099"), ("1998～2017-05", "1998", "2017-05-15")):
        inp = np.array([lo <= x["d"] < hi for x in rows])
        out.append(f"== (A) {per} ==")
        for w, lab in enumerate(("週一（跨週末）", "週二", "週三", "週四", "週五")):
            msk = sig & inp & ok & (wd == w)
            idx = np.where(msk)[0]
            if len(idx) < 5:
                out.append(f"{lab} {len(idx)} 次")
                continue
            pools = {k: np.where(~sig & ok & inp & (dec == dec[k]))[0] for k in idx}
            diff = np.mean([r[k] - r[pools[k]].mean() for k in idx])
            null = np.array([np.mean([r[rng.choice(pools[k])] - r[pools[k]].mean() for k in idx]) for _ in range(2000)])
            out.append(f"{lab:8s} {len(idx):3d} 次  每筆 {r[msk].mean():+.2%}  勝率 {np.mean(r[msk] > 0):.0%}  比同波動 {diff:+.2%}（p {(1 + np.sum(null >= diff)) / 2001:.3f}）")
        out.append("")
    # (B)
    L = l631()
    ds = sorted(L)
    nxt = {ds[k]: ds[k + 1] for k in range(len(ds) - 1)}
    a, b, f = [], [], []
    for k, x in enumerate(rows):
        d = x["d"]
        if not x["sig"] or d < "2015-10-01" or d not in L or d not in nxt:
            continue
        o, c = L[d]
        o1 = L[nxt[d]][0]
        a.append(o1 / o - 1 - STOCK_COST)
        b.append(c / o - 1 - DAYTRADE_COST)
        f.append(2 * x["r"])
    a, b, f = map(np.array, (a, b, f))
    out.append(f"== (B) 00631L 現股版（2015-10～，{len(a)} 次；成本 隔日 0.27%、當沖 0.22%）==")
    out.append(f"D 開盤買→D+1 開盤賣：每筆 {a.mean():+.2%}  勝率 {np.mean(a > 0):.0%}  最差 {a.min():+.2%}")
    out.append(f"D 開盤買→D 收盤賣（當沖）：每筆 {b.mean():+.2%}  勝率 {np.mean(b > 0):.0%}")
    out.append(f"同天台指期 ×2（對應正2 曝險）：每筆 {f.mean():+.2%}  勝率 {np.mean(f > 0):.0%}")
    out.append("（00631L 曝險約 2 倍：買 X 元 00631L ≈ 2X 名目，要和期貨 0.5 倍名目對應，00631L 只買資金的 25%）")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究151_恐慌星期與00631L版.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
