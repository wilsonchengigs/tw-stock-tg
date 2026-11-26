"""三大法人台指期（TX 大台）未平倉與交易口數 → backtest/tx_inst_oi.csv：date,investor,long_oi,short_oi,long_vol,short_vol
來源：FinMind TaiwanFuturesInstitutionalInvestors（2018-06 起）；每次全部重抓（約 10 次請求）
用法：python -X utf8 backtest/build_tx_inst_oi.py
"""
import csv
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "tx_inst_oi.csv")


def main():
    rows = []
    for y in range(2018, date.today().year + 1):
        u = "https://api.finmindtrade.com/api/v4/data?" + urllib.parse.urlencode(
            {"dataset": "TaiwanFuturesInstitutionalInvestors", "data_id": "TX", "start_date": f"{y}-01-01", "end_date": f"{y}-12-31"})
        d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=60))
        for r in d.get("data", []):
            rows.append((r["date"], r["institutional_investors"], r["long_open_interest_balance_volume"], r["short_open_interest_balance_volume"],
                         r["long_deal_volume"], r["short_deal_volume"]))
        print(y, len(d.get("data", [])), flush=True)
        time.sleep(2)
    if len(rows) < 1000:
        raise SystemExit("FinMind 回傳太少，不覆蓋舊檔")
    rows.sort()
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "investor", "long_oi", "short_oi", "long_vol", "short_vol"])
        w.writerows(rows)
    print(len(rows), "列，到", rows[-1][0])


if __name__ == "__main__":
    main()
