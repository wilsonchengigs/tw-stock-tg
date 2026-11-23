"""研究 2：雙動能（Dual Momentum / GEM，Antonacci）在台股的版本

規則（依 Antonacci GEM：先做絕對動能、再做相對動能，回顧 12 個月）：
- 絕對動能：台股過去 N 個月報酬 > 同期現金（年 1%）才考慮持有股票，否則持有債券（或現金）
- 相對動能：台股 vs 美股（SPY，未換匯）比過去 N 個月報酬，持有較強者；台股持有用 2x（00631L）
- 防守資產：美國長債（VUSTX）或中期公債（VFITX）；抓不到就用現金
- 週五判斷、隔日收盤成交；N = 6/9/12 個月看鄰近參數穩定度
- 組合版：現行均線策略（MA60+1% 進／MA80-2% 出），出場時改持債券而非現金

外部資料（SPY、VUSTX、VFITX）另存 backtest/ext_*.json（已被 .gitignore 忽略）。
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

TW = timezone(timedelta(hours=8))
PER = {"全期": ("1998-01-01", "2026-12-31"), "前段": ("1998-01-01", "2012-12-31"), "後段": ("2013-01-01", "2026-12-31")}


def ext(sym):
    """回傳 {日期: 調整後收盤}；抓不到回傳 None"""
    path = os.path.join(HERE, f"ext_{sym}.json")
    try:
        if not os.path.exists(path):
            u = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1=0&period2=9999999999&interval=1d&events=div%2Csplit"
            d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read())
            json.dump(d["chart"]["result"][0], open(path, "w"))
        r = json.load(open(path))
    except Exception as e:  # noqa: BLE001
        print(f"抓不到 {sym}：{e}")
        return None
    adj = r["indicators"]["adjclose"][0]["adjclose"]
    return {datetime.fromtimestamp(t, TW).strftime("%Y-%m-%d"): a for t, a in zip(r["timestamp"], adj) if a}


def aligned_returns(series):
    """把外部資產對齊台股交易日（用最近一個已知收盤，台灣時間的日期），回傳每日報酬與價格"""
    if series is None:
        return None, None
    keys = sorted(series)
    px, j, last = [], 0, None
    for d in bt.DAYS:
        while j < len(keys) and keys[j] <= d:
            last = series[keys[j]]
            j += 1
        px.append(last)
    r = [0.0] + [(px[i] / px[i - 1] - 1) if px[i] and px[i - 1] else bt.RC for i in range(1, len(px))]
    return r, px


SPY_R, SPY_P = aligned_returns(ext("SPY"))
LT_R, _ = aligned_returns(ext("VUSTX"))
IT_R, _ = aligned_returns(ext("VFITX"))
M60, M80 = bt.get_sma(60), bt.get_sma(80)
MON = 21  # 一個月 ≈ 21 交易日


def asset_ret(a, i):
    if a == "tw2x":
        return bt.R2[i]
    if a == "spy":
        return SPY_R[i] if SPY_R else bt.RC
    if a == "lt":
        return LT_R[i] if LT_R else bt.RC
    if a == "it":
        return IT_R[i] if IT_R else bt.RC
    return bt.RC


def expo(a):
    return 2.0 if a == "tw2x" else (0.0 if a == "cash" else 1.0)


def run(start, end, choose):
    i0 = next(i for i, d in enumerate(bt.DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(bt.DAYS) if d <= end)
    eq = peak = 1.0
    mdd, pos, pend, n = 0.0, "cash", None, 0
    st = {"on": False}
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + asset_ret(pos, i)
        if pend is not None:
            eq *= 1 - bt.COST * (expo(pos) + expo(pend))  # 賣舊＋買新
            pos, pend, n = pend, None, n + 1
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if bt.WEEK_END[i]:
            t = choose(i, st)
            if t != pos:
                pend = t
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, n / yrs


def tw_mom(i, m):
    k = i - m * MON
    return bt.PX[i] / bt.PX[k] - 1 + 0.03 * m / 12 if k >= 0 else None


def spy_mom(i, m):
    k = i - m * MON
    if not SPY_P or k < 0 or not SPY_P[k] or not SPY_P[i]:
        return None
    return SPY_P[i] / SPY_P[k] - 1


def gem(m, defense="lt", use_spy=True):
    def f(i, s):
        tm = tw_mom(i, m)
        if tm is None:
            return "cash"
        hurdle = 0.01 * m / 12
        sm = spy_mom(i, m) if use_spy else None
        best_eq = max(tm, sm if sm is not None else -9)
        if best_eq <= hurdle:  # 絕對動能不過 → 防守
            return defense
        return "spy" if sm is not None and sm > tm else "tw2x"
    return f


def current(defense="cash"):
    def f(i, s):
        if not s["on"] and bt.PX[i] > M60[i] * 1.01:
            s["on"] = True
        elif s["on"] and bt.PX[i] < M80[i] * 0.98:
            s["on"] = False
        return "tw2x" if s["on"] else defense
    return f


def current_rel(m, defense="cash"):
    """現行均線決定進出；在場時若美股 N 月動能較強改持 SPY"""
    base = current(defense)

    def f(i, s):
        a = base(i, s)
        if a == "tw2x":
            tm, sm = tw_mom(i, m), spy_mom(i, m)
            if tm is not None and sm is not None and sm > tm:
                return "spy"
        return a
    return f


def row(name, fn):
    cells = []
    for p, (a, b) in PER.items():
        c, d, t = run(a, b, fn)
        cells.append(f"{p} {c:5.1%}/{d:6.1%}")
    return f"{name:34s} " + " | ".join(cells) + f" | 年交易 {run(*PER['全期'], fn)[2]:.1f}"


if __name__ == "__main__":
    out = ["格式：年化/最大回檔；台股持有用 2x，美股/債券 1x（未計匯率），週五判斷、隔日收盤成交", ""]
    out.append(f"外部資料：SPY {'有' if SPY_R else '無'}、VUSTX {'有' if LT_R else '無'}、VFITX {'有' if IT_R else '無'}（無則以現金代替）")
    out.append(row("現行（出場持現金）", current("cash")))
    out.append(row("現行（出場持長債）", current("lt")))
    out.append(row("現行（出場持中債）", current("it")))
    out.append("\n— 絕對動能（台股 vs 現金，出場持債）—")
    for m in (6, 9, 12):
        out.append(row(f"台股 {m} 月動能 → 2x／長債", gem(m, "lt", use_spy=False)))
    out.append("\n— GEM 雙動能（台股 2x vs SPY vs 債）—")
    for m in (6, 9, 12):
        for dfn in ("lt", "it", "cash"):
            out.append(row(f"GEM {m} 月，防守={dfn}", gem(m, dfn)))
    out.append("\n— 現行 + 相對動能（在場時美股較強改持 SPY）—")
    for m in (6, 9, 12):
        out.append(row(f"現行+相對 {m} 月，出場長債", current_rel(m, "lt")))
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究02_雙動能.txt"), "w", encoding="utf-8").write(txt)
