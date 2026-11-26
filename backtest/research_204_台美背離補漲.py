"""研究 204：台股 vs 美股短期極度背離後，台股會不會補漲？（2026-11：加權 20 日 -20%、S&P 只離高 -2～-6%）

事件：加權 20 日報酬 − S&P 20 日報酬（對齊到台股日，用前一個美股收盤）≤ -10／-15／-20%；去叢集（事件後 20 天內不重複）
結果：事件後 5／20／60 日 加權報酬（絕對）、加權 − S&P（相對）；對照＝所有交易日同天期的平均；
家族：3 門檻 × 3 天期 × 2（絕對／相對）＝18 檢定，事件日序列環狀平移（保留群聚）取最大 z → 家族 p
兩段：1998–2012、2013–2026
用法：python -X utf8 backtest/research_204_台美背離補漲.py
"""
import bisect
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402

NY = timezone(timedelta(hours=-5))
g = json.load(open(os.path.join(HERE, "GSPC.json")))
SP = [(datetime.fromtimestamp(t, NY).strftime("%Y-%m-%d"), p) for t, p in zip(g["timestamp"], g["indicators"]["quote"][0]["close"]) if p]
SPD, SPP = [d for d, _ in SP], [p for _, p in SP]
DAYS = [d for d in bt.DAYS if d >= "1998-01-01"]
i0 = bt.DAYS.index(DAYS[0])
TW = np.array(bt.PX[i0:])
US = np.array([SPP[bisect.bisect_left(SPD, d) - 1] for d in DAYS])  # 台股該日之前最後一個美股收盤
N = len(DAYS)


def ret(a, k, h):
    return a[k + h] / a[k] - 1 if k + h < N else np.nan


