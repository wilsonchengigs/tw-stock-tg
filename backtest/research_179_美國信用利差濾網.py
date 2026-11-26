"""研究 179：美國信用市場壓力（高收益債 HYG ÷ 中期公債 IEF，還原價）當 v3 濾網（研究 41 沒測信用利差）

信用指標 CR＝HYG／IEF（越低＝信用利差擴大、風險偏好下降）；台股日 i 用「i 之前最後一個美國交易日」
壓力定義：(a) CR 低於自己的 MA50／MA100；(b) CR 20 日變化 ≤ −2％／−3％
用法：A 只擋進場（v3 要進場時若有壓力就等）；B 也出場（在場時出現壓力就出、壓力解除且 v3 仍在場才回來）
引擎：研究 138 run（v3 不動，只改在場倍數；每天收盤判斷、隔天收盤成交）；期間 2007-06～（HYG 上市）
檢定：與 v3 的年化差；壓力序列環狀平移 300 次單尾 p；8 組最小 p 家族；三段 2007–2013／2014–2019／2020–2026
用法：python -X utf8 backtest/research_179_美國信用利差濾網.py
"""
import importlib.util
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r138", os.path.join(HERE, "research_138_金字塔加碼與分段停損.py"))
R138 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R138)
DAYS, ST = R138.DAYS, R138.ST
START = "2007-06-01"
NY = ZoneInfo("America/New_York")


def adj(fn):
    r = json.load(open(os.path.join(HERE, fn)))
    a = r["indicators"]["adjclose"][0]["adjclose"]
    return {datetime.fromtimestamp(t, NY).strftime("%Y-%m-%d"): x for t, x in zip(r["timestamp"], a) if x}


def credit_series():
    h, f = adj("HYG.json"), adj("IEF.json")
    us = sorted(set(h) & set(f))
    cr = np.array([h[d] / f[d] for d in us])
    ma = {L: np.array([cr[max(0, i - L + 1):i + 1].mean() if i >= L - 1 else np.nan for i in range(len(cr))]) for L in (50, 100)}
    ch20 = np.array([cr[i] / cr[i - 20] - 1 if i >= 20 else np.nan for i in range(len(cr))])
    # 對到台股日：之前最後一個美國日
    idx = np.searchsorted(us, DAYS, side="left") - 1
    out = {}
    for nm, arr in (("CR<MA50", cr < ma[50]), ("CR<MA100", cr < ma[100]), ("20日 ≤−2%", ch20 <= -0.02), ("20日 ≤−3%", ch20 <= -0.03)):
        s = np.zeros(len(DAYS), bool)
        ok = idx >= 0
        s[ok] = arr[idx[ok]]
        out[nm] = s
    return out


def make_sizer(stress, also_exit):
    def f(i, on, px2, ctx):
        if not on:
            ctx["in"] = False
            return 0.0
        if ctx.get("in"):
            if also_exit and stress[i]:
                ctx["in"] = False
                return 0.0
            return 1.0
        if stress[i]:
            return 0.0
        ctx["in"] = True
        return 1.0
    return f


def main():
    S = credit_series()
    end = DAYS[-1]
    base = R138.run(R138.FULL, START, end)
    out = [f"研究 179：美國信用利差（HYG/IEF）當 v3 濾網（{START}～{end}）", f"v3 現行：年化 {base[0]:.1%}／最大回檔 {base[1]:.1%}", ""]
    rng = np.random.default_rng(179)
    shifts = rng.integers(250, len(DAYS) - 250, 300)
    i0 = next(i for i, d in enumerate(DAYS) if d >= START)
    real, nulls = [], []
    for nm, st_ in S.items():
        for ex in (False, True):
            res = R138.run(make_sizer(st_, ex), START, end)
            d = res[0] - base[0]
            nd = np.array([R138.run(make_sizer(np.roll(st_, s), ex), START, end)[0] - base[0] for s in shifts])
            p = (1 + np.sum(nd >= d)) / (len(nd) + 1)
            segs = []
            for a, z in (("2007-06-01", "2013-12-31"), ("2014-01-01", "2019-12-31"), ("2020-01-01", end)):
                segs.append(f"{a[:4]}–{z[:4]} {R138.run(make_sizer(st_, ex), a, z)[0] - R138.run(R138.FULL, a, z)[0]:+.1%}")
            real.append((nm, ex, p))
            nulls.append(nd)
            out.append(f"{nm:10s} {'B 也出場' if ex else 'A 只擋進'}：{res[0]:.1%}／{res[1]:.1%}（差 {d:+.2%}，p {p:.3f}）｜壓力天數 {st_[i0:].mean():.0%}｜" + "  ".join(segs))
    N = np.array(nulls).T
    ranks = np.array([[(1 + np.sum(N[:, j] >= N[s, j])) / (len(N) + 1) for j in range(N.shape[1])] for s in range(len(N))])
    minp = ranks.min(axis=1)
    best = min(x[2] for x in real)
    out.append("")
    out.append(f"家族（{len(real)} 組最小 p）：最佳單組 p {best:.3f} → 家族 p {(1 + np.sum(minp <= best)) / (len(minp) + 1):.3f}")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究179_美國信用利差濾網.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
