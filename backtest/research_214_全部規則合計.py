"""研究 214：全部上線規則合計（V 爆量收黑 1x、F 外資雙指標 0.5x、P 恐慌隔天做多 1x、D 台美背離 0.5x 隔天開盤進抱 5 天）
引擎同研究 152／205c（2018-06～，00631L＋台指期真實價，不含停損）；比較 V+F、V+F+P、V+F+P+D：
年化、最大回檔、最差單日、最差 5 日、最高曝險、曝險 ≥3x 天數、逐年報酬
用法：python -X utf8 backtest/research_214_全部規則合計.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r205b", os.path.join(HERE, "research_205b_台美背離_含P基準.py"))
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
COST = 3.0


def main():
    T = B.R141.build()
    n = len(T)
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
    d_add = np.zeros(n)
    d_u = np.zeros(n)  # 收盤時持有的 D 倍數
    k = 0
    while k < n:
        if g[k] <= -0.10 and k + 1 < n:
            d_add[k + 1] += 0.5 * roc[k + 1] - 0.5 * COST / o[k + 1]
            end = min(n - 1, k + 5)
            d_u[k + 1:end] = 0.5
            for j in range(k + 2, end + 1):
                d_add[j] += 0.5 * rcc[j]
            d_add[end] -= 0.5 * COST / c[end]
            k = end + 1
        else:
            k += 1
    d_add = d_add[1:]
    yrs = np.array([t["d"][:4] for t in T])[1:]
    out = [f"研究 214：全部上線規則合計（{T[0]['d']}～{T[-1]['d']}）", ""]
    for lab, r, ex in (("V+F", vf_r, base_u + vf_u), ("V+F+P", vf_r + p_add, base_u + vf_u + pu[1:]),
                       ("V+F+P+D", vf_r + p_add + d_add, base_u + vf_u + pu[1:] + d_u[1:])):
        e = np.cumprod(1 + r)
        cg = e[-1] ** (B.bt.TD / len(r)) - 1
        mdd = (e / np.maximum.accumulate(e) - 1).min()
        w5 = (e[5:] / e[:-5] - 1).min()
        out.append(f"{lab:8s} 年化 {cg:6.1%}  最大回檔 {mdd:6.1%}  最差單日 {r.min():+.1%}  最差 5 日 {w5:+.1%}  最高曝險 {ex.max():.1f}x  ≥3x {int((ex >= 3).sum())} 天")
        out.append("         逐年：" + "  ".join(f"{y}:{np.prod(1 + r[yrs == y]) - 1:+.0%}" for y in sorted(set(yrs))))
    both = (pu[1:] > 0) & (d_u[1:] > 0)
    out.append(f"\nP 與 D 同時持有 {both.sum()} 天；D 持有時主策略也在場 {int(((d_u[1:] > 0) & (base_u > 0)).sum())} 天")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究214_全部規則合計.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
