"""研究 256（使用者 11/26 指定）：事件型做空補測
事件（第 k 天收盤確認，k 收盤放空，抱 H 個交易日收盤回補；持有中不重複觸發）：
  a  v3 跌破出場線（價格出場，非過熱）當天 → 空 5／10 天
  b  v3 融資過熱出場當天 → 空 5／10 天
  c  反彈到 MA20 失敗：前 15 天至少 10 天收在 MA20 下、MA20 比 20 天前低（下彎），昨天收盤 ≥ MA20×0.995、今天收黑 → 空 5／10 天
  d  S&P 前一晚跌 ≥2%、但加權當天跌 <0.5%（撐住）→ 空 1／5 天
空單淨報酬＝−(加權 H 日報酬) − 逆價差 3.9%／年×H/245 − 來回 6 點／價格
對照：同波動度（前 20 日實現波動同十分位）所有日子的同天期空單淨報酬；超額＝事件 − 對照
家族：4 事件 × 2 天期＝8 檢定，事件序列環狀平移 1,000 次（平移 ≥250 天）取最小 p
兩段：1998–2012／2013～
用法：python -X utf8 backtest/research_256_事件型做空.py
"""
import bisect
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strategy_v3 as V  # noqa: E402
import research_138_金字塔加碼與分段停損 as R138  # noqa: E402

bt = V.bt
i0 = next(i for i, d in enumerate(bt.DAYS) if d >= "1998-01-01")
DAYS = bt.DAYS[i0:]
PX = np.array(bt.PX[i0:])
ST = np.array(R138.ST[i0:])
HOT = np.array([V.hot_at(i) for i in range(i0, len(bt.DAYS))])
N = len(DAYS)
CARRY = 0.039 / 245
COST = 6.0

NY = timezone(timedelta(hours=-5))
g = json.load(open(os.path.join(HERE, "GSPC.json")))
SP = [(datetime.fromtimestamp(t, NY).strftime("%Y-%m-%d"), p) for t, p in zip(g["timestamp"], g["indicators"]["quote"][0]["close"]) if p]
SPD, SPP = [d for d, _ in SP], np.array([p for _, p in SP])
spr = {SPD[j]: SPP[j] / SPP[j - 1] - 1 for j in range(1, len(SPD))}
# 台股 k 日之前最後一個美股交易日的報酬
US1 = np.array([spr.get(SPD[bisect.bisect_left(SPD, d) - 1], 0.0) for d in DAYS])

full = np.array(bt.PX)
MA20 = np.array([full[i - 19:i + 1].mean() for i in range(i0, len(bt.DAYS))])
r1 = np.r_[0.0, PX[1:] / PX[:-1] - 1]
vol = np.array([r1[max(1, k - 19):k + 1].std() if k >= 21 else np.nan for k in range(N)])
qs = np.nanquantile(vol, np.linspace(0, 1, 11)[1:-1])
VDEC = np.where(np.isnan(vol), -1, np.searchsorted(qs, np.nan_to_num(vol)))


def short_ret(k, H):
    if k + H >= N:
        return np.nan
    return -(PX[k + H] / PX[k] - 1) - CARRY * H - COST / PX[k]


SR = {H: np.array([short_ret(k, H) for k in range(N)]) for H in (1, 5, 10)}

sig = {}
prev_ok = np.r_[False, ST[:-1] == 1]
exit_day = prev_ok & (ST == 0)
exit_day[:300] = False
sig["a"] = exit_day & ~HOT
sig["b"] = exit_day & HOT
below = PX < MA20
c = np.zeros(N, bool)
for k in range(40, N):
    if below[k - 16:k - 1].sum() >= 10 and MA20[k] < MA20[k - 20] and PX[k - 1] >= MA20[k - 1] * 0.995 and PX[k] < PX[k - 1]:
        c[k] = True
sig["c"] = c
sig["d"] = (US1 <= -0.02) & (r1 > -0.005)

TESTS = [("a", 5), ("a", 10), ("b", 5), ("b", 10), ("c", 5), ("c", 10), ("d", 1), ("d", 5)]
LAB = {"a": "a 跌破出場線當天空", "b": "b 融資過熱出場當天空", "c": "c 反彈 MA20 失敗空", "d": "d 美股大跌台股撐住隔天空"}


