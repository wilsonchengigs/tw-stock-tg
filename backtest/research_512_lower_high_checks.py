"""研究 512：研究 511 候選（開低、第二個頭比第一個頭低、跌破頸線做空）的檢查
一、跟簡單做法比：開低日 09:00 直接空到收盤；開低日在同一分鐘直接空（不看型態）；所有日子同一分鐘空
二、家族檢定：把「跳空」序列環狀平移 500 次（型態與日內路徑不動），重算整個格點的最大 t 值／樣本內挑出來那組的樣本外平均，看真實值排第幾
三、候選的逐年、成本敏感度、星期、進場時段
四、近 32 天真實台指期 1 分 K 抽驗
用法：python -X utf8 backtest/research_512_lower_high_checks.py
"""
import os, sys, math, itertools
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import research_511_higher_low as R

HERE = os.path.dirname(os.path.abspath(__file__))
SPLIT = R.SPLIT
R_GRID = [("固定", 0.002), ("固定", 0.003), ("固定", 0.005), ("相對", 0.15), ("相對", 0.25), ("相對", 0.4)]
GAPS = (0.0, 0.003, 0.005, 0.01); CUTS = (90, 180, 240)
KEYS = [(s, t) for s in R.STOPS for t in R.TARGETS]
CAND = dict(side=-1, rm="相對", rv=0.25, em="E2", gap=0.003, cut=180, key=("無", None))


def st(p):
    return R.fmt(R.stats(p))


def build(days, gaps, adr):
    """每個 (side,r,em) 的型態陣列，給家族檢定用"""
    out = {}
    for side in (1, -1):
        for rm, rv in R_GRID:
            for em in ("E1", "E2"):
                S = R.setups(days, gaps, adr, side, rm, rv, em)
                d = np.array([s["day"] for s in S]); mi = np.array([s["minute"] for s in S]); fd = np.array([s["first_down"] for s in S])
                P = np.full((len(S), len(KEYS)), np.nan)
                for i, s in enumerate(S):
                    for j, k in enumerate(KEYS):
                        if k in s["pnl"]:
                            P[i, j] = s["pnl"][k]
                out[(side, rm, rv, em)] = (d, mi, fd, P)
    return out


def family(cache, gapfun, side):
    """回傳 (全期最大 t, 樣本內第一名的樣本外平均)"""
    best_t = -9; best_ins = -9; best_oos = np.nan
    for (sd, rm, rv, em), (d, mi, fd, P) in cache.items():
        if sd != side:
            continue
        g = gapfun(d) * side
        ins = d < SPLIT
        for gt, cut, f in itertools.product(GAPS, CUTS, (False, True)):
            m = (g > gt) & (mi <= cut) & (fd | (not f))
            for j in range(len(KEYS)):
                v = P[m, j]; ok = ~np.isnan(v); v = v[ok]; vi = ins[m][ok]
                if (vi).sum() < 80 or (~vi).sum() < 40:
                    continue
                t = v.mean() / (v.std(ddof=1) / math.sqrt(len(v)))
                best_t = max(best_t, t)
                mi_ = v[vi].mean()
                if mi_ > best_ins:
                    best_ins, best_oos = mi_, v[~vi].mean()
    return best_t, best_oos


