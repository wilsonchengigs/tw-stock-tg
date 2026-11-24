"""研究 30：底部爆大量（賣壓竭盡／capitulation）提早進場

使用者想法：現行要等站上 MA60×1.01 才進場，常常比底部晚很多；試著用「底部爆量」抓更早的起漲點。
規則（空手時、每週五判斷；出場規則不變＝MA80×0.975）：
- 爆量日：成交金額 ≥ k × 前 20 日均量，且當天指數距 250 日高點跌超過 d（確認是在「底部區」而不是高檔爆量）
- 近 L 個交易日內出現過爆量日，且本週五收盤站上確認條件 → 提早進場
  確認條件：A 站上 MA(m)；B 收盤高於爆量日收盤；C 收盤高於爆量日後的最低點 ×(1+x)
- 提早進場槓桿：2x 或 1x（1x 版站上正式進場線才加到 2x，同研究 12）
對照：用同樣規則但「不看量」（只看跌深＋站上 MA(m)），確認效果是不是來自量
資料：成交金額用證交所 FMTQIK（backtest/turnover_daily.csv，1997～）；沒有時退回 Yahoo ^TWII 成交量（2003～）
用法：python -X utf8 backtest/research_30_底部爆量.py
"""
import csv
import importlib.util
import itertools
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.argv = [sys.argv[0], os.path.join(HERE, "vixtwn.csv")]
spec = importlib.util.spec_from_file_location("r05", os.path.join(HERE, "research_05_波動濾網.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
bt = R.bt
DAYS, PX, N = bt.DAYS, bt.PX, len(bt.DAYS)
BOUT = 0.025  # 新版出場緩衝
PER = {"全期": ("1998-01-01", "2026-12-31"), "前段": ("1998-01-01", "2012-12-31"), "後段": ("2013-01-01", "2026-12-31")}
M60 = bt.get_sma(60)


def load_volume():
    p = os.path.join(HERE, "turnover_daily.csv")
    if os.path.exists(p):
        m = {r["date"]: float(r["amount"]) for r in csv.DictReader(open(p, encoding="utf-8")) if r["amount"]}
        if len(m) > 6000:
            return [m.get(d) for d in DAYS], "證交所成交金額"
    r = json.load(open(os.path.join(HERE, "TWII.json")))
    tw = timezone(timedelta(hours=8))
    m = {datetime.fromtimestamp(t, tw).strftime("%Y-%m-%d"): v for t, v in zip(r["timestamp"], r["indicators"]["quote"][0]["volume"]) if v}
    return [m.get(d) for d in DAYS], "Yahoo 成交量"


VOL, VSRC = load_volume()
HI250 = [max(PX[max(0, i - 249):i + 1]) for i in range(N)]


def vol_ratio(i, n=20):
    xs = [VOL[k] for k in range(i - n, i) if VOL[k]]
    if VOL[i] is None or len(xs) < n * 0.8:
        return None
    return VOL[i] / (sum(xs) / len(xs))


VR = [vol_ratio(i) if i >= 25 else None for i in range(N)]


def climax_days(k, d):
    return [VR[i] is not None and VR[i] >= k and PX[i] / HI250[i] - 1 <= -d for i in range(N)]


def early(k, d, L, conf, m=20, use_vol=True):
    cd = climax_days(k, d) if use_vol else [PX[i] / HI250[i] - 1 <= -d for i in range(N)]
    ma = bt.get_sma(m)

    def g(i):
        js = [j for j in range(max(0, i - L), i + 1) if cd[j]]
        if not js:
            return False
        j = js[-1]
        if conf == "A":
            return ma[i] is not None and PX[i] > ma[i]
        if conf == "B":
            return PX[i] > PX[j]
        if conf == "C":
            return PX[i] > min(PX[j:i + 1]) * 1.05
        return False
    return g


def lev_fn(lev_early):
    st = {"prev": -99, "full": False}

    def g(i):
        if i - st["prev"] > 7:
            st["full"] = False
        st["prev"] = i
        if PX[i] > M60[i] * 1.01:
            st["full"] = True
        return 2.0 if st["full"] else lev_early
    return g


def kw_of(k, d, L, conf, m, lev, use_vol=True):
    kw = dict(early_entry=early(k, d, L, conf, m, use_vol), bout=BOUT)
    if lev < 2:
        kw["lev_on"] = lev_fn(lev)
    return kw


def evaluate(kw):
    rs = [R.run(a, b, **kw) for a, b in PER.values()]
    rr = R.run(*R.REAL, real=True, **kw)
    return rs, rr


def fmt(rs, rr):
    return " | ".join(R.f(r) for r in rs) + f" | 真實 {R.f(rr)}"


def entry_dates(kw):
    """回傳每次空手→持有的日期（全期）"""
    out, prev = [], False
    sig = {}
    mi = bt.get_sma(60)
    mo = bt.get_sma(80)
    on = False
    for i in range(260, N):
        if bt.WEEK_END[i]:
            if not on:
                go = PX[i] > mi[i] * 1.01 or (kw.get("early_entry") and kw["early_entry"](i))
                if go:
                    on = True
                    out.append(DAYS[i])
            elif PX[i] < mo[i] * (1 - BOUT):
                on = False
    return out


def main():
    L = [f"研究 30：底部爆量提早進場（量的來源：{VSRC}；全期 | 前段 | 後段 | 真實；年化/最大回檔）"]
    base_rs, base_rr = evaluate(dict(bout=BOUT))
    L.append(f"{'現行（出場 MA80x0.975）':40s} {fmt(base_rs, base_rr)}")

    def ok(rs, rr):
        return (all(a["cagr"] >= b["cagr"] - 1e-9 for a, b in zip(rs, base_rs)) and rs[0]["mdd"] > -0.5
                and rr["cagr"] >= base_rr["cagr"] - 1e-9 and rr["mdd"] >= base_rr["mdd"] - 0.03)

    res = []
    grid = list(itertools.product((1.5, 2.0, 2.5), (0.15, 0.20, 0.25), (10, 20), ("A", "B", "C"), (2.0, 1.0)))
    for k, d, Ln, conf, lev in grid:
        m = 20
        kw = kw_of(k, d, Ln, conf, m, lev)
        rs, rr = evaluate(kw)
        res.append(((k, d, Ln, conf, lev), rs, rr, ok(rs, rr)))
    for lev in (2.0, 1.0):
        sub = [x for x in res if x[0][4] == lev]
        L.append(f"\n== 早進 {lev:.0f}x：{len(sub)} 組中三段＋真實都勝現行 {sum(x[3] for x in sub)} 組；全期年化中位 "
                 f"{sorted(x[1][0]['cagr'] for x in sub)[len(sub) // 2]:.1%}、回檔 > 50% 有 {sum(x[1][0]['mdd'] < -0.5 for x in sub)} 組 ==")
        for p, rs, rr, good in sorted(sub, key=lambda x: -x[1][0]["cagr"])[:12]:
            L.append(f"  量≥{p[0]}x 跌≥{p[1]:.0%} {p[2]}日內 確認{p[3]} {'★' if good else ' '} {fmt(rs, rr)}")
    L.append("\n== 對照：不看量（只看跌深＋同樣確認條件），早進 2x ==")
    for d, Ln, conf in itertools.product((0.15, 0.20, 0.25), (10, 20), ("A", "B", "C")):
        rs, rr = evaluate(kw_of(0, d, Ln, conf, 20, 2.0, use_vol=False))
        L.append(f"  跌≥{d:.0%} {Ln}日內 確認{conf}  {fmt(rs, rr)}")
    best = max((x for x in res if x[0][4] == 2.0), key=lambda x: (x[3], x[1][0]["cagr"]))
    p = best[0]
    L.append(f"\n== 代表組 量≥{p[0]}x 跌≥{p[1]:.0%} {p[2]}日內 確認{p[3]}：進場日期比較（2000 年後）==")
    a = entry_dates(dict(bout=BOUT))
    b = entry_dates(kw_of(*p[:4], 20, 2.0))
    L.append("  現行進場：" + "、".join(x for x in a if x >= "2000"))
    L.append("  爆量版進場：" + "、".join(x for x in b if x >= "2000"))
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究30_底部爆量.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
