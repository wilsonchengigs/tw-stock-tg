"""研究 182：大跌後一週，做多還是做空勝率高？（使用者 2026-11-26 問「現在做多或做空哪個勝率高、一週回頭看可靠嗎」）

背景：2026-11-25 加權 -4.80%（38,195），前幾天 11/19 -4.4%、11/20 -6.2%、11/24 +9.0%；主策略 10/15 起空手（在出場線下）。
做法：
- 事件：加權單日跌幅 ≤ -4%（主）、≤ -3%（敏感度）；子集：主策略空手（收盤 < MA80×0.975）、20 日波動前 10%
- 持有：事件當天收盤進 → 5 個交易日後收盤出（C0→C5）；「今天收盤才進」→ C1→C6；另看 1／10 天
- 去叢集：事件後 5 天內再觸發的不算新事件（獨立樣本）
- 基準：同一狀態（主策略空手）所有交易日的 5 天報酬；差異用拔靴（重抽基準 5,000 次，同樣本數）算單尾 p
- 三段：1998–2012、2013–2019、2020–2026
- 報酬：加權指數（不含配息），未扣成本；台指期一買一賣約 6 點（38,000 點時約 0.02%），不影響結論
用法：python -X utf8 backtest/research_182_大跌後一週多空勝率.py
"""
import math
import os
import random
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import data  # noqa: E402

TODAY = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
tw = data.load("TWII")
DAYS = [d for d in sorted(tw) if "1998-01-01" <= d < TODAY]  # 今天盤中的不算
PX = [tw[d][0] for d in DAYS]
N = len(PX)
R = [0.0] + [PX[i] / PX[i - 1] - 1 for i in range(1, N)]


