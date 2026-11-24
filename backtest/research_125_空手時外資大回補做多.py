"""研究 125：v3 現行策略「空手」時，外資台指期大回補（Δz>+x，排除結算日與次日）→ 隔天開盤買台指期抱 H 天（獨立短線）
台指期近月真實價，2018-06～；成本 3 點；對照：空手日中同筆數隨機日期 1000 次；另列「在場」時同訊號作比較
用法：python -X utf8 backtest/research_125_空手時外資大回補做多.py
"""
import importlib.util
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    b = load("r75b", "research_75b_外資期貨加減碼_真實價.py")
    fdates, fday, fnight, near = b.r63d.load()
    n = len(fdates)
    last_day = {}
    for d in fdates:
        for m in fday[d]:
            last_day[m] = d
    settle = set(last_day.values())
    excl = settle | {fdates[i + 1] for i, d in enumerate(fdates[:-1]) if d in settle}
    Z = {d: z for d, z in b.r75.zseries().items() if z is not None and d not in excl}
    S = load("r76", "research_76_加碼候選在v3重驗.py").v3_states()
    V = dict(zip(b.r64.DAYS, S))
    R = [0.0] * n
    for i in range(1, n):
        m = near[fdates[i]]
        prev = fday[fdates[i - 1]].get(m)
        R[i] = fday[fdates[i]][m][3] / prev[3] - 1 if prev else 0.0

    def trade(i, H):
        e, x = i + 1, i + H
        if x >= n:
            return None
        m = near[fdates[e]]
        px = fday[fdates[e]][m][0]
        g = fday[fdates[e]][m][3] / px
        for j in range(e + 1, x + 1):
            g *= 1 + R[j]
        return g - 1 - 3 / px, x

    fidx = {d: i for i, d in enumerate(fdates)}
    rng = random.Random(125)
    L = ["研究 125：外資期貨大回補 → 隔天開盤買台指期（依 v3 現行在場／空手分組；2018-06～；排除結算日）"]
    for state_nm, want in (("空手", False), ("在場", True)):
        days = [d for d in Z if d in fidx and d in V and V[d] == want]
        pool = [fidx[d] for d in days if fidx[d] + 21 < n]
        L.append(f"\n== 現行{state_nm}（{len(days)} 個交易日有 z）==")
        for x in (1.5, 2.0):
            for H in (1, 5, 10):
                trs, busy = [], -1
                for d in sorted(days):
                    i = fidx[d]
                    if Z[d] > x and i + 1 > busy:
                        t = trade(i, H)
                        if t:
                            trs.append(t[0])
                            busy = t[1]
                if len(trs) < 6:
                    L.append(f"  z>{x} 抱{H:2d}天：{len(trs)} 筆，樣本不足")
                    continue
                ev = sum(trs) / len(trs)
                sims = sorted(sum(trade(rng.choice(pool), H)[0] for _ in trs) / len(trs) for _ in range(1000))
                p = (sum(s >= ev for s in sims) + 1) / 1001
                L.append(f"  z>{x} 抱{H:2d}天：{len(trs):3d} 筆 勝率 {sum(t > 0 for t in trs) / len(trs):.0%} 每筆 {ev:+.2%}（≈{ev * 40000:+.0f} 點） 隨機 {sims[500]:+.2%}  p＝{p:.3f}  最差 {min(trs):+.1%}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究125_空手時外資大回補.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
