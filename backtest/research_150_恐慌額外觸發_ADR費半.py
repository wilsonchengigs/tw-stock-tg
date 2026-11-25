"""研究 150：候選 6 的額外觸發——台積電 ADR（TSM）或費半（^SOX）前一晚大跌，在「夜盤與 S&P 都沒觸發」的日子還有沒有反彈

增量日＝現有條件（夜盤跌 ≥2% 或 S&P 跌 ≥2%）沒觸發，但 TSM／SOX 跌 ≥3／4／5%；報酬 D 開盤→D+1 開盤扣 3 點
兩段：2017-05～、1998（TSM 1997 上市、SOX 1994）～2017-05；同波動度對照 2000 次；6 格×2 段 Bonferroni
用法：python -X utf8 backtest/research_150_恐慌額外觸發_ADR費半.py
"""
import importlib.util
import os
import sys
from datetime import datetime, timedelta

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r148", os.path.join(HERE, "research_148_恐慌連續觸發.py"))
R148 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R148)
R144 = R148.R144


def prev_us(s, d):
    for back in range(1, 5):
        kk = (datetime.fromisoformat(d) - timedelta(days=back)).strftime("%Y-%m-%d")
        if kk in s:
            return s[kk]
    return None


def main():
    rows = R148.build()
    n = len(rows)
    X = {"TSM": R144.us("TSM.json"), "SOX": R144.us("SOX.json")}
    cc = np.array([0.0] + [rows[k]["c"] / rows[k - 1]["c"] - 1 for k in range(1, n)])
    vol = np.array([np.std(cc[max(1, k - 20):k]) if k > 5 else np.nan for k in range(n)])
    ok = ~np.isnan(vol)
    dec = np.digitize(vol, np.nanpercentile(vol, np.arange(10, 100, 10)))
    sig = np.array([x["sig"] for x in rows])
    r = np.array([x["r"] for x in rows])
    rng = np.random.default_rng(150)
    out = ["研究 150：額外觸發（現有條件沒觸發的日子）台積電 ADR／費半 前一晚大跌 → 台指期隔天開盤做多", ""]
    for per, lo, hi in (("2017-05～", "2017-05-15", "2099"), ("1998～2017-05", "1998", "2017-05-15")):
        inp = np.array([lo <= x["d"] < hi for x in rows])
        ctrl = ~sig & ok & inp
        out.append(f"== {per} ==")
        for nm, s in X.items():
            u = np.array([prev_us(s, x["d"]) if prev_us(s, x["d"]) is not None else 0.0 for x in rows])
            ctrl2 = ctrl & (u > -0.01)
            for th in (0.03, 0.04, 0.05):
                msk = ~sig & ok & inp & (u <= -th)
                idx = np.where(msk)[0]
                if len(idx) < 5:
                    out.append(f"{nm} 跌≥{th:.0%}：{len(idx)} 次（太少）")
                    continue
                pools = {k: np.where(ctrl2 & (dec == dec[k]))[0] for k in idx}
                diff = np.mean([r[k] - r[pools[k]].mean() for k in idx])
                null = np.array([np.mean([r[rng.choice(pools[k])] - r[pools[k]].mean() for k in idx]) for _ in range(2000)])
                pv = (1 + np.sum(null >= diff)) / 2001
                out.append(f"{nm} 跌≥{th:.0%}（增量日）{len(idx):3d} 次  每筆 {r[msk].mean():+.2%}  勝率 {np.mean(r[msk] > 0):.0%}  "
                           f"比同波動 {diff:+.2%}（p {pv:.3f}，Bonferroni {min(1, pv * 12):.3f}）")
        out.append("")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究150_恐慌額外觸發_ADR費半.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