def main():
    tw20 = np.array([TW[k] / TW[k - 20] - 1 if k >= 20 else np.nan for k in range(N)])
    us20 = np.array([US[k] / US[k - 20] - 1 if k >= 20 else np.nan for k in range(N)])
    gap = tw20 - us20
    H = (5, 20, 60)
    fa = {h: np.array([ret(TW, k, h) for k in range(N)]) for h in H}
    fr = {h: np.array([ret(TW, k, h) - ret(US, k, h) for k in range(N)]) for h in H}
    L = ["研究 204：台股 20 日落後美股 ≥ x 之後（去叢集 20 天；絕對＝加權；相對＝加權 − S&P）",
         f"現況 {DAYS[-1]}：加權 20 日 {tw20[-1]:+.1%}、S&P 20 日 {us20[-1]:+.1%}、背離 {gap[-1]:+.1%}"]

    def events(th, mask=None):
        out, last = [], -99
        for k in range(20, N):
            if gap[k] <= -th and k - last > 20 and (mask is None or mask[k]):
                out.append(k)
                last = k
        return out

    tests, flags = [], {}
    for th in (0.10, 0.15, 0.20):
        ev = events(th)
        flags[th] = np.zeros(N, bool)
        flags[th][ev] = True
        L.append(f"\n【背離 ≤ -{th:.0%}】{len(ev)} 次：" + "、".join(DAYS[k] for k in ev[-8:]) + ("…" if len(ev) > 8 else ""))
        for h in H:
            for lab, f in (("絕對", fa[h]), ("相對", fr[h])):
                v = f[ev]
                v = v[~np.isnan(v)]
                base = np.nanmean(f)
                if len(v) < 3:
                    continue
                L.append(f"  {h:>2} 日 {lab}：{len(v)} 次 平均 {v.mean():+.2%}（全部日 {base:+.2%}）中位 {np.median(v):+.2%} 正的比例 {np.mean(v > 0):.0%}")
                tests.append((th, h, lab))
        for seg, lo, hi in (("1998–2012", "1998", "2013"), ("2013–2026", "2013", "2099")):
            v = np.array([fa[20][k] for k in ev if lo <= DAYS[k] < hi and not np.isnan(fa[20][k])])
            vr = np.array([fr[20][k] for k in ev if lo <= DAYS[k] < hi and not np.isnan(fr[20][k])])
            if len(v):
                L.append(f"  {seg} 20 日：絕對 {v.mean():+.2%}（{len(v)} 次）、相對 {vr.mean():+.2%}")
    # 家族檢定：環狀平移事件旗標
    valid = np.where(~np.isnan(fa[60]))[0]
    stats = {}
    for th, h, lab in tests:
        f = (fa if lab == "絕對" else fr)[h]
        stats[(th, h, lab)] = (f[valid], flags[th][valid])

    def zmax(shift):
        best = -9
        for key, (f, fl) in stats.items():
            s = np.roll(fl, shift)
            if s.sum() < 3:
                continue
            z = (f[s].mean() - f.mean()) / (f.std() / np.sqrt(s.sum()))
            best = max(best, z)
        return best

    real = {key: (f[fl].mean() - f.mean()) / (f.std() / np.sqrt(fl.sum())) for key, (f, fl) in stats.items() if fl.sum() >= 3}
    rng = np.random.default_rng(204)
    null = np.array([zmax(int(rng.integers(100, len(valid) - 100))) for _ in range(1000)])
    L.append("\n【家族檢定】（18 檢定，環狀平移 1,000 次，單尾＝補漲）")
    for key, z in sorted(real.items(), key=lambda kv: -kv[1])[:6]:
        L.append(f"  背離 ≤-{key[0]:.0%} {key[1]:>2} 日 {key[2]}：z {z:+.2f}、家族 p {np.mean(null >= z):.3f}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究204_台美背離補漲.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()


def extra():
    """5 日：兩段；以及與研究 182（近 5 日內有單日跌 ≥4%）重疊——拆成 有／沒有 大跌日 兩組"""
    tw20 = np.array([TW[k] / TW[k - 20] - 1 if k >= 20 else np.nan for k in range(N)])
    us20 = np.array([US[k] / US[k - 20] - 1 if k >= 20 else np.nan for k in range(N)])
    gap = tw20 - us20
    r1 = np.array([0.0] + [TW[k] / TW[k - 1] - 1 for k in range(1, N)])
    big = np.array([k >= 5 and (r1[k - 4:k + 1] <= -0.04).any() for k in range(N)])
    L = ["\n【補充】背離 ≤-10%，5 日（絕對／相對）"]
    ev, last = [], -99
    for k in range(20, N):
        if gap[k] <= -0.10 and k - last > 20:
            ev.append(k)
            last = k
    for seg, lo, hi in (("1998–2012", "1998", "2013"), ("2013–2026", "2013", "2099")):
        a = [ret(TW, k, 5) for k in ev if lo <= DAYS[k] < hi and k + 5 < N]
        r = [ret(TW, k, 5) - ret(US, k, 5) for k in ev if lo <= DAYS[k] < hi and k + 5 < N]
        L.append(f"  {seg}：{len(a)} 次、絕對 {np.mean(a):+.2%}、相對 {np.mean(r):+.2%}")
    for name, cond in (("近 5 日有單日跌 ≥4%", True), ("近 5 日沒有", False)):
        ks = [k for k in ev if big[k] == cond and k + 5 < N]
        if ks:
            a = [ret(TW, k, 5) for k in ks]
            r = [ret(TW, k, 5) - ret(US, k, 5) for k in ks]
            L.append(f"  {name}：{len(ks)} 次、絕對 {np.mean(a):+.2%}、相對 {np.mean(r):+.2%}、絕對為正 {np.mean(np.array(a) > 0):.0%}")
    return L


if __name__ == "__main__":
    add = extra()
    print("\n".join(add))
    open(os.path.join(HERE, "結果_研究204_台美背離補漲.txt"), "a", encoding="utf-8").write("\n".join(add) + "\n")
