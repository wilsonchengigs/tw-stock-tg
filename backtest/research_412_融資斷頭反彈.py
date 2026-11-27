"""研究 412：融資斷頭後短線反彈——上市融資金額（margin_tw.csv，2001～）單日減 ≥ x（3／5／8%）
→ 隔天開盤（指數代理：當天收盤進的近似改用隔天收盤進，避免開盤假象）買、抱 h＝1／5 天
報酬用加權收盤（D+1 收 → D+1+h 收）；對照＝同 20 日波動十分位；增量＝排除 P（S&P 前一晚跌 ≥2%）或 D（台美背離 ≤-10%）±2 天
家族：3 門檻 × 2 天期 × （全部／增量）＝12，訊號平移 1,000 次
用法：python -X utf8 backtest/research_412_融資斷頭反彈.py
"""
import csv
import io
import contextlib
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_206_台美背離延伸 as R  # noqa: E402
    import research_209_短線超賣指標 as S  # noqa: E402

D, TW, N = R.DAYS, R.TW, R.N
mg = {r["date"]: float(r["balance"]) for r in csv.DictReader(open(os.path.join(HERE, "margin_tw.csv")))}
M = np.array([mg.get(d, np.nan) for d in D])
dm = np.r_[np.nan, M[1:] / M[:-1] - 1]
F = {h: np.array([TW[k + 1 + h] / TW[k + 1] - 1 if k + 1 + h < N else np.nan for k in range(N)]) for h in (1, 5)}
dec = S.dec


def excess(f):
    out = np.full(N, np.nan)
    for d_ in range(10):
        m = (dec == d_) & ~np.isnan(f)
        out[m] = f[m] - f[m].mean()
    return out


EX = {h: excess(F[h]) for h in (1, 5)}
near = np.zeros(N, bool)
spr = R.BENCH["GSPC"]
spr = np.r_[np.nan, spr[1:] / spr[:-1] - 1]
for k in np.where((spr <= -0.02) | (R.GAP["GSPC"] <= -0.10))[0]:
    near[max(0, k - 2):k + 3] = True
valid = np.where(~np.isnan(EX[5]) & ~np.isnan(dm))[0]


def z(x, fl):
    m = fl & ~np.isnan(x)
    if m.sum() < 5:
        return np.nan
    a = x[~np.isnan(x)]
    return (x[m].mean() - a.mean()) / (a.std() / np.sqrt(m.sum()))


tests = []
for th in (0.03, 0.05, 0.08):
    sig = np.nan_to_num(dm <= -th, nan=0).astype(bool)
    for h in (1, 5):
        for lab, fl in (("全部", sig), ("增量", sig & ~near)):
            tests.append((f"融資單日 ≤-{th:.0%} 抱 {h} 天 {lab}", EX[h], fl))
pre = [(nm, x[valid], fl[valid]) for nm, x, fl in tests]
real = [z(x, fl) for _, x, fl in pre]
rng = np.random.default_rng(412)
null = np.array([np.nanmax([z(x, np.roll(fl, s)) for _, x, fl in pre]) for s in rng.integers(250, len(valid) - 250, 1000)])
L = [f"研究 412：融資斷頭後短線反彈（{D[valid[0]]}～；隔天收盤進；超額＝減同波動十分位平均）", ""]
for (nm, x, fl), zz in zip(pre, real):
    m = fl & ~np.isnan(x)
    raw = (F[1] if "抱 1" in nm else F[5])[valid][m]
    L.append(f"  {nm}：{m.sum():3d} 天 原始 {np.nanmean(raw):+.2%} 超額 {np.nanmean(x[m]):+.2%} 勝率 {np.mean(raw > 0):.0%}  z {zz:+.2f} 家族 p {np.mean(null >= zz) if not np.isnan(zz) else np.nan:.3f}")
ev = [D[k] for k in np.where(np.nan_to_num(dm <= -0.05, nan=0).astype(bool))[0]]
L.append("\n融資單日 ≤-5% 的日子：" + "、".join(ev[-12:]))
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究412_融資斷頭反彈.txt"), "w", encoding="utf-8").write(out + "\n")
