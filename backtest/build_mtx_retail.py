"""小台（MTX）散戶多空比：存 backtest/mtx_retail.csv：date,total_oi,inst_net,retail_ratio

- 小台全市場未沖銷契約數：期交所 futDataDown（MTX，一般時段，各到期月加總，排除價差）
- 三大法人小台淨未平倉（多單未平倉 − 空單未平倉，口數）：FinMind TaiwanFuturesInstitutionalInvestors（2018-06 起）
- 散戶多空比 ＝ −三大法人淨未平倉 ÷ 全市場未平倉（市場常用定義：法人以外就是散戶；正＝散戶偏多）
用法：python -X utf8 backtest/build_mtx_retail.py（每次全部重抓，約 2 分鐘）
"""
import calendar
import csv
import json
import os
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "mtx_retail.csv")
UA = {"User-Agent": "Mozilla/5.0"}


def total_oi():
    oi = defaultdict(int)
    t = date.today()
    y, m = 2018, 6
    while (y, m) <= (t.year, t.month):
        last = calendar.monthrange(y, m)[1]
        body = urllib.parse.urlencode({"down_type": "1", "commodity_id": "MTX", "commodity_id2": "",
                                       "queryStartDate": f"{y}/{m:02d}/01", "queryEndDate": f"{y}/{m:02d}/{last}"}).encode()
        for attempt in range(3):
            try:
                raw = urllib.request.urlopen(urllib.request.Request("https://www.taifex.com.tw/cht/3/futDataDown", data=body, headers=UA),
                                             timeout=60).read().decode("big5", "replace")
                break
            except Exception as e:  # noqa: BLE001
                print(y, m, "retry", e, flush=True)
                time.sleep(10)
        else:
            raw = ""
        for r in list(csv.reader(raw.splitlines()))[1:]:
            if len(r) < 18 or r[1].strip() != "MTX" or "/" in r[2] or r[17].strip() != "一般":
                continue
            try:
                oi[r[0].strip().replace("/", "-")] += int(r[11].strip())
            except ValueError:
                pass
        print(y, m, flush=True)
        time.sleep(2)
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return oi


def inst_net():
    net = defaultdict(int)
    for y in range(2018, date.today().year + 1):
        u = "https://api.finmindtrade.com/api/v4/data?" + urllib.parse.urlencode(
            {"dataset": "TaiwanFuturesInstitutionalInvestors", "data_id": "MTX", "start_date": f"{y}-01-01", "end_date": f"{y}-12-31"})
        d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60))
        for r in d.get("data", []):
            net[r["date"]] += r["long_open_interest_balance_volume"] - r["short_open_interest_balance_volume"]
        print("FinMind", y, len(d.get("data", [])), flush=True)
        time.sleep(2)
    return net


def main():
    oi, net = total_oi(), inst_net()
    rows = [(d, oi[d], net[d], -net[d] / oi[d]) for d in sorted(set(oi) & set(net)) if oi[d] > 0]
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "total_oi", "inst_net", "retail_ratio"])
        w.writerows([(d, a, b, f"{c:.4f}") for d, a, b, c in rows])
    print(len(rows), "天", rows[0][0], "～", rows[-1][0], "最近", rows[-1])


if __name__ == "__main__":
    main()
