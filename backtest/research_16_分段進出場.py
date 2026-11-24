"""研究 16：分段進出場（待研究 20、21）

20 分段進場：站上 MA60x1.01 先押 1x（0050），連續 n 週仍在進場線上（或指數比進場時高）才加到 2x
21 半出場：2x 跌破 MA80x0.98 先降成 1x（0050），跌破更長均線 MA(L)x(1-b) 才全出；1x 狀態下重新站上 MA60x1.01 回到 2x
都是週五判斷、隔天收盤成交，成本以曝險換手計
用法：python -X utf8 backtest/research_16_分段進出場.py
"""
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
M = {n: bt.get_sma(n) for n in (60, 80, 100, 120, 150, 200, 240)}
_, l1, l2 = data.series()


def real_ret(src, sim):
    px = [src.get(d, (None, None))[1] for d in DAYS]
    out, lp = [0.0], None
    for i in range(1, N):
        out.append(px[i] / lp - 1 if (px[i] and lp) else sim[i])
        if px[i]:
            lp = px[i]
    return out


R1R, R2R = real_ret(l1, bt.R1), real_ret(l2, bt.R2)
LEV_W = {0: (0.0, 0.0), 1: (0.0, 1.0), 2: (1.0, 0.0)}


def run(policy, start, end, real=False):
    """policy(i, state, ctx) -> 新 state（0 現金／1 0050／2 正2）；ctx 是 dict 可存狀態"""
    r1, r2 = (R1R, R2R) if real else (bt.R1, bt.R2)
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(DAYS) if d <= end)
    eq = peak = 1.0
    mdd, st, pos, pend, ctx, trades = 0.0, 0, 0, None, {}, 0
    for i in range(i0, i1 + 1):
        if i > i0:
            w2, w1 = LEV_W[pos]
            eq *= 1 + w2 * r2[i] + w1 * r1[i] + (1 - w2 - w1) * bt.RC
        if pend is not None:
            a, b = LEV_W[pos], LEV_W[pend]
            eq *= 1 - bt.COST * (2 * abs(a[0] - b[0]) + abs(a[1] - b[1]))
            pos, pend = pend, None
            trades += 1
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if WE[i] and i >= 260:
            st = policy(i, st, ctx)
            if st != pos:
                pend = st
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, trades / yrs


def current(i, st, ctx):
    if st == 2:
        return 0 if PX[i] < M[80][i] * 0.98 else 2
    return 2 if PX[i] > M[60][i] * 1.01 else 0


def staged_entry(n_weeks, need_higher=False):
    def p(i, st, ctx):
        if st == 0:
            if PX[i] > M[60][i] * 1.01:
                ctx["w"], ctx["px"] = 0, PX[i]
                return 1
            return 0
        if PX[i] < M[80][i] * 0.98:
            return 0
        if st == 1:
            ctx["w"] += 1
            if PX[i] > M[60][i] * 1.01 and ctx["w"] >= n_weeks and (not need_higher or PX[i] > ctx["px"]):
                return 2
            return 1
        return 2
    return p


def half_exit(L, b):
    def p(i, st, ctx):
        if st == 2:
            if PX[i] < M[L][i] * (1 - b):
                return 0
            return 1 if PX[i] < M[80][i] * 0.98 else 2
        if st == 1:
            if PX[i] < M[L][i] * (1 - b):
                return 0
            return 2 if PX[i] > M[60][i] * 1.01 else 1
        return 2 if PX[i] > M[60][i] * 1.01 else 0
    return p


def fmt(policy):
    cells = [run(policy, a, b) for a, b in PER]
    rr = run(policy, *REAL, real=True)
    return " | ".join(f"{c * 100:5.1f}%/{m * 100:6.1f}%" for c, m, _ in cells) + \
        f" | 真實 {rr[0] * 100:5.1f}%/{rr[1] * 100:6.1f}% | 年交易 {cells[0][2]:4.1f}"


def main():
    L = ["研究 16：分段進出場（全期 | 前段 | 後段 | 真實 2015-09～；年化/最大回檔）"]

    def add(nm, p):
        L.append(f"{nm:30s} {fmt(p)}")
        print(L[-1], flush=True)

    add("現行", current)
    L.append("\n== 20 分段進場：先 1x，n 週後仍在進場線上才 2x ==")
    for n in (1, 2, 4, 8):
        add(f"{n} 週後加碼", staged_entry(n))
        add(f"{n} 週後且高於進場價才加碼", staged_entry(n, True))
    L.append("\n== 21 半出場：跌破 MA80x0.98 降 1x，跌破 MA(L)x(1-b) 全出 ==")
    for Lm in (100, 120, 150, 200, 240):
        for b in (0.0, 0.03, 0.05):
            add(f"MA{Lm}x{1 - b:.2f} 全出", half_exit(Lm, b))
    out = "\n".join(L) + "\n"
    open(os.path.join(HERE, "結果_研究16_分段進出場.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
