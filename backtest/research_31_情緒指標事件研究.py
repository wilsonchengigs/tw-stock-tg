"""研究 31：情緒／爆量指標的事件研究（統計檢定）

問題：「底部爆量、VIX 飆高、CNN 恐懼貪婪極度恐懼、Put/Call 極高」出現後，台股接下來是否真的比較會漲？
做法（事件研究）：
- 事件：指標進入極端區（門檻用「過去 250 日百分位」，只用當時已知資料；CNN 用固定 25／15／10）
- 去叢集：前一次事件 20 個交易日內的不算新事件（避免同一次恐慌重複計數）
- 前瞻報酬：加權指數 t+1 收盤到 t+1+h 收盤（含 3% 配息），h＝20／60／120 日；事件當天收盤後才知道，所以從隔天算
- 比較基準：同期間所有交易日的前瞻報酬
- 檢定：(1) 事件平均 − 基準平均 的 t 值（事件間不重疊時近似獨立）；(2) 隨機抽同樣數量日期 5000 次的單尾 p 值（拔靴）
  (3) 全部檢定做 Benjamini–Hochberg 多重比較校正（FDR 10%）
- 另做「策略空手時」版本：只看現行策略空手期間的事件，對照空手期間的隨機日（這才是提早進場要的資訊）
資料：證交所成交金額（turnover_daily.csv）、美國 ^VIX（Yahoo）、台指 VIX（vixtwn.csv）、CNN 恐懼貪婪（whit3rabbit/fear-greed-data 整理，2021 前精確度有疑慮）、
CBOE Total P/C（2006-11～2019-10）、期交所台指選擇權 P/C（pcratio_daily.csv）
美國指標用「前一晚」的值（台股收盤時美股還沒開）
用法：python -X utf8 backtest/research_31_情緒指標事件研究.py
"""
import bisect
import csv
import json
import math
import os
import random
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

DAYS, PX, N = bt.DAYS, bt.PX, len(bt.DAYS)
TR = [1.0]
for i in range(1, N):
    TR.append(TR[-1] * (1 + bt.R1[i]))
HS = (20, 60, 120)
NY = timezone(timedelta(hours=-5))


def fwd(i, h):
    if i + 1 + h >= N:
        return None
    return TR[i + 1 + h] / TR[i + 1] - 1


def align_us(series):
    """美國資料 {date: v} → 每個台股日取「嚴格早於當天」的最後一筆"""
    ks = sorted(series)
    out = []
    for d in DAYS:
        k = bisect.bisect_left(ks, d) - 1
        out.append(series[ks[k]] if k >= 0 else None)
    return out


def align_tw(series):
    return [series.get(d) for d in DAYS]


def pct_rank(arr, i, n=250):
    xs = [arr[k] for k in range(max(0, i - n), i) if arr[k] is not None]
    if arr[i] is None or len(xs) < n * 0.6:
        return None
    return sum(1 for x in xs if x < arr[i]) / len(xs)


def load():
    S = {}
    p = os.path.join(HERE, "turnover_daily.csv")
    if os.path.exists(p):
        S["amount"] = align_tw({r["date"]: float(r["amount"]) for r in csv.DictReader(open(p, encoding="utf-8")) if r["amount"]})
    r = json.load(open(os.path.join(HERE, "VIX.json")))
    S["us_vix"] = align_us({datetime.fromtimestamp(t, NY).strftime("%Y-%m-%d"): c for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c})
    S["tw_vix"] = align_tw({r["date"]: float(r["vix"]) for r in csv.DictReader(open(os.path.join(HERE, "vixtwn.csv"), encoding="utf-8")) if r["vix"]})
    fng = {}
    for r in csv.DictReader(open(os.path.join(HERE, "fng_whit3rabbit.csv"), encoding="utf-8")):
        try:
            fng[r["Date"]] = float(r["Fear Greed"])
        except ValueError:
            pass
    S["cnn_fng"] = align_us(fng)
    pc = {}
    for r in csv.reader(open(os.path.join(HERE, "cboe_totalpc.csv"), encoding="utf-8")):
        try:
            d = datetime.strptime(r[0].strip(), "%m/%d/%Y").strftime("%Y-%m-%d")
            pc[d] = float(r[4])
        except (ValueError, IndexError):
            pass
    S["cboe_pc"] = align_us(pc)
    p = os.path.join(HERE, "pcratio_daily.csv")
    if os.path.exists(p):
        rows = list(csv.DictReader(open(p, encoding="utf-8")))
        S["tw_pc_oi"] = align_tw({r["date"]: float(r["oi_ratio"]) for r in rows if r["oi_ratio"]})
        S["tw_pc_vol"] = align_tw({r["date"]: float(r["vol_ratio"]) for r in rows if r["vol_ratio"]})
    return S


def strategy_off():
    m60, m80 = bt.get_sma(60), bt.get_sma(80)
    st, out = False, []
    for i in range(N):
        if bt.WEEK_END[i] and i >= 260:
            st = (not PX[i] < m80[i] * 0.975) if st else (PX[i] > m60[i] * 1.01)
        out.append(not st)
    return out


def decluster(flags, gap=20):
    out, last = [], -10 ** 9
    for i, f in enumerate(flags):
        if f and i - last > gap:
            out.append(i)
        if f:
            last = i
    return out


def tstat(xs, base_mean):
    n = len(xs)
    if n < 3:
        return None
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    return (m - base_mean) / (sd / math.sqrt(n)) if sd > 0 else None


def boot_p(obs_mean, pool, n, rng, it=3000):
    if n < 3 or not pool:
        return None
    hit = 0
    for _ in range(it):
        s = [pool[rng.randrange(len(pool))] for _ in range(n)]
        if sum(s) / n >= obs_mean:
            hit += 1
    return (hit + 1) / (it + 1)


