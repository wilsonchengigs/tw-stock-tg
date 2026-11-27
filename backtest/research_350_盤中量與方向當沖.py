"""研究 350：盤中「量 × 方向」當沖勝率（加權 1 分 K ＋ 證交所盤中累積成交金額，2010～2026）

接研究 279（開盤前已知的量×方向無效）。台指期 1 分 K 只有 32 天，改用：
- 價格：taiex_1min（加權指數 1 分 K）；當作台指期日盤的近似（盤中基差變動小；開盤前幾分鐘有成分股未成交假象，見研究 244／403）
- 量：twse_5mins（build_twse_5mins.py，MI_5MINS 累積成交金額、委買／委賣量）
交易：訊號出現的那分鐘收盤進，13:25 收盤出（13:25～13:30 是收盤集合競價），每筆成本 3 點（換算成指數 %）

A. 開盤一段時間的量 × 方向：視窗 W＝09:00→09:15／09:30／10:00
   量比＝W 結束時的累積成交金額 ÷ 前 20 天同一時間累積成交金額平均
   方向：(1) 09:05 → W 結束（避開開盤假象）(2) 昨收 → W 結束（含跳空）(3) 委買量 vs 委賣量（W 期間新增，買多＝+）
   規則：量比 ≥ k（1.2／1.5／2.0）且 |方向| ≥ 門檻 → 順勢（逆勢＝相反）
B. 盤中爆量 5 分鐘（馬克羊「爆量順著 K 棒」的長樣本版）：09:30～12:55 間，5 分鐘成交金額 ≥ k（2／3／5）倍
   前 20 天同時段中位數，且這 5 分鐘漲跌 |r| ≥ 0.1%；每天只取第一個；順勢／逆勢
檢定：環狀平移「條件序列」（以天為單位）400 次、單組 p 與最小 p 值法家族 p；前段 2010–2017、後段 2018–2026；逐年
用法：python -X utf8 backtest/research_280_盤中量與方向當沖.py
"""
import csv
import gzip
import io
import os
import random
import statistics
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
COST_PTS = 3.0
NSHIFT = 400
EXIT = "13:24"  # 這根收盤＝13:25
random.seed(350)


def mins(t):
    return int(t[:2]) * 60 + int(t[3:5])


def hm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def load():
    px = defaultdict(dict)
    for f in sorted(os.listdir(os.path.join(HERE, "taiex_1min"))):
        if f.endswith(".csv.gz"):
            for r in csv.DictReader(io.TextIOWrapper(gzip.open(os.path.join(HERE, "taiex_1min", f)), encoding="utf-8")):
                px[r["date"]][r["time"]] = float(r["close"])
    vo = defaultdict(dict)
    for f in sorted(os.listdir(os.path.join(HERE, "twse_5mins"))):
        if f.endswith(".csv.gz"):
            for r in csv.DictReader(io.TextIOWrapper(gzip.open(os.path.join(HERE, "twse_5mins", f)), encoding="utf-8")):
                vo[r["date"]][r["time"]] = (float(r["amt"]), float(r["buy_qty"]), float(r["sell_qty"]))
    days = sorted(d for d in px if d in vo and EXIT in px[d] and "09:05" in px[d])
    return days, px, vo


def cum_at(v, t):
    """t 分鐘結束時的累積值；缺就往前找"""
    m = mins(t)
    for k in range(m, m - 6, -1):
        if hm(k) in v:
            return v[hm(k)]
    return None


