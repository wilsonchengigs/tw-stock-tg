"""研究 161：日報「爆量收黑獨立短線」分段穩健性（研究 105：多頭且融資正常時有效）

訊號：證交所成交金額 ≥ 前 20 日均 1.5 倍且加權收黑、v3 在場（前一天收盤狀態）；D+1 台指期開盤進、第 10 個日盤收盤出（扣 3 點）
同一段內「v3 在場、非訊號」同波動度日子同樣進出當對照；1998～2026 分 6 段；持有中再出現的訊號略過
用法：python -X utf8 backtest/research_157_爆量收黑分段穩健性.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r139", os.path.join(HERE, "research_139_日夜盤報酬拆解.py"))
R139 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R139)
R138 = R139.R138
COST, H = 3.0, 5
SEGS = [("1998", "2003"), ("2003", "2008"), ("2008", "2012"), ("2012", "2017"), ("2017", "2022"), ("2022", "2099")]


def main():
    dates, day, night, near = R139.load_tx()
    bi = {d: k for k, d in enumerate(R138.DAYS)}
    PX, ST = R138.PX, R138.ST
    rows = []
    for k in range(21, len(dates) - H - 1):
        d = dates[k]
        if d not in bi:
            continue
        i = bi[d]
        a = R139.AMT.get(d)
        prev = [R139.AMT.get(R138.DAYS[j]) for j in range(i - 20, i)]
        prev = [x for x in prev if x]
        vr = a / (sum(prev) / len(prev)) if a and len(prev) >= 16 else None
        m = near[dates[k + 1]]
        e, x = day[dates[k + 1]].get(m), day[dates[k + H]].get(m)
        if not (e and x):
            continue
        rows.append(dict(d=d, sig=vr is not None and vr >= 1.5 and PX[i] < PX[i - 1], on=PX[i] >= R138.M80[i] * 0.975 and not R138.V.hot_at(i),
                         r=(x[3] - e[0] - COST) / e[0], c=PX[i], i=i))
    n = len(rows)
    cc = np.array([0.0] + [PX[rows[k]["i"]] / PX[rows[k]["i"] - 1] - 1 for k in range(1, n)])
    vol = np.array([np.std(cc[max(1, k - 20):k]) if k > 5 else np.nan for k in range(n)])
    ok = ~np.isnan(vol)
    dec = np.digitize(vol, np.nanpercentile(vol, np.arange(10, 100, 10)))
    sig = np.array([x["sig"] and x["on"] for x in rows])
    on = np.array([x["on"] for x in rows])
    keep = np.zeros(n, bool)
    last = -99
    for k in np.where(sig)[0]:
        if k - last >= H:
            keep[k] = True
            last = k
    r = np.array([x["r"] for x in rows])
    rng = np.random.default_rng(157)
    out = ["研究 161：爆量收黑獨立短線分段穩健性（多頭＝指數 ≥ 出場線、融資不過熱；D+1 開盤進、抱 5 天、無停損）", ""]
    for lo, hi in SEGS:
        inp = np.array([lo <= x["d"] < hi for x in rows])
        idx = np.where(keep & ok & inp)[0]
        if len(idx) < 3:
            out.append(f"{lo}～{hi if hi != '2099' else '2026'}：{len(idx)} 次（太少）")
            continue
        pools = {k: np.where(on & ~sig & ok & inp & (dec == dec[k]))[0] for k in idx}
        idx = [k for k in idx if len(pools[k])]
        diff = np.mean([r[k] - r[pools[k]].mean() for k in idx])
        null = np.array([np.mean([r[rng.choice(pools[k])] - r[pools[k]].mean() for k in idx]) for _ in range(2000)])
        pv = (1 + np.sum(null >= diff)) / 2001
        out.append(f"{lo}～{hi if hi != '2099' else '2026'}：{len(idx):3d} 次  每筆 {r[idx].mean():+.2%}  中位 {np.median(r[idx]):+.2%}  勝率 {np.mean(r[idx] > 0):.0%}  比同波動多頭日 {diff:+.2%}（p {pv:.3f}）")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究161_爆量收黑獨立短線分段.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
