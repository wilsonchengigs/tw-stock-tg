"""研究 96：同一筆錢，一次投入 vs 分 3／6／12／24 個月平均投入（未投入部分放現金 1%）
對象：v3 策略帳戶、0050 長抱、00631L 長抱；從 2002～2021 每個月初起算，看 5 年後（與 3 年後）的資產
報表：分批勝過一次投入的比例、平均差距、最差情況
用法：python -X utf8 backtest/research_96_單筆vs分批.py
"""
import importlib.util
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r93", os.path.join(HERE, "research_93_滾動窗口勝率.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
DAYS = R.DAYS
RC = R.bt.RC
i0 = next(i for i, d in enumerate(DAYS) if d >= "2002-01-01")


def main():
    curves = {k: R.spliced(k) for k in ("v3", "0050", "00631L")}
    n = min(len(c) for c in curves.values())
    days = DAYS[i0:i0 + n]
    month_starts = [k for k in range(1, n) if days[k][:7] != days[k - 1][:7]]
    L = ["研究 96：一次投入 vs 分批（同一筆 100 萬；未投入的放現金 1%）"]
    for horizon in (3, 5):
        h = horizon * 245
        L.append(f"\n== {horizon} 年後資產 ==")
        for nm, c in curves.items():
            for m in (3, 6, 12, 24):
                wins, diffs, lumps, dcas = 0, [], [], []
                for k in (s for s in month_starts if s + h < n):
                    lump = c[k + h] / c[k]
                    buys = [s for s in month_starts if s >= k][:m]
                    val = 0.0
                    for b in buys:
                        cash_days = b - k
                        amt = (1 / m) * (1 + RC) ** cash_days
                        val += amt * c[k + h] / c[b]
                    wins += val > lump
                    diffs.append(val / lump - 1)
                    lumps.append(lump)
                    dcas.append(val)
                cnt = len(diffs)
                L.append(f"  {nm:7s} 分 {m:2d} 個月：分批勝一次 {wins / cnt:.0%}、平均差距 {statistics.mean(diffs):+.1%}、"
                         f"最差起點：一次 {min(lumps):.2f} 倍 vs 分批 {min(dcas):.2f} 倍（{cnt} 個起點）")
        print("\n".join(L[-13:]), flush=True)
    open(os.path.join(HERE, "結果_研究96_單筆vs分批.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
