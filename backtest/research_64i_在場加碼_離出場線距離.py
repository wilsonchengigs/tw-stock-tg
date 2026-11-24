"""研究 64i：在場加碼（研究 64b）時，若指數離出場線（MA80×0.975）太近就不加碼——避開「加碼後現行隨即出場」（研究 64h 主要風險）
條件：PX ≥ 出場線 × (1 + m) 才加碼，m＝0（原版）／2％／3％／5％／8％；k 1.5；加 0.5x 抱 5 天、加 1x 抱 10 天
注意：壞例只有 3 筆，過度擬合風險高；三段都不變差且 m 鄰近一致才算數
用法：python -X utf8 backtest/research_64i_在場加碼_離出場線距離.py
"""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r64b", os.path.join(HERE, "research_64b_在場時爆量收黑加碼.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
R, PX, VR, N = m.R, m.PX, m.VR, m.N
P = (("2002-01-01", "2026-12-31", "全期"), ("2002-01-01", "2012-12-31", "前段"), ("2013-01-01", "2026-12-31", "後段"))


def main():
    base = {nm: m.sim(s, e) for s, e, nm in P}
    L = ["研究 64i：離出場線太近不加碼（k 1.5）", "現行：" + "  ".join(f"{nm} {b[0]:.1%}／{b[1]:.1%}" for nm, b in base.items())]
    real = list(VR)
    for add, H in ((1.0, 10), (0.5, 5)):
        L.append(f"\n== 加 {add}x 抱 {H} 天 ==")
        for mg in (0.0, 0.02, 0.03, 0.05, 0.08):
            # 不符合距離條件的日子把量比設成 0（＝不觸發）
            m.VR[:] = [v if (v is not None and R.M80[i] is not None and PX[i] >= R.M80[i] * 0.975 * (1 + mg)) else (0.0 if v is not None else None)
                       for i, v in enumerate(real)]
            res = {nm: m.sim(s, e, 1.5, add, H) for s, e, nm in P}
            m.VR[:] = real
            adds = res["全期"][2]
            L.append(f"  距出場線 ≥{mg:.0%}：" + "  ".join(f"{nm} {r[0]:.1%}({r[0] - base[nm][0]:+.1%})／{r[1]:.1%}" for nm, r in res.items())
                     + f"  ｜ {len(adds)} 次 勝率 {sum(a > 0 for a in adds) / max(1, len(adds)):.0%} 平均 {sum(adds) / max(1, len(adds)):+.2%}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究64i_離出場線距離.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