def declust(s, H):
    ev, k = [], 0
    idx = np.flatnonzero(s)
    last = -10 ** 9
    for k in idx:
        if k > last + H - 1 and k + H < N:
            ev.append(k)
            last = k
    return np.array(ev, int)


CTRL = {}
for H in (1, 5, 10):
    for dcl in range(10):
        m = (VDEC == dcl) & ~np.isnan(SR[H])
        CTRL[(H, dcl)] = SR[H][m].mean()


def excess(ev, H, mask=None):
    if mask is not None:
        ev = ev[mask[ev]]
    ev = ev[VDEC[ev] >= 0]
    if len(ev) == 0:
        return np.nan, np.nan, 0, np.nan
    x = SR[H][ev]
    cx = np.array([CTRL[(H, VDEC[k])] for k in ev])
    return x.mean(), (x - cx).mean(), len(ev), (x > 0).mean()


seg1 = np.array([d <= "2012-12-31" for d in DAYS])
seg2 = ~seg1
L = ["研究 256：事件型做空（加權指數模擬台指期空單；逆價差 3.9%／年、來回 6 點；同波動度對照）", ""]
L.append(f"{'事件':<22s}{'H':>3s} | {'全期 筆數 每筆 超額 勝率':<30s} | {'1998–2012':<22s} | {'2013～':<22s}")
obs = {}
for key, H in TESTS:
    ev = declust(sig[key], H)
    m, ex, n, w = excess(ev, H)
    obs[(key, H)] = ex
    s1 = excess(ev, H, seg1)
    s2 = excess(ev, H, seg2)
    L.append(f"{LAB[key]:<20s}{H:>3d} | {n:4d} {m:+6.2%} {ex:+6.2%} {w:4.0%} | {s1[2]:3d} {s1[0]:+6.2%} {s1[1]:+6.2%} | {s2[2]:3d} {s2[0]:+6.2%} {s2[1]:+6.2%}")

# 家族檢定：每個事件序列各自環狀平移（同一平移量套用到全部事件，保留事件間相關）
rng = np.random.default_rng(256)
S = int(os.environ.get("R256_SHIFTS", "1000"))
null = np.zeros((S, len(TESTS)))
for s in range(S):
    sh = int(rng.integers(250, N - 250))
    for j, (key, H) in enumerate(TESTS):
        ev = declust(np.roll(sig[key], sh), H)
        null[s, j] = excess(ev, H)[1]
ob = np.array([obs[t] for t in TESTS])
p_each = np.array([(np.sum(null[:, j] >= ob[j]) + 1) / (S + 1) for j in range(len(TESTS))])
pmin_null = np.array([min((np.sum(null[:, j] >= null[s, j])) / S for j in range(len(TESTS))) for s in range(S)])
L.append("")
L.append("單一 p（空單超額 > 平移）／家族 p（最小 p 值法）：")
for j, t in enumerate(TESTS):
    fam = (np.sum(pmin_null <= p_each[j]) + 1) / (S + 1)
    L.append(f"  {LAB[t[0]]} H{t[1]}：超額 {ob[j]:+.2%}、單一 p {p_each[j]:.3f}、家族 p {fam:.3f}")

# d 依 v3 狀態拆
L.append("")
for key, H in (("d", 1), ("d", 5), ("c", 5)):
    ev = declust(sig[key], H)
    on = excess(ev, H, ST == 1)
    off = excess(ev, H, ST == 0)
    L.append(f"{LAB[key]} H{H}：v3 在場 {on[2]} 筆 每筆 {on[0]:+.2%} 超額 {on[1]:+.2%}｜v3 空手 {off[2]} 筆 每筆 {off[0]:+.2%} 超額 {off[1]:+.2%}")
L.append("")
L.append("基準：所有日子放空 H 天的平均淨報酬 " + "、".join(f"H{H} {np.nanmean(SR[H]):+.2%}" for H in (1, 5, 10)))
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究256_事件型做空.txt"), "w", encoding="utf-8").write(out + "\n")
