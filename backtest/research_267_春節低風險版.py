"""研究 267：春節加碼的低風險版本（接研究 263：春節 0.5x 會讓回檔 -24.9→-26.8%、最差單日 -9.9→-12.9%）
變體（錨點 L＝封關日，R＝開紅盤日＝L+1）：
  A 原版：L−3 收盤進、R+4 收盤出，u 0.5
  B 只在 v3 空手時做（L−3 收盤 v3 狀態＝0）
  C 不抱過年：L−3 收盤進、L 收盤出（PRE 3）
  D 原版 0.25x
  E 開紅盤當天收盤才進、R+4 收盤出（POST）
  ＋年底 0.5x（已上線）為新基準
用法：python -X utf8 backtest/research_267_春節低風險版.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r263", os.path.join(HERE, "research_263_節日加碼疊加.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
import research_138_金字塔加碼與分段停損 as R138  # noqa: E402


def ov(n, rcc, px, ks, u, a_off, b_off):
    add = np.zeros(n)
    for k in ks:
        a, b = k + a_off, k + b_off
        if a < 1 or b >= n:
            continue
        add[a + 1:b + 1] += u * rcc[a + 1:b + 1]
        add[a] -= u * R.COST / px[a]
        add[b] -= u * R.COST / px[b]
    return add


def variants(days, ks, st):
    out = [("A 原版 0.5x", ks, 0.5, -3, 5), ("B 只在 v3 空手 0.5x", [k for k in ks if st[k - 3] == 0], 0.5, -3, 5),
           ("C 不抱過年 0.5x（封關出）", ks, 0.5, -3, 0), ("D 原版 0.25x", ks, 0.25, -3, 5), ("E 開紅盤收盤進 0.5x", ks, 0.5, 0, 5)]
    return out


def main():
    L = ["研究 267：春節加碼低風險版本（基準＝現行＋年底 0.5x）", ""]
    # (A) 研究 216 引擎：重用 263 的 part_a 計算 base，這裡重寫一份精簡版
    B = R.B
    T = B.R141.build()
    n = len(T)
    days = [t["d"] for t in T]
    c = np.array([t["c"] for t in T])
    rcc = np.array([t["rcc"] for t in T])
    tmp = []
    R.part_a(tmp)  # 只為了確認引擎可跑；基準數字在 263
    # 取得 263 的基準報酬序列：重新計算（複製 part_a 前段）
    _, _, main_r, _ = B.R141.run(T, useV=False, useF=False)
    main_r = np.array(main_r)
    vf_r, fo = B.R152.run_vf(T)
    base_u = np.array([b for _, b in fo])
    NN, SP = B.R142.night_series(T), B.R145.sp_series(T)
    o = c * 0 + np.array([t["o"] for t in T])
    roc, gap = c / o - 1, np.r_[0.0, o[1:] / c[:-1] - 1]
    pu = np.where((NN <= -0.02) | (SP <= -0.02), 1.0, 0.0)
    pug = np.r_[0.0, pu[:-1]]
    p_add = (pug * gap + pu * roc - np.abs(pu - pug) * R.COST / o)[1:]
    g = np.nan_to_num(np.array([B.R205.GAP.get(d, np.nan) for d in days]), nan=0.0)
    d_add = np.zeros(n)
    k = 0
    while k < n:
        if g[k] <= -0.10 and k + 1 < n:
            d_add[k + 1] += 0.5 * roc[k + 1] - 0.5 * R.COST / o[k + 1]
            end = min(n - 1, k + 5)
            for j in range(k + 2, end + 1):
                d_add[j] += 0.5 * rcc[j]
            d_add[end] -= 0.5 * R.COST / c[end]
            k = end + 1
        else:
            k += 1
    main_in = base_u > 0
    base = np.where(main_in, 0.85 * main_r + 0.15 * B.bt.RC, main_r) + (vf_r - main_r) + p_add + d_add[1:]
    lun, ye = R.anchors(days)
    base = base + ov(n, rcc, c, ye, 0.5, -3, 5)[1:]
    st = np.r_[main_in, main_in[-1]].astype(int)
    cg, mdd, w = R.stats(base, B.bt.TD)
    L.append(f"(A) 2018-06～ 研究 216 引擎：基準 {cg:6.1%}／{mdd:6.1%}／最差單日 {w:+.1%}")
    for nm, ks, u, a0, b0 in variants(days, lun, st):
        r = base + ov(n, rcc, c, ks, u, a0, b0)[1:]
        cg, mdd, w = R.stats(r, B.bt.TD)
        L.append(f"  ＋{nm}（{len(ks)} 次）：{cg:6.1%}／{mdd:6.1%}／最差單日 {w:+.1%}")
    # (B) v3 2x 模型 2002～
    import strategy_v3 as V
    bt = V.bt
    _, _, e = V.run("2002-01-01", bt.DAYS[-1], curve=True)
    e = np.asarray(e)
    i0 = next(i for i, d in enumerate(bt.DAYS) if d >= "2002-01-01")
    dd = bt.DAYS[i0:i0 + len(e)]
    bb = np.r_[0.0, e[1:] / e[:-1] - 1]
    px = np.array(bt.PX[i0:i0 + len(e)])
    rc = np.r_[0.0, px[1:] / px[:-1] - 1]
    lun2, ye2 = R.anchors(dd)
    bb = bb + ov(len(e), rc, px, ye2, 0.5, -3, 5)
    st2 = np.array(R138.ST[i0:i0 + len(e)])
    seg = (("2002～", "2002", "2099"), ("2002–2012", "2002", "2012-12-31"), ("2013～", "2013", "2099"))

    def fmt(r):
        o_ = []
        for _, a, b in seg:
            m = np.array([a <= d <= b for d in dd])
            cg, mdd, _ = R.stats(r[m], bt.TD)
            o_.append(f"{cg:5.1%}／{mdd:6.1%}")
        return "｜".join(o_)
    L.append("\n(B) v3 2x 模型＋年底 0.5x：" + "｜".join(s[0] for s in seg))
    L.append(f"  基準：{fmt(bb)}")
    for nm, ks, u, a0, b0 in variants(dd, lun2, st2):
        L.append(f"  ＋{nm}（{len(ks)} 次）：{fmt(bb + ov(len(e), rc, px, ks, u, a0, b0))}")
    txt = "\n".join(L)
    print(txt)
    open(os.path.join(HERE, "結果_研究267_春節低風險版.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
