"""研究 169：台指期日曆效應——結算日／結算週、月初月底、星期幾、夜盤 vs 日盤

台指期近月（tx_daily_ohlc.csv；R139.load_tx 的近月，結算日已換次月），同一契約計算：
  cc＝前日日盤收→今日日盤收（全天持有）；id＝今日日盤 開→收；on＝前日日盤收→今日日盤開（2017-05 後含夜盤）
結算日＝每個契約月份的最後交易日（通常第三個星期三）
家族：
  S1 結算日 id／cc；S2 結算日隔天 cc；S3 結算週（結算日前 2 天～結算日）cc；S4 結算後一週 cc
  M1 月底最後 1 天＋月初前 3 天（turn-of-month）cc；M2 月中其他日
  W 週一～週五 cc（各自 vs 其他天）；N 2017-05 後 夜盤報酬（前日日盤收→夜盤收）vs 日盤報酬（夜盤收→日盤收）
檢定：該組日子平均 vs 其他日子，置換 2000 次雙尾 p；Bonferroni；分段 1998–2007／2008–2016／2017–2026
成本：日曆效應若要交易，每筆 3 點（另列每筆扣成本後）
用法：python -X utf8 backtest/research_169_台指期日曆效應.py
"""
import importlib.util
import os
import sys
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r139", os.path.join(HERE, "research_139_爆量收黑與外資期貨_台指期家族.py"))
if not os.path.exists(spec.origin):
    import glob
    spec = importlib.util.spec_from_file_location("r139", glob.glob(os.path.join(HERE, "research_139_*.py"))[0])
R139 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R139)
SEGS = [("1998", "2008"), ("2008", "2017"), ("2017", "2027")]
COST = 3.0


