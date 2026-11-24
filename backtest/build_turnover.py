"""從證交所 FMTQIK 下載每日大盤成交股數與成交金額（1997～），存 backtest/turnover_daily.csv：date,shares,amount
可中斷續跑。用法：python -X utf8 backtest/build_turnover.py"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import report  # noqa: E402

OUT = os.path.join(HERE, "turnover_daily.csv")
done = set()
if os.path.exists(OUT):
    done = {r["date"][:7] for r in csv.DictReader(open(OUT, encoding="utf-8"))}
new = not os.path.exists(OUT)
f = open(OUT, "a", encoding="utf-8", newline="")
w = csv.writer(f)
if new:
    w.writerow(["date", "shares", "amount"])
y, m = 1997, 1
while (y, m) <= (2026, 11):
    key = f"{y}-{m:02d}"
    if key not in done:
        try:
            d = report.get_json(f"https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?date={y}{m:02d}01&response=json")
            n = 0
            for t in report.tables_of(d):
                fl = t.get("fields", [])
                if "日期" in fl and "成交金額" in fl:
                    idt, ish, iam = fl.index("日期"), fl.index("成交股數"), fl.index("成交金額")
                    for r in t.get("data", []):
                        yy, mm, dd = str(r[idt]).strip().split("/")
                        w.writerow([f"{int(yy) + 1911}-{int(mm):02d}-{int(dd):02d}", int(report.num(r[ish])), int(report.num(r[iam]))])
                        n += 1
            f.flush()
            print(key, n, flush=True)
        except Exception as e:  # noqa: BLE001
            print(key, "ERR", e, flush=True)
    m += 1
    if m > 12:
        y, m = y + 1, 1
