"""研究 449：研究 444 的 VIX 分級套到 D（台美背離）與 V（爆量收黑）；基準＝研究 411（主策略 1.7x＋P＋D＋V，2002～）
倍數用出場日前約一週（進場日前一天近似：出場日往前 6 天）的清洗 VIX（近 3 日中位）；變體 C：<25 0.5／25～35 1／≥35 1.5；B：<25 0
對 V、D 各自套；VIX 平移 300 次的安慰劑（單組 p）
用法：python -X utf8 backtest/research_449_VD依VIX倍數.py
"""
import io
import contextlib
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_411_實際配置含V as V
    import research_444_P依VIX倍數 as M
R = V.R
VV = M.V
med = np.array([np.median(VV[max(0, k - 2):k + 1]) for k in range(len(VV))])


def sz(nm, v):
    return np.where(v < 25, 0.5 if nm == "C" else 0.0, np.where(v < 35, 1.0, 1.5 if nm == "C" else 1.0))


def run(arr, nm, vser, lag=6):
    idx = np.where(arr != 0)[0]
    s = np.ones(len(arr))
    for k in idx:
        j = max(0, k - lag)
        s[k] = sz(nm, np.array([vser[j]]))[0]
    other = R.main + R.padd + R.dadd + V.vadd - arr
    r = other + arr * s
    eq = np.cumprod(1 + r)
    return eq[-1] ** (R.bt.TD / len(r)) - 1, np.mean(s[idx])


base = np.cumprod(1 + R.main + R.padd + R.dadd + V.vadd)
c0 = base[-1] ** (R.bt.TD / len(base)) - 1
L = [f"研究 449：VIX 分級套 V／D（基準＝研究 411 {c0:.1%}）", ""]
rng = np.random.default_rng(449)
for lab, arr in (("D 台美背離", R.dadd), ("V 爆量收黑", V.vadd)):
    for nm in ("B", "C"):
        cg, avg = run(arr, nm, med)
        null = [run(arr, nm, np.roll(med, int(s)))[0] for s in rng.integers(250, len(med) - 250, 300)]
        p = np.mean(np.array(null) >= cg)
        L.append(f"{lab} {nm}：{cg:.1%}（{cg - c0:+.2%}）平均倍數 {avg:.2f}｜平移 p {p:.3f}")
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究449_VD依VIX倍數.txt"), "w", encoding="utf-8").write(out + "\n")
