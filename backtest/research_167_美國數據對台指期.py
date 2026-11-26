"""研究 167：美國經濟數據（CPI、非農、FOMC）對台指期的影響——1998～2026，含 CPI（研究 67 只做了 2017 後的非農／FOMC 夜盤方向）

日曆：backtest/us_events.csv（build_us_events.py：FOMC 聯準會官網 1998～、非農 BLS 規則推算、CPI 取 ALFRED 發布日）
時點（台灣時間）：CPI／非農 美東 08:30＝台灣 E 日 20:30／21:30；FOMC 美東 14:00＝台灣 E+1 02:00／03:00
  P＝E 當天或之前最後一個台股交易日（日盤在公布「前」）；D＝E 之後第一個台股交易日（日盤在公布「後」）
台指期近月（tx_daily_ohlc.csv，換月用同一契約）；每筆來回扣 3 點
檢定（每類事件 × 每項）：
  T1 公布前一天：P 日盤 開→收 做多（「公布前漂移」，美股 FOMC 有 pre-FOMC drift 文獻）
  T2 抱過公布：P 收 → D 開 做多（跨事件夜的平均報酬，以及跳空幅度＝風險）
  T3 公布後隔天：D 開盤跳空 |gap|≥0.5% → D 日盤 順勢／回補，對照「非事件日、同樣跳空 ≥0.5%」
  T4 D 開 → D+1 開 做多
  T5 候選 6（恐慌隔天做多）：觸發日若是美國數據造成的（D 為事件後交易日）vs 其他觸發
  T6 FOMC 週期（Cieslak、Morse、Vissing-Jorgensen 2019）：距上次 FOMC 的偶數週 vs 奇數週，台指期日報酬
對照：T1/T2/T4 用同波動度（前 20 日實現波動同十分位）非事件日 2000 次抽樣，雙尾 p；T6 用 FOMC 日曆循環平移 1000 次
家族：所有主檢定 p 做 Bonferroni；分段 1998–2007／2008–2016／2017–2026
用法：python -X utf8 backtest/research_167_美國數據對台指期.py
"""
import csv
import importlib.util
import os
import sys
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r148", os.path.join(HERE, "research_148_恐慌連續觸發.py"))
R148 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R148)
COST = 3.0
SEGS = [("1998", "2008"), ("2008", "2017"), ("2017", "2027")]
KINDS = ("CPI", "NFP", "FOMC")


def events():
    ev = {k: [] for k in KINDS}
    for r in csv.DictReader(open(os.path.join(HERE, "us_events.csv"), encoding="utf-8")):
        ev[r["event"]].append(r["date"])
    return {k: sorted(set(v)) for k, v in ev.items()}


def panel():
    dates, day, night, near = R148.R144.R139.load_tx()
    rows = []
    for k in range(1, len(dates) - 1):
        pd_, d, d1 = dates[k - 1], dates[k], dates[k + 1]
        m = near[d]
        b, pb, b1 = day[d].get(m), day[pd_].get(m), day[d1].get(m)
        if not (b and pb and b1) or min(b[0], b[3], pb[3], b1[0]) <= 0:
            continue
        rows.append(dict(d=d, o=b[0], c=b[3], pc=pb[3], o1=b1[0]))
    n = len(rows)
    cc = np.array([0.0] + [rows[i]["c"] / rows[i]["pc"] - 1 for i in range(1, n)])
    vol = np.array([np.std(cc[max(1, i - 20):i]) if i > 5 else np.nan for i in range(n)])
    dec = np.digitize(np.nan_to_num(vol, nan=0), np.nanpercentile(vol, np.arange(10, 100, 10)))
    return rows, cc, vol, dec


def matched_p(r, msk, ctrl, dec, rng, B=2000):
    """事件日平均 − 同波動十分位非事件日平均；雙尾抽樣 p"""
    idx = np.where(msk)[0]
    pools = {k: np.where(ctrl & (dec == dec[k]))[0] for k in idx}
    idx = [k for k in idx if len(pools[k]) > 20]
    if len(idx) < 8:
        return np.nan, np.nan, len(idx)
    base = np.array([r[pools[k]].mean() for k in idx])
    diff = np.mean(r[idx] - base)
    null = np.array([np.mean([r[rng.choice(pools[k])] for k in idx] - base) for _ in range(B)])
    return diff, (1 + np.sum(np.abs(null) >= abs(diff))) / (B + 1), len(idx)


