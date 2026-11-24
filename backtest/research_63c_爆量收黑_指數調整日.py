"""研究 63c：研究 63b「爆量收黑買進」是不是 MSCI／指數調整日的收盤賣壓反轉？

假說：2、5、8、11 月最後一個交易日（MSCI 季度／半年度調整生效）收盤集合競價有被動基金巨量，
      成交金額暴增、收盤價被壓低，隔天反彈——這會被研究 63b 當成「爆量收黑」。
      台指期不參與現股收盤競價 → 也能解釋為何「台指期口數」版本效果較弱。
做法：
- 標記調整日＝2／5／8／11 月最後一個交易日（另測「該月最後 2 個交易日」較寬鬆的版本）
- 研究 63b 的訊號拆成「調整日」與「非調整日」，各自算隔天開盤買、抱 H 天的報酬與隨機進場 p
- 再看所有調整日（不論量）的隔天報酬，量化調整日本身的反彈
用法：python -X utf8 backtest/research_63c_爆量收黑_指數調整日.py
"""
import importlib.util
import os
import random
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r63b", os.path.join(HERE, "research_63b_爆量收黑買進.py"))
r63b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r63b)
O, C, N, DAYS = r63b.O, r63b.C, r63b.N, r63b.DAYS
VR = r63b.r61.VR


def rebalance_set(last_n=1):
    s = set()
    for i in range(N - 1):
        ym = DAYS[i][:7]
        if int(DAYS[i][5:7]) in (2, 5, 8, 11):
            # 該月最後 last_n 個交易日
            k = 1
            while i + k < N and DAYS[i + k][:7] == ym:
                k += 1
            if k <= last_n:
                s.add(i)
    return s


def show(L, nm, sig, H, rng):
    trs = r63b.trades(sig, H)
    if len(trs) < 5:
        L.append(f"  {nm:30s} {len(trs):3d} 筆，樣本不足")
        return
    rets = [t[2] for t in trs]
    rnd = r63b.random_ev(trs, rng, reps=2000)
    ev = statistics.mean(rets)
    L.append(f"  {nm:30s} {len(trs):3d} 筆 勝率 {sum(r > 0 for r in rets) / len(rets):4.0%} 每筆 {ev:+.2%}  隨機 {rnd[1000]:+.2%}  p＝{(sum(x >= ev for x in rnd) + 1) / 2001:.3f}")


def main():
    rng = random.Random(6303)
    L = ["研究 63c：爆量收黑買進 vs MSCI 調整日（2／5／8／11 月最後交易日）"]
    for last_n in (1, 2):
        rb = rebalance_set(last_n)
        L.append(f"\n==== 調整日定義：該月最後 {last_n} 個交易日 ====")
        for vsrc, k in (("成交金額", 1.5), ("成交金額", 1.3), ("台指期口數", 1.5), ("台指期口數", 2.0)):
            sig = r63b.signals(vsrc, k, 0.0)
            on = [i for i in sig if i in rb]
            off = [i for i in sig if i not in rb]
            L.append(f"-- {vsrc} ≥{k}x 收黑：共 {len(sig)} 天，其中調整日 {len(on)} 天（{len(on) / max(1, len(sig)):.0%}）--")
            for H in (1, 5, 10):
                show(L, f"調整日 抱 {H} 天", on, H, rng)
                show(L, f"非調整日 抱 {H} 天", off, H, rng)
        # 調整日本身（不論量）
        allrb = [i for i in rb if i >= r63b.START and i < N - 1]
        allrb.sort()
        down = [i for i in allrb if C[i] < C[i - 1]]
        L.append(f"-- 所有調整日（不論量）{len(allrb)} 天、收黑 {len(down)} 天 --")
        for H in (1, 5):
            show(L, f"所有調整日 抱 {H} 天", allrb, H, rng)
            show(L, f"調整日且收黑 抱 {H} 天", down, H, rng)
        ratio = [VR["成交金額"][i] for i in allrb if VR["成交金額"][i]]
        L.append(f"  調整日成交金額／20 日均 中位 {statistics.median(ratio):.2f}x（≥1.5x 的比例 {sum(x >= 1.5 for x in ratio) / len(ratio):.0%}）")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究63c_指數調整日.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