def build(days, px, vo):
    prev_close = {}
    for a, b in zip(days, days[1:]):
        p = px[a]
        prev_close[b] = p.get("13:30") or p[EXIT]
    W = ("09:14", "09:29", "09:59")   # 這根收盤＝09:15／09:30／10:00
    feats = []
    hist = defaultdict(list)  # (W) -> 前幾天累積金額
    slot_hist = []            # 每天 5 分鐘金額 dict
    for d in days:
        p, v = px[d], vo[d]
        f = {"d": d, "exit": p[EXIT]}
        for w in W:
            cw = cum_at(v, w)
            pw = p.get(w)
            h = hist[w][-20:]
            if cw and pw and len(h) >= 16 and d in prev_close:
                f[w] = {
                    "vr": cw[0] / statistics.mean(h),
                    "dir_in": pw / p["09:05"] - 1,
                    "dir_gap": pw / prev_close[d] - 1,
                    "ob": (cw[1] - cw[2]) / (cw[1] + cw[2]) if cw[1] + cw[2] else 0,
                    "entry": pw,
                }
            if cw:
                hist[w].append(cw[0])
        # 5 分鐘金額
        amt5 = {}
        for m in range(mins("09:30"), mins("12:56")):
            a1, a0 = cum_at(v, hm(m)), cum_at(v, hm(m - 5))
            if a1 and a0 and hm(m) in p and hm(m - 5) in p:
                amt5[hm(m)] = (a1[0] - a0[0], p[hm(m)] / p[hm(m - 5)] - 1, p[hm(m)])
        if len(slot_hist) >= 16:
            base = {}
            for t in amt5:
                xs = [s[t][0] for s in slot_hist[-20:] if t in s]
                if len(xs) >= 12:
                    base[t] = statistics.median(xs)
            for k in (0, 1, 2, 3, 5):  # 0／1＝對照（不看量／只要不低於平常）
                for t in sorted(amt5):
                    a, r, pr = amt5[t]
                    if t in base and base[t] > 0 and a >= k * base[t] and abs(r) >= 0.001:
                        f[f"spike{k}"] = {"dir": r, "entry": pr, "t": t}
                        break
        slot_hist.append({t: (x[0],) for t, x in amt5.items()})
        feats.append(f)
    return feats


def specs_all():
    S = []
    for w, wn in (("09:14", "09:15"), ("09:29", "09:30"), ("09:59", "10:00")):
        for dk, dn, th in (("dir_in", "09:05起", 0.0), ("dir_in", "09:05起≥0.3%", 0.003),
                           ("dir_gap", "昨收起", 0.0), ("dir_gap", "昨收起≥0.5%", 0.005), ("ob", "委買賣", 0.0)):
            for k in (1.2, 1.5, 2.0):
                S.append((f"開盤到{wn}", w, dk, dn, th, k))
    for k in (2, 3, 5):
        S.append(("盤中爆量5分", f"spike{k}", "dir", "5分K", 0.0, k))
    return S


def signal(feats, sp):
    _, key, dk, _, th, k = sp
    sig, ent = [], []
    for f in feats:
        x = f.get(key)
        if x is None or (not key.startswith("spike") and x["vr"] < k) or abs(x[dk]) < th or x[dk] == 0:
            sig.append(0)
            ent.append(None)
        else:
            sig.append(1 if x[dk] > 0 else -1)
            ent.append(x["entry"])
    return sig, ent


