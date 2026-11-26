"""研究 242：5 年資產情境模擬（使用者 11/26 問：現有 100 萬、每年年底再存 100 萬，5 年後多少）
做法：每日報酬序列做平穩區塊拔靴（平均區塊 60 個交易日，保留崩跌／趨勢的連續性），抽 5 年（1,260 天）× 10,000 條
  A 只有主策略：v3 模型價 lev 1.7（85% 00631L，其餘現金），2002～2026
  B 主策略 1.7x＋期貨加碼（V+F+P+D；研究 214 的加碼損益），2018-06～2026（只有 8 年、含 2026 崩跌大賺，偏樂觀）
  C 同 A 但只抽 2002～2017（不含近年多頭，偏保守）
每年年底（第 252、504…天）存 100 萬；報告：5 年後總資產 中位／10／25／75／90 分位、虧本（< 600 萬）機率、期間帳面最大回檔中位與 10 分位
用法：python -X utf8 backtest/research_242_五年資產情境.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strategy_v3 as V  # noqa: E402

bt = V.bt


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def daily(start, end, lev):
    _, _, e = V.run(start, end, lev=lev, curve=True)
    e = np.asarray(e)
    i0 = next(i for i, d in enumerate(bt.DAYS) if d >= start)
    return e[1:] / e[:-1] - 1, bt.DAYS[i0 + 1:i0 + len(e)]


def boot(r, n_days=1260, paths=10000, L=60, seed=242):
    rng = np.random.default_rng(seed)
    n = len(r)
    out = np.empty((paths, n_days))
    p = 1 / L
    for k in range(paths):
        i = rng.integers(n)
        for t in range(n_days):
            out[k, t] = r[i]
            i = rng.integers(n) if rng.random() < p else (i + 1) % n
    return out


def wealth(R):
    paths, T = R.shape
    w = np.full(paths, 100.0)
    peak = w.copy()
    mdd = np.zeros(paths)
    for t in range(T):
        w = w * (1 + R[:, t])
        peak = np.maximum(peak, w)
        mdd = np.minimum(mdd, w / peak - 1)
        if (t + 1) % 252 == 0:
            w = w + 100
            peak = np.maximum(peak, w)
    return w, mdd


def main():
    rA, dA = daily("2002-01-01", bt.DAYS[-1], 1.7)
    rC = rA[[d < "2018-01-01" for d in dA]]
    R214 = load("r214", "research_214_全部規則合計.py")
    B = R214.B
    T = B.R141.build()
    _, _, main2, _ = B.R141.run(T, useV=False, useF=False)
    main2 = np.array(main2)
    vf_r, fo = B.R152.run_vf(T)
    NN, SP = B.R142.night_series(T), B.R145.sp_series(T)
    o = np.array([t["o"] for t in T])
    c = np.array([t["c"] for t in T])
    rcc = np.array([t["rcc"] for t in T])
    roc, gap = c / o - 1, np.r_[0.0, o[1:] / c[:-1] - 1]
    pu = np.where((NN <= -0.02) | (SP <= -0.02), 1.0, 0.0)
    pug = np.r_[0.0, pu[:-1]]
    p_add = (pug * gap + pu * roc - np.abs(pu - pug) * 3 / o)[1:]
    g = np.nan_to_num(np.array([B.R205.GAP.get(t["d"], np.nan) for t in T]), nan=0.0)
    d_add = np.zeros(len(T))
    k = 0
    while k < len(T):
        if g[k] <= -0.10 and k + 1 < len(T):
            d_add[k + 1] += 0.5 * roc[k + 1] - 1.5 / o[k + 1]
            end = min(len(T) - 1, k + 5)
            for j in range(k + 2, end + 1):
                d_add[j] += 0.5 * rcc[j]
            d_add[end] -= 1.5 / c[end]
            k = end + 1
        else:
            k += 1
    main_in = np.array([b for _, b in fo]) > 0
    rc = bt.RC
    rB = np.where(main_in, 0.85 * main2 + 0.15 * rc, main2) + (vf_r - main2) + p_add + d_add[1:]
    L = ["研究 242：5 年資產情境（現有 100 萬、每年年底存 100 萬、共投入 600 萬；區塊拔靴 10,000 條、平均區塊 60 天）", ""]
    for lab, r in (("A 只有主策略 1.7x（2002～2026 抽樣）", rA), ("B 主策略 1.7x＋期貨加碼（2018-06～2026 抽樣，偏樂觀）", rB),
                   ("C 只有主策略 1.7x（2002～2017 抽樣，不含近年多頭，偏保守）", rC)):
        e = np.prod(1 + r) ** (bt.TD / len(r)) - 1
        w, mdd = wealth(boot(r))
        q = np.quantile(w, [0.1, 0.25, 0.5, 0.75, 0.9])
        L.append(f"【{lab}】歷史年化 {e:.1%}")
        L.append(f"  5 年後總資產：10 分位 {q[0]:,.0f} 萬｜25 分位 {q[1]:,.0f}｜中位 {q[2]:,.0f}｜75 分位 {q[3]:,.0f}｜90 分位 {q[4]:,.0f} 萬")
        L.append(f"  低於投入 600 萬的機率 {np.mean(w < 600):.0%}；期間帳面最大回檔 中位 {np.median(mdd):.0%}、最差 10% 路徑 ≤ {np.quantile(mdd, 0.1):.0%}")
    txt = "\n".join(L)
    print(txt)
    open(os.path.join(HERE, "結果_研究242_五年資產情境.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
