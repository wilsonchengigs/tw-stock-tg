"""研究 172b：爆量收黑加碼（V）的長期勝率／期望值——研究 172 只有 2018-06～ 7 筆，改用 1998～ 台指期真實價

條件同日報：v3 在場、證交所成交金額 ≥ 20 日均 1.5 倍且收黑 → 隔天 08:45 開盤買近月，抱 10 個交易日收盤出（v3 出場提前出）；
每筆不重疊、扣 3 點×2；另列分段 1998–2007／2008–2016／2017–
用法：python -X utf8 backtest/research_172b_爆量收黑加碼長期勝率.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r141", os.path.join(HERE, "research_141_加碼總曝險上限.py"))
R141 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R141)
R139, R138, bt = R141.R139, R141.R138, R141.bt
COST, H = 3.0, 10


def main():
    dates, day, night, near = R139.load_tx()
    bi = {d: k for k, d in enumerate(R138.DAYS)}
    seq = [d for d in dates if d in bi]
    rows = []
    for k, d in enumerate(seq):
        i = bi[d]
        m = near[d]
        o, c = day[d][m][0], day[d][m][3]
        amts = [R139.AMT.get(R138.DAYS[j]) for j in range(i - 20, i)]
        amts = [a for a in amts if a]
        a0 = R139.AMT.get(d)
        vr = a0 / (sum(amts) / len(amts)) if a0 and len(amts) >= 16 else None
        rows.append(dict(d=d, m=m, o=o, c=c, st=R138.ST[i], v=vr is not None and vr >= 1.5 and bt.PX[i] < bt.PX[i - 1]))
    res = []
    k = 0
    n = len(rows)
    while k < n - 1:
        t = rows[k]
        if t["v"] and t["st"] == 1:
            j = k + 1
            m = rows[j]["m"]
            e = day[rows[j]["d"]][m][0]
            last = j
            for h in range(H):
                last = min(j + h, n - 1)
                if rows[last]["st"] == 0:
                    break
            px = day[rows[last]["d"]].get(m)
            x = px[3] if px else rows[last]["c"]
            res.append((rows[j]["d"], (x - e - 2 * COST) / e))
            k = last + 1
        else:
            k += 1
    out = ["研究 172b：爆量收黑加碼（v3 在場、1.5 倍量收黑 → 隔天開盤買台指期抱 10 天）長期勝率", ""]
    for lab, lo, hi in (("全期", "1998", "2100"), ("1998–2007", "1998", "2008"), ("2008–2016", "2008", "2017"), ("2017–", "2017", "2100")):
        x = np.array([r for d, r in res if lo <= d < hi])
        if len(x) == 0:
            out.append(f"{lab}：0 筆")
            continue
        out.append(f"{lab:10s} {len(x):3d} 筆  勝率 {np.mean(x > 0):.0%}  期望值每筆 {x.mean():+.2%}  平均賺 {x[x > 0].mean() if (x > 0).any() else 0:+.2%}／賠 {x[x <= 0].mean() if (x <= 0).any() else 0:+.2%}  最差 {x.min():+.1%}")
    out.append("")
    out.append("明細：" + "；".join(f"{d} {r:+.1%}" for d, r in res))
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究172b_爆量收黑加碼長期勝率.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
