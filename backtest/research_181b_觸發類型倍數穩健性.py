"""研究 181b：研究 181 的穩健性——N／S 倍數網格、夜盤門檻 1.5／2／2.5%、逐年增量

網格：夜盤門檻 th ∈ {1.5%, 2%, 2.5%}（N＝夜盤跌 ≥th；S＝S&P 跌 ≥2% 且不是 N）× N 倍數 {1, 1.25, 1.5, 2} × S 倍數 {0.25, 0.5, 1}
每格：年化、回檔；與「現行（th 2%、1／1）」比；逐年（N 1.5／S 0.5、th 2%）增量
用法：python -X utf8 backtest/research_181b_觸發類型倍數穩健性.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r181", os.path.join(HERE, "research_181_恐慌觸發類型倍數.py"))
R181 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R181)
R141, R142, R145, bt = R181.R141, R181.R142, R181.R145, R181.bt


def main():
    T = R141.build()
    NN, SP = R142.night_series(T), R145.sp_series(T)
    base_n, base_s = NN <= -0.02, (SP <= -0.02) & ~(NN <= -0.02)
    cur = R181.run_sized(T, np.where(base_n | base_s, 1.0, 0.0))
    out = [f"研究 181b：觸發類型倍數穩健性（現行 {cur[0]:.1%}／{cur[1]:.1%}）", "", "夜盤門檻｜N 倍數｜S 倍數 → 年化／回檔（與現行差）"]
    for th in (0.015, 0.02, 0.025):
        nN = NN <= -th
        sS = (SP <= -0.02) & ~nN
        cells = []
        for a in (1.0, 1.25, 1.5, 2.0):
            for b in (0.25, 0.5, 1.0):
                cg, md = R181.run_sized(T, np.where(nN, a, np.where(sS, b, 0.0)))
                cells.append(f"N{a:g}/S{b:g} {cg:.1%}/{md:.0%}({cg - cur[0]:+.1%})")
        out.append(f"th {th:.1%}：" + "  ".join(cells))
    # 逐年增量
    out.append("")
    nN, sS = base_n, base_s
    ds = [t["d"] for t in T]

    def yearly(size):
        eq = {}
        for y in sorted(set(d[:4] for d in ds)):
            idx = [k for k, d in enumerate(ds) if d[:4] == y]
            sub = [T[k] for k in range(max(0, idx[0] - 1), idx[-1] + 1)]
            eq[y] = R181.run_sized(sub, size[max(0, idx[0] - 1):idx[-1] + 1])
        return eq
    a = yearly(np.where(nN, 1.5, np.where(sS, 0.5, 0.0)))
    b = yearly(np.where(nN | sS, 1.0, 0.0))
    out.append("逐年（N1.5/S0.5 − 現行，年報酬近似）：" + "  ".join(f"{y[2:]}:{a[y][0] - b[y][0]:+.1%}" for y in a))
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究181b_觸發類型倍數穩健性.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
