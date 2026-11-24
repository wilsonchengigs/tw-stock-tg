"""研究 85b：「現行融資過熱 或 z 分數 > z」並用的鄰近參數（z 1.5～3、z 的視窗 120／250／500）與安慰劑（z 序列平移 100 次）
用法：python -X utf8 backtest/research_85b_z分數並用.py
"""
import importlib.util
import itertools
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r85", os.path.join(HERE, "research_85_融資過熱定義.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
N = R.N


def main():
    rng = random.Random(851)
    L = ["研究 85b：現行 或 z 分數 > z（全期 2002- | 前段 | 後段 | 真實 | p＝z 序列平移 100 次）"]
    cur = [R.cur_fn(v) for v in R.CUR] if hasattr(R, "cur_fn") else [v is not None and v > 0.175 for v in R.CUR]
    base, br = R.ev(cur)
    L.append("現行 " + " | ".join(f"{r['cagr']:.1%}/{r['mdd']:.1%}" for r in base) + f" | 真實 {br['cagr']:.1%}/{br['mdd']:.1%}")
    good = tot = 0
    for n, z in itertools.product((120, 250, 500), (1.5, 1.75, 2.0, 2.25, 2.5, 3.0)):
        zs = R.z_series(R.RATIO, n)
        flag = [cur[i] or (zs[i] is not None and zs[i] > z) for i in range(N)]
        rs, rr = R.ev(flag)
        sims = []
        for _ in range(100):
            sh = R.shifted(zs, rng)
            f2 = [cur[i] or (sh[i] is not None and sh[i] > z) for i in range(N)]
            sims.append(R.R3.run("2002-01-01", "2026-12-31", **R.kw(f2))["cagr"])
        p = (sum(x >= rs[0]["cagr"] for x in sims) + 1) / 101
        ok = all(a["cagr"] >= b["cagr"] - 1e-9 for a, b in zip(rs, base)) and rr["cagr"] >= br["cagr"] - 1e-9 and rs[0]["mdd"] >= base[0]["mdd"] - 0.03
        tot += 1
        good += ok
        L.append(f"n={n:3d} z>{z:<4} {'★' if ok else ' '} " + " | ".join(f"{r['cagr']:.1%}/{r['mdd']:.1%}" for r in rs) + f" | 真實 {rr['cagr']:.1%}/{rr['mdd']:.1%} | p {p:.2f}")
        print(L[-1], flush=True)
    L.append(f"\n四段都 ≥ 現行且回檔不深於 3 點：{good}/{tot}")
    open(os.path.join(HERE, "結果_研究85b_z分數並用.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(L[-1])


if __name__ == "__main__":
    main()
