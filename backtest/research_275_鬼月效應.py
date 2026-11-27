"""研究 275：農曆七月（鬼月）效應——台股俗稱「鬼月不進場、鬼月底買」
鬼月＝包含「處暑」（太陽黃經 150°，約 8/23）的那個農曆月：前一次新月（台灣時間日期）＝初一、下一次新月前一天＝最後一天
新月用 Meeus《Astronomical Algorithms》第 49 章（含主要週期修正，誤差約數分鐘）；處暑用太陽視黃經近似（誤差 < 1 小時）
窗格（做多加權，收盤對收盤，扣來回 6 點）：
  GHOST     初一前一個交易日收盤 → 鬼月最後交易日收盤（整個鬼月）
  PRE 5     鬼月前 5 個交易日
  FIRST 5   鬼月第 1～5 個交易日
  LAST 5    鬼月最後 5 個交易日
  AFTER 10  鬼月結束後第 1～10 個交易日（「鬼月底買」）
對照：同天數、同前 20 日波動十分位所有窗格平均；家族：所有錨點一起平移 ±40～200 交易日 1,000 次（最小 p 值法、雙尾）；兩段 1998–2012／2013～
另列：v3 主策略在鬼月期間 vs 其他時間的每日報酬（主策略要不要在鬼月避開）
用法：python -X utf8 backtest/research_275_鬼月效應.py
"""
import datetime as dt
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402


def new_moon_jde(k):
    T = k / 1236.85
    jde = 2451550.09766 + 29.530588861 * k + 0.00015437 * T ** 2 - 0.000000150 * T ** 3 + 0.00000000073 * T ** 4
    E = 1 - 0.002516 * T - 0.0000074 * T ** 2
    r = math.radians
    M = r(2.5534 + 29.10535670 * k - 0.0000014 * T ** 2)
    Mp = r(201.5643 + 385.81693528 * k + 0.0107582 * T ** 2)
    F = r(160.7108 + 390.67050284 * k - 0.0016118 * T ** 2)
    Om = r(124.7746 - 1.56375588 * k + 0.0020672 * T ** 2)
    c = (-0.40720 * math.sin(Mp) + 0.17241 * E * math.sin(M) + 0.01608 * math.sin(2 * Mp)
         + 0.01039 * math.sin(2 * F) + 0.00739 * E * math.sin(Mp - M) - 0.00514 * E * math.sin(Mp + M)
         + 0.00208 * E * E * math.sin(2 * M) - 0.00111 * math.sin(Mp - 2 * F) - 0.00057 * math.sin(Mp + 2 * F)
         + 0.00056 * E * math.sin(2 * Mp + M) - 0.00042 * math.sin(3 * Mp) + 0.00042 * E * math.sin(M + 2 * F)
         + 0.00038 * E * math.sin(M - 2 * F) - 0.00024 * E * math.sin(2 * Mp - M) - 0.00017 * math.sin(Om)
         - 0.00007 * math.sin(Mp + 2 * M) + 0.00004 * math.sin(2 * Mp - 2 * F) + 0.00004 * math.sin(3 * M)
         + 0.00003 * math.sin(Mp + M - 2 * F) + 0.00003 * math.sin(2 * Mp + 2 * F) - 0.00003 * math.sin(Mp + M + 2 * F)
         + 0.00003 * math.sin(Mp - M + 2 * F) - 0.00002 * math.sin(Mp - M - 2 * F) - 0.00002 * math.sin(3 * Mp + M)
         + 0.00002 * math.sin(4 * Mp))
    return jde + c


def jd_to_tw_date(jd):
    jd += 8 / 24 + 0.5  # 台灣時間；TT 與 UT 差約 1 分鐘，忽略
    z = int(jd)
    a = z if z < 2299161 else z + 1 + int((z - 1867216.25) / 36524.25) - int(int((z - 1867216.25) / 36524.25) / 4)
    b = a + 1524
    c = int((b - 122.1) / 365.25)
    d = int(365.25 * c)
    e = int((b - d) / 30.6001)
    day = b - d - int(30.6001 * e)
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715
    return dt.date(year, month, day)


