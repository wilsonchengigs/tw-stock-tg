"""研究 162：台指期連假效應（休市 ≥4 個日曆天，例如春節、清明、端午、中秋、國慶連假）

事件 D＝連假前最後一個交易日、D1＝連假後第一個交易日；同契約（D 的近月）
看：(1) D 日盤（開→收）(2) D 收→D1 開（跨連假跳空，含夜盤時代 D 晚上的夜盤）(3) D1 日盤 (4) D 收→D1 收
對照：一般週末（休 3 天）與平日；1998～2026、分 1998–2012／2013–2026；sign-flip 雙尾 p（2000 次）
用法：python -X utf8 backtest/research_162_連假效應.py
"""
import importlib.util
import os
import sys
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r139", os.path.join(HERE, "research_139_日夜盤報酬拆解.py"))
R139 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R139)


def signflip(x, rng):
    x = np.asarray(x)
    m = x.mean()
    sims = np.array([(x * rng.choice((-1, 1), len(x))).mean() for _ in range(2000)])
    return (1 + np.sum(np.abs(sims) >= abs(m))) / 2001


def main():
    dates, day, night, near = R139.load_tx()
    rows = []
    for k in range(len(dates) - 1):
        d, d1 = dates[k], dates[k + 1]
        m = near[d]
        a, b = day[d].get(m), day[d1].get(m)
        if not (a and b):
            continue
        gap_days = (date.fromisoformat(d1) - date.fromisoformat(d)).days
        rows.append(dict(d=d, g=gap_days, dy=a[3] / a[0] - 1, x=b[0] / a[3] - 1, dy1=b[3] / b[0] - 1, cc=b[3] / a[3] - 1))
    rng = np.random.default_rng(162)
    out = ["研究 162：台指期連假效應（D＝連假前最後交易日、D1＝連假後第一天）", ""]
    for per, lo, hi in (("1998–2026", "1998", "2099"), ("1998–2012", "1998", "2013"), ("2013–2026", "2013", "2099")):
        out.append(f"== {per} ==")
        for lab, f in (("連假（休 ≥4 天）", lambda x: x["g"] >= 5), ("一般週末（3 天）", lambda x: x["g"] == 3), ("平日", lambda x: x["g"] == 1)):
            s = [x for x in rows if lo <= x["d"] < hi and f(x)]
            parts = []
            for key, nm in (("dy", "D 日盤"), ("x", "跨假跳空"), ("dy1", "D1 日盤"), ("cc", "D收→D1收")):
                v = [x[key] for x in s]
                parts.append(f"{nm} {np.mean(v):+.2%}（勝 {np.mean(np.array(v) > 0):.0%}, p {signflip(v, rng):.3f}）")
            out.append(f"{lab:12s} {len(s):4d} 次  " + "  ".join(parts))
        out.append("")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究162_連假效應.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
