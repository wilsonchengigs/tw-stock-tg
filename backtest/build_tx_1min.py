"""從期交所「近 30 個交易日期貨每筆成交資料」(Daily_YYYY_MM_DD.zip) 建台指期（TX）近月 1 分 K
存 backtest/tx_1min.csv：trade_day,session,ts,open,high,low,close,volume
- trade_day：期交所的交易日（夜盤歸到下一個交易日，與期交所一致）
- session：day（08:45～13:45）／night（15:00～隔日 05:00）
- 近月：每個交易日成交量最大的單一月份（不含價差單 202612/202701、不含週選代號）
- volume：檔案的「成交數量(B+S)」÷ 2 ＝ 口數
- 可重跑，已有的交易日跳過；原始 zip 只在記憶體處理不落地
用法：python -X utf8 backtest/build_tx_1min.py
"""
import csv
import io
import os
import time
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "tx_1min.csv")
URL = "https://www.taifex.com.tw/file/taifex/Dailydownload/DailydownloadCSV/Daily_{:%Y_%m_%d}.zip"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"}


def fetch(d):
    try:
        raw = urllib.request.urlopen(urllib.request.Request(URL.format(d), headers=UA), timeout=120).read()
        return raw if raw[:2] == b"PK" else None  # 不存在的日期會回 HTML 錯誤頁
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def bars_of(raw, d):
    z = zipfile.ZipFile(io.BytesIO(raw))
    text = z.read(z.namelist()[0]).decode("big5", errors="replace").splitlines()[1:]
    ticks = []
    vol_by_month = defaultdict(int)
    for line in text:
        f = line.split(",")
        if len(f) < 6 or f[1].strip() != "TX":
            continue
        mon = f[2].strip()
        if "/" in mon or not mon.isdigit():
            continue
        q = int(f[5]) // 2 if f[5].strip().isdigit() else 0
        ticks.append((f[0].strip(), f[3].strip().zfill(6), float(f[4]), q, mon))
        vol_by_month[mon] += q
    if not ticks:
        return []
    ranked = sorted(vol_by_month, key=vol_by_month.get, reverse=True)
    near = ranked[0]
    # 結算日：到期月份 13:30 就停止交易，整天改用下一個月份（K 棒才會完整到 13:45）
    last_day_tick = max((t for dd, t, _p, _q, mon in ticks if mon == near and dd == f"{d:%Y%m%d}" and t <= "134500"), default="000000")
    if last_day_tick < "133100" and len(ranked) > 1:
        near = ranked[1]
    ticks.sort(key=lambda x: (x[0], x[1]))  # 穩定排序：同一秒內保留檔案原順序
    agg = {}
    for dd, tt, px, q, mon in ticks:
        if mon != near:
            continue
        ts = datetime.strptime(dd + tt[:4], "%Y%m%d%H%M")  # 該分鐘起點（成交在 hh:mm:ss → hh:mm）
        hm = int(tt[:4])
        session = "day" if 845 <= hm <= 1345 else "night"
        k = (session, ts)
        b = agg.get(k)
        if b is None:
            agg[k] = [px, px, px, px, q]
        else:
            b[1] = max(b[1], px)
            b[2] = min(b[2], px)
            b[3] = px  # 已排序；同一分鐘最後一筆為收
            b[4] += q
    return [(f"{d:%Y-%m-%d}", s, ts.strftime("%Y-%m-%d %H:%M"), *v) for (s, ts), v in sorted(agg.items(), key=lambda x: x[0][1])]


def main():
    done = set()
    if os.path.exists(OUT):
        done = {r["trade_day"] for r in csv.DictReader(open(OUT, encoding="utf-8"))}
    new = not os.path.exists(OUT)
    f = open(OUT, "a", encoding="utf-8", newline="")
    w = csv.writer(f)
    if new:
        w.writerow(["trade_day", "session", "ts", "open", "high", "low", "close", "volume"])
    d = date.today() - timedelta(days=1)  # 今天的檔案可能是盤中、不完整，不抓
    misses = 0
    while misses < 15:  # 往回找，連續 15 個工作日抓不到就停（超過 30 個交易日的檔案會被移除）
        if d.weekday() < 5 and f"{d:%Y-%m-%d}" not in done:
            raw = fetch(d)
            if raw is None:
                misses += 1
            else:
                misses = 0
                rows = bars_of(raw, d)
                w.writerows(rows)
                f.flush()
                print(d, len(rows), "根", flush=True)
                time.sleep(1)
        d -= timedelta(days=1)
    f.close()
    # 依時間重新排序
    rows = list(csv.DictReader(open(OUT, encoding="utf-8")))
    rows.sort(key=lambda r: r["ts"])
    with open(OUT, "w", encoding="utf-8", newline="") as g:
        w = csv.DictWriter(g, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("共", len({r["trade_day"] for r in rows}), "個交易日，", len(rows), "根 1 分 K")


if __name__ == "__main__":
    main()
