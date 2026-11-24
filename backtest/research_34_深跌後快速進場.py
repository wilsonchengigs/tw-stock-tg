"""研究 34：進場太晚的量化，以及「深跌後改用較快進場線」

1. 量化：每次空手期間的最低點 → 實際進場日，相隔幾週、指數已經從低點漲了多少（錯過的漲幅）
2. 規則：空手期間若指數曾距 250 日高點跌超過 d，改用快速進場線「站上 MA(m)×b」；否則用原本 MA60×1.01
   提早用快速線進場的部位，在站上 MA60×1.01 之前，若跌破「空手期間最低點」就出場（停損）
3. 統計：網格（d × m × b）三段＋真實、樣本外（只用前段挑參數）、與「不分深淺都用快速線」對照
用法：python -X utf8 backtest/research_34_深跌後快速進場.py
"""
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402
import data  # noqa: E402

DAYS, PX, WE, N = bt.DAYS, bt.PX, bt.WEEK_END, len(bt.DAYS)
M60, M80 = bt.get_sma(60), bt.get_sma(80)
HI250 = [max(PX[max(0, i - 249):i + 1]) for i in range(N)]
PER = [("1998-01-01", "2026-12-31"), ("1998-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31")]
REAL = ("2015-09-01", "2026-12-31")
_, _, l2 = data.series()
_px = [l2.get(d, (None, None))[1] for d in DAYS]
R2R, _lp = [0.0], None
for _i in range(1, N):
    R2R.append(_px[_i] / _lp - 1 if (_px[_i] and _lp) else bt.R2[_i])
    if _px[_i]:
        _lp = _px[_i]


