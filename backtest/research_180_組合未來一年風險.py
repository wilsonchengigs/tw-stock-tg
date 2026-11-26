"""研究 180：現行組合「未來一年」的報酬與回檔分布（讓使用者對波動有實際預期）

兩個來源：
  (1) 現行全組合（v3＋V 1x＋F 0.5x＋P 1x；研究 171 引擎、00631L＋台指期真實價，2018-06～）的每日報酬
  (2) v3 主策略長期（1997～，研究 138 引擎，模擬正2）——含 2000、2008 兩次大空頭，比較保守
方法：定態區塊拔靴（平均區塊 60 天）抽 250 個交易日 × 5000 次 → 一年報酬分位、一年內最大回檔分位、P(一年虧損)、P(回檔 >30%／40%)
另外：三年期（750 天）
注意：2018～2026 剛好大多頭，(1) 偏樂觀；(2) 沒有加碼規則，但涵蓋更多空頭
用法：python -X utf8 backtest/research_180_組合未來一年風險.py
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
R138 = load("r138", "research_138_金字塔加碼與分段停損.py")


def boot(r, H, B=5000, L=60, seed=180):
    r = np.asarray(r)
    n = len(r)
    rng = np.random.default_rng(seed)
    tot, mdd = np.empty(B), np.empty(B)
    for b in range(B):
        idx = np.empty(H, int)
        i = rng.integers(n)
        for k in range(H):
            if k == 0 or rng.random() < 1 / L:
                i = rng.integers(n)
            else:
                i = (i + 1) % n
            idx[k] = i
        e = np.cumprod(1 + r[idx])
        tot[b] = e[-1] - 1
        mdd[b] = (e / np.maximum.accumulate(np.r_[1.0, e])[1:] - 1).min()
    return tot, mdd


def summarize(lab, r, out):
    for H, hl in ((250, "一年"), (750, "三年")):
        tot, mdd = boot(r, H)
        q = np.percentile(tot, [5, 25, 50, 75, 95])
        m = np.percentile(mdd, [50, 10, 5])
        out.append(f"{lab}｜{hl}：報酬 5／25／50／75／95 分位 {q[0]:+.0%}／{q[1]:+.0%}／{q[2]:+.0%}／{q[3]:+.0%}／{q[4]:+.0%}；"
                   f"P(虧損) {np.mean(tot < 0):.0%}；期間最大回檔 中位 {m[0]:.0%}、最差 10% {m[1]:.0%}、最差 5% {m[2]:.0%}；"
                   f"P(回檔 >30%) {np.mean(mdd < -0.3):.0%}、P(>40%) {np.mean(mdd < -0.4):.0%}")


def main():
    T = R171.R141.build()
    NN, SP = R171.R142.night_series(T), R171.R145.sp_series(T)
    P = np.maximum(-NN, -SP) >= 0.02
    cg, mdd, r1, _ = R171.run(T, P)
    base = R138.run(R138.FULL, "1997-07-02", R138.DAYS[-1])
    r2 = np.array(base[2])
    out = ["研究 180：現行組合未來一年／三年的報酬與回檔分布（區塊拔靴 5000 次）", "",
           f"(1) 現行全組合 2018-06～：歷史年化 {cg:.1%}、最大回檔 {mdd:.1%}",
           f"(2) v3 主策略 1997～（不含加碼，含 2000／2008 空頭）：歷史年化 {base[0]:.1%}、最大回檔 {base[1]:.1%}", ""]
    summarize("(1) 全組合 2018～", r1, out)
    summarize("(2) v3 1997～", r2, out)
    out.append("")
    out.append("解讀：(1) 來自 2018～2026 多頭，偏樂觀；(2) 較保守。真實未來大概落在兩者之間；最大回檔是「一年內從高點最多跌多少」")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究180_組合未來一年風險.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
