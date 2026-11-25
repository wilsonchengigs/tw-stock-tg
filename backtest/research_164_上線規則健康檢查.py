"""研究 164：上線規則健康檢查（每月跑一次，看規則有沒有開始失效）

恐慌隔天做多（P）：全部、最近 24／12 個月的筆數、勝率、每筆；滾動 24 個月每筆的歷史分位（現在的近期表現在歷史上算不算差）
警戒：最近 24 個月每筆 < 歷史滾動值的 10 分位 → 標示 ⚠️
資料：tx_daily_ohlc.csv、GSPC.json 需先更新（build_tx_ohlc.py 新月份、Yahoo）
用法：python -X utf8 backtest/research_164_上線規則健康檢查.py
"""
import importlib.util
import os
import sys
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r148", os.path.join(HERE, "research_148_恐慌連續觸發.py"))
R148 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R148)


def months_before(d, k):
    y, m = d.year, d.month - k
    while m <= 0:
        y, m = y - 1, m + 12
    return f"{y}-{m:02d}-{min(d.day, 28):02d}"


def main():
    rows = [x for x in R148.build() if x["sig"]]
    last = date.fromisoformat(rows[-1]["d"])
    out = [f"研究 164：上線規則健康檢查（資料到 {rows[-1]['d']}）", "", "== 恐慌隔天做多（P）=="]
    for lab, lo in (("全部 1998～", "1998"), ("2017-05～（夜盤時代）", "2017-05-15"), ("最近 24 個月", months_before(last, 24)), ("最近 12 個月", months_before(last, 12))):
        v = np.array([x["r"] for x in rows if x["d"] >= lo])
        out.append(f"{lab:16s} {len(v):3d} 筆  勝率 {np.mean(v > 0):.0%}  每筆 {v.mean():+.2%}  中位 {np.median(v):+.2%}")
    # 滾動 24 個月每筆（每月底取一次）
    ds = [x["d"] for x in rows]
    rs = np.array([x["r"] for x in rows])
    roll = []
    for y in range(2000, last.year + 1):
        for m in range(1, 13):
            end = f"{y}-{m:02d}-28"
            if end > rows[-1]["d"]:
                break
            start = f"{y - 2}-{m:02d}-28"
            sel = [(d >= start) & (d < end) for d in ds]
            if sum(sel) >= 10:
                roll.append(rs[np.array(sel)].mean())
    roll = np.array(roll)
    cur = rs[np.array([d >= months_before(last, 24) for d in ds])].mean()
    pct = np.mean(roll <= cur)
    flag = "⚠️ 近期偏弱，留意" if pct < 0.10 else "✅ 正常"
    out.append(f"滾動 24 個月每筆：歷史 10／50／90 分位 {np.percentile(roll, 10):+.2%}／{np.percentile(roll, 50):+.2%}／{np.percentile(roll, 90):+.2%}；"
               f"目前 {cur:+.2%}（第 {pct:.0%} 分位）→ {flag}")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究164_上線規則健康檢查.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
