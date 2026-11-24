"""研究 83：回檔期間與回本時間（新版策略 vs 0050 長抱 vs 正2 長抱；2015-09 起真實價格）
列出每段回檔超過 15% 的：開始（前高）、谷底、深度、跌到谷底花幾個月、從谷底回到前高花幾個月（未回本標示）
另算「水下時間比例」（淨值低於前高的天數比例）與最長水下期
用法：python -X utf8 backtest/research_83_回本時間.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r53", os.path.join(HERE, "research_53_新版逐年.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
bt, DAYS, PX, N, WE, HOT = R.bt, R.DAYS, R.PX, R.N, R.WE, R.HOT


def curve(kind):
    eq, on, pos, pend, out = 1.0, False, False, None, [1.0]
    for i in range(1, N):
        if kind == "0050":
            eq *= 1 + R.R1[i]
        elif kind == "hold2":
            eq *= 1 + R.R2[i]
        else:
            eq *= 1 + (R.R2[i] if pos else bt.RC)
            if pend is not None:
                eq *= 1 - bt.COST * 2
                pos, pend = pend, None
            if WE[i] and i >= 260:
                on = (not (PX[i] < R.R.M80[i] * 0.975 or HOT[i])) if on else (PX[i] > R.R.M60[i] * 1.01 and not HOT[i])
                if on != pos:
                    pend = on
        out.append(eq)
    return out


def episodes(eq, i0, th=0.15):
    eps, peak_i, trough_i, in_dd = [], i0, i0, False
    for i in range(i0, N):
        if eq[i] >= eq[peak_i]:
            if in_dd and eq[trough_i] / eq[peak_i] - 1 <= -th:
                eps.append((peak_i, trough_i, i))
            peak_i, trough_i, in_dd = i, i, False
        else:
            in_dd = True
            if eq[i] < eq[trough_i]:
                trough_i = i
    if in_dd and eq[trough_i] / eq[peak_i] - 1 <= -th:
        eps.append((peak_i, trough_i, None))
    return eps


def main():
    i0 = next(i for i, d in enumerate(DAYS) if d >= "2002-01-01")
    L = ["研究 83：回檔與回本時間（2002～2026/11；2015-09 起真實價格；只列回檔 ≥ 15%）"]
    for nm, kind in (("新版策略", "new"), ("0050 長抱", "0050"), ("00631L 長抱", "hold2")):
        eq = curve(kind)
        eps = episodes(eq, i0)
        under = sum(1 for i in range(i0, N) if eq[i] < max(eq[i0:i + 1]) * 0.999) / (N - i0)
        L.append(f"\n== {nm}：回檔 ≥15% 共 {len(eps)} 次；水下時間比例 {under:.0%} ==")
        longest = 0
        for p, t, rcv in eps:
            dn = (t - p) / 21
            up = (rcv - t) / 21 if rcv else None
            longest = max(longest, ((rcv or N - 1) - p) / 21)
            L.append(f"  {DAYS[p]} → 谷底 {DAYS[t]}（{eq[t] / eq[p] - 1:+.0%}，跌 {dn:.0f} 個月）→ "
                     + (f"回本 {DAYS[rcv]}（{up:.0f} 個月）" if rcv else "尚未回本"))
        L.append(f"  最長從前高到回本：{longest:.0f} 個月")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究83_回本時間.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
