"""研究 511：開高等「第二個底比第一個底高」做多／開低等「第二個頭比第一個頭低」做空，及其變形
- 開高／開低：台指期近月日盤開盤 vs 前一日日盤收盤（同研究 510）
- 盤中路徑：加權 1 分 K 2010～2026（09:00～13:30）近似台指期日盤
- 轉折（zigzag）：從低點反彈 ≥ r 確認一個底，從高點回落 ≥ r 確認一個頭。
  r 固定 0.2／0.3／0.5%，或相對波動 0.15／0.25／0.4 × 前 20 天平均日內振幅（ADR20）
- 型態（做多）：開盤後第 1、2 個底 T1、T2，T2 低點 > T1 低點；中間的頭 P＝頸線
  進場 E1：T2 確認那根收盤；E2：T2 之後收盤站上頸線 P（站上前先破 T2 低點則作廢）
- 出場：停損 無／T2 低點／T1 低點；停利 無／1R／2R（R＝進場－T2 低點）；其餘 13:30 收盤出
  同一分鐘同時碰停損、停利，算停損（保守）
- 篩選：跳空門檻 0／0.3／0.5／1%；最晚進場時間 10:30／12:00／13:00；是否要求「開盤後先跌」（第一個轉折是頭）
- 損益以 % 計，成本每筆 3 點（÷ 進場價）；另算「同時刻基準」＝所有交易日從同一分鐘抱到收盤的平均，扣掉它看型態本身
- 樣本內 2010～2017 挑參數、樣本外 2018～2026 驗證；做空的型態把價格上下翻轉，邏輯相同
用法：python -X utf8 backtest/research_511_higher_low.py
"""
import csv, gzip, glob, os, itertools, math, random
from collections import defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
COST_PT = 3.0
SPLIT = "2018-01-01"


def tx_gaps():
    best = {}
    for r in csv.DictReader(open(os.path.join(HERE, "tx_daily_ohlc.csv"), encoding="utf-8")):
        if r["session"] != "day" or r["open"] in ("-", "") or r["close"] in ("-", ""):
            continue
        v = int(r["volume"] or 0)
        if r["date"] not in best or v > best[r["date"]][0]:
            best[r["date"]] = (v, float(r["open"]), float(r["close"]))
    ds = sorted(best)
    return {b: best[b][1] / best[a][2] - 1 for a, b in zip(ds, ds[1:])}


def load_days():
    raw = defaultdict(list)
    for f in sorted(glob.glob(os.path.join(HERE, "taiex_1min", "*.csv.gz"))):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                t = r["time"]
                raw[r["date"]].append((int(t[:2]) * 60 + int(t[3:5]) - 540, float(r["high"]), float(r["low"]), float(r["close"])))
    days = {}
    for d, rows in raw.items():
        a = np.array(rows)
        if len(a) < 200:
            continue
        days[d] = a  # 欄：分鐘(0=09:00), high, low, close
    return days


def drift_table(days):
    """每個分鐘 m（0～270）：所有交易日從 m 收盤抱到當天收盤的平均報酬（%），做多方向"""
    acc = np.zeros(271); n = np.zeros(271)
    for a in days.values():
        mins = a[:, 0].astype(int); c = a[:, 3]
        last = c[-1]
        ok = (mins >= 0) & (mins <= 270)
        acc[mins[ok]] += (last / c[ok] - 1) * 100
        n[mins[ok]] += 1
    return acc / np.maximum(n, 1)


def pivots(h, l, c, r):
    """zigzag。回傳 [(類型 'T'/'P', 極值所在 idx, 極值, 確認 idx)]，從開盤起的中性狀態開始"""
    out = []
    mode = 0; hi = h[0]; hi_i = 0; lo = l[0]; lo_i = 0
    for i in range(len(c)):
        if h[i] > hi:
            hi, hi_i = h[i], i
        if l[i] < lo:
            lo, lo_i = l[i], i
        if mode == 0:
            if c[i] >= lo * (1 + r):
                out.append(("T", lo_i, lo, i)); mode = 1; hi, hi_i = h[i], i
            elif c[i] <= hi * (1 - r):
                out.append(("P", hi_i, hi, i)); mode = -1; lo, lo_i = l[i], i
        elif mode == 1:  # 找頭
            if c[i] <= hi * (1 - r):
                out.append(("P", hi_i, hi, i)); mode = -1; lo, lo_i = l[i], i
        else:  # 找底
            if c[i] >= lo * (1 + r):
                out.append(("T", lo_i, lo, i)); mode = 1; hi, hi_i = h[i], i
    return out


def exits(h, l, c, i0, entry, stop, target):
    """i0 之後逐根檢查；回傳出場價"""
    if i0 + 1 >= len(c):
        return None
    hh = h[i0 + 1:]; ll = l[i0 + 1:]
    js = np.nonzero(ll <= stop)[0] if stop is not None else np.array([], int)
    jt = np.nonzero(hh >= target)[0] if target is not None else np.array([], int)
    s = js[0] if len(js) else 10**9; t = jt[0] if len(jt) else 10**9
    if s == 10**9 and t == 10**9:
        return c[-1]
    return stop if s <= t else target


