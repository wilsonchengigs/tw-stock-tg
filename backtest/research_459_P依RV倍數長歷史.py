"""研究 459：P 依前一天台指期近月 20 日實現波動（RV20）調倍數，1998～ 全部 P（研究 148 build）
變體 A：RV<23% 0.5x；C：<23% 0.5／≥36% 1.5；B：<23% 0。P 部分損益加總、每單位曝險、兩段、RV 環狀平移 500 次（家族 3 變體取最大每單位改善）
用法：python -X utf8 backtest/research_459_P依RV倍數長歷史.py
"""
import io
import contextlib
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_148_恐慌連續觸發 as R
dates, day, night, near = R.R144.R139.load_tx()
pos = {d: k for k, d in enumerate(dates)}
cl = np.array([np.nan] + [(day[d].get(near[dates[k - 1]]) or [np.nan] * 4)[3] for k, d in enumerate(dates) if k])
r1 = np.r_[np.nan, np.log(cl[1:] / cl[:-1])]
rv = np.array([np.nanstd(r1[max(1, k - 19):k + 1]) * np.sqrt(252) if k > 20 else np.nan for k in range(len(cl))])
P = [(x["d"], rv[pos[x["d"]] - 1], x["r"]) for x in R.build() if x["sig"]]
P = [p for p in P if not np.isnan(p[1])]
d_ = np.array([p[0] for p in P])
v_ = np.array([p[1] for p in P])
r_ = np.array([p[2] for p in P])
y_ = np.array([d[:4] for d in d_])
VAR = {"A": lambda v: np.where(v < 0.23, 0.5, 1.0), "B": lambda v: np.where(v < 0.23, 0.0, 1.0),
       "C": lambda v: np.where(v < 0.23, 0.5, np.where(v >= 0.36, 1.5, 1.0))}


def unit(s, r):
    return np.sum(s * r) / np.mean(s) - np.sum(r)


L = [f"研究 459：P 依 RV20 調倍數（{len(P)} 筆，{d_[0][:4]}～）", ""]
for lo, hi in (("1998", "2099"), ("1998", "2013"), ("2013", "2099")):
    m = (y_ >= lo) & (y_ < hi)
    row = [f"固定 {r_[m].sum():+.0%}"]
    for k, f in VAR.items():
        s = f(v_[m])
        row.append(f"{k} {np.sum(s * r_[m]):+.0%}（{s.mean():.2f}x，每單位 {np.sum(s * r_[m]) / s.mean():+.0%}）")
    L.append(f"{lo}～{'' if hi == '2099' else hi}（{m.sum()} 筆）：" + "｜".join(row))
t0 = max(unit(f(v_), r_) for f in VAR.values())
rng = np.random.default_rng(459)
null = []
for sh in rng.integers(50, len(v_) - 50, 500):
    vv = np.roll(v_, int(sh))
    null.append(max(unit(f(vv), r_) for f in VAR.values()))
L.append(f"\n家族（3 變體）每單位改善最大 {t0:+.0%}；RV 平移 500 次 p {np.mean(np.array(null) >= t0):.3f}")
o = "\n".join(L)
print(o)
open(os.path.join(HERE, "結果_研究459_P依RV倍數長歷史.txt"), "w", encoding="utf-8").write(o + "\n")
