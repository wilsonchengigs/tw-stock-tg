"""研究 261b：春節效應的鄰近參數、台指期真實價、主策略狀態拆分
(1) 進場 L−p（p 1～6）× 出場 R+q（q 0～6）每筆與 2013～ 每筆
(2) 台指期近月真實價（研究 175 trade：L−p+1 開盤進 ≈ L−p 收盤後、R+q 收盤出、換月銜接、扣 6 點）
(3) v3 在場／空手拆分、逐筆最差
用法：python -X utf8 backtest/research_261b_春節穩健性.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


R = load("r261", "research_261_春節效應.py")
R175 = load("r175", "research_175_加碼規則停損.py")
DAYS, PX, L_IDX, win = R.DAYS, R.PX, R.L_IDX, R.win
out = ["研究 261b：春節效應穩健性", "", "(1) 每筆（全期／2013～），列＝買在封關前 p 天收盤，欄＝賣在開紅盤後第 q 天收盤（q=0 開紅盤當天）"]
out.append("p\q " + " ".join(f"{q:>13d}" for q in range(7)))
for p in range(0, 7):
    row = []
    for q in range(7):
        x = np.array([win(k - p, k + 1 + q) for k in L_IDX])
        y = np.array([win(k - p, k + 1 + q) for k in L_IDX if DAYS[k] > "2013"])
        row.append(f"{x.mean():+5.1%}/{y.mean():+5.1%}")
    out.append(f"{p:>3d} " + " ".join(f"{c:>13s}" for c in row))
out.append("")
dates, day, night, near = R175.R139.load_tx()
pos = {d: i for i, d in enumerate(dates)}
ST = dict(zip(R175.R138.DAYS, R175.R138.ST))
for p, q in ((3, 4), (3, 0), (5, 4), (2, 3)):
    rs, lab = [], []
    for k in L_IDX:
        dL = DAYS[k]
        if dL not in pos or DAYS[k - p] not in pos:
            continue
        j = pos[DAYS[k - p]] + 1
        last = pos[dL] + 1 + q
        if last >= len(dates):
            continue
        m = near[DAYS[k - p]]
        rs.append(R175.trade(day, night, dates, j, m, (last, "close"), None))
        lab.append(dL)
    rs = np.array(rs)
    on = np.array([ST.get(d, 0) == 1 for d in lab])
    late = np.array([d > "2013" for d in lab])
    out.append(f"(2) 台指期真實價 p{p} q{q}：{len(rs)} 筆 每筆 {rs.mean():+.2%} 勝率 {np.mean(rs > 0):.0%} 最差 {rs.min():+.1%}｜2013～ {rs[late].mean():+.2%}（{late.sum()} 筆）｜v3 在場 {rs[on].mean():+.2%}（{on.sum()}）空手 {rs[~on].mean():+.2%}（{(~on).sum()}）")
    if (p, q) == (3, 4):
        out.append("    逐筆：" + "、".join(f"{d[:4]} {r:+.1%}" for d, r in zip(lab, rs)))
txt = "\n".join(out)
print(txt)
open(os.path.join(HERE, "結果_研究261b_春節穩健性.txt"), "w", encoding="utf-8").write(txt + "\n")
