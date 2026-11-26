"""研究 181：恐慌隔天做多依觸發類型調整倍數（研究 158：只有 S&P 觸發 61 筆每筆 +0.20%，夜盤觸發 +0.94%～+1.06%）

類型（2017-05～，有夜盤）：N＝夜盤跌 ≥2%（含雙觸發）；S＝只有 S&P 跌 ≥2%（夜盤沒跌到 2%）
(A) 單筆：S 類 D 開→D+1 開 的每筆、勝率、比同波動度（2000 次）p
(B) 組合（研究 171 引擎，2018-06～，v3＋V＋F＋P）：N 類固定 1x，S 類 1x（現行）／0.5x／0 → 年化、回檔；
    兩條序列一起環狀平移 300 次，比「S 類降倍 − 現行」看降倍本身有沒有資訊
(C) 夜盤前（1998～2017）所有觸發都是 S&P 類，研究 144 樣本外 +0.50%——S 類變弱是否因為夜盤已先反映：S 類當晚夜盤的平均跌幅
用法：python -X utf8 backtest/research_181_恐慌觸發類型倍數.py
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


R171 = load("r171", "research_171_全部加碼疊加壓力測試.py")
R141, R142, R145, bt = R171.R141, R171.R142, R171.R145, R171.bt
COST = R141.COST


def run_sized(T, size):
    """研究 171 run 的 P 改成每天的倍數陣列 size"""
    eq, peak, mdd = 1.0, 1.0, 0.0
    base = 0.0
    hold = {"V": None, "F": None}
    uprev = 0.0
    rets = []
    for k in range(1, len(T)):
        t, y = T[k], T[k - 1]
        r = base / 2 * t["r2"] + (1 - base / 2) * bt.RC
        for key, h in hold.items():
            if h is None:
                continue
            r += h[0] * (t["roc"] if h[2] else t["rcc"])
            if h[2]:
                r -= h[0] * COST / t["o"]
                h[2] = False
            h[1] -= 1
        u = size[k]
        gap = t["o"] / y["c"] - 1
        r += uprev * gap + u * t["roc"] - abs(u - uprev) * COST / t["o"]
        uprev = u
        for key in hold:
            h = hold[key]
            if h is not None and (h[1] <= 0 or t["st"] == 0):
                r -= h[0] * COST / t["c"]
                hold[key] = None
        nb = 2.0 * y["st"]
        if nb != base:
            r -= bt.COST * abs(nb - base)
            base = nb
        eq *= 1 + r
        rets.append(r)
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        for key, flag, add, H in (("V", t["vsig"], 1.0, 10), ("F", t["fsig"], 0.5, 5)):
            if flag and t["st"] == 1 and hold[key] is None:
                hold[key] = [add, H, True]
    return eq ** (bt.TD / len(rets)) - 1, mdd


def main():
    T = R141.build()
    n = len(T)
    NN, SP = R142.night_series(T), R145.sp_series(T)
    nN = NN <= -0.02
    sS = (SP <= -0.02) & ~nN
    out = ["研究 181：恐慌做多依觸發類型調整倍數（2018-06～ 組合）", ""]
    # (A)（用研究 171 的 T：D 開→D+1 開）
    o = np.array([t["o"] for t in T])
    r = np.r_[o[1:] / o[:-1] - 1 - 2 * COST / o[:-1], np.nan]
    for lab, m in (("N 夜盤觸發（含雙觸發）", nN), ("S 只有 S&P 觸發", sS)):
        x = r[m & ~np.isnan(r)]
        out.append(f"{lab}：{len(x)} 筆 每筆 {x.mean():+.2%} 勝率 {np.mean(x > 0):.0%} 最差 {x.min():+.1%}")
    out.append(f"S 類當晚夜盤平均 {np.nanmean(NN[sS]):+.2%}（S&P 跌 ≥2% 但夜盤只跌這麼多＝衝擊已被吸收一部分）")
    out.append("")
    # (B)
    plans = {"現行 N 1x／S 1x": (1.0, 1.0), "S 降 0.5x": (1.0, 0.5), "S 不做": (1.0, 0.0), "N 1.5x／S 0.5x（同平均曝險附近）": (1.5, 0.5)}

    def sizes(nm, ss, a, b):
        return np.where(nm, a, np.where(ss, b, 0.0))
    res = {k: run_sized(T, sizes(nN, sS, *v)) for k, v in plans.items()}
    base = res["現行 N 1x／S 1x"][0]
    rng = np.random.default_rng(181)
    shifts = rng.integers(20, n - 20, 300)
    out.append("== (B) 組合（v3＋V＋F＋P）==")
    for k, (cg, md) in res.items():
        line = f"{k:30s} 年化 {cg:.1%}／回檔 {md:.1%}"
        if k != "現行 N 1x／S 1x":
            d = cg - base
            nd = []
            for s in shifts:
                a_, b_ = np.roll(nN, s), np.roll(sS, s)
                nd.append(run_sized(T, sizes(a_, b_, *plans[k]))[0] - run_sized(T, sizes(a_, b_, 1.0, 1.0))[0])
            nd = np.array(nd)
            line += f"（差 {d:+.2%}；平移中位 {np.median(nd):+.2%}、單尾 p {(1 + np.sum(nd >= d)) / (len(nd) + 1):.3f}）"
        out.append(line)
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究181_恐慌觸發類型倍數.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