def main():
    ev = events()
    rows, cc, vol, dec = panel()
    n = len(rows)
    ds = [x["d"] for x in rows]
    pos = {d: i for i, d in enumerate(ds)}
    ok = ~np.isnan(vol)
    o = np.array([x["o"] for x in rows])
    c = np.array([x["c"] for x in rows])
    pc = np.array([x["pc"] for x in rows])
    o1 = np.array([x["o1"] for x in rows])
    intraday = (c - o - COST) / o           # 日盤 開→收 做多
    gap = o / pc - 1                        # 前收 → 今開
    overnight = (o - pc - COST) / pc        # 前收 → 今開 做多（扣成本）
    d2d = (o1 - o - COST) / o               # 今開 → 明開
    # P、D 標記
    P = {k: np.zeros(n, bool) for k in KINDS}
    D = {k: np.zeros(n, bool) for k in KINDS}
    for k in KINDS:
        for e in ev[k]:
            j = np.searchsorted(ds, e, side="right")   # 第一個 > e 的交易日
            if 0 < j < n:
                D[k][j] = True
                if ds[j - 1] <= e:
                    P[k][j - 1] = True
    anyP = P["CPI"] | P["NFP"] | P["FOMC"]
    anyD = D["CPI"] | D["NFP"] | D["FOMC"]
    ctrl = ok & ~anyP & ~anyD
    rng = np.random.default_rng(167)
    fam = []
    out = [f"研究 167：美國數據（CPI／非農／FOMC）× 台指期（{ds[0]}～{ds[-1]}，{n} 天；每筆扣 3 點）",
           f"事件數：CPI {len(ev['CPI'])}、非農 {len(ev['NFP'])}、FOMC {len(ev['FOMC'])}", ""]

    def seg_str(r, msk):
        return "  ".join(f"{a[2:]}–{str(int(z) - 1)[2:]} {r[msk & np.array([a <= x < z for x in ds])].mean():+.2%}"
                         if (msk & np.array([a <= x < z for x in ds])).sum() else f"{a[2:]}–{str(int(z) - 1)[2:]} —"
                         for a, z in SEGS)

    for tag, r, MK in (("T1 公布前一天 P 日盤開→收做多", intraday, P),
                       ("T2 抱過公布 P 收→D 開做多", overnight, D),
                       ("T4 公布後 D 開→D+1 開做多", d2d, D)):
        out.append(f"== {tag}（非事件日平均 {r[ctrl].mean():+.3%}）==")
        for k in KINDS:
            msk = MK[k] & ok
            diff, p, m = matched_p(r, msk, ctrl, dec, rng)
            fam.append((f"{tag[:2]} {k}", p))
            out.append(f"{k:5s} {m:4d} 次  每筆 {r[msk].mean():+.3%}  勝率 {np.mean(r[msk] > 0):.0%}  比同波動 {diff:+.3%}（p {p:.3f}）｜{seg_str(r, msk)}")
        out.append("")

    out.append("== 跳空幅度（風險）：|P 收→D 開| 平均 ==")
    for k in KINDS:
        out.append(f"{k:5s} {np.abs(gap[D[k] & ok]).mean():.2%}（非事件日 {np.abs(gap[ctrl]).mean():.2%}，倍數 {np.abs(gap[D[k] & ok]).mean() / np.abs(gap[ctrl]).mean():.2f}）"
                   f"｜2017 後 {np.abs(gap[D[k] & ok & (np.array(ds) >= '2017-05-15')]).mean():.2%} vs {np.abs(gap[ctrl & (np.array(ds) >= '2017-05-15')]).mean():.2%}")
    out.append("")

    out.append("== T3 公布後跳空 ≥0.5% → D 日盤順勢（負＝回補較好）；對照：非事件日同樣跳空 ==")
    big = np.abs(gap) >= 0.005
    follow = np.sign(gap) * (c - o) / o - COST / o
    for k in KINDS + ("全部",):
        msk = (anyD if k == "全部" else D[k]) & big & ok
        cm = ctrl & big
        x, y = follow[msk], follow[cm]
        # 差異的置換檢定
        allv = np.concatenate([x, y])
        null = []
        for _ in range(2000):
            rng.shuffle(allv)
            null.append(allv[:len(x)].mean() - allv[len(x):].mean())
        p = (1 + np.sum(np.abs(null) >= abs(x.mean() - y.mean()))) / 2001
        if k != "全部":
            fam.append((f"T3 {k}", p))
        out.append(f"{k:5s} {len(x):4d} 次  順勢每筆 {x.mean():+.3%}（對照 {len(y)} 次 {y.mean():+.3%}，差 p {p:.3f}）｜{seg_str(follow, msk)}")
    out.append("")

    # T5 候選 6 觸發來源
    r148 = {x["d"]: x for x in R148.build()}
    sig = np.array([r148[d]["sig"] if d in r148 else False for d in ds])
    rr = np.array([r148[d]["r"] if d in r148 else np.nan for d in ds])
    out.append("== T5 恐慌隔天做多（候選 6）：觸發當天是不是美國數據公布後 ==")
    for per, lo in (("1998～", "1998"), ("2017-05～", "2017-05-15")):
        inp = np.array([x >= lo for x in ds])
        a, b = rr[sig & anyD & inp], rr[sig & ~anyD & inp]
        allv = np.concatenate([a, b])
        null = []
        for _ in range(2000):
            rng.shuffle(allv)
            null.append(allv[:len(a)].mean() - allv[len(a):].mean())
        p = (1 + np.sum(np.abs(null) >= abs(a.mean() - b.mean()))) / 2001
        fam.append((f"T5 {per}", p))
        out.append(f"{per:10s} 數據後觸發 {len(a)} 次 每筆 {a.mean():+.2%} 勝率 {np.mean(a > 0):.0%} ｜其他觸發 {len(b)} 次 {b.mean():+.2%} 勝率 {np.mean(b > 0):.0%}（差 p {p:.3f}）")
        for k in KINDS:
            z = rr[sig & D[k] & inp]
            if len(z):
                out.append(f"   {k:5s} {len(z):3d} 次 每筆 {z.mean():+.2%} 勝率 {np.mean(z > 0):.0%}")
    out.append("")

    # T6 FOMC 週期：距最近一次 FOMC（含之前 1 天）的週數；週 0＝E-1～E+5（日曆日），偶數週 vs 奇數週
    fomc = np.array([date.fromisoformat(e).toordinal() for e in ev["FOMC"]])
    dord = np.array([date.fromisoformat(d).toordinal() for d in ds])
    ret = np.concatenate([[0.0], c[1:] / pc[1:] - 1])  # 收→收（同契約）

    def even_odd(fo):
        j = np.searchsorted(fo, dord + 1, side="right") - 1
        valid = j >= 0
        wk = np.where(valid, (dord - fo[np.clip(j, 0, None)] + 1) // 7, -1)
        ev_ = valid & (wk % 2 == 0) & (wk <= 6)
        od_ = valid & (wk % 2 == 1) & (wk <= 6)
        return ret[ev_].mean() - ret[od_].mean(), ev_, od_

    diff, ev_, od_ = even_odd(fomc)
    null = np.array([even_odd(np.sort(fomc + s))[0] for s in rng.integers(7, 42, 1000)])
    p6 = (1 + np.sum(np.abs(null) >= abs(diff))) / 1001
    fam.append(("T6 FOMC 週期", p6))
    out.append("== T6 FOMC 週期（距 FOMC 偶數週 vs 奇數週，台指期日報酬）==")
    out.append(f"偶數週 {ev_.sum()} 天 每天 {ret[ev_].mean():+.3%}（年化 {ret[ev_].mean() * 250:+.0%}）｜奇數週 {od_.sum()} 天 {ret[od_].mean():+.3%}｜差 {diff:+.3%}（平移安慰劑 p {p6:.3f}）")
    for a, z in SEGS:
        s = np.array([a <= x < z for x in ds])
        out.append(f"   {a}–{int(z) - 1}：偶 {ret[ev_ & s].mean():+.3%}  奇 {ret[od_ & s].mean():+.3%}")
    out.append("")

    K = len(fam)
    out.append(f"== 家族 Bonferroni（{K} 個主檢定）==")
    for nm, p in sorted(fam, key=lambda x: x[1]):
        out.append(f"{nm:14s} p {p:.3f} → 校正 {min(1, p * K):.3f}")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究167_美國數據對台指期.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
