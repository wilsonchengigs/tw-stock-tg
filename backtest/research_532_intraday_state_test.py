"""研究 532：研究 531「主策略空手時日內順勢較好」的家族檢定與四格（狀態×VIX）資金曲線
- 檢定：主策略狀態序列（交易日）環狀平移 2000 次（位移 ≥250 天），統計量＝空手組每筆 − 在場組每筆；另做 VIX 序列平移看 VIX 效果
- 四格：在場／空手 × VIX<18／≥18，每筆、筆數／年、t
- 版本資金曲線（點數用當時指數、1 口小台每點 50 元）：全做／VIX≥18／空手才做／空手或 VIX≥18／空手且 VIX≥18
D30＋E（09:30～12:30）、一天 1 口、反向 0.75% 停損、13:25 出、成本 3 點
用法：python -X utf8 backtest/research_532_intraday_state_test.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138
from research_531_intraday_by_main_state import trade


def main():
    days = M.load_idx(); ds = sorted(days)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    vv = np.array([vix[vk[np.searchsorted(vk, d) - 1]] for d in ds])
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    sv = np.array([st[keys[np.searchsorted(keys, d) - 1]] for d in ds])
    r = np.full(len(ds), np.nan); px = np.array([M.at(days[d], 5) for d in ds])
    for i, d in enumerate(ds):
        t = trade(days[d])
        if t:
            r[i] = t[1]
    has = ~np.isnan(r)
    out = [__doc__]

    def diff(state):
        a = r[has & (state == 0)]; b = r[has & (state == 1)]
        return a.mean() - b.mean()
    obs = diff(sv); rng = np.random.default_rng(532); n = len(ds); cnt = 0; B = 2000
    for _ in range(B):
        if diff(np.roll(sv, rng.integers(250, n - 250))) >= obs:
            cnt += 1
    out.append(f"狀態平移：空手−在場 每筆差 {obs:+.3f}%，p = {(cnt+1)/(B+1):.4f}")
    hv = (vv >= 18).astype(int)
    def dv(h):
        return r[has & (h == 1)].mean() - r[has & (h == 0)].mean()
    obs2 = dv(hv); cnt = 0
    for _ in range(B):
        if dv(np.roll(hv, rng.integers(250, n - 250))) >= obs2:
            cnt += 1
    out.append(f"VIX 平移：VIX≥18 − <18 每筆差 {obs2:+.3f}%，p = {(cnt+1)/(B+1):.4f}")
    out.append("\n四格（每筆％、筆數／年、t）：")
    for s0, sl in ((1, "在場"), (0, "空手")):
        for h, hl in ((0, "VIX<18"), (1, "VIX≥18")):
            x = r[has & (sv == s0) & (hv == h)]
            out.append(f"  {sl} {hl}：{len(x)} 筆（{len(x)/17:.1f}/年）每筆 {x.mean():+.3f}% t {x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):+.2f} 勝率 {(x>0).mean()*100:.0f}%")
    out.append("\n版本資金曲線（1 口小台）：")
    vers = {"全做": np.ones(n, bool), "VIX≥18": hv == 1, "空手才做": sv == 0, "空手或 VIX≥18": (sv == 0) | (hv == 1), "空手且 VIX≥18": (sv == 0) & (hv == 1)}
    for k, m in vers.items():
        sel = has & m
        pts = r[sel] / 100 * px[sel]; eq = np.cumsum(pts)
        mdd = (eq - np.maximum.accumulate(np.concatenate([[0], eq]))[1:]).min()
        yrs = {}
        for d, p in zip(np.array(ds)[sel], pts):
            yrs[d[:4]] = yrs.get(d[:4], 0) + p
        rec = pts[np.array(ds)[sel] >= "2024"]
        x = r[sel]
        out.append(f"  {k:12s} {sel.sum():4d} 筆（{sel.sum()/17:.0f}/年）每筆 {x.mean():+.3f}% t {x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):+.2f} 合計 {pts.sum():+.0f} 點（{pts.sum()*50/1e4:+.0f} 萬）回檔 {mdd:.0f} 點 正的年 {sum(1 for v in yrs.values() if v>0)}/{len(yrs)}｜2024～ 每筆 {rec.mean():+.0f} 點")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究532_日內順勢狀態檢定.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
