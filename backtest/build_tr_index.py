"""從證交所 MFI94U 下載「發行量加權股價報酬指數」每日值（2003～），存 backtest/tr_index_daily.csv：date,tr
可中斷續跑。用法：python -X utf8 backtest/build_tr_index.py"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import report  # noqa: E402

OUT = os.path.join(HERE, "tr_index_daily.csv")
done = set()
if os.path.exists(OUT):
    done = {r["date"][:7] for r in csv.DictReader(open(OUT, encoding="utf-8"))}
new = not os.path.exists(OUT)
f = open(OUT, "a", encoding="utf-8", newline="")
w = csv.writer(f)
if new:
    w.writerow(["date", "tr"])
y, m = 2003, 1
while (y, m) <= (2026, 11):
    key = f"{y}-{m:02d}"
    if key not in done:
        try:
            d = report.get_json(f"https://www.twse.com.tw/rwd/zh/TAIEX/MFI94U?date={y}{m:02d}01&response=json")
            n = 0
            for r in d.get("data") or []:
                yy, mm, dd = str(r[0]).strip().split("/")
                w.writerow([f"{int(yy) + 1911}-{int(mm):02d}-{int(dd):02d}", report.num(r[1])])
                n += 1
            f.flush()
            print(key, n, flush=True)
        except Exception as e:  # noqa: BLE001
            print(key, "ERR", e, flush=True)
    m += 1
    if m > 12:
        y, m = y + 1, 1
