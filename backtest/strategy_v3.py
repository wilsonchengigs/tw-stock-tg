"""現行策略（v3，2026-11-24）的共用回測引擎：與 report.py 的 strategy_state 一致
- 週五收盤判斷、隔天收盤成交
- 進場：PX > MA60×1.01 且不過熱；出場：PX < MA80×0.975 或過熱
- 過熱：融資÷指數 偏離 250 日均 > 17.5% 或 z（偏離÷250 日標準差）> 2
- 過熱出場後回補：偏離 < 12.5% 且 z ≤ 2 且 PX ≥ MA80×0.975
參數可調（給研究用）；hot_lev＝過熱時保留的槓桿（0＝全出）
"""
import importlib.util
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r38", os.path.join(HERE, "research_38_融資過熱安慰劑.py"))
R38 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R38)
R3 = R38.R
bt = R3.bt
DAYS, PX, N, WE = bt.DAYS, bt.PX, len(bt.DAYS), bt.WEEK_END
M60, M80 = bt.get_sma(60), bt.get_sma(80)
RATIO = R3.RATIO
R2R = R38.R2R
_, _L1, _ = R3.data.series()
_p1 = [_L1.get(d, (None, None))[1] for d in DAYS]
R1R, _lp = [0.0], None
for _i in range(1, N):
    R1R.append(_p1[_i] / _lp - 1 if (_p1[_i] and _lp) else bt.R1[_i])
    if _p1[_i]:
        _lp = _p1[_i]


def _dev_z(n=250):
    dev, z = [None] * N, [None] * N
    for i in range(n - 1, N):
        w = RATIO[i - n + 1:i + 1]
        if any(v is None for v in w):
            continue
        avg = sum(w) / n
        sd = math.sqrt(sum((v - avg) ** 2 for v in w) / n)
        dev[i] = RATIO[i] / avg - 1
        z[i] = (RATIO[i] - avg) / sd if sd else 0.0
    return dev, z


DEV, Z = _dev_z()


def hot_at(i, th=0.175, zth=2.0):
    return DEV[i] is not None and (DEV[i] > th or (zth is not None and Z[i] > zth))


def run(start, end, real=False, lev=2.0, hot_lev=0.0, th=0.175, zth=2.0, reentry=0.125, use_heat=True, curve=False):
    """回傳 (年化, 最大回檔[, 每日淨值])；lev＝正常持有槓桿（00631L＋0050 混合）"""
    r1 = R1R if real else bt.R1
    r2 = R2R if real else bt.R2
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, state, heat_out, cur, pend = 0.0, 0, False, 0.0, None
    out = []

    def ret(i, L):
        if L <= 0:
            return bt.RC
        if L <= 1:
            return L * r1[i] + (1 - L) * bt.RC
        return (L - 1) * r2[i] + (2 - L) * r1[i]

    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + ret(i, cur)
        if pend is not None:
            eq *= 1 - bt.COST * abs(pend - cur)
            cur, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        out.append(eq)
        if WE[i] and i >= 260:
            hot = use_heat and hot_at(i, th, zth)
            p = PX[i]
            above = p >= M80[i] * 0.975
            if state == 0:
                if heat_out and not above:
                    heat_out = False
                cooled = DEV[i] is None or (DEV[i] < reentry and (zth is None or Z[i] <= zth))
                if (p > M60[i] * 1.01 and not hot) or (heat_out and cooled and above):
                    state, heat_out = 1, False
            elif hot:
                state, heat_out = 0, True
            elif not above:
                state, heat_out = 0, False
            # 過熱期間若設定 hot_lev，空手但仍在出場線上時保留部分部位
            if state == 1:
                t = lev
            elif heat_out and above and hot_lev > 0:
                t = hot_lev
            else:
                t = 0.0
            if t != cur:
                pend = t
    yrs = (i1 - i0) / bt.TD
    res = (eq ** (1 / yrs) - 1, mdd)
    return res + (out,) if curve else res


PER = [("2002-01-01", "2026-12-31"), ("2002-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31")]
REAL = ("2015-09-01", "2026-12-31")


def fmt(**kw):
    rs = [run(a, b, **kw) for a, b in PER]
    rr = run(*REAL, real=True, **kw)
    return " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%}"


if __name__ == "__main__":
    print("v3（現行）", fmt())
    print("無 z     ", fmt(zth=None))
    print("無融資濾網", fmt(use_heat=False))