def main():
    gaps = R.tx_gaps(); days = R.load_days(); adr = R.adr20(days); drift = R.drift_table(days)
    out = [__doc__]
    c = CAND
    S = R.setups(days, gaps, adr, c["side"], c["rm"], c["rv"], c["em"])
    sel = [s for s in S if -s["gap"] > c["gap"] and s["minute"] <= c["cut"]]
    p = np.array([s["pnl"][c["key"]] for s in sel])
    ds = sorted(days)
    gd_days = [d for d in ds if d in gaps and -gaps[d] > c["gap"]]
    out.append(f"候選：開低 >{c['gap']*100:.1f}%、轉折 0.25×ADR20、第 2 頭低於第 1 頭、收盤跌破頸線做空、12:00 前進場、收盤出")
    out.append(f"\n===== 一、跟簡單做法比 =====")
    out.append(f"候選                         ：{st(p)}")
    # 開低日 09:00 收盤空到收盤
    def short_from(d, m):
        a = days[d]; i = np.searchsorted(a[:, 0], m)
        if i >= len(a) - 1:
            return None
        e = a[i, 3]; return (e - a[-1, 3]) / e * 100 - R.COST_PT / e * 100
    b1 = [short_from(d, 0) for d in gd_days]; b1 = [x for x in b1 if x is not None]
    out.append(f"開低日 09:00 直接空到收盤     ：{st(b1)}")
    # 同一天、同一分鐘，但不看型態：所有開低日在候選的進場分鐘分布中隨機抽一分鐘
    rng = np.random.default_rng(0); mins = [s["minute"] for s in sel]
    b2 = []
    for _ in range(20):
        for d in gd_days:
            x = short_from(d, int(rng.choice(mins)))
            if x is not None:
                b2.append(x)
    out.append(f"開低日 隨機同時段空（×20）    ：{st(b2)}")
    ex_all = p - np.array([-drift[s["minute"]] for s in sel])
    out.append(f"候選 扣「所有日子同一分鐘空」：{st(ex_all)}")
    # 開低日同一分鐘的平均
    gd_drift = np.zeros(271); n = np.zeros(271)
    for d in gd_days:
        a = days[d]; m = a[:, 0].astype(int); ok = (m >= 0) & (m <= 270)
        gd_drift[m[ok]] += (a[-1, 3] / a[ok, 3] - 1) * 100; n[m[ok]] += 1
    gd_drift /= np.maximum(n, 1)
    ex_gd = p - np.array([-gd_drift[s["minute"]] for s in sel])
    out.append(f"候選 扣「開低日同一分鐘空」  ：{st(ex_gd)}")
    for lab, m in (("樣本內 2010～2017", np.array([s["day"] < SPLIT for s in sel])), ("樣本外 2018～2026", np.array([s["day"] >= SPLIT for s in sel]))):
        out.append(f"  {lab}：候選 {st(p[m])}｜扣開低日同分鐘 {st(ex_gd[m])}")

    out.append("\n===== 三、逐年／成本／星期／進場時段 =====")
    yrs = sorted({s["day"][:4] for s in sel})
    for y in yrs:
        m = np.array([s["day"][:4] == y for s in sel])
        out.append(f"{y}：{st(p[m])}")
    for cost in (3, 5, 8):
        pc = np.array([s["pnl"][c["key"]] + R.COST_PT / days[s["day"]][0, 3] * 100 - cost / days[s["day"]][0, 3] * 100 for s in sel])
        out.append(f"成本 {cost} 點：{st(pc)}")
    import datetime as dt
    for wd in range(5):
        m = np.array([dt.date.fromisoformat(s["day"]).weekday() == wd for s in sel])
        out.append(f"星期{'一二三四五'[wd]}：{st(p[m])}")
    for lo, hi in ((0, 30), (30, 60), (60, 120), (120, 180)):
        m = np.array([lo <= s["minute"] < hi for s in sel])
        out.append(f"進場 {9+lo//60}:{lo%60:02d}～{9+hi//60}:{hi%60:02d}：{st(p[m])}")
    # 鄰近參數
    out.append("\n鄰近參數（全期，收盤出）：")
    for rv in (0.2, 0.25, 0.3, 0.35):
        S2 = R.setups(days, gaps, adr, -1, "相對", rv, "E2")
        for g in (0.0, 0.002, 0.003, 0.005):
            for cut in (90, 180, 240):
                v = [s["pnl"][("無", None)] for s in S2 if -s["gap"] > g and s["minute"] <= cut]
                out.append(f"  r {rv}×ADR 跳空<-{g*100:.1f}% ≤{9+cut//60}:{cut%60:02d}：{st(v)}")

    out.append("\n===== 二、家族檢定（跳空序列環狀平移 500 次，型態不動）=====")
    cache = build(days, gaps, adr)
    gd = sorted(gaps); garr = np.array([gaps[d] for d in gd]); idx = {d: i for i, d in enumerate(gd)}
    for side, name in ((-1, "做空"), (1, "做多")):
        real = family(cache, lambda d: garr[[idx[x] for x in d]], side)
        sims = []
        rng = np.random.default_rng(1)
        for k in rng.integers(50, len(gd) - 50, 500):
            sh = np.roll(garr, k)
            sims.append(family(cache, lambda d: sh[[idx[x] for x in d]], side))
        sims = np.array(sims)
        p_t = (sims[:, 0] >= real[0]).mean(); p_o = (sims[:, 1] >= real[1]).mean()
        out.append(f"[{name}] 真實：格點最大 t {real[0]:.2f}（平移中 ≥ 此值的比例 p={p_t:.3f}）；樣本內第一名的樣本外平均 {real[1]:+.3f}%（p={p_o:.3f}）")
        out.append(f"        平移分布：最大 t 中位 {np.median(sims[:,0]):.2f}、95% {np.percentile(sims[:,0],95):.2f}；樣本外平均 中位 {np.nanmedian(sims[:,1]):+.3f}%、95% {np.nanpercentile(sims[:,1],95):+.3f}%")

    out.append("\n===== 四、近 32 天真實台指期 1 分 K =====")
    tx = R.load_days.__globals__["np"]  # 佔位避免未用
    import csv
    from collections import defaultdict
    raw = defaultdict(list)
    for r in csv.DictReader(open(os.path.join(HERE, "tx_1min.csv"), encoding="utf-8")):
        if r["session"] == "day":
            t = r["ts"][-5:]
            raw[r["trade_day"]].append((int(t[:2]) * 60 + int(t[3:5]) - 540, float(r["high"]), float(r["low"]), float(r["close"])))
    txd = {d: np.array(v) for d, v in raw.items()}
    adr_tx = {d: adr.get(d, 0.015) for d in txd}
    S3 = R.setups(txd, gaps, adr_tx, -1, "相對", 0.25, "E2")
    v = [s["pnl"][("無", None)] for s in S3 if -s["gap"] > 0.003 and s["minute"] <= 180]
    gdn = sum(1 for d in txd if d in gaps and -gaps[d] > 0.003)
    out.append(f"開低 >0.3% 的日子 {gdn} 天，出現型態並進場：{st(v)}")

    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究512_第二頭壓低檢查.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
