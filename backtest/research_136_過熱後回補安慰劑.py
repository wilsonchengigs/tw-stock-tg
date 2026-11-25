"""研究 136：過熱出場後回補（研究 81，偏離 < 12.5% 且 z ≤ 2、仍在出場線上就回補）單獨的安慰劑檢定

研究 131 把 DEV／Z 一起平移時，過熱出場和回補「一起」被打亂，只證明整個濾網有效，沒單獨看回補。
- 虛無假設：過熱出場後「冷卻了沒」與之後的行情無關（回補時點換成任意日子也一樣好）
- 做法：過熱出場照真實 DEV／Z；只有回補判斷（cooled）改用環狀平移後的 DEV／Z（避開 ±250 日）
- 機制對照：出場後固定等 N 週就回補（不看融資），看融資資訊是否比單純「等一段時間」好
- 注意：平移版的回補幾乎在出場後馬上發生（平移後多數日子都「已冷卻」），偏向證明「要等」，不是證明「等融資冷卻」
- 家族：回補門檻 10／12.5／15%（12.5%＝現行），另列「不回補」（只靠 MA60×1.01 重新進場）做對照
- 指標：全期 2002–2026、後段 2013–2026、真實價 2015-09～ 的年化；家族 p 用最小 p 值法
用法：python -X utf8 backtest/research_136_過熱後回補安慰劑.py（R136_SHIFTS 控制平移次數，預設 200）
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
path = os.path.join(HERE, "strategy_v3.py")
src = open(path, encoding="utf-8").read()
old = "cooled = DEV[i] is None or (DEV[i] < reentry and (zth is None or Z[i] <= zth))"
assert old in src
src = src.replace(old, "cooled = (DEVR[i] is None or (DEVR[i] < reentry and (zth is None or ZR[i] <= zth))) if DELAY is None else (i - hout_i >= DELAY)")
for a, b in (("mdd, state, heat_out, cur, pend = 0.0, 0, False, 0.0, None", "mdd, state, heat_out, cur, pend, hout_i = 0.0, 0, False, 0.0, None, 0"),
             ("state, heat_out = 0, True  # 融資過熱每天檢查", "state, heat_out, hout_i = 0, True, i  # 融資過熱每天檢查"),
             ("            elif hot:\n                state, heat_out = 0, True", "            elif hot:\n                state, heat_out, hout_i = 0, True, i")):
    assert a in src, a
    src = src.replace(a, b)
spec = importlib.util.spec_from_loader("v3r", loader=None)
V = importlib.util.module_from_spec(spec)
V.__file__ = path
exec(compile(src, path, "exec"), V.__dict__)
V.DEVR, V.ZR = list(V.DEV), list(V.Z)
V.DELAY = None
DEV0, Z0 = list(V.DEV), list(V.Z)
GRID = (0.10, 0.125, 0.15)
SEGS = (("全期", "2002-01-01", "2026-12-31", False), ("後段", "2013-01-01", "2026-12-31", False), ("真實", "2015-09-01", "2026-12-31", True))


def family():
    return [[V.run(a, b, real=real, reentry=r)[0] for _, a, b, real in SEGS] for r in GRID]


def pval(v, col, skip=None):
    others = [c for i, c in enumerate(col) if i != skip]
    return (sum(c >= v for c in others) + 1) / (len(others) + 1)


def main():
    valid = [i for i in range(V.N) if DEV0[i] is not None]
    n = len(valid)
    norebuy = [V.run(a, b, real=real, reentry=-9)[0] for _, a, b, real in SEGS]
    real_res = family()
    K = int(os.environ.get("R136_SHIFTS", "200"))
    gap = 250
    shifts = [gap + round(k * (n - 2 * gap) / (K - 1)) for k in range(K)]
    allfam = []
    for k, s in enumerate(shifts):
        dev, z = [None] * V.N, [None] * V.N
        for p in range(n):
            q = valid[(p - s) % n]
            dev[valid[p]], z[valid[p]] = DEV0[q], Z0[q]
        V.DEVR, V.ZR = dev, z
        allfam.append(family())
        if (k + 1) % 50 == 0:
            print(f"  平移 {k + 1}/{K}", flush=True)
    V.DEVR, V.ZR = DEV0, Z0
    L = [f"研究 136：過熱後回補單獨安慰劑（過熱出場用真實融資，只有回補判斷用環狀平移 {K} 次的融資序列，{shifts[0]}～{shifts[-1]} 日）",
         "不回補（只靠 MA60×1.01 重新進場）：" + "、".join(f"{nm} {c:.1%}" for (nm, *_), c in zip(SEGS, norebuy)), "",
         "實際（各段年化｜平移中位｜平移後勝過不回補的比例｜單組 p；★＝現行）："]
    singles = []
    for g, r in enumerate(GRID):
        ps, parts = [], []
        for si, (nm, *_) in enumerate(SEGS):
            col = [f[g][si] for f in allfam]
            ps.append(pval(real_res[g][si], col))
            beat = sum(c > norebuy[si] + 1e-9 for c in col) / K
            parts.append(f"{nm} {real_res[g][si]:.1%}（中位 {sorted(col)[K // 2]:.1%}，平移勝不回補 {beat:.0%}，p {ps[-1]:.3f}）")
        singles.append(ps)
        L.append(f" {'★' if r == 0.125 else ' '} 回補 < {r:.1%}：" + "｜".join(parts))
    L += ["", "家族檢定（最小 p 值法）："]
    for si, (nm, *_) in enumerate(SEGS):
        cols = [[f[g][si] for f in allfam] for g in range(len(GRID))]
        real_minp = min(singles[g][si] for g in range(len(GRID)))
        null_minp = [min(pval(allfam[k][g][si], cols[g], skip=k) for g in range(len(GRID))) for k in range(K)]
        pm = (sum(v <= real_minp for v in null_minp) + 1) / (K + 1)
        L.append(f"  {nm}：家族最小單組 p {real_minp:.3f}｜家族 p {pm:.3f}｜現行單組 p {singles[1][si]:.3f}")
    # 機制對照：過熱出場後固定等 N 週（交易日 ×5）、仍在出場線上就回補，完全不看融資
    L += ["", "機制對照：出場後固定等 N 週就回補（不看融資是否冷卻）："]
    for wk in (2, 4, 8, 13, 26, 52):
        V.DELAY = wk * 5
        L.append(f"  等 {wk:2d} 週：" + "、".join(f"{nm} {V.run(a, b, real=real)[0]:.1%}" for nm, a, b, real in SEGS))
    V.DELAY = None
    txt = "\n".join(L) + "\n"
    print(txt)
    open(os.path.join(HERE, "結果_研究136_過熱後回補安慰劑.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
