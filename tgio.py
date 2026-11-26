"""日報的底層工具：HTTP 退避重試、證交所 JSON 抓取、data/ CSV 快取讀寫、Telegram 發送（只用標準函式庫）
report.py 與 backtest/ 腳本都從這裡取用（report 仍會重新匯出同名函式，舊的 report.xxx 用法照舊）"""
import csv
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (tw-stock-tg report)"}
_JSON_MEMO = {}  # 同一次執行裡同一個網址只抓一次（例如當月 FMTQIK 成交量與指數都要用）
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def urlopen_retry(req, tries: int = 3, retry_post: bool = False):
    """urlopen（逾時 30 秒）＋退避重試：429／5xx／連線錯誤等 2、4 秒再試，其他 HTTP 錯誤（404 等）直接丟。
    POST（Telegram）預設只在 429／5xx 重試——連線逾時時訊息可能已送出，重試會重複"""
    for k in range(tries):
        try:
            return urllib.request.urlopen(req, timeout=30)
        except urllib.error.HTTPError as e:
            if k == tries - 1 or not (e.code == 429 or e.code >= 500):
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if k == tries - 1 or (req.data is not None and not retry_post):
                raise
        time.sleep(2 ** (k + 1))


def get_json(url: str) -> dict:
    if url in _JSON_MEMO:
        return _JSON_MEMO[url]
    req = urllib.request.Request(url, headers=UA)
    with urlopen_retry(req) as res:
        data = json.loads(res.read().decode("utf-8"))
    time.sleep(2)  # 證交所對短時間大量請求會擋，間隔一下
    if data.get("stat") == "OK":
        _JSON_MEMO[url] = data
    return data


def load_csv(name: str) -> dict:
    """data/{name}：第一欄日期 YYYYMMDD → 其餘欄位（字串）"""
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8", newline="") as f:
        lines = [r for r in csv.reader(f) if r][1:]
    return {r[0]: r[1:] for r in lines}


def save_csv(name: str, header: str, rows: dict):
    with open(os.path.join(DATA_DIR, name), "w", encoding="utf-8", newline="") as f:
        f.write(header + "\n")
        for d in sorted(rows):
            f.write(",".join([d] + [str(x) for x in rows[d]]) + "\n")


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


TG_LIMIT = 4096  # Telegram 單則訊息上限（字元）


def split_message(text: str, limit: int = TG_LIMIT) -> list:
    """超過上限時依行切成多則（不切斷一行；單行就超過才硬切）"""
    parts, cur = [], ""
    for line in text.split("\n"):
        while len(line) > limit:
            if cur:
                parts.append(cur)
                cur = ""
            parts.append(line[:limit])
            line = line[limit:]
        if cur and len(cur) + 1 + len(line) > limit:
            parts.append(cur)
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        parts.append(cur)
    return parts or [""]


def send(text: str):
    token, chat = os.environ["TG_BOT_TOKEN"], os.environ["TG_CHAT_ID"]
    for part in split_message(text):
        body = urllib.parse.urlencode({"chat_id": chat, "text": part}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body)
        with urlopen_retry(req) as res:
            res.read()