def bh(ps, q=0.10):
    """Benjamini–Hochberg：回傳通過的索引集合"""
    idx = sorted((p, k) for k, p in enumerate(ps) if p is not None)
    m = len(idx)
    ok = set()
    cut = 0
    for r, (p, k) in enumerate(idx, 1):
        if p <= q * r / m:
            cut = r
    for r, (p, k) in enumerate(idx, 1):
        if r <= cut:
            ok.add(k)
    return ok


def main():
    S = load()
    off = strategy_off()
    hi250 = [max(PX[max(0, i - 249):i + 1]) for i in range(N)]
    dd = [PX[i] / hi250[i] - 1 for i in range(N)]
    pr = {k: [pct_rank(v, i) if i >= 150 else None for i in range(N)] for k, v in S.items() if k not in ("cnn_fng",)}
    vr = [None] * N
    if "amount" in S:
        a = S["amount"]
        for i in range(25, N):
            xs = [a[k] for k in range(i - 20, i) if a[k]]
            if a[i] and len(xs) >= 16:
                vr[i] = a[i] / (sum(xs) / len(xs))
    sigs = []
    if "amount" in S:
        for k_, d_ in ((1.5, 0.15), (2.0, 0.15), (2.0, 0.20), (2.5, 0.15)):
            sigs.append((f"爆量 ≥{k_}x 均量 且 跌≥{d_:.0%}", [vr[i] is not None and vr[i] >= k_ and dd[i] <= -d_ for i in range(N)]))
        sigs.append(("爆量 ≥2x 均量（不限跌幅）", [vr[i] is not None and vr[i] >= 2.0 for i in range(N)]))
    for nm, key in (("美國 VIX", "us_vix"), ("台指 VIX", "tw_vix"), ("CBOE P/C", "cboe_pc"), ("台指選 P/C 未平倉", "tw_pc_oi"), ("台指選 P/C 成交量", "tw_pc_vol")):
        if key not in S:
            continue
        for q in (0.90, 0.95, 0.99):
            sigs.append((f"{nm} > 過去 250 日 {q:.0%} 分位", [pr[key][i] is not None and pr[key][i] >= q for i in range(N)]))
    for nm, key in (("台指選 P/C 未平倉", "tw_pc_oi"),):
        if key in S:
            sigs.append((f"{nm} < 過去 250 日 5% 分位（過度樂觀）", [pr[key][i] is not None and pr[key][i] <= 0.05 for i in range(N)]))
    for th in (25, 15, 10):
        f = S["cnn_fng"]
        sigs.append((f"CNN 恐懼貪婪 < {th}", [f[i] is not None and f[i] < th for i in range(N)]))
    sigs.append(("CNN 恐懼貪婪 > 80（極度貪婪）", [S["cnn_fng"][i] is not None and S["cnn_fng"][i] > 80 for i in range(N)]))
    for d_ in (0.15, 0.20, 0.25):
        sigs.append((f"對照：只看跌≥{d_:.0%}（不看情緒／量）", [dd[i] <= -d_ for i in range(N)]))

    rng = random.Random(1)
    rows, pvals = [], []
    for nm, flags in sigs:
        valid = [i for i in range(260, N) if flags[i] is not None]
        first = next((i for i in range(N) if flags[i]), None)
        ev = decluster(flags)
        for scope in ("全部", "空手時"):
            evs = [i for i in ev if i >= 260 and (scope == "全部" or off[i])]
            span = [i for i in range(max(260, first or 260), N) if scope == "全部" or off[i]]
            for h in HS:
                xs = [fwd(i, h) for i in evs if fwd(i, h) is not None]
                pool = [fwd(i, h) for i in span if fwd(i, h) is not None]
                if len(xs) < 3 or not pool:
                    rows.append((nm, scope, h, len(xs), None, None, None, None, None))
                    pvals.append(None)
                    continue
                m = sum(xs) / len(xs)
                bm = sum(pool) / len(pool)
                hit = sum(x > 0 for x in xs) / len(xs)
                bhit = sum(x > 0 for x in pool) / len(pool)
                t = tstat(xs, bm)
                p = boot_p(m, pool, len(xs), rng)
                rows.append((nm, scope, h, len(xs), m, bm, hit, bhit, (t, p)))
                pvals.append(p)
    ok = bh(pvals, 0.10)
    L = ["研究 31：情緒／爆量指標事件研究（前瞻報酬＝加權含息，事件隔天收盤起算；事件去叢集 20 日）",
         "欄位：訊號 | 範圍 | 天期 | 事件數 | 事件平均 vs 基準平均 | 上漲機率 vs 基準 | t 值 | 拔靴 p | BH 校正後顯著（FDR 10%）",
         "注意：120 日報酬彼此高度重疊，事件數少時 t 值與 p 值偏樂觀；空手時的基準＝策略空手期間所有交易日"]
    last = None
    for k, (nm, scope, h, n, m, bm, hit, bhit, tp) in enumerate(rows):
        if nm != last:
            L.append(f"\n【{nm}】")
            last = nm
        if m is None:
            L.append(f"  {scope} {h:3d}日 事件 {n}（太少）")
            continue
        t, p = tp
        L.append(f"  {scope} {h:3d}日 事件 {n:3d} | {m:+6.1%} vs {bm:+6.1%} | {hit:4.0%} vs {bhit:4.0%} | t {t if t is None else round(t, 2)} | p {p:.3f} | {'✔' if k in ok else ''}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究31_情緒指標事件研究.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