def run(start, end, d=None, m=20, b=1.0, real=False, log=None):
    r2 = R2R if real else bt.R2
    fast = bt.get_sma(m)
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, state, pos, pend = 0.0, 0, False, None
    off_low, deep = None, False
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (r2[i] if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * 2
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if i < 260:
            continue
        if state == 0:
            off_low = PX[i] if off_low is None else min(off_low, PX[i])
            if d is not None and PX[i] / HI250[i] - 1 <= -d:
                deep = True
        if not WE[i]:
            continue
        new = state
        if state == 0:
            if PX[i] > M60[i] * 1.01:
                new = 2
            elif deep and PX[i] > fast[i] * b:
                new = 1
        elif state == 1:
            if PX[i] > M60[i] * 1.01:
                new = 2
            elif PX[i] < off_low:
                new = 0
        elif PX[i] < M80[i] * 0.975:
            new = 0
        if new != state:
            if log is not None:
                log.append((DAYS[i], state, new, PX[i], off_low))
            if new == 0:
                off_low, deep = None, False
        state = new
        want = state != 0
        if want != pos:
            pend = want
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def ev(**kw):
    return [run(a, b, **kw) for a, b in PER], run(*REAL, real=True, **kw)


def fmt(rs, rr):
    return " | ".join(f"{c * 100:5.1f}%/{m * 100:6.1f}%" for c, m in rs) + f" | 真實 {rr[0] * 100:5.1f}%/{rr[1] * 100:6.1f}%"


def lateness():
    """現行策略：每次空手期間最低點 → 進場日"""
    out, st, low_i, start_i = [], False, None, None
    for i in range(260, N):
        if not st:
            if low_i is None or PX[i] < PX[low_i]:
                low_i = i
        if WE[i]:
            if not st and PX[i] > M60[i] * 1.01:
                st = True
                if PX[low_i] / HI250[low_i] - 1 <= -0.15:
                    out.append((DAYS[low_i], PX[low_i], DAYS[i], PX[i], (i - low_i) / 5, PX[i] / PX[low_i] - 1, PX[low_i] / HI250[low_i] - 1))
            elif st and PX[i] < M80[i] * 0.975:
                st, low_i = False, None
    return out


def main():
    L = ["研究 34：深跌後快速進場（全期 | 前段 | 後段 | 真實；年化/最大回檔）"]
    L.append("\n== 1. 現行策略在深跌（距高點 ≥ 15%）之後進場晚了多少 ==")
    gaps = lateness()
    for lo_d, lo, en_d, en, wk, miss, dd in gaps:
        L.append(f"  低點 {lo_d} {lo:,.0f}（距高 {dd:.0%}）→ 進場 {en_d} {en:,.0f}：晚 {wk:4.1f} 週、已漲 {miss:+.1%}")
    if gaps:
        L.append(f"  平均晚 {sum(g[4] for g in gaps) / len(gaps):.1f} 週、錯過 {sum(g[5] for g in gaps) / len(gaps):+.1%}（中位 {sorted(g[5] for g in gaps)[len(gaps) // 2]:+.1%}）")
    base = ev()
    L.append(f"\n現行 {fmt(*base)}")

    def ok(rs, rr):
        return (all(a[0] >= b[0] - 1e-9 for a, b in zip(rs, base[0])) and rs[0][1] > -0.5
                and rr[0] >= base[1][0] - 1e-9 and rr[1] >= base[1][1] - 0.03)

    res = []
    for d, m, b in itertools.product((0.15, 0.20, 0.25, 0.30), (10, 20, 40), (1.0, 1.02, 1.04)):
        rs, rr = ev(d=d, m=m, b=b)
        res.append(((d, m, b), rs, rr, ok(rs, rr)))
    L.append(f"\n== 2. 網格 {len(res)} 組：三段＋真實都勝現行 {sum(x[3] for x in res)} 組；回檔 > 50% {sum(x[1][0][1] < -0.5 for x in res)} 組 ==")
    for idx, nm in ((0, "深跌門檻"), (1, "快速均線"), (2, "緩衝")):
        vals = sorted({x[0][idx] for x in res})
        L.append(f"  {nm}：" + "、".join(f"{v}→{sum(x[3] for x in res if x[0][idx] == v)}/{sum(1 for x in res if x[0][idx] == v)}" for v in vals))
    for p, rs, rr, g in sorted(res, key=lambda x: -x[1][0][0])[:10]:
        L.append(f"  跌≥{p[0]:.0%} 站上 MA{p[1]}x{p[2]} {'★' if g else ' '} {fmt(rs, rr)}")
    best = max(res, key=lambda x: x[1][1][0])
    L.append(f"  樣本外：前段最佳 跌≥{best[0][0]:.0%} MA{best[0][1]}x{best[0][2]} → 後段 {best[1][2][0]:.1%}（現行 {base[0][2][0]:.1%}）、真實 {best[2][0]:.1%}（現行 {base[1][0]:.1%}）")
    L.append("\n== 3. 對照：不分深淺都用快速線（d＝0）==")
    for m, b in itertools.product((10, 20, 40), (1.0, 1.02)):
        rs, rr = ev(d=0.0, m=m, b=b)
        L.append(f"  任何時候 站上 MA{m}x{b}  {fmt(rs, rr)}")
    log = []
    p = max(res, key=lambda x: (x[3], x[1][0][0]))[0]
    run("1998-01-01", "2026-12-31", d=p[0], m=p[1], b=p[2], log=log)
    L.append(f"\n== 代表組 跌≥{p[0]:.0%} 站上 MA{p[1]}x{p[2]} 的快速進場事件 ==")
    for k, (dt, s0, s1, px, lo) in enumerate(log):
        if s1 == 1:
            nx = log[k + 1] if k + 1 < len(log) else None
            L.append(f"  {dt} 快速進場 {px:,.0f}（低點 {lo:,.0f}）→ " + (f"{nx[0]} {'轉正常持有' if nx[2] == 2 else '停損'} {nx[3]:,.0f}（{nx[3] / px - 1:+.1%}）" if nx else "持有中"))
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究34_深跌後快速進場.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
