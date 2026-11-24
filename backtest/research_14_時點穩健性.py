"""研究 14：現行策略的時點穩健性（不是找新方法，而是確認「週五判斷、隔日收盤成交」不是運氣）

1. 判斷日：週一～週五各試一次（該週的第 k 個交易日；不足就用該週最後一天）
2. 成交延遲：當天收盤（實務上 13:20 用盤中價估算）、隔 1 天、隔 2 天、隔 3 天
3. 判斷頻率：每天、每週、每兩週、每月底
4. 出場後冷卻：出場後 n 週內不再進場（減少洗盤？）
用法：python -X utf8 backtest/research_14_時點穩健性.py
"""
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402
import data  # noqa: E402

PX, DAYS = bt.PX, bt.DAYS
N = len(PX)
PER = [("1998-01-01", "2026-12-31"), ("1998-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31"), ("2015-09-01", "2026-12-31")]
M60, M80 = bt.get_sma(60), bt.get_sma(80)
_, _, l2 = data.series()
_px = [l2.get(d, (None, None))[1] for d in DAYS]
R2R, _lp = [0.0], None
for _i in range(1, N):
    R2R.append(_px[_i] / _lp - 1 if (_px[_i] and _lp) else bt.R2[_i])
    if _px[_i]:
        _lp = _px[_i]
WEEK = [date.fromisoformat(d).isocalendar()[:2] for d in DAYS]


def flags_weekday(k):
    """每週第 k 個交易日（1 起算），若該週不足 k 天則用最後一天"""
    out = [False] * N
    i = 0
    while i < N:
        j = i
        while j + 1 < N and WEEK[j + 1] == WEEK[i]:
            j += 1
        out[min(i + k - 1, j)] = True
        i = j + 1
    return out


def flags_every(n_weeks):
    we = bt.WEEK_END
    out, c = [False] * N, 0
    for i in range(N):
        if we[i]:
            if c % n_weeks == 0:
                out[i] = True
            c += 1
    return out


FLAGS = {
    "每天": [True] * N,
    "每週五（現行）": bt.WEEK_END,
    "每兩週": flags_every(2),
    "每四週": flags_every(4),
    "每月底": [i == N - 1 or DAYS[i][:7] != DAYS[i + 1][:7] for i in range(N)],
}
for k, nm in ((1, "週一"), (2, "週二"), (3, "週三"), (4, "週四")):
    FLAGS[f"每週{nm}"] = flags_weekday(k)


def run(flags, start, end, lag=1, cool=0, real=False):
    r2 = R2R if real else bt.R2
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(DAYS) if d <= end)
    eq = peak = 1.0
    mdd, on, pos, queue, trades, cool_until = 0.0, False, False, [], 0, -1
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (r2[i] if pos else bt.RC)
        while queue and queue[0][0] <= i:
            _, t = queue.pop(0)
            if t != pos:
                eq *= 1 - bt.COST * 2
                trades += 1
                pos = t
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if flags[i] and i >= 260:
            if on and PX[i] < M80[i] * 0.98:
                on = False
                cool_until = i + cool * 5
            elif not on and PX[i] > M60[i] * 1.01 and i >= cool_until:
                on = True
            if lag == 0:
                # 當天收盤成交：今天的漲跌已在上面算過，切換只影響明天起
                if on != pos:
                    eq *= 1 - bt.COST * 2
                    trades += 1
                    pos = on
            else:
                queue.append((i + lag, on))
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, trades / yrs


def fmt(**kw):
    out = []
    for k, (a, b) in enumerate(PER):
        c, m, t = run(start=a, end=b, real=(k == 3), **kw)
        out.append(f"{'真實 ' if k == 3 else ''}{c * 100:5.1f}%/{m * 100:6.1f}%")
    t = run(start=PER[0][0], end=PER[0][1], **kw)[2]
    return " | ".join(out) + f" | 年交易 {t:4.1f}"


def main():
    L = ["研究 14：時點穩健性（全期 | 前段 | 後段 | 真實 2015-09～；年化/最大回檔）"]

    def add(name, **kw):
        L.append(f"{name:22s} {fmt(**kw)}")
        print(L[-1], flush=True)

    L.append("\n== 判斷頻率／判斷日（隔 1 天收盤成交）==")
    for nm, fl in FLAGS.items():
        add(nm, flags=fl)
    L.append("\n== 成交延遲（週五判斷）==")
    for lag, nm in ((0, "當天收盤"), (1, "隔 1 天（現行）"), (2, "隔 2 天"), (3, "隔 3 天"), (5, "隔 5 天")):
        add(nm, flags=bt.WEEK_END, lag=lag)
    L.append("\n== 出場後冷卻（週五判斷、隔 1 天）==")
    for c in (0, 1, 2, 4, 8):
        add(f"冷卻 {c} 週", flags=bt.WEEK_END, cool=c)
    out = "\n".join(L) + "\n"
    open(os.path.join(HERE, "結果_研究14_時點穩健性.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()


def run_tranches(flag_list, start, end, real=False):
    """資金平分成 len(flag_list) 份，各自用自己的判斷日跑現行規則（隔 1 天成交），不互相再平衡"""
    r2 = R2R if real else bt.R2
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(DAYS) if d <= end)
    k = len(flag_list)
    eqs, on, pos, pend = [1.0 / k] * k, [False] * k, [False] * k, [None] * k
    peak, mdd = 1.0, 0.0
    for i in range(i0, i1 + 1):
        for j in range(k):
            if i > i0:
                eqs[j] *= 1 + (r2[i] if pos[j] else bt.RC)
            if pend[j] is not None:
                if pend[j] != pos[j]:
                    eqs[j] *= 1 - bt.COST * 2
                pos[j], pend[j] = pend[j], None
            if flag_list[j][i] and i >= 260:
                if on[j] and PX[i] < M80[i] * 0.98:
                    on[j] = False
                elif not on[j] and PX[i] > M60[i] * 1.01:
                    on[j] = True
                if on[j] != pos[j]:
                    pend[j] = on[j]
        eq = sum(eqs)
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def tranches_main():
    days5 = [FLAGS["每週週一"], FLAGS["每週週二"], FLAGS["每週週三"], FLAGS["每週週四"], FLAGS["每週五（現行）"]]
    L = ["\n== 分批：資金分 5 份，週一～週五各自判斷（降低判斷日運氣）=="]
    for nm, fl in (("5 份（週一～五）", days5), ("2 份（週二＋週五）", [days5[1], days5[4]]), ("單一週五（現行）", [days5[4]])):
        cells = []
        for k, (a, b) in enumerate(PER):
            c, m = run_tranches(fl, a, b, real=(k == 3))
            cells.append(f"{'真實 ' if k == 3 else ''}{c * 100:5.1f}%/{m * 100:6.1f}%")
        L.append(f"{nm:22s} " + " | ".join(cells))
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究14_時點穩健性.txt"), "a", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    tranches_main()
