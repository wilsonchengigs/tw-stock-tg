"""研究 168：美國前一晚的跨資產衝擊（殖利率、VIX、美元、日圓、油、金）→ 台指期隔天（候選 6 的架構換成其他資產）

訊號：台股交易日 D 之前最後一個美國交易日 u 的變動（Yahoo 日線）
  ^TNX 10 年殖利率 ±10bp／±15bp；^IRX 3 個月 ±10bp（升息預期）；^VIX 單日 +20%／+30%、−15%；
  DX-Y.NYB 美元指數 ±0.8%；JPY=X 美元兌日圓 ±1.5%（日圓急升＝套利平倉，如 2024-08-05）；CL=F 原油 ±5%；GC=F 黃金 ±2.5%
  （JPY=X 是 UTC 日線，日期用 UTC；其餘用美東）
報酬：台指期近月 D 08:45 開盤進多、D+1 08:45 開盤出，扣 3 點（研究 148 的 build）；負值＝做空較好
對照：同波動度（前 20 日實現波動同十分位）非訊號日 2000 次抽樣，雙尾 p
另看「排除候選 6 已觸發的日子」（夜盤或 S&P 跌 ≥2%）＝有沒有新增資訊
期間：1998-07～2017-05（夜盤前）與 2017-05～；家族 Bonferroni
用法：python -X utf8 backtest/research_168_美國跨資產衝擊隔天台指期.py
"""
import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r148", os.path.join(HERE, "research_148_恐慌連續觸發.py"))
R148 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R148)
NY = ZoneInfo("America/New_York")


def series(fn, tz=NY, diff=False):
    r = json.load(open(os.path.join(HERE, fn)))
    c = r["indicators"]["quote"][0]["close"]
    rows = []
    for t, x in zip(r["timestamp"], c):
        if x and x > 0:
            rows.append((datetime.fromtimestamp(t, tz).strftime("%Y-%m-%d"), x))
    out = {}
    for i in range(1, len(rows)):
        if rows[i][0] == rows[i - 1][0]:
            continue
        out[rows[i][0]] = (rows[i][1] - rows[i - 1][1]) if diff else (rows[i][1] / rows[i - 1][1] - 1)
    return out


def prev_val(S, d):
    for back in range(1, 5):
        kk = (datetime.fromisoformat(d) - timedelta(days=back)).strftime("%Y-%m-%d")
        if kk in S:
            return S[kk]
    return None


