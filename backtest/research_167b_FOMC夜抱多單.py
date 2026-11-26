"""研究 167b：研究 167 最強的一項——「FOMC 前一個台股交易日收盤買台指期、FOMC 公布後第一個交易日 08:45 開盤賣」的穩健性

1. FOMC 日曆循環平移安慰劑（把 FOMC 日期整體平移 ±3～20 個交易日，1000 次）：是不是 FOMC 本身，而不是隨便一晚
2. 去掉最好的 5／10 筆、中位數、最差一筆；每年平均（幾年為正）
3. 機制：同一晚 S&P 500 在 FOMC 當天（美東）的漲跌——pre-FOMC drift（Lucca & Moench 2015）是不是傳到台股
4. 2017-05 後拆兩段：P 日盤收 → 夜盤收（05:00，含 FOMC 公布）與 夜盤收 → D 開
5. 如果改成夜盤 15:00 開盤進（不想抱日盤收盤那 75 分鐘）
成本：每筆 3 點
用法：python -X utf8 backtest/research_167b_FOMC夜抱多單.py
"""
import importlib.util
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r167", os.path.join(HERE, "research_167_美國數據對台指期.py"))
R167 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R167)
COST = 3.0


def main():
    ev = R167.events()
    fomc = ev["FOMC"]
    dates, day, night, near = R167.R148.R144.R139.load_tx()
    US = R167.R148.R144.us("GSPC.json")
    n = len(dates)
    # 每一晚：P＝dates[i]，D＝dates[i+1]；同一契約（P 的近月）
    on = np.full(n, np.nan)
    for i in range(n - 1):
        m = near[dates[i]]
        a, b = day[dates[i]].get(m), day[dates[i + 1]].get(m)
        if a and b and a[3] > 0 and b[0] > 0:
            on[i] = (b[0] - a[3] - COST) / a[3]
    ok = ~np.isnan(on)

    def mark(evs):
        msk = np.zeros(n, bool)
        for e in evs:
            j = np.searchsorted(dates, e, side="right")
            if 0 < j < n and dates[j - 1] <= e:
                msk[j - 1] = True
        return msk & ok

    P = mark(fomc)
    x = on[P]
    others = on[ok & ~P]
    out = [f"研究 167b：FOMC 夜抱台指期多單（P 日盤收 → D 開，{dates[0]}～{dates[-1]}，每筆扣 3 點）", ""]
    out.append(f"FOMC 夜 {len(x)} 次：每筆 {x.mean():+.3%}  中位 {np.median(x):+.3%}  勝率 {np.mean(x > 0):.0%}  最好 {x.max():+.2%}  最差 {x.min():+.2%}")
    out.append(f"其他所有夜 {len(others)} 次：每筆 {others.mean():+.3%}  勝率 {np.mean(others > 0):.0%}")
    xs = np.sort(x)
    out.append(f"去掉最好 5 筆 {xs[:-5].mean():+.3%}；去掉最好 10 筆 {xs[:-10].mean():+.3%}")
    # 平移安慰劑：FOMC 夜的位置整體平移 k 個交易日
    idx = np.where(P)[0]
    rng = np.random.default_rng(1671)
    null = []
    for _ in range(1000):
        k = rng.integers(3, 21) * rng.choice((-1, 1))
        j = idx + k
        j = j[(j >= 0) & (j < n)]
        j = j[ok[j]]
        null.append(on[j].mean())
    null = np.array(null)
    out.append(f"日曆平移安慰劑（±3～20 個交易日，1000 次）：平均 {null.mean():+.3%}、95 分位 {np.percentile(null, 95):+.3%}；"
               f"真實 {x.mean():+.3%} → 單尾 p {(1 + np.sum(null >= x.mean())) / 1001:.3f}")
    # 每年
    by = defaultdict(list)
    for i in idx:
        by[dates[i][:4]].append(on[i])
    pos = sum(np.mean(v) > 0 for v in by.values())
    out.append(f"每年平均：{pos}/{len(by)} 年為正｜" + " ".join(f"{y[2:]}:{np.mean(v):+.2%}" for y, v in sorted(by.items())))
    out.append("")
    # 機制：S&P 在 FOMC 當天
    sp = np.array([US.get(e, np.nan) for e in fomc])
    allsp = np.array(list(US.values()))
    spm = ~np.isnan(sp)
    out.append(f"S&P 500 在 FOMC 當天（美東）：{spm.sum()} 次 平均 {np.nanmean(sp):+.3%}  勝率 {np.nanmean(sp[spm] > 0):.0%}（S&P 所有日 {allsp.mean():+.3%}）")
    for a, z in (("1998", "2008"), ("2008", "2017"), ("2017", "2027")):
        s = np.array([a <= e < z for e in fomc]) & spm
        out.append(f"   {a}–{int(z) - 1}：S&P FOMC 日 {sp[s].mean():+.3%}")
    # 台股 FOMC 夜報酬 vs 同晚 S&P
    pair = [(on[i], US.get(e, np.nan)) for e in fomc for i in [np.searchsorted(dates, e, side="right") - 1] if 0 <= i < n and P[i]]
    pair = np.array([p for p in pair if not np.isnan(p[1])])
    up, dn = pair[pair[:, 1] > 0, 0], pair[pair[:, 1] <= 0, 0]
    out.append(f"台指期 FOMC 夜：當天 S&P 漲 {len(up)} 次 → {up.mean():+.2%}；S&P 跌 {len(dn)} 次 → {dn.mean():+.2%}（S&P 方向事前不知道，只說明來源）")
    out.append("")
    # 2017 後拆段、夜盤開盤進
    a_, b_, c_ = [], [], []
    for i in idx:
        if dates[i] < "2017-05-15" or i + 1 >= n:
            continue
        m = near[dates[i]]
        nb = night[dates[i + 1]].get(m)
        dp, dd = day[dates[i]].get(m), day[dates[i + 1]].get(m)
        if not (nb and dp and dd) or nb[4] < 1000:
            continue
        a_.append((nb[3] - dp[3]) / dp[3])
        b_.append((dd[0] - nb[3]) / dp[3])
        c_.append((dd[0] - nb[0] - COST) / nb[0])
    a_, b_, c_ = map(np.array, (a_, b_, c_))
    out.append(f"2017-05 後 {len(a_)} 次拆段：P 日盤收→夜盤收（含公布）{a_.mean():+.3%}；夜盤收→D 開 {b_.mean():+.3%}")
    out.append(f"改成 15:00 夜盤開盤進 → D 開出：每筆 {c_.mean():+.3%}  勝率 {np.mean(c_ > 0):.0%}（同期間日盤收進 {on[P & (np.array(dates) >= '2017-05-15')].mean():+.3%}）")
    out.append("")
    out.append(f"規模：一年約 8 次 × {x.mean():+.2%} ≈ 每年 {8 * x.mean():+.1%}（以 1 倍名目計）；0.5 倍加碼 ≈ {4 * x.mean():+.1%}／年")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究167b_FOMC夜抱多單.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
