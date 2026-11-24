"""研究 53：新版策略（出場 2.5%＋融資過熱濾網）逐年報酬，對照 0050、正2 長抱與舊版（出場 2%、無濾網）
2015-09 前用模擬價格，之後用 00631L／0050 真實價格
用法：python -X utf8 backtest/research_53_新版逐年.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r41", os.path.join(HERE, "research_41_總經濾網.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
bt, DAYS, PX, N, WE, HOT = R.bt, R.DAYS, R.PX, R.N, R.WE, R.HOT
RR = R.R40.R32.R
R1 = [RR.R1R[i] if DAYS[i] >= "2015-09-01" else bt.R1[i] for i in range(N)]
R2 = [RR.R2R[i] if DAYS[i] >= "2015-09-01" else bt.R2[i] for i in range(N)]


def yearly(kind):
    eq, on, pos, pend, ys, peak, mdd, mdd_y = 1.0, False, False, None, {}, 1.0, 0.0, {}
    for i in range(1, N):
        if kind == "0050":
            eq *= 1 + R1[i]
        elif kind == "hold2":
            eq *= 1 + R2[i]
        else:
            eq *= 1 + (R2[i] if pos else bt.RC)
            if pend is not None:
                eq *= 1 - bt.COST * 2
                pos, pend = pend, None
            if WE[i] and i >= 260:
                if kind == "new":
                    on = (not (PX[i] < R.M80[i] * 0.975 or HOT[i])) if on else (PX[i] > R.M60[i] * 1.01 and not HOT[i])
                else:
                    on = (not PX[i] < R.M80[i] * 0.98) if on else (PX[i] > R.M60[i] * 1.01)
                if on != pos:
                    pend = on
        y = DAYS[i][:4]
        if y != DAYS[i - 1][:4]:
            peak = ys.get(DAYS[i - 1][:4], eq)  # 每年從年初重新算回檔
        peak = max(peak, eq)
        mdd_y[y] = min(mdd_y.get(y, 0.0), eq / peak - 1)
        ys[y] = eq
    out, prev = {}, None
    for y in sorted(ys):
        if prev is not None:
            out[y] = ys[y] / prev - 1
        prev = ys[y]
    return out, mdd_y


def main():
    a, ma = yearly("new")
    b, _ = yearly("old")
    c, mc = yearly("0050")
    d, _ = yearly("hold2")
    L = ["研究 53：新版策略逐年報酬（2015-09 起真實價格；2026 只到 11/20）", "年份 | 新版 | 舊版 | 0050 長抱 | 正2 長抱 | 新版年內最大回檔 | 0050 年內最大回檔"]
    wins = 0
    for y in sorted(a):
        if y < "2002":
            continue
        wins += a[y] > c[y]
        L.append(f"{y} | {a[y]:+7.1%} | {b[y]:+7.1%} | {c[y]:+7.1%} | {d[y]:+7.1%} | {ma[y]:6.1%} | {mc[y]:6.1%}")
    n = sum(1 for y in a if y >= "2002")
    L.append(f"\n2002～2026 共 {n} 年，新版勝 0050 的年數：{wins}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究53_新版逐年.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
