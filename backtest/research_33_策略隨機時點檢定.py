"""研究 33：現行策略的優勢是不是運氣？——隨機時點置換檢定（permutation test）

做法：取現行策略（MA60×1.01 進／MA80×0.975 出）1998–2026 的實際「持有區段長度」與「空手區段長度」（以週計），
各自隨機重排後交錯拼回去（保留持有比例、交易次數、區段長度分布，只打亂「什麼時候持有」），2000 次。
比較實際策略與隨機策略的年化、最大回檔；p＝隨機策略 ≥ 實際的比例。另做 2013–2026 後段與真實價格。
用法：python -X utf8 backtest/research_33_策略隨機時點檢定.py
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402
import data  # noqa: E402

DAYS, PX, WE, N = bt.DAYS, bt.PX, bt.WEEK_END, len(bt.DAYS)
M60, M80 = bt.get_sma(60), bt.get_sma(80)
_, _, l2 = data.series()
_px = [l2.get(d, (None, None))[1] for d in DAYS]
R2R, _lp = [0.0], None
for _i in range(1, N):
    R2R.append(_px[_i] / _lp - 1 if (_px[_i] and _lp) else bt.R2[_i])
    if _px[_i]:
        _lp = _px[_i]
WK = [i for i in range(N) if WE[i]]


def weekly_signal():
    st, out = False, []
    for i in WK:
        if i >= 260:
            st = (not PX[i] < M80[i] * 0.975) if st else (PX[i] > M60[i] * 1.01)
        out.append(st)
    return out


def run_weekly(sig, start, end, real=False):
    r2 = R2R if real else bt.R2
    pos_day = [False] * N
    for k, i in enumerate(WK):
        nxt = WK[k + 1] if k + 1 < len(WK) else N
        for j in range(i + 2, min(nxt + 2, N)):  # 週五判斷、隔天收盤成交 → 從 i+2 起吃到報酬
            pos_day[j] = sig[k]
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(DAYS) if d <= end)
    eq = peak = 1.0
    mdd = 0.0
    for i in range(i0 + 1, i1 + 1):
        eq *= 1 + (r2[i] if pos_day[i] else bt.RC)
        if pos_day[i] != pos_day[i - 1]:
            eq *= 1 - bt.COST * 2
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def runs(sig, k0):
    seg = []
    cur, n = sig[k0], 0
    for s in sig[k0:]:
        if s == cur:
            n += 1
        else:
            seg.append((cur, n))
            cur, n = s, 1
    seg.append((cur, n))
    return seg


def shuffle(sig, k0, rng):
    seg = runs(sig, k0)
    ons = [n for s, n in seg if s]
    offs = [n for s, n in seg if not s]
    rng.shuffle(ons)
    rng.shuffle(offs)
    first = seg[0][0]
    out = list(sig[:k0])
    a, b = list(ons), list(offs)
    turn = first
    while a or b:
        if turn and a:
            out += [True] * a.pop()
        elif not turn and b:
            out += [False] * b.pop()
        turn = not turn
    return out[:len(sig)]


def main():
    sig = weekly_signal()
    k0 = next(k for k, i in enumerate(WK) if DAYS[i] >= "1998-01-01")
    rng = random.Random(5)
    L = ["研究 33：現行策略隨機時點置換檢定（2000 次；保留持有比例與區段長度，只打亂時點）"]
    seg = runs(sig, k0)
    L.append(f"持有區段 {sum(1 for s, _ in seg if s)} 段、空手 {sum(1 for s, _ in seg if not s)} 段、持有比例 {sum(n for s, n in seg if s) / sum(n for _, n in seg):.0%}")
    sims = [shuffle(sig, k0, rng) for _ in range(2000)]
    for nm, a, b, real in (("全期 1998-2026", "1998-01-01", "2026-12-31", False), ("後段 2013-2026", "2013-01-01", "2026-12-31", False),
                           ("真實 2015-09～", "2015-09-01", "2026-12-31", True)):
        act = run_weekly(sig, a, b, real)
        rs = [run_weekly(s, a, b, real) for s in sims]
        cs = sorted(r[0] for r in rs)
        ms = sorted(r[1] for r in rs)
        pc = (sum(1 for r in rs if r[0] >= act[0]) + 1) / 2001
        pm = (sum(1 for r in rs if r[1] >= act[1]) + 1) / 2001
        L.append(f"{nm}：實際 {act[0]:.1%}／{act[1]:.1%}｜隨機 年化中位 {cs[1000]:.1%}（95 分位 {cs[1900]:.1%}）、回檔中位 {ms[1000]:.1%}（最好 5% {ms[1900]:.1%}）｜p(年化)＝{pc:.4f}、p(回檔)＝{pm:.4f}")
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究33_策略隨機時點檢定.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
