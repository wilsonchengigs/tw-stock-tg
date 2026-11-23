"""
每個交易日 21:30 傳台股日報到 Telegram（資料來源：臺灣證券交易所公開資料）

- 下午（REPORT_PART=close）：加權指數漲跌、成交量（成交金額）、三大法人買賣超（證交所約 15:00 公布）
- 晚上（REPORT_PART=margin）：大盤（上市）融資維持率（融資資料約 21:00 公布）
- REPORT_PART=all（預設，排程用這個）：兩段一起

融資維持率 = Σ(個股融資餘額張數 × 1000 × 收盤價) ÷ 融資餘額總金額（證交所不直接公布，一般網站也是這樣估算）

環境變數：TG_BOT_TOKEN、TG_CHAT_ID；REPORT_PART；REPORT_DATE（選填，YYYYMMDD，測試用）
只用 Python 標準函式庫。
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

TW = timezone(timedelta(hours=8))
UA = {"User-Agent": "Mozilla/5.0 (tw-stock-tg report)"}
# 資料還沒公布時每 5 分鐘再試一次，最多等 30 分鐘
RETRY_TIMES = 6
RETRY_WAIT_SEC = 300


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode("utf-8"))
    time.sleep(2)  # 證交所對短時間大量請求會擋，間隔一下
    return data


def num(s) -> float:
    s = str(s).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def tables_of(data: dict) -> list:
    """新版回傳 tables:[{fields,data}]；舊版是 fields/data 或 fields1/data1…，統一成 list"""
    if isinstance(data.get("tables"), list):
        return data["tables"]
    out = []
    if "fields" in data:
        out.append({"fields": data["fields"], "data": data.get("data", [])})
    for i in range(1, 20):
        if f"fields{i}" in data:
            out.append({"fields": data[f"fields{i}"], "data": data.get(f"data{i}", [])})
    return out


def taiex(date: str):
    """加權指數 {close, change, pct}；非交易日或還沒收盤回 None"""
    d = get_json(f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date}&type=IND&response=json")
    if d.get("stat") != "OK":
        return None
    for t in tables_of(d):
        for r in t.get("data", []):
            if str(r[0]).strip() == "發行量加權股價指數":
                # 欄位：指數, 收盤指數, 漲跌(+/-，可能是 HTML), 漲跌點數, 漲跌百分比(%)
                sign = -1 if "-" in re.sub(r"<[^>]+>", "", str(r[2])) else 1
                return {"close": num(r[1]), "change": sign * num(r[3]), "pct": sign * abs(num(r[4]))}
    return None


def turnover(date: str):
    """大盤成交金額（元）{today, prev}；非交易日回 None。資料是整個月一張表，日期是民國年（115/11/20）"""
    def month_rows(yyyymm: str) -> list:
        d = get_json(f"https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?date={yyyymm}01&response=json")
        rows = []
        for t in tables_of(d):
            f = t.get("fields", [])
            if "日期" in f and "成交金額" in f:
                idate, iamt = f.index("日期"), f.index("成交金額")
                for r in t.get("data", []):
                    y, m, dd = str(r[idate]).strip().split("/")
                    rows.append((f"{int(y) + 1911}{int(m):02d}{int(dd):02d}", num(r[iamt])))
        return rows

    rows = month_rows(date[:6])
    keys = [k for k, _ in rows]
    if date not in keys:
        return None
    i = keys.index(date)
    if i > 0:
        prev = rows[i - 1][1]
    else:
        first = datetime.strptime(date[:6] + "01", "%Y%m%d") - timedelta(days=1)
        last_month = month_rows(first.strftime("%Y%m"))
        prev = last_month[-1][1] if last_month else 0.0
    return {"today": rows[i][1], "prev": prev}


def institutional(date: str):
    """回傳 {名稱: 買賣差額(元)}；非交易日或還沒公布回 None"""
    d = get_json(f"https://www.twse.com.tw/rwd/zh/fund/BFI82U?type=day&dayDate={date}&response=json")
    if d.get("stat") != "OK":
        return None
    rows = {}
    for t in tables_of(d):
        for r in t.get("data", []):
            rows[str(r[0]).strip()] = num(r[-1])
    if not rows:
        return None
    foreign = sum(v for k, v in rows.items() if k.startswith("外資"))
    dealer = sum(v for k, v in rows.items() if k.startswith("自營商"))
    trust = rows.get("投信", 0.0)
    total = rows.get("合計", foreign + dealer + trust)
    return {"外資": foreign, "投信": trust, "自營商": dealer, "合計": total}


def close_prices(date: str) -> dict:
    d = get_json(f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date}&type=ALLBUT0999&response=json")
    prices = {}
    for t in tables_of(d):
        f = t.get("fields", [])
        if "證券代號" in f and "收盤價" in f:
            ic, ip = f.index("證券代號"), f.index("收盤價")
            for r in t.get("data", []):
                p = num(r[ip])
                if p > 0:
                    prices[str(r[ic]).strip()] = p
    return prices


def margin_ratio(date: str):
    """回傳融資維持率（%）；非交易日或資料不齊回 None"""
    d = get_json(f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date}&selectType=ALL&response=json")
    if d.get("stat") != "OK":
        return None
    total_amount = 0.0  # 融資今日餘額（仟元）
    holdings = {}       # 代號 -> 融資今日餘額（張）
    for t in tables_of(d):
        f = [str(x) for x in t.get("fields", [])]
        rows = t.get("data", [])
        if f and f[0] == "項目":
            for r in rows:
                if "融資金額" in str(r[0]):
                    total_amount = num(r[5])  # 欄位：項目, 買進, 賣出, 現金償還, 前日餘額, 今日餘額
        elif f and f[0] in ("代號", "股票代號"):
            # 欄位：代號, 名稱, 融資買進, 融資賣出, 現金償還, 前日餘額, 今日餘額, 限額, 融券…
            for r in rows:
                holdings[str(r[0]).strip()] = num(r[6])
    if total_amount <= 0 or not holdings:
        return None
    prices = close_prices(date)
    if not prices:
        return None
    value = sum(lots * 1000 * prices.get(code, 0.0) for code, lots in holdings.items())
    return value / (total_amount * 1000) * 100


def prev_trading_ratio(date: str):
    day = datetime.strptime(date, "%Y%m%d")
    for _ in range(10):
        day -= timedelta(days=1)
        if day.weekday() >= 5:
            continue
        r = margin_ratio(day.strftime("%Y%m%d"))
        if r is not None:
            return r
    return None


def wait_for(fetch, date: str, retry: bool):
    """排程時資料可能晚幾分鐘公布：拿不到就等一下再試；手動指定日期時不等"""
    for i in range(RETRY_TIMES if retry else 1):
        v = fetch(date)
        if v is not None:
            return v
        if retry and i < RETRY_TIMES - 1:
            print(f"{fetch.__name__} 還沒有資料，{RETRY_WAIT_SEC // 60} 分鐘後再試")
            time.sleep(RETRY_WAIT_SEC)
    return None


def yi(v: float) -> str:
    return f"{v / 1e8:+,.1f} 億"


def word(v: float) -> str:
    return "買超" if v > 0 else "賣超" if v < 0 else "持平"


def send(text: str):
    token, chat = os.environ["TG_BOT_TOKEN"], os.environ["TG_CHAT_ID"]
    body = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body)
    with urllib.request.urlopen(req, timeout=30) as res:
        res.read()


def close_lines(date: str, retry: bool):
    idx = wait_for(taiex, date, retry)
    if idx is None:
        return None
    inst = wait_for(institutional, date, retry)
    arrow = "🔺" if idx["change"] > 0 else "🔻" if idx["change"] < 0 else "➖"
    trend = "上漲" if idx["change"] > 0 else "下跌" if idx["change"] < 0 else "平盤"
    lines = [f"加權指數：{idx['close']:,.2f}　{arrow}{trend} {abs(idx['change']):,.2f} 點（{idx['pct']:+.2f}%）"]
    vol = turnover(date)
    if vol is not None:
        diff = f"，比前一交易日 {yi(vol['today'] - vol['prev'])}" if vol["prev"] > 0 else ""
        lines.append(f"成交量：{vol['today'] / 1e8:,.0f} 億{diff}")
    if inst is None:
        lines.append("三大法人：資料還沒公布")
    else:
        lines += [
            f"三大法人：合計{word(inst['合計'])} {yi(inst['合計'])}",
            f"・外資 {yi(inst['外資'])}　・投信 {yi(inst['投信'])}　・自營商 {yi(inst['自營商'])}",
        ]
    return lines


def margin_lines(date: str, retry: bool):
    ratio = wait_for(margin_ratio, date, retry)
    if ratio is None:
        return ["大盤融資維持率：資料還沒公布"]
    prev = prev_trading_ratio(date)
    if prev is None:
        return [f"大盤融資維持率：{ratio:.1f}%"]
    return [f"大盤融資維持率：{ratio:.1f}%（前一交易日 {prev:.1f}%，{ratio - prev:+.1f}）"]


def main():
    part = os.environ.get("REPORT_PART") or "all"
    date = os.environ.get("REPORT_DATE") or ""
    retry = not date
    date = date or datetime.now(TW).strftime("%Y%m%d")
    if datetime.strptime(date, "%Y%m%d").weekday() >= 5:
        print(f"{date} 是週末，不送")
        return
    md = f"{int(date[4:6])}/{int(date[6:])}"

    # 先確認這天有開盤（國定假日證交所回非 OK）：只等「下午」那段，晚上那段收盤資料一定早就有了
    if part in ("close", "all"):
        body = close_lines(date, retry)
        if body is None:
            print(f"{date} 不是交易日或資料還沒公布，不送")
            return
    else:
        if taiex(date) is None:
            print(f"{date} 不是交易日，不送")
            return
        body = []

    title = {"close": "台股收盤", "margin": "台股融資", "all": "台股日報"}[part]
    if part in ("margin", "all"):
        body += margin_lines(date, retry)
    text = "\n".join([f"📊 {md} {title}"] + body)
    print(text)
    send(text)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # 失敗也通知，免得默默沒收到
        print(f"失敗：{e}", file=sys.stderr)
        if os.environ.get("TG_BOT_TOKEN") and os.environ.get("TG_CHAT_ID"):
            send(f"⚠️ 台股日報抓資料失敗：{e}")
        sys.exit(1)
