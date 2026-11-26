"""研究 211：D 台美背離加碼（研究 205c：背離 ≤-10% → 隔天開盤進、抱 5 個交易日收盤出、持有中不重複）的停損
方法同研究 175（台指期近月真實價 1998-07～、日盤低點與夜盤低點觸價、跳空用開盤價、換月銜接、每筆扣 6 點）
停損：無／3／4／5／7／10%；另列 2018-06 前後
用法：python -X utf8 backtest/research_211_台美背離停損.py
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


R175 = load("r175", "research_175_加碼規則停損.py")
R205 = load("r205", "research_205_台美背離台指期部位.py")
STOPS = (None, 0.03, 0.04, 0.05, 0.07, 0.10)


def main():
    dates, day, night, near = R175.R139.load_tx()
    bi = set(R175.R138.DAYS)
    ds = [d for d in dates if d in bi]
    n = len(ds)
    g = np.array([R205.GAP.get(d, np.nan) for d in ds])
    ev, k = [], 0
    while k < n - 2:
        if g[k] <= -0.10:
            j = k + 1
            last = min(j + 4, n - 1)
            ev.append((j, near[ds[k]], (last, "close")))
            k = last + 1
        else:
            k += 1
    out = [f"研究 211：D 台美背離加碼的停損（{len(ev)} 筆，{ds[ev[0][0]]}～{ds[ev[-1][0]]}；台指期真實價、日盤＋夜盤觸價、每筆扣 6 點）", ""]
    for lab, sel in (("全部", lambda d: True), ("1998～2018-05", lambda d: d < "2018-06"), ("2018-06～", lambda d: d >= "2018-06")):
        sub = [e for e in ev if sel(ds[e[0]])]
        out.append(f"== {lab}：{len(sub)} 筆 ==")
        out.append(f"{'停損':>6s} {'每筆':>7s} {'勝率':>5s} {'最差':>7s} {'觸發':>5s} {'累積(1x)':>9s}")
        for s in STOPS:
            rs = np.array([R175.trade(day, night, ds, j, m, hl, s) for j, m, hl in sub])
            hit = int(np.sum(rs <= -s + 0.0005)) if s else 0
            out.append(f"{'無' if s is None else f'{s:.0%}':>6s} {rs.mean():+7.2%} {np.mean(rs > 0):5.0%} {rs.min():+7.1%} {hit:5d} {np.prod(1 + rs) - 1:+9.0%}")
        out.append("")
    rs = [R175.trade(day, night, ds, j, m, hl, None) for j, m, hl in ev]
    out.append("逐筆（無停損）：" + "、".join(f"{ds[j]} {r:+.1%}" for (j, _, _), r in zip(ev, rs)))
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究211_台美背離停損.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
