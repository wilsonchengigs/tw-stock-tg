"""建立美國重大經濟事件日曆，存 backtest/us_events.csv：date,event（美東日期）
- FOMC：聯準會官網（2021～：fomccalendars.htm；2017～2020：fomchistorical{年}.htm），取會議最後一天（決策公布日），1998 起，
        不含臨時電話會議
- CPI：ALFRED 發布日清單 us_cpi_dates.txt（FRED／BLS 擋程式下載，手動取得）
- 非農（NFP）：BLS 網站擋爬蟲，用發布規則推算——「包含 12 日那一週的週六」＋20 天的星期五；
        遇美國假日順延到下週五。少數政府關門延後的月份（如 2013-10、2025-10／11）會不準
台灣時間：非農 20:30／21:30（夏令／冬令），FOMC 隔天 02:00／03:00 → 都落在台指期夜盤
用法：python -X utf8 backtest/build_us_events.py
"""
import csv
import html
import os
import re
import urllib.request
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"}
MON = {m: i for i, m in enumerate(("January", "February", "March", "April", "May", "June", "July", "August", "September",
                                   "October", "November", "December"), 1)}
ABBR = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def get(u):
    raw = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read().decode("utf-8", "replace")
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def month_no(s):
    s = s.strip()
    return MON.get(s) or ABBR.get(s[:3])


def fomc():
    out = set()
    txt = get("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")
    blocks = re.split(r"(\d{4}) FOMC Meetings", txt)
    for k in range(1, len(blocks) - 1, 2):
        y = int(blocks[k])
        for m1, m2, d1, d2 in re.findall(r"\b([A-Z][a-z]+)(?:/([A-Z][a-z]+))? (\d{1,2})-(\d{1,2})\*? ", blocks[k + 1]):
            mo = month_no(m2 or m1)
            if mo:
                dd = date(y, mo, int(d2))
                if dd <= date.today():
                    out.add(dd)
    for y in range(1998, 2021):  # 2008 前常是一天的會議（"March 22 Meeting"）
        txt = get(f"https://www.federalreserve.gov/monetarypolicy/fomchistorical{y}.htm")
        for m1, m2, d1, d2 in re.findall(r"\b([A-Z][a-z]+)(?:/([A-Z][a-z]+))? (\d{1,2})(?:-(\d{1,2}))? Meeting", txt):
            mo = month_no(m2 or m1)
            if mo:
                out.add(date(y, mo, int(d2 or d1)))
    return sorted(out)


def us_holidays(y):
    def nth(wd, mo, n):
        d = date(y, mo, 1)
        d += timedelta(days=(wd - d.weekday()) % 7)
        return d + timedelta(weeks=n - 1)

    def last(wd, mo):
        d = date(y, mo + 1, 1) - timedelta(days=1) if mo < 12 else date(y, 12, 31)
        return d - timedelta(days=(d.weekday() - wd) % 7)

    def obs(d):
        return d - timedelta(days=1) if d.weekday() == 5 else d + timedelta(days=1) if d.weekday() == 6 else d
    return {obs(date(y, 1, 1)), nth(0, 1, 3), nth(0, 2, 3), last(0, 5), obs(date(y, 6, 19)), obs(date(y, 7, 4)), nth(0, 9, 1),
            nth(0, 10, 2), obs(date(y, 11, 11)), nth(3, 11, 4), obs(date(y, 12, 25))}


def nfp(y0=1998):
    out = []
    for y in range(y0, date.today().year + 1):
        for mo in range(1, 13):
            d12 = date(y, mo, 12)
            sat = d12 + timedelta(days=(5 - d12.weekday()) % 7)
            rel = sat + timedelta(days=20)
            while rel in us_holidays(rel.year):
                rel += timedelta(days=7)
            if rel <= date.today():
                out.append(rel)
    return out


def main():
    rows = [(d.isoformat(), "FOMC") for d in fomc()] + [(d.isoformat(), "NFP") for d in nfp()]
    # CPI：ALFRED 發布日（https://alfred.stlouisfed.org/release/downloaddates?rid=10），1998 起每月一筆（同月兩筆時前一筆多為季節因子修正，取後一筆）
    rows += [(d.strip(), "CPI") for d in open(os.path.join(HERE, "us_cpi_dates.txt"), encoding="utf-8") if d.strip()]
    rows.sort()
    with open(os.path.join(HERE, "us_events.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "event"])
        w.writerows(rows)
    print(len(rows), "筆；", {k: sum(r[1] == k for r in rows) for k in ("FOMC", "NFP", "CPI")})
    print("FOMC 近期：", [r[0] for r in rows if r[1] == "FOMC"][-8:])
    print("FOMC 2017-2018：", [r[0] for r in rows if r[1] == "FOMC" and r[0] < "2019"])
    print("NFP 近期：", [r[0] for r in rows if r[1] == "NFP"][-8:])


if __name__ == "__main__":
    main()
