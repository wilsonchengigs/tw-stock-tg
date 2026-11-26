"""研究 174c：「前十大交易人單日急加多 z≥2 → 隔天開盤買抱 5 天」（研究 174b p 0.003）能不能變成新規則

(1) 與現有「外資期貨加碼 F」重疊：2018-06 後 L 訊號日有多少同時（±1 天）是 F 訊號日；排除 F 後還剩多少效果
(2) v3 在場／空手分組（現有加碼都只在 v3 在場時做）
(3) 疊在現行組合（研究 171 引擎：v3＋V 1x＋F 0.5x＋P 1x，2018-06～）再加 L 0.5x／1x 抱 5 天：年化、最大回檔；
    L 序列環狀平移 400 次（兩者一起比「加 L − 不加 L」）
(4) 停損 5% 的影響（研究 175 方法）
用法：python -X utf8 backtest/research_174c_大戶急加多加碼.py
"""
import csv
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


R171 = load("r171", "research_171_全部加碼疊加壓力測試.py")
R175 = load("r175", "research_175_加碼規則停損.py")
R141, R142, R145, bt = R171.R141, R171.R142, R171.R145, R171.bt
R139, R138 = R141.R139, R141.R138
COST = 3.0


def lsig_by_date():
    lt = {}
    for r in csv.DictReader(open(os.path.join(HERE, "large_trader_tx.csv"), encoding="utf-8")):
        if r["cat"] == "0" and int(r["oi"]) > 0:
            lt[r["date"]] = (int(r["top10_buy"]) - int(r["top10_sell"])) / int(r["oi"])
    ds = sorted(lt)
    x = np.array([lt[d] for d in ds])
    dx = np.r_[np.nan, np.diff(x)]
    out = {}
    for i in range(250, len(ds)):
        w = dx[i - 249:i]
        out[ds[i]] = (dx[i] - w.mean()) / w.std() >= 2
    return out


def run_with_L(T, P, L, sizeL):
    """研究 171 的 run 再加 L：L[k]（第 k 天收盤後訊號）→ k+1 開盤進、抱 5 天收盤出、v3 出場一起出、同時只持有一筆"""
    eq, peak, mdd = 1.0, 1.0, 0.0
    base = 0.0
    hold = {"V": None, "F": None, "L": None}
    uprev = 0.0
    rets = []
    for k in range(1, len(T)):
        t, y = T[k], T[k - 1]
        r = base / 2 * t["r2"] + (1 - base / 2) * bt.RC
        for key, h in hold.items():
            if h is None:
                continue
            r += h[0] * (t["roc"] if h[2] else t["rcc"])
            if h[2]:
                r -= h[0] * COST / t["o"]
                h[2] = False
            h[1] -= 1
        u = 1.0 if P[k] else 0.0
        gap = t["o"] / y["c"] - 1
        r += uprev * gap + u * t["roc"] - abs(u - uprev) * COST / t["o"]
        uprev = u
        for key in hold:
            h = hold[key]
            if h is not None and (h[1] <= 0 or t["st"] == 0):
                r -= h[0] * COST / t["c"]
                hold[key] = None
        nb = 2.0 * y["st"]
        if nb != base:
            r -= bt.COST * abs(nb - base)
            base = nb
        eq *= 1 + r
        rets.append(r)
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        for key, flag, add, H in (("V", t["vsig"], 1.0, 10), ("F", t["fsig"], 0.5, 5), ("L", L[k], sizeL, 5)):
            if add > 0 and flag and t["st"] == 1 and hold[key] is None:
                hold[key] = [add, H, True]
    return eq ** (bt.TD / len(rets)) - 1, mdd


def main():
    ls = lsig_by_date()
    T = R141.build()
    n = len(T)
    NN, SP = R142.night_series(T), R145.sp_series(T)
    P = np.maximum(-NN, -SP) >= 0.02
    L = np.array([bool(ls.get(t["d"], False)) for t in T])
    F = np.array([t["fsig"] for t in T])
    st = np.array([t["st"] for t in T])
    out = ["研究 174c：前十大交易人急加多（L）→ 新加碼規則？", ""]
    # (1) 重疊
    li = np.where(L)[0]
    near_f = np.array([F[max(0, i - 1):i + 2].any() for i in li])
    out.append(f"== (1) 2018-06～ L 訊號 {len(li)} 天，其中 {near_f.sum()} 天（{near_f.mean():.0%}）與外資期貨 F 訊號同時（±1 天）==")
    # 每筆報酬（隔天開盤→第 5 天收盤，同研究 174b，T 上的近月）
    def h5(i):
        if i + 5 >= n:
            return np.nan
        return T[i + 5]["c"] / T[i + 1]["o"] - 1 - 2 * COST / T[i + 1]["o"]
    r = np.array([h5(i) for i in li])
    g = ~np.isnan(r)
    out.append(f"全部 {g.sum()} 筆 每筆 {np.nanmean(r):+.2%} 勝率 {np.mean(r[g] > 0):.0%}｜排除 F 同時 {np.sum(g & ~near_f)} 筆 {np.nanmean(r[~near_f]):+.2%} 勝率 {np.mean(r[g & ~near_f] > 0):.0%}")
    out.append(f"v3 在場 {np.sum(g & (st[li] == 1))} 筆 {np.nanmean(r[st[li] == 1]):+.2%}｜v3 空手 {np.sum(g & (st[li] == 0))} 筆 {np.nanmean(r[st[li] == 0]):+.2%}")
    out.append("")
    # (3) 組合
    out.append("== (3) 疊在現行組合（v3＋V 1x＋F 0.5x＋P 1x）==")
    base = run_with_L(T, P, L, 0.0)
    out.append(f"不加 L：{base[0]:.1%}／{base[1]:.1%}")
    rng = np.random.default_rng(1743)
    shifts = rng.integers(20, n - 20, 400)
    for size in (0.5, 1.0):
        res = run_with_L(T, P, L, size)
        d = res[0] - base[0]
        null = np.array([run_with_L(T, P, np.roll(L, s), size)[0] - run_with_L(T, P, np.roll(L, s), 0.0)[0] for s in shifts[:150]])
        out.append(f"加 L {size}x 抱 5 天：{res[0]:.1%}／{res[1]:.1%}（年化 {d:+.1%}；平移 150 次中位 {np.median(null):+.1%}、單尾 p {(1 + np.sum(null >= d)) / 151:.3f}）")
    out.append("")
    # (4) 停損：用研究 175 的 trade（全期 2005～）
    dates, day, night, near = R139.load_tx()
    bi = {d: k for k, d in enumerate(R138.DAYS)}
    ds = [d for d in dates if d in bi]
    k_of = {d: k for k, d in enumerate(ds)}
    ev, last = [], -99
    for d, flag in sorted(ls.items()):
        if flag and d in k_of:
            k = k_of[d]
            if k - last >= 5 and k + 6 < len(ds):
                ev.append((k + 1, near[d], (k + 5, "close")))
            last = k
    out.append(f"== (4) 停損（2005～，{len(ev)} 筆，日盤＋夜盤觸價）==")
    for s in (None, 0.03, 0.05):
        rs = np.array([R175.trade(day, night, ds, j, m, hl, s) for j, m, hl in ev])
        out.append(f"{'無' if s is None else f'{s:.0%}'}：每筆 {rs.mean():+.2%} 勝率 {np.mean(rs > 0):.0%} 最差 {rs.min():+.1%}")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究174c_大戶急加多加碼.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