def main():
    rows = R148.build()
    n = len(rows)
    ds = [x["d"] for x in rows]
    cc = np.array([0.0] + [rows[k]["c"] / rows[k - 1]["c"] - 1 for k in range(1, n)])
    vol = np.array([np.std(cc[max(1, k - 20):k]) if k > 5 else np.nan for k in range(n)])
    ok = ~np.isnan(vol)
    dec = np.digitize(np.nan_to_num(vol), np.nanpercentile(vol, np.arange(10, 100, 10)))
    r = np.array([x["r"] for x in rows])
    c6 = np.array([x["sig"] for x in rows])
    S = {"TNX": series("TNX.json", diff=True), "IRX": series("IRX.json", diff=True), "VIX": series("VIX.json"),
         "DXY": series("DXY.json"), "JPY": series("JPY.json", tz=timezone.utc), "CL": series("CL.json"), "GC": series("GC.json")}
    V = {k: np.array([prev_val(s, d) if prev_val(s, d) is not None else np.nan for d in ds]) for k, s in S.items()}
    rules = [("10Y 殖利率 +10bp", "TNX", lambda x: x >= 0.10), ("10Y 殖利率 +15bp", "TNX", lambda x: x >= 0.15),
             ("10Y 殖利率 −10bp", "TNX", lambda x: x <= -0.10), ("10Y 殖利率 −15bp", "TNX", lambda x: x <= -0.15),
             ("3M 殖利率 +10bp", "IRX", lambda x: x >= 0.10), ("3M 殖利率 −10bp", "IRX", lambda x: x <= -0.10),
             ("VIX +20%", "VIX", lambda x: x >= 0.20), ("VIX +30%", "VIX", lambda x: x >= 0.30), ("VIX −15%", "VIX", lambda x: x <= -0.15),
             ("美元 +0.8%", "DXY", lambda x: x >= 0.008), ("美元 −0.8%", "DXY", lambda x: x <= -0.008),
             ("日圓急升 USDJPY −1.5%", "JPY", lambda x: x <= -0.015), ("日圓急貶 USDJPY +1.5%", "JPY", lambda x: x >= 0.015),
             ("原油 +5%", "CL", lambda x: x >= 0.05), ("原油 −5%", "CL", lambda x: x <= -0.05),
             ("黃金 +2.5%", "GC", lambda x: x >= 0.025), ("黃金 −2.5%", "GC", lambda x: x <= -0.025)]
    rng = np.random.default_rng(168)
    out = [f"研究 168：美國前一晚跨資產衝擊 → 台指期 D 開→D+1 開做多（{ds[0]}～{ds[-1]}；扣 3 點；負＝做空較好）",
           f"全部日子平均 {r[ok].mean():+.3%}", ""]
    fam = []
    for per, lo, hi in (("1998-07～2017-05（夜盤前）", "1998", "2017-05-15"), ("2017-05～（有夜盤）", "2017-05-15", "2099")):
        inp = np.array([lo <= d < hi for d in ds])
        out.append(f"== {per} ==")
        out.append(f"{'規則':22s} {'次數':>5s} {'每筆':>8s} {'勝率':>4s} {'比同波動':>8s} {'p':>6s} ｜排除候選6觸發：次數 每筆")
        for nm, k, f in rules:
            v = V[k]
            fire = np.zeros(n, bool)
            good = ~np.isnan(v)
            fire[good] = f(v[good])
            msk = fire & ok & inp
            ctrl = ~fire & ok & inp & good
            idx = np.where(msk)[0]
            if len(idx) < 8:
                out.append(f"{nm:22s} {len(idx):5d}（太少）")
                continue
            pools = {i: np.where(ctrl & (dec == dec[i]))[0] for i in idx}
            base = np.array([r[pools[i]].mean() for i in idx])
            diff = np.mean(r[idx] - base)
            null = np.array([np.mean([r[rng.choice(pools[i])] for i in idx] - base) for _ in range(2000)])
            p = (1 + np.sum(np.abs(null) >= abs(diff))) / 2001
            fam.append((f"{per[:4]} {nm}", p, diff, len(idx)))
            ex = msk & ~c6
            out.append(f"{nm:22s} {len(idx):5d} {r[msk].mean():+8.3%} {np.mean(r[msk] > 0):4.0%} {diff:+8.3%} {p:6.3f} ｜{ex.sum():4d} {r[ex].mean() if ex.sum() else 0:+.3%}")
        out.append("")
    K = len(fam)
    out.append(f"== 家族 Bonferroni（{K} 個檢定）：p < 0.05／{K} ＝ {0.05 / K:.4f} 才算 ==")
    for nm, p, diff, m in sorted(fam, key=lambda x: x[1])[:10]:
        out.append(f"{nm:30s} {m:4d} 次 比同波動 {diff:+.3%}  p {p:.3f} → 校正 {min(1, p * K):.3f}")
    # 兩段同方向且都 p<0.1 的
    out.append("")
    out.append("兩段同方向且兩段 p < 0.10：")
    a = {nm[5:]: (p, d) for nm, p, d, m in fam if nm.startswith("1998")}
    b = {nm[5:]: (p, d) for nm, p, d, m in fam if nm.startswith("2017")}
    hit = [k for k in a if k in b and a[k][0] < 0.1 and b[k][0] < 0.1 and np.sign(a[k][1]) == np.sign(b[k][1])]
    out.append("、".join(f"{k}（{a[k][1]:+.2%}／{b[k][1]:+.2%}）" for k in hit) or "沒有")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究168_美國跨資產衝擊.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