def main():
    days, px, vo = load()
    feats = build(days, px, vo)
    L = ["研究 350：盤中量 × 方向當沖（加權 1 分 K ＋ 證交所盤中累積成交金額；訊號那分鐘收盤進、13:25 出；每筆成本 3 點）",
         f"交易日 {len(feats)}（{feats[0]['d']}～{feats[-1]['d']}）"]
    S = specs_all()
    # 每個規則的「做多報酬」序列（以該規則的進場價）
    rows = []
    for sp in S:
        sig, ent = signal(feats, sp)
        rets = [(f["exit"] / e - 1) if e else 0.0 for f, e in zip(feats, ent)]
        cost = [COST_PTS / e if e else 0.0 for e in ent]
        rows.append((sp, sig, rets, cost))
    # 基準：每天 09:30 做多到 13:25
    base = [f["exit"] / px[f["d"]]["09:29"] - 1 for f in feats if "09:29" in px[f["d"]]]
    L.append(f"基準：每天 09:30 做多到 13:25 平均 {statistics.mean(base)*100:+.3f}%、上漲比例 {sum(1 for x in base if x>0)/len(base)*100:.0f}%")
    L.append("\n規則：量比 ≥ k 且方向成立 → 順勢當沖；每筆％已扣成本；p＝環狀平移條件序列 400 次（順勢看 ≥、逆勢看 ≤）")
    L.append(f"{'視窗':<12}{'方向':<12}{'k':>4}{'筆數':>6}{'順勝率':>7}{'順每筆%':>9}{'逆每筆%':>9}{'p順':>6}{'p逆':>6}{'前段順%':>9}{'後段順%':>9}")
    n = len(feats)
    real, perm = [], []
    pf, pr = [], []
    for sp, sig, rets, cost in rows:
        # 平移時，訊號（方向）與進場價綁在一起移到別天，但出場用該天價格 → 用「進場時點的報酬」近似：
        # 以訊號日 d 的 rets[d]（從該天同一時點進場）當目標；平移後的方向乘上目標天的「同規則」報酬，
        # 目標天若本身沒有該時點報酬，改用 09:30→13:25 報酬
        t0 = sp[1] if not sp[1].startswith("spike") else "09:29"
        tgt = [rets[i] if sig[i] else (feats[i]["exit"] / px[feats[i]["d"]].get(t0, feats[i]["exit"]) - 1) for i in range(n)]
        m_real = sum(s * t for s, t in zip(sig, tgt)) / max(1, sum(1 for s in sig if s))
        sh_means = []
        for _ in range(NSHIFT):
            sh = random.randint(30, n - 30)
            ss = sig[sh:] + sig[:sh]
            sh_means.append(sum(s * t for s, t in zip(ss, tgt)) / max(1, sum(1 for s in ss if s)))
        real.append(m_real)
        perm.append(sh_means)
        p_f = sum(1 for x in sh_means if x >= m_real) / NSHIFT
        p_r = sum(1 for x in sh_means if x <= m_real) / NSHIFT
        pf.append(p_f)
        pr.append(p_r)
        fol = [s * r - c for s, r, c in zip(sig, rets, cost) if s]
        rev = [-s * r - c for s, r, c in zip(sig, rets, cost) if s]
        ear = [s * r - c for s, r, c, f in zip(sig, rets, cost, feats) if s and f["d"] < "2018"]
        lat = [s * r - c for s, r, c, f in zip(sig, rets, cost, feats) if s and f["d"] >= "2018"]
        mm = lambda xs: statistics.mean(xs) * 100 if xs else 0.0  # noqa: E731
        win = sum(1 for x in fol if x > 0) / len(fol) * 100 if fol else 0
        L.append(f"{sp[0]:<12}{sp[3]:<12}{sp[5]:>4}{len(fol):>6}{win:>6.0f}%{mm(fol):>+9.3f}{mm(rev):>+9.3f}{p_f:>6.2f}{p_r:>6.2f}"
                 f"{mm(ear):>+9.3f}{mm(lat):>+9.3f}")

    def fam(pp, side):
        rp = min(pp)
        mins_ = []
        for t in range(NSHIFT):
            mp = 1.0
            for j in range(len(S)):
                x = perm[j][t]
                c = sum(1 for y in perm[j] if (y >= x if side > 0 else y <= x)) / NSHIFT
                mp = min(mp, c)
            mins_.append(mp)
        return rp, sum(1 for m in mins_ if m <= rp) / NSHIFT
    for pp, side, nm in ((pf, 1, "順勢"), (pr, -1, "逆勢")):
        rp, fp = fam(pp, side)
        best = S[pp.index(rp)]
        L.append(f"家族（{len(S)} 組）{nm}：最小單組 p {rp:.3f}（{best[0]} {best[3]} k{best[5]}）→ 家族 p {fp:.3f}")

    # 逐年：單組 p 最小的順勢、逆勢各一條
    for pp, side, nm in ((pf, 1, "順勢"), (pr, -1, "逆勢")):
        j = pp.index(min(pp))
        sp, sig, rets, cost = rows[j]
        L.append(f"\n【逐年】{nm}最佳：{sp[0]} {sp[3]} k{sp[5]}（每筆% ／筆數／勝率）")
        for y in sorted({f["d"][:4] for f in feats}):
            xs = [side * s * r - c for s, r, c, f in zip(sig, rets, cost, feats) if s and f["d"][:4] == y]
            if xs:
                L.append(f"{y}  {statistics.mean(xs)*100:+7.3f}%  {len(xs):4d}  {sum(1 for x in xs if x>0)/len(xs)*100:3.0f}%")

    # ── 對照：量到底有沒有加分？ ──
    L.append("\n【對照 1：同一個方向規則、不看量（k=0）】順勢每筆%（扣成本）／筆數／勝率")
    for w, wn in (("09:14", "09:15"), ("09:29", "09:30"), ("09:59", "10:00")):
        for dk, dn, th in (("dir_in", "09:05起", 0.0), ("dir_in", "09:05起≥0.3%", 0.003),
                           ("dir_gap", "昨收起", 0.0), ("dir_gap", "昨收起≥0.5%", 0.005)):
            sig, ent = signal(feats, (None, w, dk, dn, th, 0.0))
            xs = [s * (f["exit"] / e - 1) - COST_PTS / e for s, e, f in zip(sig, ent, feats) if s]
            L.append(f"開盤到{wn} {dn:<12} {statistics.mean(xs)*100:+.3f}%  {len(xs):5d}  {sum(1 for x in xs if x>0)/len(xs)*100:.0f}%")
    for k in (0, 1):
        sig, ent = signal(feats, (None, f"spike{k}", "dir", "", 0.0, k))
        xs = [s * (f["exit"] / e - 1) - COST_PTS / e for s, e, f in zip(sig, ent, feats) if s]
        L.append(f"盤中 5 分 K 漲跌≥0.1% 第一根、量 ≥{k} 倍 {statistics.mean(xs)*100:+.3f}%  {len(xs):5d}  {sum(1 for x in xs if x>0)/len(xs)*100:.0f}%")

    L.append("\n【對照 2：方向維持真實，只把「量比」序列環狀平移 400 次】p＝平移後順勢每筆 ≥ 實際的比例（小＝量真的有加分）")
    for sp, sig, rets, cost in rows:
        if sp[1].startswith("spike"):
            continue
        _, w, dk, dn, th, k = sp
        ids = [i for i, f in enumerate(feats) if f.get(w)]
        vr = [feats[i][w]["vr"] for i in ids]
        dirs = [feats[i][w][dk] for i in ids]
        rr = [feats[i]["exit"] / feats[i][w]["entry"] - 1 for i in ids]

        def mean_for(vv):
            tot = cnt = 0
            for v, x, r in zip(vv, dirs, rr):
                if v >= k and abs(x) >= th and x != 0:
                    tot += (1 if x > 0 else -1) * r
                    cnt += 1
            return tot / cnt if cnt else 0.0
        real_m = mean_for(vr)
        cnt_ge = 0
        for _ in range(NSHIFT):
            sh = random.randint(30, len(vr) - 30)
            if mean_for(vr[sh:] + vr[:sh]) >= real_m:
                cnt_ge += 1
        L.append(f"{sp[0]:<12}{dn:<12} k{k:<4} 順勢每筆（未扣成本）{real_m*100:+.3f}%  量平移 p {cnt_ge/NSHIFT:.2f}")

    txt = "\n".join(L)
    print(txt)
    open(os.path.join(HERE, "結果_研究350_盤中量與方向當沖.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