STOPS = ("無", "T2", "T1")
TARGETS = (None, 1.0, 2.0)


def setups(days, gaps, adr, side, rmode, rval, entry_mode, delay=0):
    """回傳每個型態一筆：dict(day, gap, minute, first_down, pnl{(stop,tgt):%}, base%)"""
    res = []
    for d, a in days.items():
        if d not in gaps or d not in adr:
            continue
        mins = a[:, 0]
        if side > 0:
            h, l, c = a[:, 1], a[:, 2], a[:, 3]
        else:  # 翻轉：做空＝在負價格上找底
            h, l, c = -a[:, 2], -a[:, 1], -a[:, 3]
        r = rval if rmode == "固定" else rval * adr[d]
        # 負價格時 lo*(1+r) 方向會反，改用絕對值的比例
        pv = pivots_abs(h, l, c, r)
        ts = [p for p in pv if p[0] == "T"]
        if len(ts) < 2:
            continue
        T1, T2 = ts[0], ts[1]
        if not T2[2] > T1[2]:
            continue
        peaks = [p for p in pv if p[0] == "P" and T1[3] <= p[3] <= T2[3]]
        if not peaks:
            continue
        P = peaks[-1]
        first_down = pv[0][0] == "P"
        if entry_mode == "E1":
            i0 = T2[3]
        else:
            i0 = None
            for i in range(T2[3] + 1, len(c)):
                if l[i] <= T2[2]:
                    break
                if c[i] > P[2]:
                    i0 = i; break
            if i0 is None:
                continue
        i0 += delay  # 延後幾分鐘進場（測指數成分股報價延遲）
        if i0 >= len(c) - 1:
            continue
        entry = c[i0]
        price = abs(entry)
        out = {}
        for st in STOPS:
            stop = None if st == "無" else (T2[2] if st == "T2" else T1[2])
            for tg in TARGETS:
                if tg is not None and stop is None:
                    risk = entry - T2[2]
                else:
                    risk = entry - stop if stop is not None else None
                target = entry + tg * risk if (tg is not None and risk and risk > 0) else None
                if tg is not None and target is None:
                    continue
                x = exits(h, l, c, i0, entry, stop, target)
                out[(st, tg)] = (x - entry) / price * 100 - COST_PT / price * 100
        res.append(dict(day=d, gap=gaps[d], minute=int(mins[i0]), first_down=first_down, pnl=out))
    return res


def pivots_abs(h, l, c, r):
    """pivots 但門檻用 |價格|×r，讓翻轉後的負價格也適用"""
    out = []
    mode = 0; hi = h[0]; hi_i = 0; lo = l[0]; lo_i = 0
    for i in range(len(c)):
        if h[i] > hi:
            hi, hi_i = h[i], i
        if l[i] < lo:
            lo, lo_i = l[i], i
        th = abs(c[i]) * r
        if mode == 0:
            if c[i] >= lo + th:
                out.append(("T", lo_i, lo, i)); mode = 1; hi, hi_i = h[i], i
            elif c[i] <= hi - th:
                out.append(("P", hi_i, hi, i)); mode = -1; lo, lo_i = l[i], i
        elif mode == 1:
            if c[i] <= hi - th:
                out.append(("P", hi_i, hi, i)); mode = -1; lo, lo_i = l[i], i
        else:
            if c[i] >= lo + th:
                out.append(("T", lo_i, lo, i)); mode = 1; hi, hi_i = h[i], i
    return out


def adr20(days):
    ds = sorted(days)
    rng = {d: (days[d][:, 1].max() - days[d][:, 2].min()) / days[d][0, 3] for d in ds}
    out = {}
    for i in range(20, len(ds)):
        out[ds[i]] = float(np.mean([rng[x] for x in ds[i - 20:i]]))
    return out


def stats(p):
    p = np.asarray(p)
    if len(p) == 0:
        return dict(n=0, win=float("nan"), mean=float("nan"), t=float("nan"))
    sd = p.std(ddof=1) if len(p) > 1 else float("nan")
    return dict(n=len(p), win=(p > 0).mean() * 100, mean=p.mean(), t=p.mean() / (sd / math.sqrt(len(p))) if sd and sd > 0 else float("nan"))


def fmt(s, pts=39000):
    if s["n"] == 0:
        return "   0 筆"
    return f"{s['n']:4d} 筆 勝率 {s['win']:5.1f}% 平均 {s['mean']:+.3f}%（≈{s['mean']/100*pts:+6.0f} 點@39000）t {s['t']:+.2f}"


