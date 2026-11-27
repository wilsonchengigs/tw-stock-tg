"""研究 514：研究 513 的盤中型態依市況分組（VIX、S&P 前一晚、加權相對 MA60、近期波動 ADR20）
型態：開低或開高（|跳空|>0.3%）後「第 2 頭較低＋跌破頸線」做空；開高日「第 2 底較高＋站上頸線」做多
參數同 513：轉折 0.25×ADR20、E2 進場、12:00 前、13:30 收盤出、成本 3 點；另扣所有日子同一分鐘基準
目的：找出型態只在哪種市況有效（可當過濾），或確認不分市況都一樣（不需要過濾）
用法：python -X utf8 backtest/research_514_pattern_regime.py
"""
import os, sys, json, datetime as dt
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_511_higher_low as R


def yahoo(name):
    d = json.load(open(os.path.join(HERE, name), encoding="utf-8"))
    off = d["meta"].get("gmtoffset", 0)
    q = d["indicators"]["quote"][0]
    out = {}
    for t, c in zip(d["timestamp"], q["close"]):
        if c is None:
            continue
        out[(dt.datetime.utcfromtimestamp(t + off)).strftime("%Y-%m-%d")] = c
    return out


def prev_value(series, day):
    """day（台灣日期）之前最後一個美國收盤（美國日期 < 台灣日期）"""
    ks = series["_keys"]
    i = np.searchsorted(ks, day) - 1
    return (ks[i], i) if i >= 0 else (None, None)


def main():
    gaps = R.tx_gaps(); days = R.load_days(); adr = R.adr20(days); drift = R.drift_table(days)
    spx = yahoo("GSPC.json"); vix = yahoo("VIX.json"); twii = yahoo("TWII.json")
    sk = np.array(sorted(spx)); vk = np.array(sorted(vix)); tk = sorted(twii)
    tclose = np.array([twii[k] for k in tk]); tk = np.array(tk)
    ma60 = {tk[i]: tclose[i - 59:i + 1].mean() for i in range(59, len(tk))}
    adr_vals = np.array([adr[d] for d in sorted(adr)])
    q1, q2 = np.quantile(adr_vals, [1 / 3, 2 / 3])

    def feats(d):
        f = {}
        i = np.searchsorted(vk, d) - 1
        f["VIX"] = vix[vk[i]] if i >= 0 else None
        i = np.searchsorted(sk, d) - 1
        f["SPX"] = (spx[sk[i]] / spx[sk[i - 1]] - 1) * 100 if i >= 1 else None
        i = np.searchsorted(tk, d) - 1
        f["MA60"] = (tclose[i] / ma60[tk[i]] - 1) * 100 if i >= 0 and tk[i] in ma60 else None
        f["ADR"] = adr.get(d)
        return f

    groups = {
        "VIX": [("<18", lambda v: v < 18), ("18～25", lambda v: 18 <= v < 25), ("≥25", lambda v: v >= 25)],
        "SPX": [("前晚跌>1%", lambda v: v < -1), ("±1%", lambda v: -1 <= v <= 1), ("前晚漲>1%", lambda v: v > 1)],
        "MA60": [("加權<MA60", lambda v: v < 0), ("MA60 上 0～5%", lambda v: 0 <= v < 5), ("MA60 上 ≥5%", lambda v: v >= 5)],
        "ADR": [("低波動", lambda v: v < q1), ("中波動", lambda v: q1 <= v < q2), ("高波動", lambda v: v >= q2)],
    }
    out = [__doc__, f"ADR20 三等分界：{q1*100:.2f}%／{q2*100:.2f}%"]
    combos = [(-1, "開低做空", lambda g: g < -0.003), (-1, "開高做空", lambda g: g > 0.003), (-1, "開低＋開高做空", lambda g: abs(g) > 0.003), (1, "開高做多", lambda g: g > 0.003)]
    cache = {}
    for side, name, gf in combos:
        if side not in cache:
            cache[side] = R.setups(days, gaps, adr, side, "相對", 0.25, "E2")
        sel = [s for s in cache[side] if s["minute"] <= 180 and gf(s["gap"])]
        rows = []
        for s in sel:
            p = s["pnl"][("無", None)]
            rows.append((s["day"], p, p - side * drift[s["minute"]], feats(s["day"])))
        ex_all = np.array([r[2] for r in rows])
        out.append(f"\n===== {name}：{len(rows)} 筆，超額 {R.fmt(R.stats(ex_all))}")
        for key, bins in groups.items():
            for lab, fn in bins:
                sub = [r for r in rows if r[3][key] is not None and fn(r[3][key])]
                if len(sub) < 15:
                    out.append(f"  {key:5s} {lab:12s} 樣本 {len(sub)} 筆太少"); continue
                p = np.array([r[1] for r in sub]); ex = np.array([r[2] for r in sub])
                ins = np.array([r[0] < R.SPLIT for r in sub])
                si, so = R.stats(ex[ins]), R.stats(ex[~ins])
                out.append(f"  {key:5s} {lab:12s} {len(sub):4d} 筆 勝率 {(p>0).mean()*100:5.1f}% 平均 {p.mean():+.3f}% 超額 {ex.mean():+.3f}%（≈{ex.mean()*390:+5.0f} 點）t {R.stats(ex)['t']:+.2f}｜內 {si['mean']:+.3f}%({si['n']}) 外 {so['mean']:+.3f}%({so['n']})")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究514_型態依市況.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
