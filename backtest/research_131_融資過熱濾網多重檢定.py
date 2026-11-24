"""研究 131：現行融資過熱濾網（v3：偏離 > 17.5% 或 z > 2、每天檢查、過熱後回補）的家族多重檢定——比照研究 129、130

研究 38／38b／85／85b／90 在同一份融資資料上陸續挑了門檻、z 並用、每天檢查；各自做過安慰劑，但沒有把整個現行濾網和它的變形一起檢定。
- 虛無假設：融資÷指數 的過熱程度與之後的行情無關
- 做法：把偏離度 DEV 與 z 分數 Z 兩條序列「一起」在有值的區間環狀平移 s 天（避開 ±250 日），回測時用平移後的序列判斷過熱，
  價格進出場規則不變；每個平移重跑整個家族
- 家族：門檻 15／17.5／20% × z 並用（無／1.5／2／2.5）× 過熱每天檢查／只週五，共 24 組（現行＝17.5%、z 2、每天）
- 指標：2002–2026 全期年化；另列後段 2013–2026 與真實價 2015-09～ 的單組 p（看近年是否還有效）
- 家族 p：最小 p 值法（各組先和自己的平移分布比，取家族最小 p，再和平移樣本的家族最小 p 比）
用法：python -X utf8 backtest/research_131_融資過熱濾網多重檢定.py（R131_SHIFTS 控制平移次數，預設 200）
"""
import importlib.util
import itertools
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("v3", os.path.join(HERE, "strategy_v3.py"))
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)
DEV0, Z0 = list(V.DEV), list(V.Z)
GRID = list(itertools.product((0.15, 0.175, 0.20), (None, 1.5, 2.0, 2.5), (True, False)))
SEGS = (("全期", "2002-01-01", "2026-12-31", False), ("後段", "2013-01-01", "2026-12-31", False), ("真實", "2015-09-01", "2026-12-31", True))


def family():
    out = []
    for th, zth, daily in GRID:
        out.append([V.run(a, b, real=real, th=th, zth=zth, daily_heat=daily)[0] for _, a, b, real in SEGS])
    return out


def main():
    valid = [i for i in range(V.N) if DEV0[i] is not None]
    n = len(valid)
    base = [V.run(a, b, real=real, use_heat=False)[0] for _, a, b, real in SEGS]
    real_res = family()
    K = int(os.environ.get("R131_SHIFTS", "200"))
    gap = 250
    shifts = [gap + round(k * (n - 2 * gap) / (K - 1)) for k in range(K)]
    allfam = []
    for k, s in enumerate(shifts):
        dev, z = [None] * V.N, [None] * V.N
        for p in range(n):
            q = valid[(p - s) % n]
            dev[valid[p]], z[valid[p]] = DEV0[q], Z0[q]
        V.DEV, V.Z = dev, z
        allfam.append(family())
        if (k + 1) % 20 == 0:
            print(f"  平移 {k + 1}/{K}", flush=True)
    V.DEV, V.Z = DEV0, Z0

    def pval(v, col, skip=None):
        others = [c for i, c in enumerate(col) if i != skip]
        return (sum(c >= v for c in others) + 1) / (len(others) + 1)

    L = [f"研究 131：融資過熱濾網家族多重檢定（v3 價格規則；DEV＋Z 一起環狀平移 {K} 次，{shifts[0]}～{shifts[-1]} 日，有值 {n} 天）",
         "不用濾網：" + "、".join(f"{nm} {c:.1%}" for (nm, *_), c in zip(SEGS, base)), "",
         "實際結果（各段年化｜平移中位｜單組 p；★＝現行）："]
    singles = []
    for g, (th, zth, daily) in enumerate(GRID):
        ps, meds = [], []
        for si in range(len(SEGS)):
            col = [f[g][si] for f in allfam]
            ps.append(pval(real_res[g][si], col))
            meds.append(sorted(col)[K // 2])
        singles.append(ps)
        mark = "★" if (th, zth, daily) == (0.175, 2.0, True) else " "
        L.append(f" {mark} {th:.1%} z{str(zth):4s} {'每天' if daily else '週五'}：" + "｜".join(
            f"{nm} {real_res[g][si]:.1%}（中位 {meds[si]:.1%}，p {ps[si]:.3f}）" for si, (nm, *_) in enumerate(SEGS)))
    L += ["", "家族檢定（最小 p 值法）："]
    for si, (nm, *_) in enumerate(SEGS):
        cols = [[f[g][si] for f in allfam] for g in range(len(GRID))]
        real_minp = min(singles[g][si] for g in range(len(GRID)))
        null_minp = [min(pval(allfam[k][g][si], cols[g], skip=k) for g in range(len(GRID))) for k in range(K)]
        pm = (sum(v <= real_minp for v in null_minp) + 1) / (K + 1)
        g0 = GRID.index((0.175, 2.0, True))
        L.append(f"  {nm}：家族最小單組 p {real_minp:.3f}；平移樣本家族最小 p 中位 {sorted(null_minp)[K // 2]:.3f}｜家族 p {pm:.3f}｜現行單組 p {singles[g0][si]:.3f}")
    txt = "\n".join(L) + "\n"
    print(txt)
    open(os.path.join(HERE, "結果_研究131_融資過熱濾網多重檢定.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
