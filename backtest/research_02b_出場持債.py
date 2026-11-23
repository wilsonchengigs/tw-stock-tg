"""研究 2 延伸：現行均線策略「出場時改持美國公債」是否真的比持現金好

研究 02 未計匯率時，出場持中債（VFITX）全期 19.4%/-41.5% 看起來比現行 18.0%/-43.8% 好。這裡檢查：
1. 換成台幣報酬（美元兌台幣 FRED DEXTAUS）——台灣投資人實際買的 00679B／00697B 等也是不避險
2. 鄰近參數（進場均線 50/60/70、出場均線 70/80/100、緩衝）看是否穩定
3. 防守資產：現金、中債（VFITX→IEF）、長債（VUSTX→TLT）、半現金半中債
4. 2015-09 之後用 00631L 真實價格 + IEF（台幣）驗證
5. 各年度差異（看好處集中在哪幾年）
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402
import data  # noqa: E402

TW = timezone(timedelta(hours=8))
PER = {"全期": ("1998-01-01", "2026-12-31"), "前段": ("1998-01-01", "2012-12-31"), "後段": ("2013-01-01", "2026-12-31")}


def ext(sym):
    r = json.load(open(os.path.join(HERE, f"ext_{sym}.json")))
    adj = r["indicators"]["adjclose"][0]["adjclose"]
    return {datetime.fromtimestamp(t, TW).strftime("%Y-%m-%d"): a for t, a in zip(r["timestamp"], adj) if a}


def align(series):
    keys, px, j, last = sorted(series), [], 0, None
    for d in bt.DAYS:
        while j < len(keys) and keys[j] <= d:
            last = series[keys[j]]
            j += 1
        px.append(last)
    return px


FX = align(ext("USDTWD"))


def rets(sym, twd=True):
    px = align(ext(sym))
    out = [0.0]
    for i in range(1, len(px)):
        if not px[i] or not px[i - 1]:
            out.append(bt.RC)
            continue
        r = px[i] / px[i - 1]
        if twd:
            r *= FX[i] / FX[i - 1]
        out.append(r - 1)
    return out


A = {
    "cash": [bt.RC] * len(bt.DAYS),
    "it_usd": rets("VFITX", False),
    "it": rets("VFITX"),
    "lt": rets("VUSTX"),
}
A["half_it"] = [(a + b) / 2 for a, b in zip(A["cash"], A["it"])]
EXPO = {"cash": 0.0, "half_it": 0.5}


def run(start, end, ein, eout, bin_=0.01, bout=0.02, defense="cash", r2=None, d_ret=None):
    """現行規則：週五 > MA(ein)×(1+bin) 進 2x；< MA(eout)×(1−bout) 出到 defense；隔日收盤成交"""
    r2 = r2 or bt.R2
    dr = d_ret or A[defense]
    mi, mo = bt.get_sma(ein), bt.get_sma(eout)
    i0 = next(i for i, d in enumerate(bt.DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(bt.DAYS) if d <= end)
    eq = peak = 1.0
    mdd, on, pos, pend = 0.0, False, False, None
    yearly, ystart = {}, (bt.DAYS[i0][:4], 1.0)
    de = EXPO.get(defense, 1.0)
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (r2[i] if pos else dr[i])
        if pend is not None:
            eq *= 1 - bt.COST * (2 + de)
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        y = bt.DAYS[i][:4]
        if y != ystart[0]:
            yearly[ystart[0]] = eq_prev / ystart[1] - 1  # noqa: F821
            ystart = (y, eq_prev)  # noqa: F821
        eq_prev = eq
        if bt.WEEK_END[i] and mi[i] and mo[i]:
            if not on and bt.PX[i] > mi[i] * (1 + bin_):
                on = True
            elif on and bt.PX[i] < mo[i] * (1 - bout):
                on = False
            if on != pos:
                pend = on
    yearly[ystart[0]] = eq / ystart[1] - 1
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, yearly


def cell(**kw):
    return " | ".join(f"{p} {c:5.1%}/{d:6.1%}" for p, (a, b) in PER.items() for c, d, _ in [run(a, b, **kw)])


if __name__ == "__main__":
    out = ["格式：年化/最大回檔；在場 2x（模擬 00631L），出場持防守資產；美國資產換成台幣報酬（除非註明 USD）", ""]
    out.append("== 1. 防守資產比較（現行參數 MA60×1.01 進 / MA80×0.98 出）==")
    names = {"cash": "現金 1%", "it_usd": "中債 VFITX（美元，未計匯率）", "it": "中債 VFITX（台幣）",
             "lt": "長債 VUSTX（台幣）", "half_it": "半現金半中債（台幣）"}
    for k, nm in names.items():
        out.append(f"{nm:24s} {cell(ein=60, eout=80, defense=k)}")

    out.append("\n== 2. 鄰近參數：中債（台幣）減現金 的全期年化差／最大回檔 ==")
    wins = tot = 0
    for ein in (50, 60, 70):
        for eout in (70, 80, 100):
            for bin_, bout in ((0.0, 0.0), (0.01, 0.02), (0.02, 0.03)):
                a = run(*PER["全期"], ein, eout, bin_, bout, "cash")
                b = run(*PER["全期"], ein, eout, bin_, bout, "it")
                tot += 1
                wins += b[0] > a[0]
                out.append(f"MA{ein}+{bin_:.0%} 進 / MA{eout}-{bout:.0%} 出：現金 {a[0]:5.1%}/{a[1]:6.1%}  中債 {b[0]:5.1%}/{b[1]:6.1%}  差 {b[0]-a[0]:+5.1%}")
    out.append(f"中債勝過現金：{wins}/{tot} 組")

    out.append("\n== 3. 各年度報酬（現行參數）：現金 vs 中債（台幣），只列差異 > 2% 的年份 ==")
    yc = run(*PER["全期"], 60, 80, defense="cash")[2]
    yi = run(*PER["全期"], 60, 80, defense="it")[2]
    for y in sorted(yc):
        if abs(yi[y] - yc[y]) > 0.02:
            out.append(f"{y}: 現金 {yc[y]:6.1%}  中債 {yi[y]:6.1%}  差 {yi[y]-yc[y]:+5.1%}")

    out.append("\n== 4. 真實價格 2015-09-01 之後（00631L 調整後收盤；IEF 換台幣）==")
    _, _, l2 = data.series()
    px = [l2.get(d, (None, None))[1] for d in bt.DAYS]
    lp = None
    r2r = [0.0]
    for i in range(1, len(px)):
        if px[i]:
            r2r.append(px[i] / lp - 1 if lp else 0.0)
            lp = px[i]
        else:
            r2r.append(bt.R2[i])
    ief = rets("IEF")
    s, e = "2015-09-01", "2026-12-31"
    for nm, kw in (("現金", dict(defense="cash")), ("中債 IEF（台幣）", dict(defense="it", d_ret=ief)),
                   ("長債 TLT（台幣）", dict(defense="lt", d_ret=rets("TLT")))):
        c, d, _ = run(s, e, 60, 80, r2=r2r, **kw)
        c2, d2, _ = run(s, e, 60, 80, **kw)
        out.append(f"{nm:16s} 真實 {c:5.1%}/{d:6.1%}   模擬 {c2:5.1%}/{d2:6.1%}")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究02b_出場持債.txt"), "w", encoding="utf-8").write(txt)
