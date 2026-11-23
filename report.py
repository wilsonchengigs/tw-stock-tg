"""
每個交易日 21:30 傳台股日報到 Telegram（資料來源：臺灣證券交易所公開資料）

- 下午（REPORT_PART=close）：加權指數漲跌、成交量（成交金額）、三大法人買賣超（證交所約 15:00 公布）
- 晚上（REPORT_PART=margin）：大盤（上市）融資維持率、融資餘額增減（約 21:00 公布）、外資台指期淨未平倉（期交所）
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


def margin_data(date: str):
    """回傳 {ratio 融資維持率%, amount 融資餘額(元), prev_amount 前日融資餘額(元)}；非交易日或資料不齊回 None"""
    d = get_json(f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date}&selectType=ALL&response=json")
    if d.get("stat") != "OK":
        return None
    total_amount = 0.0  # 融資今日餘額（仟元）
    prev_amount = 0.0   # 融資前日餘額（仟元）
    holdings = {}       # 代號 -> 融資今日餘額（張）
    for t in tables_of(d):
        f = [str(x) for x in t.get("fields", [])]
        rows = t.get("data", [])
        if f and f[0] == "項目":
            for r in rows:
                if "融資金額" in str(r[0]):
                    # 欄位：項目, 買進, 賣出, 現金償還, 前日餘額, 今日餘額
                    prev_amount, total_amount = num(r[4]), num(r[5])
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
    return {
        "ratio": value / (total_amount * 1000) * 100,
        "amount": total_amount * 1000,
        "prev_amount": prev_amount * 1000,
    }


def margin_ratio(date: str):
    m = margin_data(date)
    return m["ratio"] if m else None


def foreign_futures(date: str):
    """外資台指期（TXF）多空未平倉口數淨額 {net, prev}；資料來源期交所，非交易日回 None"""
    start = (datetime.strptime(date, "%Y%m%d") - timedelta(days=14)).strftime("%Y/%m/%d")
    end = f"{date[:4]}/{date[4:6]}/{date[6:]}"
    body = urllib.parse.urlencode({"queryStartDate": start, "queryEndDate": end, "commodityId": "TXF"}).encode()
    req = urllib.request.Request("https://www.taifex.com.tw/cht/3/futContractsDateDown", data=body, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as res:
        raw = res.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("big5", errors="replace")
    lines = [ln.split(",") for ln in text.strip().splitlines()]
    if not lines or "身份別" not in lines[0]:
        return None
    h = lines[0]
    idate, iwho, inet = h.index("日期"), h.index("身份別"), h.index("多空未平倉口數淨額")
    rows = [(r[idate].strip(), num(r[inet])) for r in lines[1:] if len(r) > inet and r[iwho].strip().startswith("外資")]
    rows.sort()
    if not rows or rows[-1][0] != end:
        return None
    prev = rows[-2][1] if len(rows) >= 2 else None
    return {"net": rows[-1][1], "prev": prev}


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


def oi_text(v: float) -> str:
    return f"{'空單' if v < 0 else '多單'} {abs(v):,.0f} 口"


def margin_lines(date: str, retry: bool):
    lines = []
    m = wait_for(margin_data, date, retry)
    if m is None:
        lines.append("大盤融資維持率：資料還沒公布")
    else:
        prev = prev_trading_ratio(date)
        tail = f"（前一交易日 {prev:.1f}%，{m['ratio'] - prev:+.1f}）" if prev is not None else ""
        lines.append(f"大盤融資維持率：{m['ratio']:.1f}%{tail}")
        delta = m["amount"] - m["prev_amount"]
        trend = "增加" if delta > 0 else "減少" if delta < 0 else "持平"
        lines.append(f"融資餘額：{m['amount'] / 1e8:,.0f} 億（{trend} {abs(delta) / 1e8:,.1f} 億）")

    fut = foreign_futures(date)
    if fut is None:
        lines.append("外資台指期淨未平倉：資料還沒公布")
    else:
        line = f"外資台指期淨未平倉：{oi_text(fut['net'])}"
        if fut["prev"] is not None:
            diff = fut["net"] - fut["prev"]
            if diff == 0:
                line += "（與前一交易日相同）"
            elif (fut["net"] < 0) != (fut["prev"] < 0):
                line += f"（前一交易日 {oi_text(fut['prev'])}，多空翻轉）"
            else:
                side = "空單" if fut["net"] < 0 else "多單"
                # 淨空單時數字變小（更負）＝空單增加；淨多單時數字變大＝多單增加
                grew = (diff < 0) if fut["net"] < 0 else (diff > 0)
                line += f"（{side}{'增加' if grew else '減少'} {abs(diff):,.0f} 口）"
        lines.append(line)
    return lines


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
