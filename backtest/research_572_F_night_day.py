"""研究 572：F 外資期貨雙指標（未平倉變化 z 與交易淨額 z 都 >1.5、v3 在場、排除結算日與次日）與「獨立短線」（只看未平倉 z>1.5）
(a) 5 天持有報酬拆白天／晚上（同研究 555）
(b) 資料 15:00 後公布：改在當晚夜盤開盤（15:00 後）進 vs 隔天 08:45 進——差＝夜盤開盤→隔天 08:45 的報酬
z 用前 250 天（與日報 foreign_fut_lines 相同）；台指期近月、遇換月略過
用法：python -X utf8 backtest/research_572_F_night_day.py
"""
import os, sys, csv, datetime as dt
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_138_金字塔加碼與分段停損 as S138
from research_555_VD_night_day_split import split


def main():
    net = {}; flow = {}
    for r in csv.DictReader(open(os.path.join(HERE, "tx_inst_oi.csv"), encoding="utf-8")):
        if r["investor"].startswith("外資"):
            net[r["date"]] = float(r["long_oi"]) - float(r["short_oi"]); flow[r["date"]] = float(r["long_vol"]) - float(r["short_vol"])
    nd = sorted(net)
    best = {}
    for r in csv.DictReader(open(os.path.join(HERE, "tx_daily_ohlc.csv"), encoding="utf-8")):
        if r["open"] in ("-", "") or r["close"] in ("-", ""):
            continue
        k = (r["date"], r["session"]); v = int(r["volume"] or 0)
        if k not in best or v > best[k][0]:
            best[k] = (v, r["month"], float(r["open"]), float(r["close"]))
    b = {d: best[(d, s)] for d, s in best if s == "day"}; ds = sorted(b); pos = {d: i for i, d in enumerate(ds)}
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    tw = lambda d: dt.date.fromisoformat(d).weekday() == 2 and 15 <= dt.date.fromisoformat(d).day <= 21
    sig2 = []; sig1 = []
    deltas = [net[nd[k]] - net[nd[k - 1]] for k in range(1, len(nd))]; fl = [flow[nd[k]] for k in range(1, len(nd))]
    for k in range(251, len(deltas)):
        d = nd[k + 1]; p = nd[k]
        if tw(d) or tw(p):
            continue
        h = np.array(deltas[k - 250:k]); z = (deltas[k] - h.mean()) / h.std()
        fh = np.array(fl[k - 250:k]); zf = (fl[k] - fh.mean()) / fh.std()
        on = st[keys[np.searchsorted(keys, d, side="right") - 1]] == 1
        if z > 1.5:
            sig1.append(d)
            if zf > 1.5 and on:
                sig2.append(d)
    out = [__doc__]
    for name, sig in (("F 雙指標（在場）", sig2), ("獨立短線（未平倉 z>1.5）", sig1)):
        rows = []; pre = []
        for d in sig:
            if d not in pos or pos[d] + 1 >= len(ds):
                continue
            nx = ds[pos[d] + 1]
            r = split(b, ds, pos[d] + 1, 5)
            if r:
                rows.append(r)
            if (nx, "night") in best and best[(nx, "night")][1] == b[nx][1]:
                pre.append((b[nx][2] / best[(nx, "night")][2] - 1) * 100)
        x = np.array(rows) * 100; pre = np.array(pre)
        out.append(f"{name}：{len(sig)} 次訊號、{len(x)} 筆可拆")
        for j, lab in enumerate(("白天合計", "晚上合計", "連抱（現行）")):
            out.append(f"   {lab}：每筆 {x[:, j].mean():+.3f}% 勝率 {(x[:, j]>0).mean()*100:.0f}%")
        out.append(f"   當晚夜盤開盤 → 隔天 08:45（提早進可多拿）：{len(pre)} 次 每次 {pre.mean():+.3f}% t {pre.mean()/(pre.std(ddof=1)/np.sqrt(len(pre))):+.2f}")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究572_F日夜.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
