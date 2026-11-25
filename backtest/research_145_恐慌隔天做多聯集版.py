"""研究 145：候選 6 聯集版——「夜盤跌 ≥x%」或「S&P500 前一晚跌 ≥x%」→ D 08:45 開盤做多台指期、D+1 08:45 開盤出（研究 143、144）

疊在現行 V+F 之上（研究 141 引擎，2018-06～，00631L＋台指期真實價），不分 v3 狀態
家族：觸發 {夜盤, S&P, 聯集} × x {2, 3%} × u {0.5, 1} ＝ 12 組；虛無：夜盤與 S&P 兩條序列一起環狀平移 400 次（避開 ±20 天），最小 p 值法
連續兩天都觸發＝續抱（不重複加碼）
用法：python -X utf8 backtest/research_145_恐慌隔天做多聯集版.py （R145_SHIFTS 控制平移次數）
"""
import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


R142 = _load("r142", "research_142_夜盤大跌隔天加碼.py")
R141 = R142.R141
bt = R141.bt
NY = timezone(timedelta(hours=-5))
COST = 3.0


def sp_series(T):
    r = json.load(open(os.path.join(HERE, "GSPC.json")))
    c = r["indicators"]["quote"][0]["close"]
    rows = [(datetime.fromtimestamp(t, NY).strftime("%Y-%m-%d"), x) for t, x in zip(r["timestamp"], c) if x]
    s = {rows[i][0]: rows[i][1] / rows[i - 1][1] - 1 for i in range(1, len(rows))}
    out = []
    for t in T:
        v = 0.0
        for back in range(1, 5):
            k = (datetime.fromisoformat(t["d"]) - timedelta(days=back)).strftime("%Y-%m-%d")
            if k in s:
                v = s[k]
                break
        out.append(v)
    return np.array(out)


def main():
    S = int(os.environ.get("R145_SHIFTS", "400"))
    T = R141.build()
    n = len(T)
    _, _, base_r, _ = R141.run(T)
    NN, SP = R142.night_series(T), sp_series(T)
    o = np.array([t["o"] for t in T])
    c = np.array([t["c"] for t in T])
    roc = c / o - 1
    gap = np.r_[0.0, o[1:] / c[:-1] - 1]
    GRID = [(trig, x, u) for trig in ("夜盤", "S&P", "聯集") for x in (0.02, 0.03) for u in (0.5, 1.0)]

    def one(nn, sp, trig, x, u):
        sig = (nn <= -x) if trig == "夜盤" else (sp <= -x) if trig == "S&P" else ((nn <= -x) | (sp <= -x))
        pos_day = np.where(sig, u, 0.0)
        pos_gap = np.r_[0.0, pos_day[:-1]]
        add = pos_gap * gap + pos_day * roc
        add -= np.where((pos_day > 0) & (pos_gap == 0), u * COST / o, 0.0)
        add -= np.where((pos_gap > 0) & (pos_day == 0), u * COST / o, 0.0)
        r = base_r + add[1:]
        e = np.cumprod(1 + r)
        return e[-1] ** (bt.TD / len(r)) - 1, (e / np.maximum.accumulate(e) - 1).min(), int(sig.sum())

    real = [one(NN, SP, *g) for g in GRID]
    e0 = np.cumprod(1 + base_r)
    c0, m0 = e0[-1] ** (bt.TD / len(base_r)) - 1, (e0 / np.maximum.accumulate(e0) - 1).min()
    rng = np.random.default_rng(145)
    shifts = rng.integers(20, n - 20, S)
    null = np.array([[one(np.roll(NN, s), np.roll(SP, s), *g)[0] for g in GRID] for s in shifts])
    realc = np.array([r[0] for r in real])
    single = (1 + (null >= realc).sum(axis=0)) / (S + 1)
    ranks = np.array([[(1 + np.sum(null[:, j] >= null[s, j])) / (S + 1) for j in range(len(GRID))] for s in range(S)])
    minp = ranks.min(axis=1)
    out = [f"研究 145：恐慌隔天做多（D 開盤進、D+1 開盤出）疊在現行 V+F 上（{T[0]['d']}～{T[-1]['d']}；平移 {S} 次）",
           f"現行 V+F：{c0:.1%}／{m0:.1%}", ""]
    for j, (trig, x, u) in enumerate(GRID):
        cc, mm, k = real[j]
        fam = (1 + np.sum(minp <= single[j])) / (S + 1)
        out.append(f"{trig:4s} 跌≥{x:.0%} 加{u}x  {k:3d} 次  {cc:6.1%}／{mm:6.1%}（{cc - c0:+.2%}）  平移中位 {np.median(null[:, j]) - c0:+.2%}  單組 p {single[j]:.3f}  家族 p {fam:.3f}")
    # 逐年（聯集 2% 加 0.5x）
    sig = (NN <= -0.02) | (SP <= -0.02)
    pos_day = np.where(sig, 0.5, 0.0)
    pos_gap = np.r_[0.0, pos_day[:-1]]
    add = pos_gap * gap + pos_day * roc - np.where((pos_day > 0) & (pos_gap == 0), 0.5 * COST / o, 0) - np.where((pos_gap > 0) & (pos_day == 0), 0.5 * COST / o, 0)
    yrs = np.array([t["d"][:4] for t in T])
    out.append("\n聯集 2% 加 0.5x 逐年增量（加總報酬）：" + "  ".join(f"{y}:{add[yrs == y].sum():+.1%}" for y in sorted(set(yrs))))
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究145_恐慌隔天做多聯集版.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
