"""研究 177：新台幣單日急升／急貶 → 台指期之後（研究 168 測了美元、日圓，沒測台幣）

匯率：Yahoo TWD=X（美元兌台幣，UTC 日線；台股交易日 D 之前最後一根＝涵蓋 D−1 台北匯市收盤，D 開盤前已知）
訊號：USD/TWD 單日 ≤ −0.5%／−0.8%（台幣急升＝外資匯入？）、≥ +0.5%／+0.8%（台幣急貶＝匯出？）
報酬：台指期近月 D 開盤做多 → D+1 開盤（研究 148 build），以及 D 開盤 → 第 5 天收盤；扣成本；負＝做空較好
對照：同波動度十分位 2000 次抽樣（D+1）；5 天版去叢集 sign-flip；兩段 2003～2016／2017～；8 格 Bonferroni
另看：排除恐慌做多觸發日（台幣急貶常與股災同天）
用法：python -X utf8 backtest/research_177_台幣急升急貶.py
"""
import importlib.util
import os
import sys
from datetime import timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r168", os.path.join(HERE, "research_168_美國跨資產衝擊隔天台指期.py"))
R168 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R168)
R148 = R168.R148
COST = 3.0


def main():
    rows = R148.build()
    n = len(rows)
    ds = [x["d"] for x in rows]
    cc = np.array([0.0] + [rows[k]["c"] / rows[k - 1]["c"] - 1 for k in range(1, n)])
    vol = np.array([np.std(cc[max(1, k - 20):k]) if k > 5 else np.nan for k in range(n)])
    ok = ~np.isnan(vol)
    dec = np.digitize(np.nan_to_num(vol), np.nanpercentile(vol, np.arange(10, 100, 10)))
    r1 = np.array([x["r"] for x in rows])
    c6 = np.array([x["sig"] for x in rows])
    # 5 天：D 開 → D+4 收（rows 的 c 是收盤；開盤價從 r 反推不到，改用 R148 的台指期資料）
    dates, day, night, near = R148.R144.R139.load_tx()
    k_of = {d: i for i, d in enumerate(dates)}
    r5 = np.full(n, np.nan)
    for i, d in enumerate(ds):
        k = k_of[d]
        m = near[dates[k - 1]]
        b = day[d].get(m)
        if b and k + 4 < len(dates) and day[dates[k + 4]].get(m):
            r5[i] = (day[dates[k + 4]][m][3] - b[0] - 2 * COST) / b[0]
    S = R168.series("TWDX.json", tz=timezone.utc)
    v = np.array([R168.prev_val(S, d) if R168.prev_val(S, d) is not None else np.nan for d in ds])
    rules = [("台幣急升 USD/TWD ≤ −0.5%", v <= -0.005), ("台幣急升 ≤ −0.8%", v <= -0.008),
             ("台幣急貶 USD/TWD ≥ +0.5%", v >= 0.005), ("台幣急貶 ≥ +0.8%", v >= 0.008)]
    rng = np.random.default_rng(177)
    out = [f"研究 177：新台幣單日急升急貶 → 台指期（{ds[0]}～{ds[-1]}；TWD=X 有值 {np.sum(~np.isnan(v))} 天）", ""]
    fam = []
    for nm, sig in rules:
        sig = sig & ~np.isnan(v)
        msk = sig & ok
        idx = np.where(msk)[0]
        ctrl = ok & ~sig & ~np.isnan(v)
        pools = {i: np.where(ctrl & (dec == dec[i]))[0] for i in idx}
        base = np.array([r1[pools[i]].mean() for i in idx])
        diff = np.mean(r1[idx] - base)
        null = np.array([np.mean([r1[rng.choice(pools[i])] for i in idx] - base) for _ in range(2000)])
        p1 = (1 + np.sum(np.abs(null) >= abs(diff))) / 2001
        # 5 天去叢集
        ev, last = [], -99
        for i in idx:
            if i - last >= 5 and not np.isnan(r5[i]):
                ev.append(i)
            last = i
        ev = np.array(ev)
        d5 = np.array([r5[i] - np.nanmean(r5[np.where(ctrl & (dec == dec[i]))[0]]) for i in ev])
        sims = np.array([(d5 * rng.choice((-1, 1), len(d5))).mean() for _ in range(2000)])
        p5 = (1 + np.sum(np.abs(sims) >= abs(d5.mean()))) / 2001
        fam += [(f"{nm} 隔天", p1), (f"{nm} 5 天", p5)]
        ex = msk & ~c6
        seg = "  ".join(f"{a[:4]}～ {r1[msk & (np.array(ds) >= a) & (np.array(ds) < z)].mean():+.2%}" for a, z in (("2003", "2017-05-15"), ("2017-05-15", "2099")))
        out.append(f"{nm}：{len(idx)} 次")
        out.append(f"   D 開→D+1 開：每筆 {r1[msk].mean():+.2%} 勝率 {np.mean(r1[msk] > 0):.0%} 比同波動 {diff:+.2%}（p {p1:.3f}）｜{seg}｜排除恐慌觸發 {ex.sum()} 次 {r1[ex].mean():+.2%}")
        out.append(f"   D 開→5 天：{len(ev)} 個獨立事件 每筆 {r5[ev].mean():+.2%} 勝率 {np.mean(r5[ev] > 0):.0%} 比同波動 {d5.mean():+.2%}（p {p5:.3f}）")
    K = len(fam)
    out.append("")
    out.append(f"== Bonferroni（{K} 格）==")
    for nm, p in sorted(fam, key=lambda z: z[1])[:4]:
        out.append(f"{nm:30s} p {p:.3f} → 校正 {min(1, p * K):.3f}")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究177_台幣急升急貶.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
