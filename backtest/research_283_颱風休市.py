"""研究 283：颱風休市前後的加權走勢

找事件：證交所交易日（turnover_daily.csv）缺的平日，扣掉證交所 holidaySchedule 公告的休市日（不含颱風假，
已驗證 2024-10-02／03、2026-07-10 都不在公告裡），落在 6～10 月的＝颱風臨時休市。公告休市日快取在
backtest/twse_holidays.json（第一次執行會抓 2000～2026，每次間隔 2 秒）。
連續休市算同一事件；E＝休市後第一個交易日，E0＝休市前最後一個交易日。
窗格（加權收盤對收盤，bp）：PRE1＝E0 前一日→E0（颱風來前一天，宣布休市多在前一晚）、GAP＝E0→E（休市期間＋復市當天）、
  POST5＝E→E+5
基準：所有非事件日同長度窗格；GAP 的基準用「間隔同樣交易日數」＝隔 1 個交易日的報酬（E0→E 只有 1 個交易日）。
安慰劑：隨機抽同數量的 6～10 月非事件日 5,000 次（PRE1、GAP、POST5 取最小 p×3）
用法：python -X utf8 backtest/research_283_颱風休市.py
"""
import csv
import datetime as dt
import json
import os
import random
import statistics
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "twse_holidays.json")


