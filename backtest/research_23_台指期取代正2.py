"""研究 23：用台指期（TX）取代 00631L 的實際效果（待研究 19）

資料：backtest/tx_daily.csv（build_tx_history.py 從期交所下載，1998-07～，一般交易時段）
連續近月：每天持有「成交量最大」的月合約（通常是近月，結算前幾天會轉到次月）；換約時當天報酬用舊約計算，隔天起用新約
- 期貨持有報酬 vs 加權價格指數報酬：差額＝逆／正價差帶來的「隱含配息」減掉資金成本（台股除息季常見逆價差）
- 策略：同現行訊號（出場 MA80×0.975），在場時名目曝險 2 倍（2 口大台 ≈ 2 × 指數 × 200 元），全部資金放現金 1%（保證金不計息的話少約 0.3%/年，另列）
- 成本：每次進出 0.02%（手續費＋期交稅 0.002%＋滑價 1 點）× 名目；每次換約同樣 0.02%
比較：模擬 2x（bt.R2）、00631L 真實、期貨 2x
用法：python -X utf8 backtest/research_23_台指期取代正2.py
"""
import csv
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402
import data  # noqa: E402

DAYS, PX, WE = bt.DAYS, bt.PX, bt.WEEK_END
N = len(DAYS)
M60, M80 = bt.get_sma(60), bt.get_sma(80)
FCOST = 0.0002


def load_tx():
    by_day = defaultdict(dict)
    for r in csv.DictReader(open(os.path.join(HERE, "tx_daily.csv"), encoding="utf-8")):
        try:
            c = float(r["close"])
            v = float(r["volume"] or 0)
        except ValueError:
            continue
        if c <= 0:
            continue
        by_day[r["date"]][r["month"]] = (c, v)
    return by_day


def futures_returns(by_day):
    """回傳 (每日期貨報酬 list, 是否換約 list)；台股交易日沒有期貨資料時報酬＝指數報酬"""
    ret, roll = [0.0], [False]
    held = None
    for i in range(1, N):
        d0, d1 = DAYS[i - 1], DAYS[i]
        t0, t1 = by_day.get(d0), by_day.get(d1)
        if not t0 or not t1:
            ret.append(PX[i] / PX[i - 1] - 1)
            roll.append(False)
            held = None
            continue
        if held is None or held not in t0:
            held = max(t0, key=lambda m: t0[m][1])
        if held in t1:
            ret.append(t1[held][0] / t0[held][0] - 1)
        else:  # 已結算：用結算當天指數近似
            ret.append(PX[i] / t0[held][0] - 1)
        best = max(t1, key=lambda m: t1[m][1])
        roll.append(best != held)
        held = best
    return ret, roll


def signal():
    st, out = False, []
    for i in range(N):
        if WE[i] and i >= 260:
            st = (not PX[i] < M80[i] * 0.975) if st else (PX[i] > M60[i] * 1.01)
        out.append(st)
    return out


def run(kind, start, end, fr=None, roll=None, r2r=None, cash=bt.RC, hold=False):
    sig = signal()
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(DAYS) if d <= end)
    eq = peak = 1.0
    mdd, pos, pend = 0.0, hold, None
    for i in range(i0, i1 + 1):
        if i > i0:
            if kind == "fut":
                eq *= 1 + (2 * fr[i] + cash if pos else bt.RC)
                if pos and roll[i]:
                    eq *= 1 - FCOST * 2
            elif kind == "real":
                eq *= 1 + (r2r[i] if pos else bt.RC)
            else:
                eq *= 1 + (bt.R2[i] if pos else bt.RC)
        if pend is not None:
            eq *= 1 - (FCOST * 2 if kind == "fut" else bt.COST * 2)
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if not hold and WE[i] and sig[i] != pos:
            pend = sig[i]
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def main():
    by_day = load_tx()
    fr, roll = futures_returns(by_day)
    first = min(by_day)
    L = [f"研究 23：台指期取代 00631L（期貨資料 {first}～{max(by_day)}，共 {len(by_day)} 天）"]
    # 每年期貨 vs 指數價格報酬差（＝隱含配息－資金成本）
    L.append("\n== 各年：近月期貨持有報酬 − 加權價格指數報酬（正值代表逆價差收益）==")
    yr = defaultdict(lambda: [1.0, 1.0])
    for i in range(1, N):
        if DAYS[i] < first:
            continue
        y = DAYS[i][:4]
        yr[y][0] *= 1 + fr[i]
        yr[y][1] *= 1 + PX[i] / PX[i - 1] - 1
    diffs = []
    for y in sorted(yr):
        a, b = yr[y]
        diffs.append(a / b - 1)
        L.append(f"  {y} 期貨 {a - 1:+7.1%}  指數 {b - 1:+7.1%}  差 {a / b - 1:+6.2%}")
    L.append(f"  平均每年差 {sum(diffs) / len(diffs):+.2%}（框架假設 1x＝指數＋3% 配息）")
    _, _, l2 = data.series()
    px = [l2.get(d, (None, None))[1] for d in DAYS]
    r2r, lp = [0.0], None
    for i in range(1, N):
        r2r.append(px[i] / lp - 1 if (px[i] and lp) else bt.R2[i])
        if px[i]:
            lp = px[i]
    L.append("\n== 現行策略：模擬 2x vs 00631L 真實 vs 台指期 2 倍名目（年化/最大回檔）==")
    for nm, a, b in (("1999-2026", "1999-01-01", "2026-12-31"), ("1999-2012", "1999-01-01", "2012-12-31"),
                     ("2013-2026", "2013-01-01", "2026-12-31"), ("2015-09～", "2015-09-01", "2026-12-31")):
        m = run("sim", a, b)
        f = run("fut", a, b, fr, roll)
        f0 = run("fut", a, b, fr, roll, cash=0.0)
        line = f"{nm:10s} 模擬 {m[0]:6.1%}/{m[1]:6.1%} | 期貨 {f[0]:6.1%}/{f[1]:6.1%} | 期貨(保證金不計息) {f0[0]:6.1%}/{f0[1]:6.1%}"
        if a >= "2015":
            r = run("real", a, b, r2r=r2r)
            line += f" | 00631L {r[0]:6.1%}/{r[1]:6.1%}"
        L.append(line)
        print(line, flush=True)
    out = "\n".join(L) + "\n"
    print("\n".join(L[:len(diffs) + 4]))
    open(os.path.join(HERE, "結果_研究23_台指期取代正2.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
