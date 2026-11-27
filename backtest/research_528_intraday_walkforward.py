"""研究 528：日內順勢（D＋E 合併，一天最多 1 口）滾動前進
參數格：D 量測時點 {10:00,10:30,11:00,11:30} × D 門檻 {0.3,0.5,0.75}% × E 門檻 {0.75,1.0,1.5}% × VIX 門檻 {無,15,18,22}＝144 組
停損反向 0.75%、13:25 出、成本 3 點（停損多扣 2 點）
每年年初只用過去所有年份挑：A 過去合計報酬最大、B 過去 t 值最大（筆數 ≥50）；2013～2026 逐年套用
對照：固定 10:30/0.5%/1%/VIX18（研究 523～526 的選擇，有後見之明）、固定不設 VIX
用法：python -X utf8 backtest/research_528_intraday_walkforward.py
"""
import os, sys, itertools
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M
from research_514_pattern_regime import yahoo
CM = 265


def precompute(a):
    """回傳每個 (T, xd, xe) 的報酬；先算 D 各時點方向與 E 各門檻第一次觸發"""
    o = M.at(a, 5); mins = a[:, 0].astype(int); cl = a[:, 1]
    res = {}
    efirst = {}
    for xe in (0.0075, 0.01, 0.015):
        idx = np.nonzero((mins >= 6) & (mins <= 240) & (np.abs(cl / o - 1) >= xe))[0]
        efirst[xe] = (int(mins[idx[0]]), 1 if cl[idx[0]] > o else -1) if len(idx) else None
    for T in (60, 90, 120, 150):
        tr = M.at(a, T) / o - 1
        for xd in (0.003, 0.005, 0.0075):
            dsig = (T, 1 if tr > 0 else -1) if abs(tr) >= xd else None
            for xe in (0.0075, 0.01, 0.015):
                c = [z for z in (dsig, efirst[xe]) if z]
                if not c:
                    res[(T, xd, xe)] = None; continue
                mm, s = min(c); e = M.at(a, mm); lvl = e * (1 - s * 0.0075); r = None
                after = (mins > mm) & (mins <= CM)
                hit = np.nonzero(after & (s * (cl - lvl) <= 0))[0]
                if len(hit):
                    r = s * (cl[hit[0]] / e - 1) - 5 / e
                else:
                    r = s * (M.at(a, CM) / e - 1) - 3 / e
                res[(T, xd, xe)] = r
    return res


def main():
    days = M.load_idx(); ds = sorted(days)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    v = {d: vix[vk[np.searchsorted(vk, d) - 1]] for d in ds}
    pre = {d: precompute(days[d]) for d in ds}
    keys = list(pre[ds[0]].keys()); VG = [0, 15, 18, 22]
    grid = [(k, g) for k in keys for g in VG]
    def rets(cfg, pred):
        k, g = cfg
        return [pre[d][k] for d in ds if pred(d) and v[d] >= g and pre[d][k] is not None]
    out = [__doc__]
    sel = {"A 合計": [], "B t值": [], "固定 10:30/0.5/1/VIX18": [], "固定 10:30/0.5/1/不設VIX": []}
    picks = {"A 合計": [], "B t值": []}
    for y in range(2013, 2027):
        ys = str(y)
        best = {"A 合計": None, "B t值": None}
        for cfg in grid:
            x = np.array(rets(cfg, lambda d: d[:4] < ys))
            if len(x) < 50:
                continue
            sc = {"A 合計": x.sum(), "B t值": x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))}
            for kk in best:
                if best[kk] is None or sc[kk] > best[kk][0]:
                    best[kk] = (sc[kk], cfg)
        for kk in best:
            cfg = best[kk][1]
            picks[kk].append(f"{y}:{cfg[0][0]//60+9}:{cfg[0][0]%60:02d}/{cfg[0][1]*100:.2g}/{cfg[0][2]*100:.2g}/V{cfg[1]}")
            sel[kk] += [(ys, r) for r in rets(cfg, lambda d: d[:4] == ys)]
        sel["固定 10:30/0.5/1/VIX18"] += [(ys, r) for r in rets(((90, 0.005, 0.01), 18), lambda d: d[:4] == ys)]
        sel["固定 10:30/0.5/1/不設VIX"] += [(ys, r) for r in rets(((90, 0.005, 0.01), 0), lambda d: d[:4] == ys)]
    for kk in picks:
        out.append(f"{kk} 每年挑到：" + " ".join(picks[kk]))
    for kk, lst in sel.items():
        x = np.array([r for _, r in lst]) * 100
        yrs = {}
        for y, r in lst:
            yrs[y] = yrs.get(y, 0) + r
        out.append(f"  {kk:22s} {len(x)} 筆 每筆 {x.mean():+.3f}% t {x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):+.2f} 合計 {x.sum():+.1f}% 正的年 {sum(1 for r in yrs.values() if r>0)}/{len(yrs)}")
    # 格點分布：144 組全期每筆
    allm = np.array([np.mean(rets(cfg, lambda d: True)) for cfg in grid]) * 100
    out.append(f"  144 組全期每筆：最小 {allm.min():+.3f}% 中位 {np.median(allm):+.3f}% 最大 {allm.max():+.3f}%；為正 {np.mean(allm>0)*100:.0f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究528_日內順勢滾動前進.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