def sun_lon(jd):
    T = (jd - 2451545.0) / 36525
    L0 = 280.46646 + 36000.76983 * T
    M = math.radians(357.52911 + 35999.05029 * T)
    C = (1.914602 - 0.004817 * T) * math.sin(M) + 0.019993 * math.sin(2 * M) + 0.000289 * math.sin(3 * M)
    om = math.radians(125.04 - 1934.136 * T)
    return (L0 + C - 0.00569 - 0.00478 * math.sin(om)) % 360


def chushu_jd(year):
    jd = 2451545.0 + (year - 2000) * 365.2422 + 235  # 約 8 月中，往後找黃經 150°
    for _ in range(60):
        diff = (150 - sun_lon(jd) + 540) % 360 - 180
        if abs(diff) < 1e-6:
            break
        jd += diff / 360 * 365.2422
    return jd


def ghost_month(year):
    cd = jd_to_tw_date(chushu_jd(year))  # 農曆以「日」為單位：新月日期 ≤ 處暑日期 就算包含
    k = math.floor((year + 7.6 / 12 - 2000) * 12.3685) - 2
    while jd_to_tw_date(new_moon_jde(k + 1)) <= cd:
        k += 1
    while jd_to_tw_date(new_moon_jde(k)) > cd:
        k -= 1
    start = jd_to_tw_date(new_moon_jde(k))
    end = jd_to_tw_date(new_moon_jde(k + 1)) - dt.timedelta(days=1)
    return start, end


GM = {y: ghost_month(y) for y in range(1998, 2027)}
KNOWN = {2017: "2017-08-22", 2020: "2020-08-19", 2023: "2023-08-16", 2024: "2024-08-04", 2025: "2025-08-23", 2026: "2026-08-13"}

i0 = next(i for i, d in enumerate(bt.DAYS) if d >= "1997-10-01")
DAYS = bt.DAYS[i0:]
PX = np.array(bt.PX[i0:])
N = len(DAYS)
r1 = np.r_[0.0, PX[1:] / PX[:-1] - 1]
vol = np.array([r1[max(1, k - 19):k + 1].std() if k >= 21 else np.nan for k in range(N)])
qs = np.nanquantile(vol, np.linspace(0, 1, 11)[1:-1])
VDEC = np.where(np.isnan(vol), -1, np.searchsorted(qs, np.nan_to_num(vol)))

EV = []  # (a＝初一前一交易日, b＝鬼月最後交易日)
for y, (s, e) in GM.items():
    ins = [k for k, d in enumerate(DAYS) if s.isoformat() <= d <= e.isoformat()]
    if ins and ins[0] > 30 and ins[-1] + 11 < N:
        EV.append((ins[0] - 1, ins[-1]))
A = np.array([a for a, _ in EV])
B = np.array([b for _, b in EV])
LEN = int(np.round(np.mean(B - A)))


def win(a, b):
    return PX[b] / PX[a] - 1 - 6.0 / PX[a]


# 每個檢定：(名稱, 進場=錨點+偏移, 出場=錨點+偏移)；錨點 a（鬼月開始前一交易日）、b（鬼月最後交易日）
def windows(a, b):
    return [("GHOST 整個鬼月", a, b), ("PRE 5 鬼月前", a - 5, a), ("FIRST 5", a, a + 5),
            ("LAST 5", b - 5, b), ("AFTER 10 鬼月後", b, b + 10)]


NAMES = [w[0] for w in windows(100, 120)]
CTRL = {}


def ctrl(h):
    if h not in CTRL:
        x = np.array([win(k, k + h) for k in range(30, N - h)])
        dec = VDEC[30:N - h]
        CTRL[h] = {d: x[dec == d].mean() for d in range(10)}
    return CTRL[h]


