"""研究 278：月內時段——上旬（1～10 日）、中旬（11～20 日）、下旬（21 日～月底），另看月營收公布高峰（6～10 日）
每個月切段：段報酬＝該段最後交易日收盤 ÷ 前一段最後交易日收盤 − 1（加權價格指數）
比較：各段平均日報酬（段報酬 ÷ 交易日數）減全月平均日報酬；月份配對 t（以月為單位、互相獨立），4 檢定 Bonferroni ×4
兩段 1998–2012／2013～；另列 v3 在場時的同樣比較
用法：python -X utf8 backtest/research_278_月內時段.py
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402
import research_138_金字塔加碼與分段停損 as R138  # noqa: E402

i0 = next(i for i, d in enumerate(bt.DAYS) if d >= "1998-01-01")
DAYS = bt.DAYS[i0:]
PX = np.array(bt.PX[i0:])
ST = np.array(R138.ST[i0:])
r1 = np.r_[0.0, np.log(PX[1:] / PX[:-1])]
held = np.r_[False, ST[:-1] == 1]
SEGS = [("上旬 1～10 日", 1, 10), ("中旬 11～20 日", 11, 20), ("下旬 21 日～", 21, 31), ("營收公布 6～10 日", 6, 10)]


FULL_ONLY = True


def table(mask):
    months = sorted({d[:7] for d in DAYS})
    rows = []
    for m in months:
        idx0 = [k for k, d in enumerate(DAYS) if d[:7] == m and k > 0]
        idx = [k for k in idx0 if mask[k]]
        if len(idx) < 12 or (FULL_ONLY and len(idx) < len(idx0)):  # 只看整個月都符合的月份，避免進出場切在月中造成選樣偏誤
            continue
        allm = r1[idx].mean()
        vals = []
        for _, a, b in SEGS:
            seg = [k for k in idx if a <= int(DAYS[k][8:]) <= b]
            vals.append(r1[seg].mean() - allm if seg else np.nan)
        rows.append((m, vals))
    return rows


def summarize(rows, label):
    out = [f"== {label}：{len(rows)} 個月 =="]
    X = np.array([v for _, v in rows])
    for j, (nm, _, _) in enumerate(SEGS):
        x = X[:, j][~np.isnan(X[:, j])]
        t = x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
        p = 2 * (1 - __import__("math").erf(abs(t) / np.sqrt(2)) / 2 - 0.5) if False else None
        from math import erf, sqrt
        p = 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2))))
        s1 = np.array([v[j] for m, v in rows if m <= "2012-12" and not np.isnan(v[j])])
        s2 = np.array([v[j] for m, v in rows if m > "2012-12" and not np.isnan(v[j])])
        out.append(f"{nm:<12s} 日均超額 {x.mean() * 1e4:+6.2f} bp（年化 {x.mean() * 245:+5.1%}）t {t:+5.2f} p {p:.3f} Bonf {min(1, p * 4):.3f}｜1998–2012 {s1.mean() * 1e4:+6.2f}｜2013～ {s2.mean() * 1e4:+6.2f} bp")
    return out


all_mask = np.ones(len(DAYS), bool)
all_mask[0] = False
L = ["研究 278：月內時段（加權日報酬，減同月平均；月份配對 t、4 檢定 Bonferroni）", ""]
L += summarize(table(all_mask), "全部交易日")
L.append("")
# 無選樣偏誤版：以「上個月最後交易日收盤 v3 在場」決定整個月，當月所有交易日都算（之後出不出場都不管）
start_in = np.zeros(len(DAYS), bool)
cur = False
for k in range(1, len(DAYS)):
    if DAYS[k][:7] != DAYS[k - 1][:7]:
        cur = ST[k - 1] == 1
    start_in[k] = cur if k > 1 else False
L += summarize(table(start_in), "上月底 v3 在場（當月全部日子，無選樣偏誤）")
L.append("")
start_out = np.zeros(len(DAYS), bool)
cur0 = False
for k in range(1, len(DAYS)):
    if DAYS[k][:7] != DAYS[k - 1][:7]:
        cur0 = ST[k - 1] == 0
    start_out[k] = cur0 if k > 1 else False
L += summarize(table(start_out), "上月底 v3 空手（當月全部日子）")
L.append("")
L += summarize(table(held), "v3 整月在場（有選樣偏誤：月初大跌會出場而被排除，僅對照）")
FULL_ONLY = False
L.append("")
L += summarize(table(held), "v3 在場日（含部分月份，有選樣偏誤，僅對照）")
L.append("")
L.append("（1 bp＝0.01%；台指期來回成本約 6 點 ≈ 1.5 bp，一段 10 天要每天多 ≥0.2 bp 才付得起成本）")
txt = "\n".join(L)
print(txt)
open(os.path.join(HERE, "結果_研究278_月內時段.txt"), "w", encoding="utf-8").write(txt + "\n")