def main():
    dates, day, night, near = R139.load_tx()
    last_day = {}
    for d in dates:
        for m in day[d]:
            if day[d][m][4] > 0:
                last_day[m] = d
    settle = set(last_day.values()) & set(dates)
    rows = []
    for k in range(1, len(dates)):
        d, pd_ = dates[k], dates[k - 1]
        m = near[d]
        b, pb = day[d].get(m), day[pd_].get(m)
        if not (b and pb) or min(b[0], b[3], pb[3]) <= 0:
            continue
        nb = night[d].get(m)
        nr = (nb[3] / pb[3] - 1) if (nb and nb[4] >= 1000 and d >= "2017-05-15") else np.nan
        dr = (b[3] / nb[3] - 1) if not np.isnan(nr) else np.nan
        rows.append(dict(d=d, k=k, cc=b[3] / pb[3] - 1, id=(b[3] - b[0]) / b[0], on=b[0] / pb[3] - 1, nr=nr, dr=dr, px=b[0]))
    n = len(rows)
    ds = np.array([x["d"] for x in rows])
    K_ = np.array([x["k"] for x in rows])
    cc, idr, on = (np.array([x[f] for x in rows]) for f in ("cc", "id", "on"))
    nr, dr = np.array([x["nr"] for x in rows]), np.array([x["dr"] for x in rows])
    px = np.array([x["px"] for x in rows])
    # 標記
    is_set = np.array([d in settle for d in ds])
    k_of = {d: i for i, d in enumerate(dates)}
    set_k = sorted(k_of[d] for d in settle)
    after = np.zeros(n, bool)
    week_pre = np.zeros(n, bool)
    week_post = np.zeros(n, bool)
    sk = np.array(set_k)
    for i, k in enumerate(K_):
        j = np.searchsorted(sk, k)          # 下一個（或今天）結算日
        if j < len(sk) and 0 <= sk[j] - k <= 2:
            week_pre[i] = True
        if j > 0 and k - sk[j - 1] == 1:
            after[i] = True
        if j > 0 and 1 <= k - sk[j - 1] <= 5:
            week_post[i] = True
    ym = np.array([d[:7] for d in ds])
    tom = np.zeros(n, bool)
    for i in range(n):
        if i + 1 < n and ym[i + 1] != ym[i]:
            tom[i] = True                   # 月底最後一天
        first = [j for j in range(max(0, i - 3), i + 1) if j == 0 or ym[j] != ym[j - 1]]
        if first and i - first[-1] <= 2 and ym[first[-1]] == ym[i]:
            tom[i] = True                   # 月初前 3 天
    wd = np.array([date.fromisoformat(d).weekday() for d in ds])
    rng = np.random.default_rng(169)
    fam = []

    def test(nm, x, msk, base=None):
        g = ~np.isnan(x)
        a = x[msk & g]
        b = x[(~msk if base is None else base) & g]
        allv = np.concatenate([a, b])
        obs = a.mean() - b.mean()
        null = np.empty(2000)
        for t in range(2000):
            rng.shuffle(allv)
            null[t] = allv[:len(a)].mean() - allv[len(a):].mean()
        p = (1 + np.sum(np.abs(null) >= abs(obs))) / 2001
        fam.append((nm, p))
        seg = "  ".join(f"{s[2:]}–{str(int(z) - 1)[2:]} {x[msk & g & (ds >= s) & (ds < z)].mean():+.3%}"
                        if (msk & g & (ds >= s) & (ds < z)).sum() else f"{s[2:]}–{str(int(z) - 1)[2:]} —" for s, z in SEGS)
        net = a.mean() - COST / np.median(px)
        return f"{nm:26s} {len(a):5d} 天  平均 {a.mean():+.3%}（其他 {b.mean():+.3%}）差 {obs:+.3%}  p {p:.3f}  扣成本 {net:+.3%}｜{seg}"

    out = [f"研究 169：台指期日曆效應（{ds[0]}～{ds[-1]}，{n} 天）", "（差＝該組平均 − 其他日；扣成本＝該組平均 − 3 點，假設專門為這個效應進出一次）", ""]
    out.append("== 結算 ==")
    out.append(test("S1 結算日 日盤開→收", idr, is_set))
    out.append(test("S1 結算日 全天 cc", cc, is_set))
    out.append(test("S2 結算日隔天 cc", cc, after))
    out.append(test("S3 結算前 2 天～結算日 cc", cc, week_pre))
    out.append(test("S4 結算後 5 天 cc", cc, week_post))
    out.append("")
    out.append("== 月初月底 ==")
    out.append(test("M1 月底 1 天＋月初 3 天 cc", cc, tom))
    out.append(test("M1 同上 日盤開→收", idr, tom))
    out.append("")
    out.append("== 星期幾（全天 cc）==")
    for w, lab in enumerate("一二三四五"):
        out.append(test(f"W 星期{lab}", cc, wd == w))
    out.append("")
    post = ds >= "2017-05-15"
    g = post & ~np.isnan(nr)
    out.append(f"== N 2017-05 後：夜盤 vs 日盤（{g.sum()} 天）==")
    out.append(f"夜盤（前日收→夜盤收）平均 {nr[g].mean():+.3%}／天、勝率 {np.mean(nr[g] > 0):.0%}、累積 {np.prod(1 + nr[g]) - 1:+.0%}")
    out.append(f"日盤（夜盤收→日盤收）平均 {dr[g].mean():+.3%}／天、勝率 {np.mean(dr[g] > 0):.0%}、累積 {np.prod(1 + dr[g]) - 1:+.0%}")
    out.append(f"隔夜（前日收→今開）{on[post].mean():+.3%}／天；日盤開→收 {idr[post].mean():+.3%}／天")
    diff = nr[g] - dr[g]
    sims = np.array([(diff * rng.choice((-1, 1), len(diff))).mean() for _ in range(2000)])
    pN = (1 + np.sum(np.abs(sims) >= abs(diff.mean()))) / 2001
    fam.append(("N 夜盤−日盤", pN))
    out.append(f"夜盤 − 日盤 每天 {diff.mean():+.3%}（sign-flip p {pN:.3f}）")
    for y in range(2017, 2027):
        s = g & (ds >= f"{y}") & (ds < f"{y + 1}")
        if s.sum():
            out.append(f"   {y}：夜盤 {np.prod(1 + nr[s]) - 1:+.1%}  日盤 {np.prod(1 + dr[s]) - 1:+.1%}")
    out.append("")
    Kf = len(fam)
    out.append(f"== 家族 Bonferroni（{Kf} 個檢定）==")
    for nm, p in sorted(fam, key=lambda x: x[1])[:8]:
        out.append(f"{nm:26s} p {p:.3f} → 校正 {min(1, p * Kf):.3f}")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究169_台指期日曆效應.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
