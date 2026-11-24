"""研究 26：Jason Kelly 9Sig（季度目標成長再平衡）套到正2

規則（第三方整理，Kelly 官方規則書未公開全文）：
- 起始 60% 槓桿 ETF＋40% 現金（原版用 AGG 債券基金，這裡用現金 1%，另列「現金 3%」近似債券）
- 每季底：槓桿部位目標＝上季再平衡後的槓桿部位 × (1+g)。實際 > 目標 → 多的賣成現金；實際 < 目標 → 用現金買到目標（現金不夠就全買）
- 30 Down：槓桿 ETF 價格比近 2 年高點低 30% 以上時，忽略接下來兩次賣出訊號；兩次之後重設為 60/40
來源：https://saisantosh97.github.io/9sig-strategy/TQQQ 、https://www.quantconnect.com/terminal/cache/embedded_backtest_787203b6e727a617e96937d5e61a763e.html
用法：python -X utf8 backtest/research_26_9Sig.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402
import data  # noqa: E402

DAYS, N = bt.DAYS, len(bt.DAYS)
PER = [("1998-01-01", "2026-12-31"), ("1998-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31")]
REAL = ("2015-09-01", "2026-12-31")
QE = [i == N - 1 or (DAYS[i][5:7] in ("03", "06", "09", "12") and DAYS[i][:7] != DAYS[i + 1][:7]) for i in range(N)]
_, _, l2 = data.series()
_px = [l2.get(d, (None, None))[1] for d in DAYS]
R2R, _lp = [0.0], None
for _i in range(1, N):
    R2R.append(_px[_i] / _lp - 1 if (_px[_i] and _lp) else bt.R2[_i])
    if _px[_i]:
        _lp = _px[_i]


def run(start, end, g=0.09, init=0.6, thirty=True, cash_rate=0.01, real=False):
    r2 = R2R if real else bt.R2
    rc = cash_rate / bt.TD
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(DAYS) if d <= end)
    lev, cash = init, 1 - init
    nav = [1.0]  # 槓桿 ETF 價格（用來判斷 30 down）
    base = lev
    skips = 0
    peak, mdd = 1.0, 0.0
    for i in range(i0 + 1, i1 + 1):
        lev *= 1 + r2[i]
        cash *= 1 + rc
        nav.append(nav[-1] * (1 + r2[i]))
        eq = lev + cash
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if QE[i]:
            target = base * (1 + g)
            hi2 = max(nav[-490:])
            if thirty and nav[-1] <= hi2 * 0.7 and skips == 0:
                skips = 2
            if lev > target:
                if skips > 0:
                    skips -= 1
                    if skips == 0:
                        lev, cash = eq * init * (1 - bt.COST), eq * (1 - init)
                        base = lev
                        continue
                    base = lev
                    continue
                sell = lev - target
                lev -= sell
                cash += sell * (1 - bt.COST * 2)
            else:
                buy = min(target - lev, cash)
                cash -= buy
                lev += buy * (1 - bt.COST * 2)
            base = lev
    yrs = (i1 - i0) / bt.TD
    return (lev + cash) ** (1 / yrs) - 1, mdd


def fmt(**kw):
    cs = [run(a, b, **kw) for a, b in PER]
    rr = run(*REAL, real=True, **kw)
    return " | ".join(f"{c * 100:5.1f}%/{m * 100:6.1f}%" for c, m in cs) + f" | 真實 {rr[0] * 100:5.1f}%/{rr[1] * 100:6.1f}%"


def main():
    L = ["研究 26：9Sig 套正2（全期 | 前段 | 後段 | 真實；年化/最大回檔）；對照現行 18.3%/-43.8% | 13.0%/-43.8% | 24.2%/-36.8% | 真實 30.4%/-37.2%"]
    for g in (0.06, 0.09, 0.12):
        for thirty in (True, False):
            for cr in (0.01, 0.03):
                L.append(f"g={g:.0%} 30down={'有' if thirty else '無'} 現金 {cr:.0%}  {fmt(g=g, thirty=thirty, cash_rate=cr)}")
                print(L[-1], flush=True)
    for init in (0.5, 0.7, 0.8):
        L.append(f"g=9% 起始 {init:.0%}  {fmt(init=init)}")
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究26_9Sig.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
