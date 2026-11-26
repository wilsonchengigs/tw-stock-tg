"""研究 202：從現況往前推演（2026-11-25：加權 38,195、v3 空手、進場線 45,821 差 -16.6%、20 日波動 62%）

蒙地卡羅：以真實歷史（到 2026-11-25）為起點，接上「抽樣的未來日報酬」，往後 250 個交易日，每條路徑重算均線與核心訊號
（MA60×1.01 進、MA80×0.975 出；不含融資濾網——它在空手時只會延後進場，不影響何時「可以」進場）
抽樣來源（平穩區塊拔靴，平均區塊 20 天）：
 A 全部歷史 1998～2026（一般市況）
 B 只抽 20 日波動 >30% 的日子所在區塊（延續高波動）
 C 只抽「離 250 日高 ≤ -20%」期間的日子（熊市延續）
每種 3,000 條：v3 進場機率（1／3／6／12 個月內）、進場時加權、12 個月後加權、
核心策略 2x 12 個月報酬 vs 一直抱 0050（1x）vs 一直抱 00631L（2x 每日重設）
用法：python -X utf8 backtest/research_202_現況推演.py
"""
import importlib.util
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402
import data  # noqa: E402

TD = 245
DIV, DRAG, RC, COST = 0.03 / TD, 0.01 / TD, 0.01 / TD, 0.0025


def main():
    tw, _, _ = data.series()
    days = [d for d in sorted(tw) if d <= "2026-11-25"]
    px = np.array([tw[d][0] for d in days])
    r = px[1:] / px[:-1] - 1
    n = len(r)
    vol = np.array([np.std(r[max(0, k - 19):k + 1]) * math.sqrt(TD) if k >= 19 else 0 for k in range(n)])
    hi = np.array([px[max(0, k - 249):k + 1].max() for k in range(len(px))])
    dd = px / hi - 1
    pools = {"A 全部歷史": np.arange(n), "B 高波動延續（20 日波動 >30%）": np.where(vol > 0.30)[0],
             "C 熊市延續（離 250 日高 ≤-20%）": np.where(dd[1:] <= -0.20)[0]}
    H = 250
    hist = px[-300:]
    rng = np.random.default_rng(202)
    L = [f"研究 202：現況推演（起點 {days[-1]} 加權 {px[-1]:,.0f}；未來 {H} 個交易日；每種 3,000 條；核心訊號不含融資濾網）"]
    for name, pool in pools.items():
        pool_set = set(pool.tolist())
        res = {"ent": [], "ent_px": [], "end": [], "strat": [], "b1": [], "b2": [], "low": []}
        for _ in range(3000):
            fut, k = [], int(rng.choice(pool))
            while len(fut) < H:
                fut.append(r[k])
                k = k + 1 if (rng.random() > 1 / 20 and k + 1 < n and (k + 1) in pool_set) else int(rng.choice(pool))
            fut = np.array(fut)
            path = np.concatenate([hist, hist[-1] * np.cumprod(1 + fut)])
            s0 = len(hist)
            st, cur, pend, eq, ent = False, 0.0, None, 1.0, None
            m60 = np.convolve(path, np.ones(60) / 60, "valid")
            m80 = np.convolve(path, np.ones(80) / 80, "valid")
            for t in range(s0, len(path)):
                rr = path[t] / path[t - 1] - 1
                eq *= 1 + ((2 * (rr + DIV) - DRAG) if cur > 0 else RC)
                if pend is not None:
                    eq *= 1 - COST * 2
                    cur, pend = pend, None
                if (t - s0) % 5 == 4:  # 每 5 天當一次週五
                    a60, a80 = m60[t - 59], m80[t - 79]
                    st = (not path[t] < a80 * 0.975) if st else (path[t] > a60 * 1.01)
                    tgt = 2.0 if st else 0.0
                    if tgt != cur:
                        pend = tgt
                        if tgt > 0 and ent is None:
                            ent = t - s0
            res["ent"].append(ent if ent is not None else 999)
            res["ent_px"].append(path[s0 + ent] if ent is not None else np.nan)
            res["end"].append(path[-1] / path[s0 - 1] - 1)
            res["low"].append(path[s0:].min() / path[s0 - 1] - 1)
            res["strat"].append(eq - 1)
            res["b1"].append(np.prod(1 + fut + DIV) - 1)
            res["b2"].append(np.prod(1 + 2 * (fut + DIV) - DRAG) - 1)
        e = np.array(res["ent"])
        L.append(f"\n【{name}】抽樣天數 {len(pool)}")
        L.append("  v3 進場機率：" + "、".join(f"{m} 個月內 {np.mean(e <= m * 21):.0%}" for m in (1, 3, 6, 12)))
        ep = np.array(res["ent_px"])
        if np.any(~np.isnan(ep)):
            L.append(f"  進場時加權：中位 {np.nanmedian(ep):,.0f}（比現在 {np.nanmedian(ep) / px[-1] - 1:+.0%}）")
        for key, lab in (("end", "12 月後加權"), ("low", "期間最低（相對現在）"), ("strat", "核心策略 2x"), ("b1", "抱 0050"), ("b2", "抱 00631L")):
            a = np.array(res[key])
            L.append(f"  {lab:<14}：中位 {np.median(a):+.0%}、10 分位 {np.percentile(a, 10):+.0%}、90 分位 {np.percentile(a, 90):+.0%}" +
                     (f"、虧損機率 {np.mean(a < 0):.0%}" if key in ("strat", "b1", "b2", "end") else ""))
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究202_現況推演.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