def sma(n):
    out, s = [None] * N, 0.0
    for i, p in enumerate(PX):
        s += p
        if i >= n:
            s -= PX[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


MA80 = sma(80)
VOL = [None] * N
for i in range(20, N):
    w = R[i - 19:i + 1]
    m = sum(w) / 20
    VOL[i] = math.sqrt(sum((x - m) ** 2 for x in w) / 19) * math.sqrt(245)
vols = sorted(v for v in VOL if v is not None)
VOL90 = vols[int(len(vols) * 0.9)]
OFF = [MA80[i] is not None and PX[i] < MA80[i] * 0.975 for i in range(N)]


def fwd(i, k, lag=0):
    a, b = i + lag, i + lag + k
    return PX[b] / PX[a] - 1 if b < N else None


def events(th, cond=lambda i: True, gap=5):
    out, last = [], -99
    for i in range(1, N):
        if R[i] <= th and cond(i) and i - last > gap:
            out.append(i)
            last = i
    return out


def summarize(rets):
    n = len(rets)
    if not n:
        return "（0 筆）"
    up = sum(r > 0 for r in rets) / n
    mean = sum(rets) / n
    med = sorted(rets)[n // 2]
    return f"{n:>3} 筆  做多勝率 {up:5.0%}  做空勝率 {1 - up:5.0%}  平均 {mean:+6.2%}  中位 {med:+6.2%}  最好 {max(rets):+6.1%}  最差 {min(rets):+6.1%}"


def boot_p(rets, base, it=5000, seed=1):
    """事件平均 vs 從基準隨機抽同樣多筆的平均；回傳（基準平均, P(隨機 >= 事件), P(隨機 <= 事件)）"""
    rnd = random.Random(seed)
    n, m = len(rets), sum(rets) / len(rets)
    sims = [sum(rnd.choice(base) for _ in range(n)) / n for _ in range(it)]
    return sum(base) / len(base), sum(s >= m for s in sims) / it, sum(s <= m for s in sims) / it


def main():
    L = ["研究 182：大跌後一週做多還是做空（加權收盤，去叢集 5 天，未扣成本）",
         f"資料 {DAYS[0]}～{DAYS[-1]}；20 日年化波動第 90 分位 = {VOL90:.0%}"]
    i = N - 1
    L.append(f"最新 {DAYS[i]}：收 {PX[i]:,.0f}、當天 {R[i]:+.2%}、MA80×0.975 = {MA80[i] * 0.975:,.0f}（{'主策略空手' if OFF[i] else '主策略在場'}）、"
             f"20 日波動 {VOL[i]:.0%}（{sum(v <= VOL[i] for v in vols) / len(vols):.0%} 分位）")

    base_all = [fwd(j, 5) for j in range(1, N) if fwd(j, 5) is not None]
    base_off = [fwd(j, 5) for j in range(1, N) if OFF[j] and fwd(j, 5) is not None]
    L.append("\n【基準】所有交易日抱 5 天：" + summarize(base_all))
    L.append("【基準】主策略空手的日子抱 5 天：" + summarize(base_off))

    sets = [
        ("跌 ≥4%", -0.04, lambda j: True),
        ("跌 ≥4% 且主策略空手", -0.04, lambda j: OFF[j]),
        ("跌 ≥4% 且 20 日波動前 10%", -0.04, lambda j: VOL[j] is not None and VOL[j] >= VOL90),
        ("跌 ≥3%", -0.03, lambda j: True),
        ("跌 ≥3% 且主策略空手", -0.03, lambda j: OFF[j]),
    ]
    for name, th, cond in sets:
        ev = events(th, cond)
        L.append(f"\n== {name}（獨立事件 {len(ev)} 次）==")
        for k, lag, lab in ((1, 0, "抱 1 天（當天收盤進）"), (5, 0, "抱 5 天（當天收盤進）"), (5, 1, "抱 5 天（隔天收盤才進）"), (10, 0, "抱 10 天（當天收盤進）")):
            rets = [r for r in (fwd(j, k, lag) for j in ev) if r is not None]
            L.append(f"  {lab}：" + summarize(rets))
            if k == 5 and rets:
                b = base_off if "空手" in name else base_all
                bm, p_hi, p_lo = boot_p(rets, b)
                L.append(f"     vs 基準平均 {bm:+.2%}：事件比基準高的機率 p={p_hi:.3f}（低 p={p_lo:.3f}）")
        for y0, y1 in (("1998", "2012"), ("2013", "2019"), ("2020", "2026")):
            rets = [fwd(j, 5) for j in ev if y0 <= DAYS[j][:4] <= y1 and fwd(j, 5) is not None]
            L.append(f"  {y0}–{y1} 抱 5 天：" + summarize(rets))

    # 連續大跌群聚：近 5 天內已經有過一次 ≥4% 大跌（像 11/20、11/25）之後
    ev2 = [j for j in range(5, N) if R[j] <= -0.04 and any(R[k] <= -0.04 for k in range(j - 5, j))]
    rets = [fwd(j, 5) for j in ev2 if fwd(j, 5) is not None]
    L.append("\n== 5 天內第二次跌 ≥4%（不去叢集，像 11/20→11/25）==")
    L.append("  抱 5 天：" + summarize(rets))
    L.append("  日期：" + "、".join(DAYS[j] for j in ev2))

    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究182_大跌後一週多空勝率.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()


def family_test(shifts=2000, seed=7):
    """家族多重檢定（研究 129／130 的環狀平移＋最小 p 值）：10 組（5 種事件 × 當天／隔天進）抱 5 天的平均，
    把「事件序列」對報酬序列環狀平移，保留事件群聚；每次平移取 10 組中最好的 z，看實際最好的 z 排在哪"""
    sets = [(-0.04, lambda j: True), (-0.04, lambda j: OFF[j]), (-0.04, lambda j: VOL[j] is not None and VOL[j] >= VOL90),
            (-0.03, lambda j: True), (-0.03, lambda j: OFF[j])]
    f5 = [[fwd(j, 5, lag) for j in range(N)] for lag in (0, 1)]
    valid = [j for j in range(N) if f5[1][j] is not None]
    mu = {lag: sum(f5[lag][j] for j in valid) / len(valid) for lag in (0, 1)}
    sd = {lag: math.sqrt(sum((f5[lag][j] - mu[lag]) ** 2 for j in valid) / len(valid)) for lag in (0, 1)}
    flags = [[j in set(events(th, c)) for j in range(N)] for th, c in sets]

    def zs(shift):
        out = []
        for fl in flags:
            ev = [(j + shift) % len(valid) for j in range(len(valid)) if fl[valid[j]]]
            for lag in (0, 1):
                r = [f5[lag][valid[k]] for k in ev]
                out.append((sum(r) / len(r) - mu[lag]) / (sd[lag] / math.sqrt(len(r))))
        return out

    real = zs(0)
    rnd = random.Random(seed)
    best = [max(zs(rnd.randrange(20, len(valid) - 20))) for _ in range(shifts)]
    lines = ["\n== 家族檢定（10 組，環狀平移 %d 次，單尾做多）==" % shifts]
    names = ["≥4%", "≥4%空手", "≥4%高波動", "≥3%", "≥3%空手"]
    for k, z in enumerate(real):
        p = sum(b >= z for b in best) / shifts
        lines.append(f"  {names[k // 2]:<9}{'隔天進' if k % 2 else '當天進'}：z {z:+.2f}  家族校正 p {p:.3f}")
    return lines


def extra():
    L = []
    hv = events(-0.04, lambda j: VOL[j] is not None and VOL[j] >= VOL90)
    for lab, ev in (("≥4% 隔天收盤進", events(-0.04)), ("≥4% 高波動 隔天收盤進", hv)):
        L.append(f"\n== {lab}：分段 ==")
        for y0, y1 in (("1998", "2012"), ("2013", "2019"), ("2020", "2026")):
            rets = [fwd(j, 5, 1) for j in ev if y0 <= DAYS[j][:4] <= y1 and fwd(j, 5, 1) is not None]
            L.append(f"  {y0}–{y1}：" + summarize(rets))
        # 5% 停損（收盤價檢查，觸發就以當天收盤出；實際盤中觸價會更早、更少滑價以外的差）
        for stop in (None, 0.05, 0.07):
            rets = []
            for j in ev:
                a = j + 1
                if a + 5 >= N:
                    continue
                r = PX[a + 5] / PX[a] - 1
                if stop:
                    for k in range(a + 1, a + 6):
                        if PX[k] / PX[a] - 1 <= -stop:
                            r = PX[k] / PX[a] - 1
                            break
                rets.append(r)
            L.append(f"  停損 {'無' if not stop else f'{stop:.0%}（收盤檢查）'}：" + summarize(rets))
        L.append("  明細：" + "、".join(f"{DAYS[j]} {fwd(j, 5, 1):+.1%}" for j in ev if fwd(j, 5, 1) is not None))
    return L


if __name__ == "__main__":
    add = extra() + family_test()
    print("\n".join(add))
    p = os.path.join(HERE, "結果_研究182_大跌後一週多空勝率.txt")
    open(p, "a", encoding="utf-8").write("\n".join(add) + "\n")
