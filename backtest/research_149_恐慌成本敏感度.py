"""研究 149：候選 6 的成本／滑價敏感度（崩跌日開盤滑價可能遠大於 3 點）

每筆來回成本 3／10／20／40／80 點；報酬＝D 開盤 → D+1 開盤；2017-05～（夜盤或 S&P 跌 ≥2%）與 1998–2017（S&P 代理）
另列：損益兩平的每筆成本（點）
用法：python -X utf8 backtest/research_149_恐慌成本敏感度.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r148", os.path.join(HERE, "research_148_恐慌連續觸發.py"))
R148 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R148)


def main():
    rows = R148.build()  # r 已扣 3 點
    out = ["研究 149：恐慌隔天做多 成本敏感度（每筆來回成本，點）", ""]
    for per, lo, hi in (("2017-05～", "2017-05-15", "2099"), ("1998～2017-05", "1998", "2017-05-15")):
        s = [x for x in rows if x["sig"] and lo <= x["d"] < hi]
        px = np.array([x["c"] for x in s])  # 用當天收盤近似價位換算點數
        gross = np.array([x["r"] for x in s]) + 3.0 / px
        parts = []
        for cst in (3, 10, 20, 40, 80):
            net = gross - cst / px
            parts.append(f"{cst} 點 {net.mean():+.2%}/{np.mean(net > 0):.0%}")
        be = np.mean(gross * px)
        out.append(f"{per} {len(s)} 次（平均價位 {px.mean():,.0f}）：" + "  ".join(parts) + f"  ｜損益兩平成本約 {be:,.0f} 點／筆")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究149_恐慌成本敏感度.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
