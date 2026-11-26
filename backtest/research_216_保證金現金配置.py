"""研究 216：實際資金配置——主策略在場時 00631L 吃滿資金，台指期加碼（V 1x、F 0.5x、P 1x、D 0.5x）的保證金從哪來
期交所 2026-11-26 臺股期貨：原始 701,000、維持 538,000；一口名目 38,173×200＝763 萬 → 原始 9.2%、維持 7.0%（高波動期、偏保守）
(1) 每段期貨持有（連續有部位的日子）所需現金＝max(原始 9.2%×進場時名目, 期間每天 維持 7.0%×名目 − 累積損益)，以「總資金」為單位；
    分主策略在場／空手（空手時資金全是現金，不成問題）
(2) 主策略在場時預留現金 c（00631L 只用 1−c，主策略曝險 2(1−c)）對 V+F+P+D 年化與回檔的影響；c＝0／10／15／20／30%
(3) 替代：主策略改用台指期 2x（研究 192：成本與 00631L 打平），全部資金在期貨帳戶，最高名目 4x 時保證金約 37%
用法：python -X utf8 backtest/research_216_保證金現金配置.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r214", os.path.join(HERE, "research_214_全部規則合計.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
B = R.B
COST = 3.0
IM, MM = 0.092, 0.070


def main():
    T = B.R141.build()
    n = len(T)
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
    g = np.nan_to_num(np.array([B.R205.GAP.get(t["d"], np.nan) for t in T]), nan=0.0)
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
    fut_r = (vf_r - main_r) + p_add + d_add[1:]          # 期貨損益（占總資金）
    units = vf_u + pu[1:] + d_u[1:]                     # 當天持有名目倍數
    main_in = base_u > 0
    # (1) 每段持有所需現金
    eps, cur = [], None
    for t in range(n - 1):
        if units[t] > 0:
            if cur is None:
                cur = {"s": t, "cum": 0.0, "need": IM * units[t], "in": main_in[t]}
            cur["cum"] += fut_r[t]
            cur["need"] = max(cur["need"], MM * units[t] - cur["cum"], IM * units[t] if t == cur["s"] else 0)
            cur["in"] = cur["in"] or main_in[t]
        elif cur is not None:
            cur["e"] = t - 1
            eps.append(cur)
            cur = None
    L = [f"研究 216：台指期加碼的保證金與現金配置（{T[0]['d']}～{T[-1]['d']}；原始 {IM:.1%}／維持 {MM:.1%}）", ""]
    for lab, sel in (("主策略在場時", True), ("主策略空手時", False)):
        need = np.array([e["need"] for e in eps if e["in"] == sel])
        worst = max((e for e in eps if e["in"] == sel), key=lambda e: e["need"], default=None)
        if len(need):
            L.append(f"{lab}：{len(need)} 段期貨持有；所需現金（占總資金）中位 {np.median(need):.1%}、90 分位 {np.quantile(need, 0.9):.1%}、最大 {need.max():.1%}"
                     + (f"（{T[worst['s'] + 1]['d']} 起）" if worst else ""))
    L.append(f"最高名目：主策略在場時 {units[main_in].max():.1f}x、空手時 {units[~main_in].max():.1f}x")
    # (2) 預留現金 c
    L.append("\n【主策略在場時預留現金 c（00631L 只買 1−c）：V+F+P+D 年化／最大回檔】")
    rc = B.bt.RC
    for cc in (0.0, 0.10, 0.15, 0.20, 0.30):
        r = (1 - cc) * main_r + cc * rc * np.ones_like(main_r)
        r = np.where(main_in, r, main_r) + fut_r
        e = np.cumprod(1 + r)
        cg = e[-1] ** (B.bt.TD / len(r)) - 1
        mdd = (e / np.maximum.accumulate(e) - 1).min()
        short = np.array([e_["need"] for e_ in eps if e_["in"]])
        L.append(f"  c {cc:4.0%}（主策略 {2 * (1 - cc):.1f}x）：{cg:6.1%}／{mdd:6.1%}；在場時期貨持有段中現金不足的段數 {int((short > cc).sum())}／{len(short)}")
    L.append("\n【替代：主策略用台指期 2x（研究 192 成本打平）】全部資金在期貨帳戶：最高名目 "
             f"{(units + base_u).max():.1f}x → 原始保證金約 {IM * (units + base_u).max():.0%}，其餘現金可吸收損益；"
             "缺點是一口大台 763 萬，資金小於約 400 萬時 2x 要用小台（190 萬）／微台（38 萬）湊")
    txt = "\n".join(L)
    print(txt)
    open(os.path.join(HERE, "結果_研究216_保證金現金配置.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
