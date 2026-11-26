"""研究 243：使用者選研究 216 (a)（85% 00631L＋15% 現金）後，期貨帳戶 15% 現金在原始保證金 9.2% 下約撐 1.6x 名目
主策略在場時 V（1x）、F（0.5x）、P（1x）、D（0.5x）同時持有可能超過；檢查：
(1) 在場時名目 > 1.0／1.5／1.6x 的天數與事件
(2) 上限 1.5x 的處理方式：新訊號超過上限就把新部位縮到剩餘額度（先到先得）vs 不做 P（P 只抱一晚、單筆期望值最小）
    與無上限比較年化／回檔（主策略 1.7x＋15% 現金）
用法：python -X utf8 backtest/research_243_保證金上限優先順序.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r216", os.path.join(HERE, "research_216_保證金現金配置.py"))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)
B = M.B
COST = 3.0


def main():
    T = B.R141.build()
    n = len(T)
    _, _, main_r, _ = B.R141.run(T, useV=False, useF=False)
    main_r = np.array(main_r)
    vf_r, fo = B.R152.run_vf(T)
    vf_u = np.array([x[0] for x in fo])
    base_u = np.array([b for _, b in fo])
    main_in = base_u > 0
    NN, SP = B.R142.night_series(T), B.R145.sp_series(T)
    o = np.array([t["o"] for t in T])
    c = np.array([t["c"] for t in T])
    rcc = np.array([t["rcc"] for t in T])
    roc, gap = c / o - 1, np.r_[0.0, o[1:] / c[:-1] - 1]
    psig = (NN <= -0.02) | (SP <= -0.02)
    g = np.nan_to_num(np.array([B.R205.GAP.get(t["d"], np.nan) for t in T]), nan=0.0)
    d_u = np.zeros(n)
    k = 0
    while k < n:
        if g[k] <= -0.10 and k + 1 < n:
            end = min(n - 1, k + 5)
            d_u[k + 1:end + 1] = 0.5
            k = end + 1
        else:
            k += 1
    # 每天（索引 1..n-1）持有的名目：vf_u[t-1] 是第 t 天開盤時 V+F；P 當天；D 當天
    vf = vf_u
    p = np.where(psig, 1.0, 0.0)[1:]
    d = d_u[1:]
    tot = vf + p + d
    days = [t["d"] for t in T][1:]
    L = ["研究 243：15% 現金保證金下的期貨名目上限（主策略在場時；2018-06～）", ""]
    for cap in (1.0, 1.5, 1.6):
        m = main_in & (tot > cap + 1e-9)
        L.append(f"在場時名目 > {cap}x：{m.sum()} 天（在場 {main_in.sum()} 天）；例：" + "、".join(days[i] for i in np.where(m)[0][:8]))
    combos = {}
    for i in np.where(main_in & (tot > 1.5 + 1e-9))[0]:
        key = "+".join(nm for nm, u in (("V/F", vf[i]), ("P", p[i]), ("D", d[i])) if u > 0)
        combos[key] = combos.get(key, 0) + 1
    L.append("超過 1.5x 的組合：" + "、".join(f"{k_} {v} 天" for k_, v in combos.items()))
    # 上限處理：P 的報酬（每單位）、D 的報酬（每單位）
    p_unit = np.zeros(n)
    pu = np.where(psig, 1.0, 0.0)
    pug = np.r_[0.0, pu[:-1]]
    p_unit = (pug * gap + pu * roc - np.abs(pu - pug) * COST / o)[1:]
    d_unit_full = M  # placeholder
    rc = B.bt.RC
    base = np.where(main_in, 0.85 * main_r + 0.15 * rc, main_r)
    vf_add = vf_r - main_r
    # D 每日報酬（0.5x）
    d_add = np.zeros(n)
    k = 0
    while k < n:
        if g[k] <= -0.10 and k + 1 < n:
            d_add[k + 1] += 0.5 * roc[k + 1] - 1.5 / o[k + 1]
            end = min(n - 1, k + 5)
            for j in range(k + 2, end + 1):
                d_add[j] += 0.5 * rcc[j]
            d_add[end] -= 1.5 / c[end]
            k = end + 1
        else:
            k += 1
    d_add = d_add[1:]

    def stats(r):
        e = np.cumprod(1 + r)
        return f"{e[-1] ** (B.bt.TD / len(r)) - 1:6.1%}／{(e / np.maximum.accumulate(e) - 1).min():6.1%}"

    L.append("\n【主策略 1.7x＋15% 現金，年化／回檔】")
    L.append(f"  無上限（理論）：{stats(base + vf_add + p_unit + d_add)}")
    # P 縮到剩餘額度（V/F/D 先持有）
    room = np.clip(1.5 - (vf + d), 0, 1.0)
    p_scale = np.where(main_in, np.minimum(1.0, room), 1.0)
    L.append(f"  上限 1.5x、P 縮到剩餘額度：{stats(base + vf_add + p_unit * p_scale + d_add)}（P 被縮 {int(((p > 0) & (p_scale < 1)).sum())} 次）")
    L.append(f"  在場時不做 P：{stats(base + vf_add + np.where(main_in, 0, p_unit) + d_add)}")
    L.append(f"  在場時 P 只做 0.5x：{stats(base + vf_add + np.where(main_in, 0.5, 1.0) * p_unit + d_add)}")
    txt = "\n".join(L)
    print(txt)
    open(os.path.join(HERE, "結果_研究243_保證金上限優先順序.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
