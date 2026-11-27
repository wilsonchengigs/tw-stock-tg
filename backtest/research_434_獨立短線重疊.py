"""研究 434：「獨立短線」（爆量收黑 0.5x 抱 5 天、多頭且融資不過熱）與 V（主策略在場、爆量收黑 1x 抱 10 天）是同一訊號
主策略在場時兩者同時觸發＝同一天加 1.5x。逐筆：V 1x 抱 10 天 vs V＋獨立（前 5 天多 0.5x）；台指期真實價、5% 停損
另：獨立短線在主策略空手時觸發的次數（真正「獨立」的部分）
用法：python -X utf8 backtest/research_434_獨立短線重疊.py
"""
import io
import contextlib
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_411_實際配置含V as V  # noqa: E402
R175, ds, day, night, near, st, vsig = V.R175, V.ds, V.day, V.night, V.near, V.st, V.vsig
n = len(ds)
pairs, k = [], 0
while k < n - 2:
    if vsig[k] and st[k] == 1:
        j = k + 1
        last10 = j
        for h in range(10):
            last10 = min(j + h, n - 1)
            if st[last10] == 0:
                break
        last5 = min(j + 4, last10)
        r10 = R175.trade(day, night, ds, j, near[ds[k]], (last10, "close"), 0.05)
        r5 = R175.trade(day, night, ds, j, near[ds[k]], (last5, "close"), 0.05)
        pairs.append((ds[j], r10, r5))
        k = last10 + 1
    else:
        k += 1
r10 = np.array([p[1] for p in pairs])
r5 = np.array([p[2] for p in pairs])
L = [f"研究 434：獨立短線與 V 重疊（主策略在場的爆量收黑 {len(pairs)} 次，2000～；台指期真實價、5% 停損）", ""]
L.append(f"V 1x 抱 10 天：每筆（資金）{r10.mean():+.2%}、勝率 {np.mean(r10 > 0):.0%}、最差 {r10.min():+.1%}")
both = r10 + 0.5 * r5
L.append(f"V 1x ＋ 獨立 0.5x（抱 5 天）：每筆 {both.mean():+.2%}、勝率 {np.mean(both > 0):.0%}、最差 {both.min():+.1%}")
L.append(f"獨立 0.5x 的增量：每筆 {0.5 * r5.mean():+.2%}（0.5x × 5 天 {r5.mean():+.2%}）")
# 主策略空手但指數在出場線上（獨立短線真正獨立的情況）
ind = sum(1 for k in range(n) if vsig[k] and st[k] == 0)
L.append(f"\n爆量收黑時主策略空手：{ind} 次（獨立短線另有 short_skip：指數在出場線下或融資過熱就跳過，所以空手時幾乎都跳過）")
L.append("結論見研究紀錄")
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究434_獨立短線重疊.txt"), "w", encoding="utf-8").write(out + "\n")
