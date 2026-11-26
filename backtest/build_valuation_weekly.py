"""上市股票估值（每週）→ backtest/valuation_weekly.csv：date,n,pe_median,pe_ew,yield_median,yield_mean,pb_median

來源：證交所 BWIBBU_d（個股日本益比、殖利率、股價淨值比，2005-09 起），每週最後一個交易日抓一次
  pe_median：本益比 >0 的個股中位數；pe_ew：等權「盈餘殖利率」平均的倒數（1 ÷ mean(1/PE)，負盈餘當 0 盈餘）
  yield_*：殖利率（%）；pb_median：股價淨值比中位數
可續跑（已有日期跳過）；請求間隔 3 秒。用法：python -X utf8 backtest/build_valuation_weekly.py
"""
import csv
import json
import os
import statistics
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "valuation_weekly.csv")
COLS = ["date", "n", "pe_median", "pe_ew", "yield_median", "yield_mean", "pb_median"]


def num(x):
    try:
        v = float(str(x).replace(",", ""))
        return v
    except ValueError:
        return None


def main():
    import bt
    have = {}
    if os.path.exists(OUT):
        for r in csv.DictReader(open(OUT, encoding="utf-8")):
            have[r["date"]] = [r[c] for c in COLS]
    weeks = [d for d, nxt in zip(bt.DAYS, bt.DAYS[1:] + ["9999"]) if d >= "2005-09-01" and (nxt[:4] == "9999" or
             __import__("datetime").date.fromisoformat(nxt).isocalendar()[1] != __import__("datetime").date.fromisoformat(d).isocalendar()[1])]
    todo = [d for d in weeks if d not in have]
    print("要抓", len(todo), "週", flush=True)
    for k, d in enumerate(todo, 1):
        u = f"https://www.twse.com.tw/rwd/zh/afterTrading/BWIBBU_d?date={d.replace('-', '')}&selectType=ALL&response=json"
        try:
            js = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            print(d, "ERR", e, flush=True)
            time.sleep(20)
            continue
        fl = js.get("fields") or (js.get("tables") or [{}])[0].get("fields") or []
        data = js.get("data") or (js.get("tables") or [{}])[0].get("data") or []
        if not fl or not data:
            print(d, "無資料", js.get("stat"), flush=True)
            time.sleep(3)
            continue
        ipe = next(i for i, f in enumerate(fl) if "本益比" in f)
        iy = next(i for i, f in enumerate(fl) if "殖利率" in f)
        ipb = next(i for i, f in enumerate(fl) if "淨值比" in f)
        pes, eys, ys, pbs = [], [], [], []
        for r in data:
            pe, y, pb = num(r[ipe]), num(r[iy]), num(r[ipb])
            if pe and pe > 0:
                pes.append(pe)
                eys.append(1 / pe)
            elif r[ipe] in ("-", "", "0.00"):
                eys.append(0.0)
            if y is not None:
                ys.append(y)
            if pb and pb > 0:
                pbs.append(pb)
        if len(pes) < 100:
            print(d, "樣本太少", len(pes), flush=True)
            time.sleep(3)
            continue
        have[d] = [d, len(data), f"{statistics.median(pes):.2f}", f"{1 / statistics.mean(eys):.2f}" if statistics.mean(eys) > 0 else "",
                   f"{statistics.median(ys):.2f}", f"{statistics.mean(ys):.2f}", f"{statistics.median(pbs):.2f}"]
        if k % 20 == 0 or k == len(todo):
            with open(OUT, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(COLS)
                w.writerows(have[x] for x in sorted(have))
            print(f"{k}/{len(todo)} 到 {d}", flush=True)
        time.sleep(3)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        w.writerows(have[x] for x in sorted(have))


if __name__ == "__main__":
    main()
