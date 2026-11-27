"""研究 407：使用者實際配置的長歷史回測（2002～2026）
主策略 v3 1.7x（85% 00631L 模型價＋15% 現金）＋P 恐慌做多 1x（研究 148 逐筆，台指期真實價／2017 前 S&P 代理）＋D 台美背離 0.5x（研究 211 逐筆）
P、D 的每筆報酬記在出場日（簡化：持有期間不逐日計），各占資金比例＝倍數×每筆報酬
V（爆量收黑）、F（外資）需在場且 F 只有 2018 後資料，這裡不含（保守）
報告：年化、最大回檔（日頻近似）、逐年、壓力年
用法：python -X utf8 backtest/research_407_實際配置長歷史.py
"""
import importlib.util
import io
import contextlib
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strategy_v3 as V  # noqa: E402


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(m)
    return m


bt = V.bt
_, _, e = V.run("2002-01-01", bt.DAYS[-1], lev=1.7, curve=True)
e = np.asarray(e)
i0 = next(i for i, d in enumerate(bt.DAYS) if d >= "2002-01-01")
D = bt.DAYS[i0:i0 + len(e)]
idx = {d: k for k, d in enumerate(D)}
main = np.r_[0.0, e[1:] / e[:-1] - 1]
R148 = load("r148", "research_148_恐慌連續觸發.py")
padd = np.zeros(len(D))
for x in R148.build():
    if x["sig"] and x["d"] in idx and not np.isnan(x["r"]):
        k = idx[x["d"]] + 1
        if k < len(D):
            padd[k] += 1.0 * x["r"]
R175 = load("r175", "research_175_加碼規則停損.py")
R205 = load("r205", "research_205_台美背離台指期部位.py")
dates, day, night, near = R175.R139.load_tx()
bi = set(R175.R138.DAYS)
ds = [d for d in dates if d in bi]
g = np.array([R205.GAP.get(d, np.nan) for d in ds])
dadd = np.zeros(len(D))
k = 0
while k < len(ds) - 2:
    if g[k] <= -0.10:
        j = k + 1
        last = min(j + 4, len(ds) - 1)
        r = R175.trade(day, night, ds, j, near[ds[k]], (last, "close"), None)
        if ds[last] in idx:
            dadd[idx[ds[last]]] += 0.5 * r
        k = last + 1
    else:
        k += 1
yrs = np.array([d[:4] for d in D])
L = ["研究 407：使用者實際配置長歷史（2002～；主策略 1.7x＋P 1x＋D 0.5x；V／F 不含）", ""]
for lab, r in (("主策略 1.7x", main), ("＋P 1x", main + padd), ("＋P 1x＋D 0.5x", main + padd + dadd)):
    eq = np.cumprod(1 + r)
    cg = eq[-1] ** (bt.TD / len(r)) - 1
    mdd = (eq / np.maximum.accumulate(eq) - 1).min()
    seg = []
    for lo, hi in (("2002", "2013"), ("2013", "2099"), ("2018", "2099")):
        m = (yrs >= lo) & (yrs < hi)
        x = np.cumprod(1 + r[m])
        seg.append(f"{x[-1] ** (bt.TD / m.sum()) - 1:.1%}")
    L.append(f"{lab:16s} 年化 {cg:5.1%}  最大回檔 {mdd:6.1%}｜2002–2012 {seg[0]}｜2013～ {seg[1]}｜2018～ {seg[2]}")
r = main + padd + dadd
L.append("\n逐年（主策略 1.7x → 全部）：" + "  ".join(f"{y}:{np.prod(1 + main[yrs == y]) - 1:+.0%}→{np.prod(1 + r[yrs == y]) - 1:+.0%}" for y in sorted(set(yrs))))
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究407_實際配置長歷史.txt"), "w", encoding="utf-8").write(out + "\n")
