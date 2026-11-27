"""研究 402：資金曲線風控（馬克羊「少輸」）——依 v3 自己的淨值調槓桿
訊號都用「現行 v3 2x 淨值」到昨天為止的資料（不偷看未來）：
  DD x：淨值離歷史高點回檔 > x（15／20／25%）→ 在場改 1x；回檔收斂到 < x/2 才恢復 2x
  EMA w：淨值 < 自身 w 日均線（100／200）→ 在場改 1x
與「同平均曝險的固定槓桿」比；全期 2002～、兩段、真實價
用法：python -X utf8 backtest/research_402_資金曲線風控.py
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_138_金字塔加碼與分段停損 as R138  # noqa: E402

V, bt, DAYS, N = R138.V, R138.bt, R138.DAYS, R138.N
_, _, e = V.run(DAYS[0], DAYS[-1], curve=True)
e = np.asarray(e)
i0 = N - len(e)
eq = np.full(N, np.nan)
eq[i0:] = e
peak = np.fmax.accumulate(np.nan_to_num(eq, nan=0))
dd = np.where(eq > 0, eq / np.where(peak > 0, peak, 1) - 1, 0)


def flag_dd(x):
    fl = np.zeros(N, bool)
    on = False
    for i in range(1, N):
        d = dd[i - 1]
        if not on and d < -x:
            on = True
        elif on and d > -x / 2:
            on = False
        fl[i] = on
    return fl


def flag_ma(w):
    fl = np.zeros(N, bool)
    for i in range(i0 + w + 1, N):
        fl[i] = eq[i - 1] < np.mean(eq[i - w:i])
    return fl


def sizer_of(fl):
    def f(i, on, px2, ctx):
        return (0.5 if fl[i] else 1.0) if on else 0.0
    return f


def perf(sz, lev=2.0):
    out = []
    for a, b in V.PER:
        cg, mdd, _, ex = R138.run(sz, a, b, lev=lev)
        out.append((cg, mdd, ex))
    cg, mdd, _, ex = R138.run(sz, *V.REAL, real=True, lev=lev)
    out.append((cg, mdd, ex))
    return out


fmt = lambda p: "  ".join(f"{c:5.1%}／{m:6.1%}" for c, m, _ in p)  # noqa: E731
base = perf(R138.FULL)
L = ["研究 402：資金曲線風控（全期 2002～｜2002–2012｜2013～｜真實價 2015-09～）", f"現行 v3 2x：{fmt(base)}", ""]
rng = np.random.default_rng(402)
for lab, fl in [(f"回檔 >{x:.0%} 降 1x", flag_dd(x)) for x in (0.15, 0.20, 0.25)] + [(f"淨值 < MA{w} 降 1x", flag_ma(w)) for w in (100, 200)]:
    p = perf(sizer_of(fl))
    fixed = perf(R138.FULL, lev=2.0 * p[0][2] / base[0][2])
    null = [R138.run(sizer_of(np.roll(fl, int(s))), *V.PER[0])[:2] for s in rng.integers(500, N - 500, 100)]
    pc = np.mean([c >= p[0][0] for c, _ in null])
    pm = np.mean([m >= p[0][1] for _, m in null])
    L.append(f"{lab}：{fmt(p)}｜同曝險固定 {fixed[0][0]:5.1%}／{fixed[0][1]:6.1%}｜降槓桿時間 {fl[i0:].mean():.0%}｜平移 p 年化 {pc:.2f}、回檔 {pm:.2f}")
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究402_資金曲線風控.txt"), "w", encoding="utf-8").write(out + "\n")
