"""研究 188：上市股票市場廣度（新資料：build_stock_closes.py 個股收盤 2010～）→ v3 濾網與前瞻報酬

廣度指標（每日，用 4 碼普通股；ETF 代號 00 開頭排除）：
  AD10：近 10 日「上漲家數 ÷（上漲＋下跌）」平均；上漲／下跌用當天漲跌符號
  M50／M200：收盤在自己 50／200 日均線之上的家數比例（該股要有足夠歷史）
  NH-NL：創 250 日新高家數 − 新低家數（占家數比例）
訊號（事件，去叢集 20 天）：
  E1 洗盤：M50 ≤ 10%（幾乎全部跌破季線）→ 之後 10／20／60 天
  E2 廣度衝刺（Zweig）：AD10 10 天內從 < 0.40 升到 > 0.615 → 之後 20／60 天
  E3 背離：加權指數距 250 日高點 < 3% 但 M200 < 50% → 之後 20／60 天
v3 濾網（研究 138 引擎，2011～）：F1 M200 < 40% 不進場；F2 E3 背離時出場；F3 空手時 E2 衝刺提早進 1 倍（停損 −8%）；環狀平移 300 次
用法：python -X utf8 backtest/research_188_市場廣度.py
"""
import glob
import importlib.util
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r138", os.path.join(HERE, "research_138_金字塔加碼與分段停損.py"))
R138 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R138)
DAYS, PX = R138.DAYS, np.array(R138.PX)


def breadth():
    frames = [pd.read_csv(f, dtype={"code": str, "sign": str}) for f in sorted(glob.glob(os.path.join(HERE, "stock_closes", "*.csv.gz")))]
    df = pd.concat(frames)
    df = df[(df["code"].str.len() == 4) & ~df["code"].str.startswith("00")]
    px = df.pivot_table(index="date", columns="code", values="close", aggfunc="last").sort_index()
    sg = df.pivot_table(index="date", columns="code", values="sign", aggfunc="last").reindex(px.index)
    up = (sg == "+").sum(axis=1)
    dn = (sg == "-").sum(axis=1)
    ad = (up / (up + dn)).rolling(10).mean()
    out = pd.DataFrame({"AD10": ad})
    for L in (50, 200):
        ma = px.rolling(L, min_periods=L).mean()
        valid = ma.notna() & px.notna()
        out[f"M{L}"] = ((px > ma) & valid).sum(axis=1) / valid.sum(axis=1).replace(0, np.nan)
    hi = px.rolling(250, min_periods=250).max()
    lo = px.rolling(250, min_periods=250).min()
    valid = hi.notna()
    out["NHNL"] = (((px >= hi) & valid).sum(axis=1) - ((px <= lo) & valid).sum(axis=1)) / valid.sum(axis=1).replace(0, np.nan)
    out["n"] = px.notna().sum(axis=1)
    return out


def events(sig, gap=20):
    idx, last = [], -999
    for i in np.where(sig)[0]:
        if i - last >= gap:
            idx.append(i)
        last = i
    return np.array(idx, int)


def make_sizer(block, exit_, thrust, mode):
    def f(i, on, px2, ctx):
        if mode == "F3":
            if on:
                ctx.pop("early", None)
                return 1.0
            e = ctx.get("early")
            if e is not None:
                if PX[i] < e * 0.92:
                    ctx.pop("early")
                    return 0.0
                return 0.5
            if thrust[i]:
                ctx["early"] = PX[i]
                return 0.5
            return 0.0
        if not on:
            ctx["in"] = False
            return 0.0
        if ctx.get("in"):
            if mode == "F2" and exit_[i]:
                ctx["in"] = False
                return 0.0
            return 1.0
        if mode == "F1" and block[i]:
            return 0.0
        ctx["in"] = True
        return 1.0
    return f


def main():
    B = breadth().reindex(DAYS)
    first = B["M200"].first_valid_index()
    out = [f"研究 188：市場廣度（{B['n'].dropna().index[0]}～{DAYS[-1]}；M200 從 {first} 起可用）",
           f"目前：AD10 {B['AD10'].iloc[-1]:.2f}、站上 50 日線 {B['M50'].iloc[-1]:.0%}、站上 200 日線 {B['M200'].iloc[-1]:.0%}、新高−新低 {B['NHNL'].iloc[-1]:+.1%}", ""]
    n = len(DAYS)
    fwd = {H: np.r_[PX[H:] / PX[:-H] - 1, np.full(H, np.nan)] for H in (10, 20, 60)}
    m50, m200, ad = B["M50"].to_numpy(), B["M200"].to_numpy(), B["AD10"].to_numpy()
    hi250 = pd.Series(PX).rolling(250).max().to_numpy()
    thrust = np.zeros(n, bool)
    for i in range(10, n):
        w = ad[i - 10:i]
        if not np.isnan(ad[i]) and ad[i] > 0.615 and np.nanmin(w) < 0.40:
            thrust[i] = True
    diverg = (PX >= hi250 * 0.97) & (np.nan_to_num(m200, nan=1) < 0.5)
    wash = np.nan_to_num(m50, nan=1) <= 0.10
    ok = ~np.isnan(m50)
    out.append("== 事件（加權指數、去叢集 20 天；括號＝所有日子平均）==")
    for nm, sig, Hs in (("E1 洗盤 M50≤10%", wash & ok, (10, 20, 60)), ("E2 廣度衝刺", thrust & ok, (20, 60)), ("E3 指數近高但 M200<50%", diverg & ok, (20, 60))):
        idx = events(sig)
        cells = []
        for H in Hs:
            r = fwd[H][idx]
            r = r[~np.isnan(r)]
            allr = fwd[H][ok & ~np.isnan(fwd[H])]
            cells.append(f"{H} 天 {r.mean():+.1%}（{allr.mean():+.1%}）勝率 {np.mean(r > 0):.0%}" if len(r) else f"{H} 天 —")
        out.append(f"{nm}：{len(idx)} 次（{', '.join(DAYS[i] for i in idx[-6:])}）｜" + "｜".join(cells))
    out.append("")
    start = first if first else "2011-01-01"
    base = R138.run(R138.FULL, start, DAYS[-1])
    out.append(f"== v3 濾網（{start}～，現行 {base[0]:.1%}／{base[1]:.1%}）==")
    block = np.nan_to_num(m200, nan=1) < 0.40
    rng = np.random.default_rng(188)
    shifts = rng.integers(250, n - 250, 300)
    for mode, lab in (("F1", "F1 M200<40% 不進場"), ("F2", "F2 背離時出場"), ("F3", "F3 空手時衝刺提早進 1x")):
        res = R138.run(make_sizer(block, diverg, thrust, mode), start, DAYS[-1])
        d = res[0] - base[0]
        nd = np.array([R138.run(make_sizer(np.roll(block, s), np.roll(diverg, s), np.roll(thrust, s), mode), start, DAYS[-1])[0] - base[0] for s in shifts])
        out.append(f"{lab}：{res[0]:.1%}／{res[1]:.1%}（差 {d:+.2%}；平移單尾 p {(1 + np.sum(nd >= d)) / (len(nd) + 1):.3f}）")
    txt = "\n".join(out)
    print(txt)
    B.to_csv(os.path.join(HERE, "breadth_daily.csv"), float_format="%.4f")
    open(os.path.join(HERE, "結果_研究188_市場廣度.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
