"""研究 63h：「爆量」改用長期基準——補研究 63 的盲點（連續崩跌時 20 日均量被墊高，訊號不觸發）

量比定義：
  A. 前 20 日平均（研究 63b 原版）
  B. 前 120 日中位數
  C. 前 250 日中位數
  D. A 與 C 都要過（短期突出且長期也高）
訊號：量比 ≥ k 且收黑；隔天開盤買、抱 5／10 天；持有中訊號略過；成本 3 點（^TWII 近似）
另列：只在 B／C 觸發、A 沒觸發的訊號（＝原版漏掉的崩跌爆量）
用法：python -X utf8 backtest/research_63h_爆量長期基準.py
"""
import importlib.util
import os
import random
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r63b", os.path.join(HERE, "research_63b_爆量收黑買進.py"))
r63b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r63b)
r61 = r63b.r61
O, C, N, DAYS = r61.O, r61.C, r61.N, r61.DAYS
AMT = r61.VOL["成交金額"]
START = r63b.START


def ratio(kind):
    out = [None] * N
    for i in range(251, N):
        if not AMT[i]:
            continue
        if kind == "A":
            xs = [AMT[k] for k in range(i - 20, i) if AMT[k]]
            out[i] = AMT[i] / statistics.mean(xs) if len(xs) >= 16 else None
        else:
            look = 120 if kind == "B" else 250
            xs = [AMT[k] for k in range(i - look, i) if AMT[k]]
            out[i] = AMT[i] / statistics.median(xs) if len(xs) >= look * 0.8 else None
    return out


def main():
    rng = random.Random(638)
    R = {k: ratio(k) for k in "ABC"}
    L = ["研究 63h：爆量的長期基準（^TWII 近似；隔天開盤買、抱 H 天；成本 3 點）"]
    for H in (5, 10):
        L.append(f"\n== 抱 {H} 天 ==")
        for nm, cond in (
            ("A 20日均 ≥1.5", lambda i: R["A"][i] and R["A"][i] >= 1.5),
            ("B 120日中位 ≥1.5", lambda i: R["B"][i] and R["B"][i] >= 1.5),
            ("B 120日中位 ≥2.0", lambda i: R["B"][i] and R["B"][i] >= 2.0),
            ("C 250日中位 ≥1.5", lambda i: R["C"][i] and R["C"][i] >= 1.5),
            ("C 250日中位 ≥2.0", lambda i: R["C"][i] and R["C"][i] >= 2.0),
            ("D A≥1.5 且 C≥1.5", lambda i: R["A"][i] and R["A"][i] >= 1.5 and R["C"][i] and R["C"][i] >= 1.5),
            ("只在 C≥1.5、A<1.5（原版漏掉）", lambda i: R["C"][i] and R["C"][i] >= 1.5 and not (R["A"][i] and R["A"][i] >= 1.5)),
            ("只在 C≥2.0、A<1.5（原版漏掉）", lambda i: R["C"][i] and R["C"][i] >= 2.0 and not (R["A"][i] and R["A"][i] >= 1.5)),
        ):
            sig = [i for i in range(max(START, 251), N - 1) if cond(i) and C[i] < C[i - 1]]
            trs = r63b.trades(sig, H)
            if len(trs) < 8:
                L.append(f"  {nm:28s} {len(trs)} 筆，樣本不足")
                continue
            rets = [t[2] for t in trs]
            rnd = r63b.random_ev(trs, rng, reps=1000)
            ev = statistics.mean(rets)
            half = [statistics.mean([t[2] for t in trs if (DAYS[t[0]] < "2013") == f]) if any((DAYS[t[0]] < "2013") == f for t in trs) else float("nan") for f in (True, False)]
            L.append(f"  {nm:28s} {len(trs):4d} 筆 勝率 {sum(r > 0 for r in rets) / len(rets):4.0%} 每筆 {ev:+.2%}  隨機 {rnd[500]:+.2%}  p＝{(sum(x >= ev for x in rnd) + 1) / 1001:.3f}"
                     f"  前段 {half[0]:+.2%} 後段 {half[1]:+.2%}  最差 {min(rets):+.1%}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究63h_爆量長期基準.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
