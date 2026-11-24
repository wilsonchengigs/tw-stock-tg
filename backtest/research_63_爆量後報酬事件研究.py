"""研究 63：爆量日之後的報酬（事件研究；驗證研究 61／62b 的「爆量長黑後反彈」線索）

不設停損停利、不挑參數，只問：爆量日之後 1／3／5／10／20 個交易日的報酬，跟「一般日子」比有沒有不同？
- 資料：Yahoo ^TWII 日 K（1998-09～），量＝證交所成交金額（與研究 61 相同）
- 爆量：成交金額 ≥ k × 前 20 日平均，k＝1.5／2.0／2.5
- 分組：爆量且收黑（收 < 前收）、爆量且收紅、爆量長黑（跌 ≥ 2%）、爆量長紅（漲 ≥ 2%）；
        對照「非爆量但同樣跌 ≥ 2%」「非爆量但同樣漲 ≥ 2%」，分離出「量」本身的作用
- 報酬：訊號日收盤 → N 日後收盤（實務上要隔天開盤才進得去，另列「隔天開盤進」版本）
- 顯著性：拔靴（從全部日子隨機抽同樣多天，5000 次）看平均是否異於一般日子；並分 1998-2012／2013-2026
用法：python -X utf8 backtest/research_63_爆量後報酬事件研究.py
"""
import importlib.util
import os
import random
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r61", os.path.join(HERE, "research_61_爆量順勢短線.py"))
r61 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r61)
O, C, N, DAYS = r61.O, r61.C, r61.N, r61.DAYS
VR = r61.VR["成交金額"]
HS = (1, 3, 5, 10, 20)


def fwd(i, h, from_open=False):
    if i + h >= N or (from_open and i + 1 >= N):
        return None
    base = O[i + 1] if from_open else C[i]
    return C[i + h] / base - 1


def main():
    rng = random.Random(63)
    start = next(i for i, d in enumerate(DAYS) if d >= "1998-09-01")
    idx = [i for i in range(max(start, 21), N - 20)]
    L = ["研究 63：爆量日之後的報酬（事件研究；^TWII 1998-09～；量＝證交所成交金額 vs 前 20 日均）"]
    base = {h: [fwd(i, h) for i in idx] for h in HS}
    L.append("\n一般日子（全部）平均報酬：" + "  ".join(f"{h}日 {statistics.mean(base[h]):+.2%}" for h in HS))

    def chg(i):
        return C[i] / C[i - 1] - 1

    for k in (1.5, 2.0, 2.5):
        spike = lambda i: VR[i] is not None and VR[i] >= k  # noqa: E731
        calm = lambda i: VR[i] is not None and VR[i] < 1.2  # noqa: E731
        groups = [
            (f"爆量≥{k}x 收黑", lambda i: spike(i) and chg(i) < 0),
            (f"爆量≥{k}x 收紅", lambda i: spike(i) and chg(i) > 0),
            (f"爆量≥{k}x 長黑≤-2%", lambda i: spike(i) and chg(i) <= -0.02),
            (f"爆量≥{k}x 長紅≥+2%", lambda i: spike(i) and chg(i) >= 0.02),
            ("對照 量平(<1.2x) 長黑≤-2%", lambda i: calm(i) and chg(i) <= -0.02),
            ("對照 量平(<1.2x) 長紅≥+2%", lambda i: calm(i) and chg(i) >= 0.02),
        ]
        L.append(f"\n== 爆量門檻 {k}x ==")
        L.append("分組                          天數   " + "   ".join(f"{h:>2d}日平均(超額, p)" for h in HS))
        for nm, cond in groups:
            if nm.startswith("對照") and k != 2.0:
                continue
            sel = [i for i in idx if cond(i)]
            if len(sel) < 10:
                L.append(f"{nm:26s} {len(sel):4d}   樣本不足")
                continue
            cells = []
            for h in HS:
                xs = [fwd(i, h) for i in sel]
                m = statistics.mean(xs)
                bm = statistics.mean(base[h])
                # 拔靴：從全部日子抽同樣天數
                pool = base[h]
                sims = [statistics.mean(rng.choices(pool, k=len(xs))) for _ in range(2000)]
                p = (sum(abs(s - bm) >= abs(m - bm) for s in sims) + 1) / 2001
                cells.append(f"{m:+6.2%}({m - bm:+.2%},{p:.2f})")
            L.append(f"{nm:26s} {len(sel):4d}   " + "  ".join(cells))
        # 分期（只做 2.0x 長黑／長紅）
        if k == 2.0:
            L.append("  分期（5 日／10 日平均超額報酬）：")
            for nm, cond in groups[2:4]:
                for lab, a, b in (("1998-2012", "1998", "2013"), ("2013-2026", "2013", "2027")):
                    sel = [i for i in idx if a <= DAYS[i] < b and cond(i)]
                    sub = [i for i in idx if a <= DAYS[i] < b]
                    if len(sel) < 5:
                        L.append(f"    {nm} {lab}：{len(sel)} 天，樣本不足")
                        continue
                    ex = [statistics.mean(fwd(i, h) for i in sel) - statistics.mean(fwd(i, h) for i in sub) for h in (5, 10)]
                    L.append(f"    {nm} {lab}：{len(sel):3d} 天  5日超額 {ex[0]:+.2%}  10日超額 {ex[1]:+.2%}")
            # 隔天開盤進場版本
            L.append("  隔天開盤才進場（實務可行）：")
            for nm, cond in groups[2:4]:
                sel = [i for i in idx if cond(i)]
                L.append(f"    {nm}：" + "  ".join(f"{h}日 {statistics.mean(fwd(i, h, True) for i in sel):+.2%}" for h in HS)
                         + "   （一般日子隔天開盤進：" + "  ".join(f"{h}日 {statistics.mean(fwd(i, h, True) for i in idx):+.2%}" for h in (5, 10)) + "）")
    L.append("\n讀法：括號內是「超額＝該組平均－一般日子平均」與拔靴雙尾 p；p<0.05 才算有差。事件常在空頭群聚發生，重疊的 N 日報酬不獨立，p 會偏樂觀")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究63_爆量後報酬.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