def main():
    gaps = tx_gaps(); days = load_days(); adr = adr20(days); drift = drift_table(days)
    out = [__doc__]
    R_GRID = [("固定", 0.002), ("固定", 0.003), ("固定", 0.005), ("相對", 0.15), ("相對", 0.25), ("相對", 0.4)]
    GAPS = (0.0, 0.003, 0.005, 0.01)
    CUTS = (90, 180, 240)
    rows = []
    cache = {}
    for side in (1, -1):
        for rm, rv in R_GRID:
            for em in ("E1", "E2"):
                S = setups(days, gaps, adr, side, rm, rv, em)
                cache[(side, rm, rv, em)] = S
                for g, cut, fd in itertools.product(GAPS, CUTS, (False, True)):
                    sel = [s for s in S if s["gap"] * side > g and s["minute"] <= cut and (s["first_down"] or not fd)]
                    oth = [s for s in S if not (s["gap"] * side > 0) and s["minute"] <= cut and (s["first_down"] or not fd)]
                    for key in sel[0]["pnl"] if sel else []:
                        ins = [s["pnl"][key] for s in sel if s["day"] < SPLIT and key in s["pnl"]]
                        oos = [s["pnl"][key] for s in sel if s["day"] >= SPLIT and key in s["pnl"]]
                        ctl = [s["pnl"][key] for s in oth if key in s["pnl"]]
                        rows.append(dict(side=side, r=f"{rm}{rv}", em=em, gap=g, cut=cut, fd=fd, stop=key[0], tgt=key[1],
                                         ins=stats(ins), oos=stats(oos), all=stats(ins + oos), ctl=stats(ctl)))
    # 一、使用者的定義（E1、無停損停利、跳空 >0、不限時間）
    out.append("\n===== 一、使用者定義：第 2 底高於第 1 底（做空：第 2 頭低於第 1 頭），確認那根進場、收盤出 =====")
    for side, name in ((1, "開高做多"), (-1, "開低做空")):
        for rm, rv in R_GRID:
            for g in GAPS:
                rr = [x for x in rows if x["side"] == side and x["r"] == f"{rm}{rv}" and x["em"] == "E1" and x["gap"] == g
                      and x["cut"] == 240 and not x["fd"] and x["stop"] == "無" and x["tgt"] is None][0]
                out.append(f"[{name}] r {rm}{rv} 跳空>{g*100:.1f}%：全期 {fmt(rr['all'])}｜對照(非此跳空日) 平均 {rr['ctl']['mean']:+.3f}%")
    # 二、扣掉同時刻基準（型態本身有沒有東西）
    out.append("\n===== 二、扣掉同時刻基準（所有交易日同一分鐘抱到收盤的平均）=====")
    for side, name in ((1, "開高做多"), (-1, "開低做空")):
        for rm, rv in R_GRID:
            S = cache[(side, rm, rv, "E1")]
            sel = [s for s in S if s["gap"] * side > 0]
            ex = [s["pnl"][("無", None)] - side * drift[min(s["minute"], 270)] for s in sel]
            out.append(f"[{name}] r {rm}{rv}：超額 {fmt(stats(ex))}")
    # 三、全格點：樣本內挑、樣本外驗
    out.append(f"\n===== 三、全格點 {len(rows)} 組（側別×r×進場×跳空×最晚時間×先跌×停損×停利）：樣本內 2010～2017 挑、樣本外 2018～2026 驗 =====")
    for side, name in ((1, "做多"), (-1, "做空")):
        cand = [x for x in rows if x["side"] == side and x["ins"]["n"] >= 80 and x["oos"]["n"] >= 40]
        pos_both = [x for x in cand if x["ins"]["mean"] > 0 and x["oos"]["mean"] > 0]
        out.append(f"\n[{name}] 可評估 {len(cand)} 組；樣本內平均>0：{sum(x['ins']['mean']>0 for x in cand)}；樣本外>0：{sum(x['oos']['mean']>0 for x in cand)}；兩段都>0：{len(pos_both)}")
        top = sorted(cand, key=lambda x: -x["ins"]["mean"])[:10]
        out.append("  樣本內前 10 名 → 樣本外：")
        for x in top:
            out.append(f"  r {x['r']} {x['em']} 跳空>{x['gap']*100:.1f}% ≤{9+x['cut']//60}:{x['cut']%60:02d} 先跌{'是' if x['fd'] else '不限'} 停損{x['stop']} 停利{x['tgt'] or '無'}")
            out.append(f"     樣本內 {fmt(x['ins'])}")
            out.append(f"     樣本外 {fmt(x['oos'])}")
        oo = np.array([x["oos"]["mean"] for x in top])
        out.append(f"  前 10 名樣本外平均 {oo.mean():+.3f}%，>0 的 {int((oo>0).sum())}/10")
        # 樣本內排名 vs 樣本外排名的相關
        a = np.array([x["ins"]["mean"] for x in cand]); b = np.array([x["oos"]["mean"] for x in cand])
        ra = a.argsort().argsort(); rb = b.argsort().argsort()
        out.append(f"  樣本內 vs 樣本外 排名相關 {np.corrcoef(ra, rb)[0,1]:+.2f}（接近 0＝挑到的是運氣）")
    # 四、安慰劑：同樣格點換成隨機日子
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究511_第二底墊高.txt"), "w", encoding="utf-8").write(txt)
    print(txt)
    import pickle
    pickle.dump(dict(rows=rows), open(os.path.join(os.environ.get("TEMP", "."), "r511_rows.pkl"), "wb"))


if __name__ == "__main__":
    main()
