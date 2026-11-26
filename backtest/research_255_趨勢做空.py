"""研究 255（使用者 11/26 指定做空）：主策略 v3 空手時放空台指期
空單報酬≈−(加權日報酬) − 逆價差成本 3.9%／年（研究 23：近月台指期每年比價格指數多 3.9%，空方要付）；進出各 0.05%
變體：A 空手就空；B 只在 MA60 與 MA80 都比 20 天前低（均線下彎）；C＝A＋從空單期間最低點反彈 ≥10% 就停損（該段空手期不再空）
倍數 0.5／1x；基準＝v3 2x 模型價（curve）；全期 2002～、2002–2012、2013～；空單本身的逐段損益
用法：python -X utf8 backtest/research_255_趨勢做空.py
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strategy_v3 as V  # noqa: E402
import research_138_金字塔加碼與分段停損 as R138  # noqa: E402

bt = V.bt
_, _, e = V.run("2002-01-01", bt.DAYS[-1], curve=True)
e = np.asarray(e)
i0 = next(i for i, d in enumerate(bt.DAYS) if d >= "2002-01-01")
D = bt.DAYS[i0:i0 + len(e)]
base = np.r_[0.0, e[1:] / e[:-1] - 1]
PX = np.array(bt.PX[i0:i0 + len(e)])
r1 = np.r_[0.0, PX[1:] / PX[:-1] - 1]
ST = np.array(R138.ST[i0:i0 + len(e)])
full = np.array(bt.PX)
ma = lambda w: np.array([full[max(0, i - w + 1):i + 1].mean() for i in range(i0, i0 + len(e))])  # noqa: E731
m60, m80 = ma(60), ma(80)
down = np.r_[np.zeros(20, bool), (m60[20:] < m60[:-20]) & (m80[20:] < m80[:-20])]
CARRY = 0.039 / 252


def short_pos(mode):
    pos = np.zeros(len(e))
    low, stopped = None, False
    for t in range(1, len(e)):
        out = ST[t - 1] == 0  # 昨天收盤空手 → 今天持有空單（與 v3 同樣收盤成交）
        if not out:
            low, stopped = None, False
            continue
        if mode == "B" and not down[t - 1]:
            continue
        if mode == "C":
            if stopped:
                continue
            low = PX[t - 1] if low is None else min(low, PX[t - 1])
            if PX[t - 1] >= low * 1.10:
                stopped = True
                continue
        pos[t] = 1
    return pos


def stats(r, a, b):
    m = np.array([a <= d <= b for d in D])
    x = r[m]
    eq = np.cumprod(1 + x)
    return eq[-1] ** (bt.TD / len(x)) - 1, (eq / np.maximum.accumulate(eq) - 1).min()


SEG = (("2002～", "2002-01-01", "2099"), ("2002–2012", "2002-01-01", "2012-12-31"), ("2013～", "2013-01-01", "2099"))
L = ["研究 255：主策略空手時放空台指期（含逆價差成本 3.9%／年、進出 0.05%）", "期間：" + "｜".join(s[0] for s in SEG)]
L.append("v3 2x 基準：" + "｜".join(f"{c:.1%}／{m:.1%}" for c, m in (stats(base, a, b) for _, a, b in SEG)))
for mode, lab in (("A", "A 空手就空"), ("B", "B 只在均線下彎"), ("C", "C 反彈 10% 停損")):
    pos = short_pos(mode)
    turn = np.abs(np.diff(np.r_[0, pos]))
    for u in (0.5, 1.0):
        sr = u * pos * (-r1 - CARRY) - u * turn * 0.0005
        r = base + sr
        L.append(f"{lab} {u}x：" + "｜".join(f"{c:.1%}／{m:.1%}" for c, m in (stats(r, a, b) for _, a, b in SEG))
                 + f"｜空單本身年化 {np.prod(1 + sr) ** (bt.TD / len(sr)) - 1:+.1%}、持有 {pos.mean():.0%} 的日子")
yrs = np.array([d[:4] for d in D])
sr = 1.0 * short_pos("A") * (-r1 - CARRY)
L.append("\nA 1x 空單逐年：" + "  ".join(f"{y}:{np.prod(1 + sr[yrs == y]) - 1:+.0%}" for y in sorted(set(yrs))))
out = "\n".join(L)
print(out)
open(os.path.join(HERE, "結果_研究255_趨勢做空.txt"), "w", encoding="utf-8").write(out + "\n")
