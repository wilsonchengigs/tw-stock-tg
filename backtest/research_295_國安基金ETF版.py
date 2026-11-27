"""研究 295：國安基金進場 5 日——用 0050／00631L 真實開收價（研究 280 延伸，給沒有期貨帳戶的人）

事件日 E 同研究 280（第一個反應交易日）；只用資料可信的事件：0050 2014 起（Yahoo 之前有錯價）、00631L 2015-09 起。
交易：E 開盤買 → 第 1／5／20 個交易日收盤賣；成本＝手續費 0.1425%×2＋證交稅 0.1%（ETF）≈0.385%（未計折扣）。
價格用 Yahoo 原始 open／close（5 日內沒有分割；0050 2025-06 分割不在窗格內）。
用法：python -X utf8 backtest/research_295_國安基金ETF版.py
"""
import json
import os
import statistics
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
EVENTS = ["2015-08-25", "2020-03-19", "2022-07-13", "2025-04-09", "2026-11-09"]
COST = 0.001425 * 2 + 0.001


def load(sym):
    j = json.load(open(os.path.join(HERE, f"{sym}.TW.json"), encoding="utf-8"))
    tw = timezone(timedelta(hours=8))
    q = j["indicators"]["quote"][0]
    rows = []
    for t, o, c in zip(j["timestamp"], q["open"], q["close"]):
        if o and c:
            rows.append((datetime.fromtimestamp(t, tw).strftime("%Y-%m-%d"), o, c))
    return rows


def main():
    out = ["研究 295：國安基金進場——ETF 真實價（E 開盤買，扣約 0.385% 成本）\n"]
    for sym, start in (("0050", "2014-01-01"), ("00631L", "2015-09-01")):
        rows = load(sym)
        days = [r[0] for r in rows]
        out.append(f"【{sym}】")
        res = {1: [], 5: [], 20: []}
        for e in EVENTS:
            if e < start or e not in days:
                out.append(f"  {e}  —（資料不可信或缺）")
                continue
            i = days.index(e)
            o = rows[i][1]
            cells = []
            for h in (1, 5, 20):
                if i + h - 1 < len(rows):
                    r = rows[i + h - 1][2] / o - 1 - COST
                    res[h].append(r)
                    cells.append(f"{r * 100:+6.1f}%")
                else:
                    cells.append("   —  ")
            out.append(f"  {e}  開 {o:,.2f}  " + "  ".join(f"{h}日 {c}" for h, c in zip((1, 5, 20), cells)))
        for h, r in res.items():
            if r:
                out.append(f"  {h:>2} 日：{len(r)} 筆 平均 {statistics.mean(r) * 100:+.2f}%  上漲 {sum(x > 0 for x in r)}/{len(r)}")
        out.append("")
    text = "\n".join(out)
    print(text)
    open(os.path.join(HERE, "結果_研究295_國安基金ETF版.txt"), "w", encoding="utf-8").write(text + "\n")


if __name__ == "__main__":
    main()