def holidays():
    hol = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
    for y in range(2000, 2027):
        if str(y) in hol:
            continue
        url = f"https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule?response=json&date={y}0101"
        j = json.load(urllib.request.urlopen(url, timeout=30))
        hol[str(y)] = [[r[0], r[1][:30]] for r in j.get("data", [])]
        time.sleep(2)
        json.dump(hol, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return {d for v in hol.values() for d, _ in v}


def new_moons(year):
    """Meeus 新月（UTC+8 日期），誤差數分鐘"""
    import math
    res = []
    k0 = math.floor((year - 2000) * 12.3685) - 2
    for k in range(k0, k0 + 16):
        T = k / 1236.85
        jde = (2451550.09766 + 29.530588861 * k + 0.00015437 * T * T)
        M = math.radians((2.5534 + 29.10535670 * k) % 360)
        Mp = math.radians((201.5643 + 385.81693528 * k) % 360)
        F = math.radians((160.7108 + 390.67050284 * k) % 360)
        E = 1 - 0.002516 * T
        jde += (-0.40720 * math.sin(Mp) + 0.17241 * E * math.sin(M) + 0.01608 * math.sin(2 * Mp)
                + 0.01039 * math.sin(2 * F) + 0.00739 * E * math.sin(Mp - M) - 0.00514 * E * math.sin(Mp + M))
        # JDE → UTC+8 日期（忽略 ΔT 約 1 分鐘）
        d = dt.datetime(2000, 1, 1, 12) + dt.timedelta(days=jde - 2451545.0, hours=8)
        res.append(d.date())
    return sorted(res)


def lunar_festivals(year):
    """端午＝夏至（約 6/21）所在農曆月初五；中秋＝秋分（約 9/23）所在月十五。節氣日用近似日期"""
    nm = new_moons(year)
    out = []
    for term, add in ((dt.date(year, 6, 21), 4), (dt.date(year, 9, 23), 14)):
        start = max(x for x in nm if x <= term)
        out.append(start + dt.timedelta(days=add))
    return out


def fixed_holidays(year):
    base = [dt.date(year, 1, 1), dt.date(year, 2, 28), dt.date(year, 4, 4), dt.date(year, 4, 5),
            dt.date(year, 5, 1), dt.date(year, 10, 10)]
    return base + lunar_festivals(year)


def main():
    hol = holidays()
    # 驗證農曆推算：2021～2026 公告休市日應包含推算的端午、中秋（或其補假在 ±1 天）
    for y in range(2021, 2027):
        for f in lunar_festivals(y):
            near = [f + dt.timedelta(days=k) for k in (-1, 0, 1)]
            assert any(x.isoformat() in hol or x.weekday() >= 5 for x in near), (y, f)
    tdays = [r["date"] for r in csv.DictReader(open(os.path.join(HERE, "turnover_daily.csv"), encoding="utf-8"))]
    tset = set(tdays)
    # 加權收盤：strategy_v3 的 PX（日期與證交所交易日對齊）
    import sys
    sys.path.insert(0, HERE)
    import strategy_v3 as s
    px = dict(zip(s.DAYS, s.PX))
    days = [d for d in tdays if d in px and d >= "2000-01-01"]
    P = [px[d] for d in days]
    pos = {d: i for i, d in enumerate(days)}
    # 候選臨時休市
    miss = []
    d = dt.date(2000, 1, 3)
    end = dt.date.fromisoformat(tdays[-1])
    while d <= end:
        iso = d.isoformat()
        if d.weekday() < 5 and iso not in tset and iso not in hol:
            miss.append(iso)
        d += dt.timedelta(days=1)
    out = []
    p = out.append
    p("研究 283：颱風休市前後加權報酬（bp）\n")
    p("缺交易但不在證交所公告休市日的平日（全部月份）：")
    p("  " + " ".join(miss))
    # 2021 前公告不完整：排除國定假日（含推算端午／中秋）前後 3 天內的缺口（補假、彈性放假）
    near_hol = set()
    for y in range(2000, 2027):
        for h in fixed_holidays(y):
            for k in range(-3, 4):
                near_hol.add((h + dt.timedelta(days=k)).isoformat())
    typh = [m for m in miss if m[5:7] in ("06", "07", "08", "09", "10") and (m >= "2021" or m not in near_hol)
            and m != "2001-09-12"]  # 911 恐攻休市，非颱風
    p("推算端午／中秋：" + " ".join(f"{y}:{'/'.join(x.strftime('%m-%d') for x in lunar_festivals(y))}" for y in range(2000, 2027)))
    # 合併連續
    events = []
    for m in typh:
        nxt = next((x for x in days if x > m), None)
        prv = max((x for x in days if x < m), default=None)
        if nxt is None or prv is None:
            continue
        if events and events[-1][1] == nxt:
            events[-1][2].append(m)
        else:
            events.append([prv, nxt, [m]])
    p(f"\n6～10 月颱風休市事件 {len(events)} 次：")
    rows = []
    for e0, e, ms in events:
        i0, i = pos[e0], pos[e]
        if i0 < 1 or i + 5 >= len(days):
            continue
        r = {"PRE1": (P[i0] / P[i0 - 1] - 1) * 1e4, "GAP": (P[i] / P[i0] - 1) * 1e4, "POST5": (P[i + 5] / P[i] - 1) * 1e4}
        rows.append(r)
        p(f"  休市 {','.join(ms)}  E0 {e0} → E {e}  PRE1 {r['PRE1']:+6.0f}  GAP {r['GAP']:+6.0f}  POST5 {r['POST5']:+6.0f}")
    excl = set()
    for e0, e, _ in events:
        excl.update(range(pos[e0] - 2, pos[e] + 6))
    pool = [k for k in range(2, len(days) - 6) if k not in excl and days[k][5:7] in ("06", "07", "08", "09", "10")]
    base = {"PRE1": lambda k: (P[k] / P[k - 1] - 1) * 1e4, "GAP": lambda k: (P[k + 1] / P[k] - 1) * 1e4,
            "POST5": lambda k: (P[k + 6] / P[k + 1] - 1) * 1e4}
    rnd = random.Random(283)
    p(f"\n窗格   事件 平均/中位/勝率（{len(rows)} 次）     6～10 月非事件基準 平均    安慰劑雙尾 p")
    ps = []
    for k in ("PRE1", "GAP", "POST5"):
        a = [r[k] for r in rows]
        bvals = [base[k](x) for x in pool]
        b = statistics.mean(bvals)
        obs = statistics.mean(a) - b
        T = 5000
        hit = sum(abs(statistics.mean(rnd.sample(bvals, len(a))) - b) >= abs(obs) for _ in range(T))
        ps.append(hit / T)
        p(f"{k:<6} {statistics.mean(a):+7.1f} {statistics.median(a):+7.1f} {sum(x > 0 for x in a) / len(a) * 100:4.0f}%            "
          f"{b:+6.1f}                {hit / T:.3f}")
    p(f"家族（最小 p×3）≈ {min(1, min(ps) * 3):.3f}")
    for lab, sel in (("2000–2012", lambda d: d < "2013"), ("2013～", lambda d: d >= "2013")):
        a = [r["PRE1"] for r, (e0, _, _) in zip(rows, events) if sel(e0)]
        p(f"PRE1 {lab}：{len(a)} 次 平均 {statistics.mean(a):+.1f} bp 中位 {statistics.median(a):+.1f} 勝率 {sum(x > 0 for x in a) / len(a) * 100:.0f}%")
    text = "\n".join(out)
    print(text)
    with open(os.path.join(HERE, "結果_研究283_颱風休市.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
