"""研究 57：成本與成交方式敏感度（新版策略：出場 2.5%＋融資過熱）
- 換手成本：每單位曝險 0.1%／0.25%（預設）／0.5%／1.0%
- 成交：隔天收盤（預設）／隔天開盤（Yahoo ^TWII 開盤價，2x 部位當天報酬＝收盤/開盤）／當天收盤
- 現金利率：0%／1%（預設）／2%
用法：python -X utf8 backtest/research_57_成本敏感度.py
"""
import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r41", os.path.join(HERE, "research_41_總經濾網.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
bt, DAYS, PX, N, WE, HOT = R.bt, R.DAYS, R.PX, R.N, R.WE, R.HOT
TW = timezone(timedelta(hours=8))
r = json.load(open(os.path.join(HERE, "TWII.json")))
_o = {datetime.fromtimestamp(t, TW).strftime("%Y-%m-%d"): o for t, o in zip(r["timestamp"], r["indicators"]["quote"][0]["open"]) if o}
OPEN = [_o.get(d) for d in DAYS]


def run(start, end, cost=0.0025, cash=0.01, exe="next_close"):
    rc = cash / bt.TD
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, on, pos, pend = 0.0, False, False, None
    for i in range(i0, i1 + 1):
        if i > i0:
            if pend is not None and exe == "next_open" and OPEN[i]:
                # 開盤換倉：前收→開盤用舊部位，開盤→收盤用新部位
                g1 = OPEN[i] / PX[i - 1] - 1
                g2 = PX[i] / OPEN[i] - 1
                a = (1 + (2 * g1 if pos else rc / 2)) * (1 - cost * 2) * (1 + (2 * g2 if pend else rc / 2))
                eq *= a
                pos, pend = pend, None
            else:
                eq *= 1 + (bt.R2[i] if pos else rc)
        if pend is not None:
            eq *= 1 - cost * 2
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if WE[i] and i >= 260:
            on = (not (PX[i] < R.M80[i] * 0.975 or HOT[i])) if on else (PX[i] > R.M60[i] * 1.01 and not HOT[i])
            if on != pos:
                if exe == "same_close":
                    eq *= 1 - cost * 2
                    pos = on
                else:
                    pend = on
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def main():
    L = ["研究 57：成本與成交敏感度（全期 2002- | 前段 | 後段；模擬價格）"]

    def add(nm, **kw):
        rs = [run(a, b, **kw) for a, b in R.PER]
        L.append(f"{nm:24s} " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs))
        print(L[-1], flush=True)

    add("預設（0.25%、隔天收盤、現金 1%）")
    for c in (0.001, 0.005, 0.01):
        add(f"成本 {c:.2%}", cost=c)
    add("隔天開盤成交", exe="next_open")
    add("當天收盤成交", exe="same_close")
    for cr in (0.0, 0.02):
        add(f"現金利率 {cr:.0%}", cash=cr)
    open(os.path.join(HERE, "結果_研究57_成本敏感度.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
