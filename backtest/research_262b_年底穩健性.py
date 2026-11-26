"""研究 262b：年底效應（12 月最後一個交易日 L）的鄰近參數、逐年、台指期真實價、v3 狀態
用法：python -X utf8 backtest/research_262b_年底穩健性.py
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


R = load("r262", "research_262_連假效應.py")
R175 = load("r175", "research_175_加碼規則停損.py")
DAYS, win, YE = R.DAYS, R.win, R.YE
out = ["研究 262b：年底效應穩健性", "", "(1) 每筆 全期/2013～；列＝12 月最後交易日前 p 天收盤買，欄＝1 月第 q+1 個交易日收盤出（q=0 元月第一天）"]
out.append("p\q " + " ".join(f"{q:>13d}" for q in (0, 1, 2, 3, 4, 6, 9)))
for p in (0, 1, 2, 3, 4, 5, 7, 10):
    row = []
    for q in (0, 1, 2, 3, 4, 6, 9):
        x = np.array([win(k - p, k + 1 + q) for k in YE if k + 1 + q < R.N])
        y = np.array([win(k - p, k + 1 + q) for k in YE if k + 1 + q < R.N and DAYS[k] > "2013"])
        row.append(f"{x.mean():+5.1%}/{y.mean():+5.1%}")
    out.append(f"{p:>3d} " + " ".join(f"{c:>13s}" for c in row))
out.append("")
out.append("逐年 p3 q4（加權）：" + "、".join(f"{DAYS[k][:4]} {win(k - 3, k + 5):+.1%}" for k in YE if k + 5 < R.N))
dates, day, night, near = R175.R139.load_tx()
pos = {d: i for i, d in enumerate(dates)}
ST = dict(zip(R175.R138.DAYS, R175.R138.ST))
for p, q in ((3, 4), (5, 4), (3, 2)):
    rs, lab = [], []
    for k in YE:
        if DAYS[k - p] not in pos or DAYS[k] not in pos:
            continue
        j, last = pos[DAYS[k - p]] + 1, pos[DAYS[k]] + 1 + q
        if last >= len(dates):
            continue
        rs.append(R175.trade(day, night, dates, j, near[DAYS[k - p]], (last, "close"), None))
        lab.append(DAYS[k])
    rs = np.array(rs)
    on = np.array([ST.get(d, 0) == 1 for d in lab])
    late = np.array([d > "2013" for d in lab])
    out.append(f"台指期真實價 p{p} q{q}：{len(rs)} 筆 每筆 {rs.mean():+.2%} 勝率 {np.mean(rs > 0):.0%} 最差 {rs.min():+.1%}｜2013～ {rs[late].mean():+.2%}（{late.sum()}）｜v3 在場 {rs[on].mean():+.2%}（{on.sum()}）空手 {rs[~on].mean():+.2%}（{(~on).sum()}）")
txt = "\n".join(out)
print(txt)
open(os.path.join(HERE, "結果_研究262b_年底穩健性.txt"), "w", encoding="utf-8").write(txt + "\n")
