"""美股半導體：SOX 指數（1994～）模擬 1x／2x／3x，SOXL 真實價格校正"""
import json
import math
import os
from datetime import date, datetime, timedelta, timezone

SRC = os.path.dirname(os.path.abspath(__file__))
NY = timezone(timedelta(hours=-5))
TD = 252


def _fetch(name):
    import urllib.request
    path = os.path.join(SRC, name + ".json")
    if not os.path.exists(path):
        sym = {"SOX": "%5ESOX"}.get(name, name)
        u = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1=0&period2=9999999999&interval=1d&events=div%2Csplit"
        d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read())
        json.dump(d["chart"]["result"][0], open(path, "w"))
    return json.load(open(path))


def load(name):
    r = _fetch(name)
    q = r["indicators"]["quote"][0]
    adj = r["indicators"].get("adjclose", [{}])[0].get("adjclose") or q["close"]
    out = {}
    for t, c, a in zip(r["timestamp"], q["close"], adj):
        if c and a and c > 0:
            out[datetime.fromtimestamp(t, NY).strftime("%Y-%m-%d")] = a
    return out


SOX = load("SOX")
SOXL = load("SOXL")
DAYS = sorted(SOX)
PX = [SOX[d] for d in DAYS]
DIV = 0.008
R1 = [0.0] + [PX[i] / PX[i - 1] - 1 + DIV / TD for i in range(1, len(PX))]

WEEK_END = []
for i, d in enumerate(DAYS):
    if i == len(DAYS) - 1:
        WEEK_END.append(True)
    else:
        WEEK_END.append(date.fromisoformat(d).isocalendar()[:2] != date.fromisoformat(DAYS[i + 1]).isocalendar()[:2])

_S = {}


def sma(n):
    if n not in _S:
        out, s = [None] * len(PX), 0.0
        for i, p in enumerate(PX):
            s += p
            if i >= n:
                s -= PX[i - n]
            if i >= n - 1:
                out[i] = s / n
        _S[n] = out
    return _S[n]


def calibrate():
    ks = [d for d in sorted(SOXL) if d in SOX and d >= "2010-04-01"]
    act = SOXL[ks[-1]] / SOXL[ks[0]]
    idx = {d: i for i, d in enumerate(DAYS)}
    lines = [f"SOXL 實際 {ks[0]}→{ks[-1]} 倍數 {act:,.1f}"]
    for drag in (0.02, 0.03, 0.04, 0.05, 0.06):
        v = 1.0
        for a, b in zip(ks, ks[1:]):
            v *= 1 + 3 * R1[idx[b]] - drag * 2 / TD  # 槓桿多出來的 2 倍要付成本
        lines.append(f"每單位槓桿成本 {drag:.0%}/年 → 模擬 {v:,.1f}")
    return lines


if __name__ == "__main__":
    big = [(DAYS[i], round(PX[i] / PX[i - 1] - 1, 3)) for i in range(1, len(PX)) if abs(PX[i] / PX[i - 1] - 1) > 0.15]
    out = [f"SOX {DAYS[0]}～{DAYS[-1]} {len(DAYS)} 天，單日 >15%：{big[:10]}"]
    out += calibrate()
    open(os.path.join(os.path.dirname(__file__), "us_cal.txt"), "w", encoding="utf-8").write("\n".join(out))
