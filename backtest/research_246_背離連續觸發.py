"""研究 246：D 台美背離加碼的連續觸發（比照研究 148 對 P）
台指期真實價 1998～ 64 筆（研究 211 方法、無停損）；叢集：與上一筆進場相隔 ≤ G 個交易日（G＝15／30）算同一叢集
比較叢集第 1 次 vs 第 2 次以上的每筆、勝率；兩段；以及「前一筆虧損」之後的下一筆
用法：python -X utf8 backtest/research_246_背離連續觸發.py
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
            ev.append((j, ds[j], R175.trade(day, night, ds, j, near[ds[k]], (last, "close"), None), g[k]))
            k = last + 1
        else:
            k += 1
    L = [f"研究 246：D 連續觸發（{len(ev)} 筆，台指期真實價、無停損）", ""]
    for G in (15, 30):
        rank = []
        for i, e in enumerate(ev):
            rank.append(1 if i == 0 or e[0] - ev[i - 1][0] > G else rank[-1] + 1)
        rank = np.array(rank)
        r = np.array([e[2] for e in ev])
        L.append(f"【叢集＝相隔 ≤{G} 個交易日】")
        for lab, m in (("第 1 次", rank == 1), ("第 2 次", rank == 2), ("第 3 次以上", rank >= 3), ("第 2 次以上", rank >= 2)):
            if m.sum():
                seg = [r[m & np.array([d < "2013" for _, d, _, _ in ev])], r[m & np.array([d >= "2013" for _, d, _, _ in ev])]]
                L.append(f"  {lab}：{m.sum()} 筆 每筆 {r[m].mean():+.2%} 勝率 {np.mean(r[m] > 0):.0%}  （1998–2012 {seg[0].mean() if len(seg[0]) else np.nan:+.2%}／{len(seg[0])}，2013～ {seg[1].mean() if len(seg[1]) else np.nan:+.2%}／{len(seg[1])}）")
    r = np.array([e[2] for e in ev])
    after_loss = np.array([r[i] for i in range(1, len(r)) if r[i - 1] < 0 and ev[i][0] - ev[i - 1][0] <= 30])
    after_win = np.array([r[i] for i in range(1, len(r)) if r[i - 1] > 0 and ev[i][0] - ev[i - 1][0] <= 30])
    L.append(f"\n30 天內、前一筆虧損之後：{len(after_loss)} 筆 每筆 {after_loss.mean():+.2%} 勝率 {np.mean(after_loss > 0):.0%}；前一筆獲利之後：{len(after_win)} 筆 {after_win.mean():+.2%} 勝率 {np.mean(after_win > 0):.0%}")
    L.append("\n近期：" + "、".join(f"{d} {x:+.1%}（背離 {gg:+.1%}）" for _, d, x, gg in ev[-6:]))
    txt = "\n".join(L)
    print(txt)
    open(os.path.join(HERE, "結果_研究246_背離連續觸發.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
