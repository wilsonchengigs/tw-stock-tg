"""研究 11：進出場門檻細掃（待研究 16、17）

- 16：進場 MA50～70 × (0.99～1.02)、出場 MA70～100 × (0.97～0.99)，完整格點看現行 (60, 1.01, 80, 0.98) 是否在穩定高原上，
  以及研究 06／07 看到的「進場放寬到 MA60×1.00」是否真的較好（含真實價格、各年度）
- 17：現行 MA60×1.01 進場 ＋ 出場改「收盤跌破 n 日最低收盤」（Donchian 短出場），或兩種出場任一觸發
評分：全期／前段／後段三段年化都 ≥ 現行、全期回檔 < 50%、真實 2015-09～ 年化 ≥ 現行且回檔不深於現行 +3%
用法：python -X utf8 backtest/research_11_進出場細掃.py
"""
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402
import data  # noqa: E402

PX, DAYS, WE = bt.PX, bt.DAYS, bt.WEEK_END
N = len(PX)
PER = [("1998-01-01", "2026-12-31"), ("1998-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31")]
REAL = ("2015-09-01", "2026-12-31")
IDX = {(s, e): (next(i for i, d in enumerate(DAYS) if d >= s), max(i for i, d in enumerate(DAYS) if d <= e)) for s, e in PER + [REAL]}
_, _, l2 = data.series()
_px = [l2.get(d, (None, None))[1] for d in DAYS]
R2R, _lp = [0.0], None
for _i in range(1, N):
    R2R.append(_px[_i] / _lp - 1 if (_px[_i] and _lp) else bt.R2[_i])
    if _px[_i]:
        _lp = _px[_i]


def rolling_min(n):
    return [min(PX[i - n:i]) if i >= n else None for i in range(N)]


_RMIN = {}


def signals(ein, bin_, eout, bout, don=None, mode="ma"):
    """回傳每日 on/off（週五更新）；mode: ma＝均線出場、don＝Donchian 出場、any＝任一觸發出場"""
    mi, mo = bt.get_sma(ein), bt.get_sma(eout)
    if don and don not in _RMIN:
        _RMIN[don] = rolling_min(don)
    rm = _RMIN.get(don)
    st, out = False, []
    for i in range(N):
        if WE[i] and i >= 260:
            if st:
                ex_ma = PX[i] < mo[i] * bout
                ex_dn = rm is not None and PX[i] < rm[i]
                ex = ex_ma if mode == "ma" else ex_dn if mode == "don" else (ex_ma or ex_dn)
                st = not ex
            else:
                st = PX[i] > mi[i] * bin_
        out.append(st)
    return out


def run(sig, key, real=False):
    i0, i1 = IDX[key]
    r2 = R2R if real else bt.R2
    eq = peak = 1.0
    mdd, pos, pend = 0.0, False, None
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (r2[i] if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * 2
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if WE[i] and sig[i] != pos:
            pend = sig[i]
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def evaluate(sig):
    r = [run(sig, p) for p in PER]
    rr = run(sig, REAL, real=True)
    return r, rr


def fmt(r, rr):
    return " | ".join(f"{c * 100:5.1f}%/{m * 100:6.1f}%" for c, m in r) + f" | 真實 {rr[0] * 100:5.1f}%/{rr[1] * 100:6.1f}%"


def main():
    L = ["研究 11：進出場細掃（格式：全期 | 前段 | 後段 | 真實 2015-09～；年化/最大回檔）"]
    base_r, base_rr = evaluate(signals(60, 1.01, 80, 0.98))
    L.append(f"現行 MA60x1.01／MA80x0.98  {fmt(base_r, base_rr)}")

    def better(r, rr):
        return (all(r[k][0] >= base_r[k][0] - 1e-9 for k in range(3)) and r[0][1] > -0.5
                and rr[0] >= base_rr[0] - 1e-9 and rr[1] >= base_rr[1] - 0.03)

    L.append("\n== 16. 格點：進場 MA × 緩衝、出場 MA × 緩衝 ==")
    grid = list(itertools.product((50, 55, 60, 65, 70), (0.99, 1.0, 1.005, 1.01, 1.015, 1.02),
                                  (70, 75, 80, 90, 100), (0.97, 0.98, 0.99)))
    res = []
    for ein, bi, eo, bo in grid:
        r, rr = evaluate(signals(ein, bi, eo, bo))
        res.append(((ein, bi, eo, bo), r, rr, better(r, rr)))
    nb = sum(1 for x in res if x[3])
    L.append(f"共 {len(res)} 組；三段＋真實都勝現行且回檔 < 50%：{nb} 組")
    L.append("全期年化前 25 名：")
    for p, r, rr, ok in sorted(res, key=lambda x: -x[1][0][0])[:25]:
        L.append(f"  MA{p[0]}x{p[1]}／MA{p[2]}x{p[3]} {'★' if ok else ' '} {fmt(r, rr)}")
    L.append("通過全部條件的組合：")
    for p, r, rr, ok in res:
        if ok:
            L.append(f"  MA{p[0]}x{p[1]}／MA{p[2]}x{p[3]}  {fmt(r, rr)}")
    L.append("\n進場緩衝單獨變動（出場固定 MA80x0.98）：")
    for bi in (0.99, 0.995, 1.0, 1.005, 1.01, 1.015, 1.02):
        r, rr = evaluate(signals(60, bi, 80, 0.98))
        L.append(f"  MA60x{bi}  {fmt(r, rr)}")
    L.append("\n平均：各進場緩衝在全部 75 組進出場均線下的全期年化中位數／回檔中位數")
    for bi in (0.99, 1.0, 1.005, 1.01, 1.015, 1.02):
        xs = [x for x in res if x[0][1] == bi]
        cs = sorted(x[1][0][0] for x in xs)
        ms = sorted(x[1][0][1] for x in xs)
        rs = sorted(x[2][0] for x in xs)
        L.append(f"  x{bi}: 全期 {cs[len(cs) // 2] * 100:5.1f}%／{ms[len(ms) // 2] * 100:6.1f}%  真實 {rs[len(rs) // 2] * 100:5.1f}%")

    L.append("\n== 17. 現行進場＋Donchian 短出場 ==")
    for don in (10, 20, 30, 40, 60):
        for mode, nm in (("don", "只用新低出場"), ("any", "新低或 MA80x0.98 任一")):
            r, rr = evaluate(signals(60, 1.01, 80, 0.98, don, mode))
            L.append(f"  {don} 日新低 {nm:16s} {'★' if better(r, rr) else ' '} {fmt(r, rr)}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究11_進出場細掃.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
