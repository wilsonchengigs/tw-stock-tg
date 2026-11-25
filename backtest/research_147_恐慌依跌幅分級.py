"""研究 147：候選 6 依跌幅分級加碼（研究 139：夜跌越深隔天反彈越大）

訊號強度 s＝max(−夜盤報酬, −S&P 報酬)；規則同研究 145（D 開盤進、D+1 開盤出、疊在現行 V+F 上，2018-06～）
方案：固定 0.5x（現行）／固定 1x／分級 A：s≥2% 0.5x、≥3% 1x／分級 B：≥2% 0.5x、≥3% 1x、≥4% 1.5x／分級 C：≥2% 0.25x、≥3% 0.75x、≥4% 1.25x
「同平均曝險」比較：每個方案另算年化÷平均加碼倍數（每單位曝險效率）
虛無：兩條序列一起環狀平移 400 次；比的是「分級 − 固定 0.5x」的年化差（看分級本身有沒有資訊），最小 p 值法
用法：python -X utf8 backtest/research_147_恐慌依跌幅分級.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r145", os.path.join(HERE, "research_145_恐慌隔天做多聯集版.py"))
R145 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R145)
R141, R142, bt = R145.R141, R145.R142, R145.bt
COST = 3.0
PLANS = {
    "固定0.5x": [(0.02, 0.5)],
    "固定1x": [(0.02, 1.0)],
    "分級A 2%:0.5 3%:1": [(0.02, 0.5), (0.03, 1.0)],
    "分級B +4%:1.5": [(0.02, 0.5), (0.03, 1.0), (0.04, 1.5)],
    "分級C 0.25/0.75/1.25": [(0.02, 0.25), (0.03, 0.75), (0.04, 1.25)],
}


def main():
    S = int(os.environ.get("R147_SHIFTS", "400"))
    T = R141.build()
    n = len(T)
    _, _, base_r, _ = R141.run(T)
    NN, SP = R142.night_series(T), R145.sp_series(T)
    o = np.array([t["o"] for t in T])
    c = np.array([t["c"] for t in T])
    roc = c / o - 1
    gap = np.r_[0.0, o[1:] / c[:-1] - 1]

    def one(nn, sp, plan):
        s = np.maximum(-nn, -sp)
        u = np.zeros(n)
        for th, size in plan:
            u = np.where(s >= th, size, u)
        ug = np.r_[0.0, u[:-1]]
        add = ug * gap + u * roc - np.abs(u - ug) * COST / o
        r = base_r + add[1:]
        e = np.cumprod(1 + r)
        return e[-1] ** (bt.TD / len(r)) - 1, (e / np.maximum.accumulate(e) - 1).min(), u[u > 0].mean() if (u > 0).any() else 0, int((u > 0).sum())

    real = {k: one(NN, SP, v) for k, v in PLANS.items()}
    rng = np.random.default_rng(147)
    shifts = rng.integers(20, n - 20, S)
    keys = [k for k in PLANS if k != "固定0.5x"]
    nulld = np.array([[one(np.roll(NN, s), np.roll(SP, s), PLANS[k])[0] - one(np.roll(NN, s), np.roll(SP, s), PLANS["固定0.5x"])[0] for k in keys] for s in shifts])
    reald = np.array([real[k][0] - real["固定0.5x"][0] for k in keys])
    single = (1 + (nulld >= reald).sum(axis=0)) / (S + 1)
    ranks = np.array([[(1 + np.sum(nulld[:, j] >= nulld[s, j])) / (S + 1) for j in range(len(keys))] for s in range(S)])
    minp = ranks.min(axis=1)
    e0 = np.cumprod(1 + base_r)
    out = [f"研究 147：恐慌隔天做多 依跌幅分級（{T[0]['d']}～{T[-1]['d']}；平移 {S} 次）",
           f"現行 V+F（不含候選 6）：{e0[-1] ** (bt.TD / len(base_r)) - 1:.1%}／{(e0 / np.maximum.accumulate(e0) - 1).min():.1%}", ""]
    for k, (cg, m, avg, cnt) in real.items():
        line = f"{k:22s} {cnt:3d} 天  {cg:6.1%}／{m:6.1%}  平均加碼 {avg:.2f}x  增量÷平均倍數 {(cg - (e0[-1] ** (bt.TD / len(base_r)) - 1)) / avg:+.2%}"
        if k in keys:
            j = keys.index(k)
            line += f"  比固定0.5x {reald[j]:+.2%}（平移中位 {np.median(nulld[:, j]):+.2%}，單組 p {single[j]:.3f}，家族 p {(1 + np.sum(minp <= single[j])) / (S + 1):.3f}）"
        out.append(line)
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究147_恐慌依跌幅分級.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
