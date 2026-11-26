"""研究 263：春節（研究 261）＋年底（研究 262）加碼疊在現行全部規則上
規則：錨點 L（春節封關日／12 月最後交易日）前 3 個交易日收盤進台指期 u 倍，R（L 的下一交易日）後第 4 個交易日收盤出；每邊 3 點
(A) 研究 216 引擎（2018-06～，台指期真實價）：主策略 85% 00631L＋15% 現金、V+F+P+D 為基準，加 春節／年底／兩者 × u 0.5／1
(B) v3 2x 模型（2002～，加權收盤對收盤）：基準 v3，加同上；全期／2002–2012／2013～
另列：節日部位持有期間與其他加碼重疊時的最高總名目
用法：python -X utf8 backtest/research_263_節日加碼疊加.py
"""
import datetime as dtm
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


R216 = load("r216", "research_216_保證金現金配置.py")
B = R216.B
COST = 3.0


def anchors(days):
    lun, ye = [], []
    for k in range(len(days) - 1):
        a, b = dtm.date.fromisoformat(days[k]), dtm.date.fromisoformat(days[k + 1])
        if (b - a).days >= 6 and a.month in (1, 2):
            lun.append(k)
        if a.month == 12 and b.year > a.year:
            ye.append(k)
    return lun, ye


def overlay(n, rcc, px, ks, u):
    add, pos = np.zeros(n), np.zeros(n)
    for k in ks:
        a, b = k - 3, k + 5
        if a < 1 or b >= n:
            continue
        add[a + 1:b + 1] += u * rcc[a + 1:b + 1]
        add[a] -= u * COST / px[a]
        add[b] -= u * COST / px[b]
        pos[a + 1:b + 1] += u
    return add, pos


def stats(r, td):
    e = np.cumprod(1 + r)
    return e[-1] ** (td / len(r)) - 1, (e / np.maximum.accumulate(e) - 1).min(), r.min()


def part_a(L):
    T = B.R141.build()
    n = len(T)
    days = [t["d"] for t in T]
    # 重建研究 216 c=15% 的總報酬（複製 216 的計算）
    _, _, main_r, _ = B.R141.run(T, useV=False, useF=False)
    main_r = np.array(main_r)
    vf_r, fo = B.R152.run_vf(T)
    vf_u = np.array([x[0] for x in fo])
    base_u = np.array([b for _, b in fo])
    NN, SP = B.R142.night_series(T), B.R145.sp_series(T)
    o = np.array([t["o"] for t in T])
    c = np.array([t["c"] for t in T])
    rcc = np.array([t["rcc"] for t in T])
    roc, gap = c / o - 1, np.r_[0.0, o[1:] / c[:-1] - 1]
    pu = np.where((NN <= -0.02) | (SP <= -0.02), 1.0, 0.0)
    pug = np.r_[0.0, pu[:-1]]
    p_add = (pug * gap + pu * roc - np.abs(pu - pug) * COST / o)[1:]
    g = np.nan_to_num(np.array([B.R205.GAP.get(d, np.nan) for d in days]), nan=0.0)
    d_add, d_u = np.zeros(n), np.zeros(n)
    k = 0
    while k < n:
        if g[k] <= -0.10 and k + 1 < n:
            d_add[k + 1] += 0.5 * roc[k + 1] - 0.5 * COST / o[k + 1]
            end = min(n - 1, k + 5)
            d_u[k + 1:end + 1] = 0.5
            for j in range(k + 2, end + 1):
                d_add[j] += 0.5 * rcc[j]
            d_add[end] -= 0.5 * COST / c[end]
            k = end + 1
        else:
            k += 1
    main_in = base_u > 0
    fut_r = (vf_r - main_r) + p_add + d_add[1:]
    units = vf_u + pu[1:] + d_u[1:]
    base = np.where(main_in, 0.85 * main_r + 0.15 * B.bt.RC, main_r) + fut_r
    lun, ye = anchors(days)
    L.append(f"(A) 研究 216 引擎 {days[0]}～{days[-1]}：春節 {len(lun)} 次、年底 {len(ye)} 次")
    cg, mdd, worst = stats(base, B.bt.TD)
    L.append(f"  基準（85% 00631L＋V+F+P+D）：{cg:6.1%}／{mdd:6.1%}／最差單日 {worst:+.1%}")
    for lab, ks in (("＋春節", lun), ("＋年底", ye), ("＋春節＋年底", lun + ye)):
        for u in (0.5, 1.0):
            add, pos = overlay(n, rcc, c, ks, u)
            r = base + add[1:]
            cg, mdd, worst = stats(r, B.bt.TD)
            tot = (units + 1.7 * main_in + pos[1:])
            L.append(f"  {lab} {u}x：{cg:6.1%}／{mdd:6.1%}／最差單日 {worst:+.1%}；節日持有中最高總名目 {tot[pos[1:] > 0].max():.1f}x")


def part_b(L):
    V = B.R141.R138.V if hasattr(B.R141.R138, "V") else None
    import strategy_v3 as V  # noqa: E402
    bt = V.bt
    _, _, e = V.run("2002-01-01", bt.DAYS[-1], curve=True)
    e = np.asarray(e)
    i0 = next(i for i, d in enumerate(bt.DAYS) if d >= "2002-01-01")
    days = bt.DAYS[i0:i0 + len(e)]
    base = np.r_[0.0, e[1:] / e[:-1] - 1]
    px = np.array(bt.PX[i0:i0 + len(e)])
    rcc = np.r_[0.0, px[1:] / px[:-1] - 1]
    lun, ye = anchors(days)
    seg = (("2002～", "2002", "2099"), ("2002–2012", "2002", "2012-12-31"), ("2013～", "2013", "2099"))

    def fmt(r):
        out = []
        for _, a, b in seg:
            m = np.array([a <= d <= b for d in days])
            cg, mdd, _ = stats(r[m], bt.TD)
            out.append(f"{cg:5.1%}／{mdd:6.1%}")
        return "｜".join(out)
    L.append("\n(B) v3 2x 模型（加權收盤對收盤）：" + "｜".join(s[0] for s in seg))
    L.append(f"  基準 v3：{fmt(base)}")
    for lab, ks in (("＋春節", lun), ("＋年底", ye), ("＋春節＋年底", lun + ye)):
        for u in (0.5, 1.0):
            add, _ = overlay(len(e), rcc, px, ks, u)
            L.append(f"  {lab} {u}x：{fmt(base + add)}")


def main():
    L = ["研究 263：春節＋年底加碼疊在現行規則上（封關／年底前 3 天收盤進、之後第 4 個交易日收盤出）", ""]
    part_a(L)
    part_b(L)
    txt = "\n".join(L)
    print(txt)
    open(os.path.join(HERE, "結果_研究263_節日加碼疊加.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
