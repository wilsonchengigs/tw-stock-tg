"""研究 101：v3 的判斷日穩健性（週一～週五各自當判斷日；融資過熱仍每天檢查）
用法：python -X utf8 backtest/research_101_v3判斷日.py
"""
import importlib.util
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("v3", os.path.join(HERE, "strategy_v3.py"))
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)
DAYS, N = V.DAYS, V.N
WEEK = [date.fromisoformat(d).isocalendar()[:2] for d in DAYS]


def flags(k):
    out, i = [False] * N, 0
    while i < N:
        j = i
        while j + 1 < N and WEEK[j + 1] == WEEK[i]:
            j += 1
        out[min(i + k - 1, j)] = True
        i = j + 1
    return out


def main():
    L = ["研究 101：v3 判斷日（全期 2002- | 前段 | 後段 | 真實）"]
    orig = V.WE
    for k, nm in ((1, "週一"), (2, "週二"), (3, "週三"), (4, "週四"), (5, "週五（現行）")):
        V.WE = flags(k) if k < 5 else orig
        L.append(f"{nm:10s} {V.fmt()}")
        print(L[-1], flush=True)
    V.WE = orig
    open(os.path.join(HERE, "結果_研究101_v3判斷日.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
