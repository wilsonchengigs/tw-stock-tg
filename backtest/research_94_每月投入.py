"""研究 94：每月投入新資金（定期定額情境）——v3 策略 vs 定期定額 0050 vs 定期定額 00631L
每月第一個交易日投入 1 萬元：
- v3：新資金併入帳戶，跟著策略（在場就買 00631L、空手就放現金，等進場時一起買）
- 0050／00631L：每月買入長抱
比較 2007～、2012～、2016～ 起算到 2026-11 的期末資產、總投入、內部報酬率（IRR）、最大回檔（資產相對前高，含新投入）
2015-09 起用真實價格（研究 87 的串接方式）
用法：python -X utf8 backtest/research_94_每月投入.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r93", os.path.join(HERE, "research_93_滾動窗口勝率.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
DAYS = R.DAYS
i0 = next(i for i, d in enumerate(DAYS) if d >= "2002-01-01")


def irr(flows):
    """flows：[(年份小數, 金額)]，投入為負、期末為正；二分法"""
    lo, hi = -0.99, 2.0
    for _ in range(200):
        mid = (lo + hi) / 2
        v = sum(a / (1 + mid) ** t for t, a in flows)
        if v > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def main():
    curves = {k: R.spliced(k) for k in ("v3", "0050", "00631L")}
    n = min(len(c) for c in curves.values())
    days = DAYS[i0:i0 + n]
    L = ["研究 94：每月投入 1 萬元（期末資產／總投入／IRR／資產相對前高的最大回檔）"]
    for start in ("2007-01-01", "2012-01-01", "2016-01-01"):
        L.append(f"\n== {start[:4]} 起每月投入 ==")
        for nm, c in curves.items():
            units, invested, flows, peak, mdd, val = 0.0, 0.0, [], 0.0, 0.0, 0.0
            last_month = None
            for k, d in enumerate(days):
                if d < start:
                    continue
                if d[:7] != last_month:
                    units += 10000 / c[k]
                    invested += 10000
                    t = (k - days.index(next(x for x in days if x >= start))) / 245
                    flows.append((t, -10000))
                    last_month = d[:7]
                val = units * c[k]
                peak = max(peak, val)
                mdd = min(mdd, val / peak - 1)
            t_end = (len(days) - 1 - days.index(next(x for x in days if x >= start))) / 245
            r = irr(flows + [(t_end, val)])
            L.append(f"  {nm:7s}：期末 {val / 1e4:,.0f} 萬／投入 {invested / 1e4:,.0f} 萬（{val / invested:.1f} 倍）、IRR {r:.1%}、最大回檔 {mdd:.1%}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究94_每月投入.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
