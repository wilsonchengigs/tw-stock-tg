"""研究 146：候選 6（恐慌隔天做多）錯過 08:45 開盤時，晚進場還有沒有優勢（2026-11-25 使用者實際情境）

訊號同研究 145：D 的夜盤近月跌 ≥2% 或 S&P 前一晚跌 ≥2%；出場一律 D+1 08:45 開盤
晚進場時點：(a) D 13:45 日盤收盤 (b) D 15:00 夜盤開盤（＝D+1 的盤後列開盤）
再依「進場價 相對 D 08:45 開盤價」分組：全部／較低／低 ≥1%／較高
對照：同波動度（前 20 日實現波動同十分位）、非訊號日同樣時點進出，2000 次抽樣，單尾 p；家族＝全部 8 格取最小 p 的 Bonferroni（保守）
成本 3 點；2017-05～
用法：python -X utf8 backtest/research_146_錯過開盤晚進場.py
"""
import importlib.util
import os
import sys
from datetime import datetime, timedelta

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r144", os.path.join(HERE, "research_144_美股大跌隔天做多_樣本外.py"))
R144 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R144)
COST = 3.0


def main():
    dates, day, night, near = R144.R139.load_tx()
    US = R144.us("GSPC.json")
    rows = []
    for k in range(1, len(dates) - 1):
        d, pd_, d1 = dates[k], dates[k - 1], dates[k + 1]
        m = near[pd_]
        b, b1, nb, nb1 = day[d].get(m), day[d1].get(m), night[d].get(m), night[d1].get(m)
        if not (b and b1 and nb and nb1) or nb[4] < 1000 or nb1[4] < 1000:
            continue
        u = None
        for back in range(1, 5):
            kk = (datetime.fromisoformat(d) - timedelta(days=back)).strftime("%Y-%m-%d")
            if kk in US:
                u = US[kk]
                break
        sig = (nb[3] / nb[0] - 1) <= -0.02 or (u is not None and u <= -0.02)
        rows.append(dict(d=d, sig=sig, o=b[0], c=b[3], no=nb1[0], o1=b1[0]))
    n = len(rows)
    cc = np.array([0.0] + [rows[k]["c"] / rows[k - 1]["c"] - 1 for k in range(1, n)])
    vol = np.array([np.std(cc[max(1, k - 20):k]) if k > 5 else np.nan for k in range(n)])
    ok = ~np.isnan(vol)
    dec = np.digitize(vol, np.nanpercentile(vol, np.arange(10, 100, 10)))
    sig = np.array([r["sig"] for r in rows]) & ok
    ctrl = ~np.array([r["sig"] for r in rows]) & ok
    o = np.array([r["o"] for r in rows])
    o1 = np.array([r["o1"] for r in rows])
    rng = np.random.default_rng(146)
    out = [f"研究 146：恐慌隔天做多 錯過開盤晚進場（{rows[0]['d']}～{rows[-1]['d']}，訊號 {sig.sum()} 次，出場 D+1 08:45）", ""]
    base = (o1 - o - COST) / o
    out.append(f"參考：照規則 08:45 進 每筆 {base[sig].mean():+.2%}／勝率 {np.mean(base[sig] > 0):.0%}\n")
    cells = []
    for lab, px in (("D 13:45 收盤進", np.array([r["c"] for r in rows])), ("D 15:00 夜盤開盤進", np.array([r["no"] for r in rows]))):
        r = (o1 - px - COST) / px
        rel = px / o - 1
        for g, gm in (("全部", np.ones(n, bool)), ("比早上低", rel < 0), ("比早上低≥1%", rel <= -0.01), ("比早上高", rel >= 0)):
            msk = sig & gm
            idx = np.where(msk)[0]
            if len(idx) < 5:
                continue
            pools = {k: np.where(ctrl & (dec == dec[k]))[0] for k in idx}
            diff = np.mean([r[k] - r[pools[k]].mean() for k in idx])
            null = np.array([np.mean([r[rng.choice(pools[k])] - r[pools[k]].mean() for k in idx]) for _ in range(2000)])
            pv = (1 + np.sum(null >= diff)) / 2001
            cells.append(pv)
            out.append(f"{lab:12s} {g:8s} {len(idx):3d} 次  每筆 {r[msk].mean():+.2%}  勝率 {np.mean(r[msk] > 0):.0%}  "
                       f"中位 {np.median(r[msk]):+.2%}  最差 {r[msk].min():+.2%}  比同波動對照 {diff:+.2%}（p {pv:.3f}，Bonferroni {min(1, pv * 8):.3f}）")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究146_錯過開盤晚進場.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
