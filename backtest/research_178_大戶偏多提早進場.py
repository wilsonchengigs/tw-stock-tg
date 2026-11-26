"""研究 178：主策略空手時，期貨大戶（前十大交易人）極度偏多 → 提早進場 1 倍（站上進場線後照常 2 倍）

接研究 174（大戶偏「聰明錢」）；做法同研究 32（P/C 提早進場）
訊號（v3 空手時，日 d 收盤後）：前十大淨部位比 ≥ 250 日 q 分位（q 0.90／0.95）；確認版另要求加權指數從近 10 日低點反彈 ≥3%
提早部位：1 倍（00631L 一半），停損：收盤跌破進場時指數 ×0.95 → 出場；最多抱 60 個交易日沒站上進場線也出場
v3 進場後照常 2 倍；v3 引擎＝研究 138 run（每天收盤判斷、隔天收盤成交、成本同 v3）；期間 2005-07～（大戶資料起點）
檢定：與 v3 的年化差；訊號序列環狀平移 300 次（保留叢集）單尾 p；4 組最小 p 家族校正；三段 2005–2012／2013–2019／2020–2026
用法：python -X utf8 backtest/research_178_大戶偏多提早進場.py
"""
import csv
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r138", os.path.join(HERE, "research_138_金字塔加碼與分段停損.py"))
R138 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R138)
DAYS, PX, ST = R138.DAYS, R138.PX, R138.ST
START = "2005-07-05"


def signal_pct():
    lt = {}
    for r in csv.DictReader(open(os.path.join(HERE, "large_trader_tx.csv"), encoding="utf-8")):
        if r["cat"] == "0" and int(r["oi"]) > 0:
            lt[r["date"]] = (int(r["top10_buy"]) - int(r["top10_sell"])) / int(r["oi"])
    vals = np.array([lt.get(d, np.nan) for d in DAYS])
    # 前值補（假日不會有缺，資料缺漏才補）
    for i in range(1, len(vals)):
        if np.isnan(vals[i]):
            vals[i] = vals[i - 1]
    pct = np.full(len(vals), np.nan)
    for i in range(260, len(vals)):
        w = vals[i - 250:i]
        if not np.isnan(w).any() and not np.isnan(vals[i]):
            pct[i] = np.mean(w < vals[i])
    return pct


def make_sizer(pct, q, confirm):
    def f(i, on, px2, ctx):
        if on:
            ctx.pop("early", None)
            return 1.0
        e = ctx.get("early")
        if e is not None:
            if PX[i] < e[0] * 0.95 or i - e[1] >= 60:
                ctx.pop("early")
                ctx["cool"] = i
                return 0.0
            return 0.5
        if i - ctx.get("cool", -99) < 10:
            return 0.0
        p = pct[i]
        if p is not None and not np.isnan(p) and p >= q:
            if confirm and PX[i] < min(PX[i - 10:i + 1]) * 1.03:
                return 0.0
            ctx["early"] = (PX[i], i)
            return 0.5
        return 0.0
    return f


def main():
    pct = signal_pct()
    end = DAYS[-1]
    base = R138.run(R138.FULL, START, end)
    out = [f"研究 178：大戶極度偏多 → 空手時提早進場 1 倍（{START}～{end}）",
           f"v3 現行：年化 {base[0]:.1%}／最大回檔 {base[1]:.1%}", ""]
    rng = np.random.default_rng(178)
    shifts = rng.integers(250, len(pct) - 250, 300)
    groups = [(q, c) for q in (0.90, 0.95) for c in (False, True)]
    real, nulls = [], []
    for q, c in groups:
        res = R138.run(make_sizer(pct, q, c), START, end)
        d = res[0] - base[0]
        nd = []
        for s in shifts:
            ps = np.roll(pct, s)
            nd.append(R138.run(make_sizer(ps, q, c), START, end)[0] - base[0])
        nd = np.array(nd)
        p = (1 + np.sum(nd >= d)) / (len(nd) + 1)
        real.append((q, c, res, d, p))
        nulls.append(nd)
        segs = []
        for a, z in (("2005-07-05", "2012-12-31"), ("2013-01-01", "2019-12-31"), ("2020-01-01", end)):
            b0 = R138.run(R138.FULL, a, z)[0]
            b1 = R138.run(make_sizer(pct, q, c), a, z)[0]
            segs.append(f"{a[:4]}–{z[:4]} {b1 - b0:+.1%}")
        out.append(f"q≥{q:.2f}{' ＋反彈 3% 確認' if c else ''}：年化 {res[0]:.1%}／回檔 {res[1]:.1%}（差 {d:+.2%}；平移中位 {np.median(nd):+.2%}、單尾 p {p:.3f}）｜平均曝險 {res[3]:.2f}｜分段差 " + "  ".join(segs))
    # 家族（最小 p）
    N = np.array(nulls).T  # shifts × groups
    ranks = np.array([[(1 + np.sum(N[:, j] >= N[s, j])) / (len(N) + 1) for j in range(len(groups))] for s in range(len(N))])
    minp = ranks.min(axis=1)
    best = min(x[4] for x in real)
    out.append("")
    out.append(f"家族校正（4 組最小 p）：最佳單組 p {best:.3f} → 家族 p {(1 + np.sum(minp <= best)) / (len(minp) + 1):.3f}")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究178_大戶偏多提早進場.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
