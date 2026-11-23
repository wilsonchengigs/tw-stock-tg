"""從 Yahoo 抓加權指數、0050、00631L 日資料（存成同目錄的 json），整理成 {日期: (收盤, 調整後收盤)}"""
import json
import os
import urllib.request
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
TW = timezone(timedelta(hours=8))
SYMBOLS = {"TWII": "%5ETWII", "0050.TW": "0050.TW", "00631L.TW": "00631L.TW"}


def fetch(name):
    path = os.path.join(HERE, name + ".json")
    if not os.path.exists(path):
        u = f"https://query1.finance.yahoo.com/v8/finance/chart/{SYMBOLS[name]}?period1=0&period2=9999999999&interval=1d&events=div%2Csplit"
        d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read())
        json.dump(d["chart"]["result"][0], open(path, "w"))
    return json.load(open(path))


def load(name):
    r = fetch(name)
    q = r["indicators"]["quote"][0]
    adj = r["indicators"].get("adjclose", [{}])[0].get("adjclose") or q["close"]
    out = {}
    for t, c, a in zip(r["timestamp"], q["close"], adj):
        if c is None or a is None or c <= 0:
            continue
        out[datetime.fromtimestamp(t, TW).strftime("%Y-%m-%d")] = (c, a)
    return out


def series():
    return load("TWII"), load("0050.TW"), load("00631L.TW")