def evaluate(pairs, mask=None):
    res = [[] for _ in NAMES]
    for a, b in pairs:
        if mask is not None and not mask(a):
            continue
        for j, (_, s, e) in enumerate(windows(a, b)):
            if s < 30 or e >= N:
                continue
            x = win(s, e)
            res[j].append((x, x - ctrl(e - s)[max(VDEC[s], 0)]))
    out = []
    for r in res:
        r = np.array(r)
        out.append((len(r), r[:, 0].mean(), r[:, 1].mean(), (r[:, 0] > 0).mean()))
    return out


pairs = list(zip(A, B))
obs = evaluate(pairs)
s1 = evaluate(pairs, lambda k: DAYS[k] <= "2012-12-31")
s2 = evaluate(pairs, lambda k: DAYS[k] > "2012-12-31")
rng = np.random.default_rng(275)
S = 1000
null = np.zeros((S, len(NAMES)))
for s in range(S):
    off = int(rng.integers(40, 201)) * (1 if rng.random() < 0.5 else -1)
    pp = [(a + off, b + off) for a, b in pairs if 40 < a + off and b + off + 11 < N]
    null[s] = [r[2] for r in evaluate(pp)]
ob = np.array([r[2] for r in obs])
pe = np.array([(np.sum(np.abs(null[:, j]) >= abs(ob[j])) + 1) / (S + 1) for j in range(len(NAMES))])
pmin = np.array([min(np.sum(np.abs(null[:, j]) >= abs(null[s, j])) / S for j in range(len(NAMES))) for s in range(S)])

out = [f"研究 275：鬼月（農曆七月）效應（{len(EV)} 次，{DAYS[A[0]]}～{DAYS[B[-1]]}；鬼月平均 {LEN} 個交易日；做多加權、扣 6 點；同波動度對照；雙尾）", ""]
chk = "、".join(f"{y} 算 {GM[y][0]}／實際 {d}{'✅' if GM[y][0].isoformat() == d else '❌'}" for y, d in KNOWN.items())
out.append(f"日期核對：{chk}")
out.append("")
out.append(f"{'窗格':<16s} | 全期 筆數 每筆 超額 勝率 | 單一p 家族p | 1998–2012 筆 每筆 超額 | 2013～ 筆 每筆 超額")
for j, nm in enumerate(NAMES):
    n, m, e, w = obs[j]
    fam = (np.sum(pmin <= pe[j]) + 1) / (S + 1)
    out.append(f"{nm:<16s} | {n:3d} {m:+6.2%} {e:+6.2%} {w:4.0%} | {pe[j]:.3f} {fam:.3f} | {s1[j][0]:2d} {s1[j][1]:+6.2%} {s1[j][2]:+6.2%} | {s2[j][0]:2d} {s2[j][1]:+6.2%} {s2[j][2]:+6.2%}")
out.append("")
out.append("逐年 整個鬼月（加權，未扣對照）：" + "、".join(f"{DAYS[b][:4]} {win(a, b):+.1%}" for a, b in pairs))
# v3 在鬼月 vs 其他
try:
    import strategy_v3 as V
    import research_138_金字塔加碼與分段停損 as R138
    st = np.array(R138.ST[i0:])
    inside = np.zeros(N, bool)
    for a, b in pairs:
        inside[a + 1:b + 1] = True
    held = np.r_[False, st[:-1] == 1]  # 前一天收盤在場 → 吃今天報酬
    g_in = r1[inside & held]
    g_out = r1[~inside & held & (np.arange(N) > 30)]
    out.append("")
    out.append(f"v3 在場日加權日報酬：鬼月內 {len(g_in)} 天 平均 {g_in.mean():+.3%}／其他 {len(g_out)} 天 平均 {g_out.mean():+.3%}（年化約 {g_in.mean() * 245:+.0%} vs {g_out.mean() * 245:+.0%}）")
    out.append(f"v3 在鬼月內的在場比例 {held[inside].mean():.0%}（全期 {held[30:].mean():.0%}）")
except Exception as ex:  # noqa: BLE001
    out.append(f"v3 比較失敗：{ex}")
txt = "\n".join(out)
print(txt)
open(os.path.join(HERE, "結果_研究275_鬼月效應.txt"), "w", encoding="utf-8").write(txt + "\n")
