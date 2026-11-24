"""研究 88：v3 融資參數聯合鄰近檢查（偏離門檻 th × z 門檻 × 回補門檻）
用法：python -X utf8 backtest/research_88_v3參數聯合.py
"""
import importlib.util
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("v3", os.path.join(HERE, "strategy_v3.py"))
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)


def main():
    L = ["研究 88：v3 參數聯合（全期 2002- | 前段 | 後段 | 真實）"]
    base = [V.run(a, b) for a, b in V.PER]
    br = V.run(*V.REAL, real=True)
    L.append("v3（17.5%、z 2、回補 12.5%）：" + V.fmt())
    res = []
    for th, zt, re_ in itertools.product((0.15, 0.175, 0.20), (1.75, 2.0, 2.25), (0.10, 0.125, 0.15)):
        rs = [V.run(a, b, th=th, zth=zt, reentry=re_) for a, b in V.PER]
        rr = V.run(*V.REAL, real=True, th=th, zth=zt, reentry=re_)
        res.append(((th, zt, re_), rs, rr))
    cs = sorted(x[1][0][0] for x in res)
    good = sum(1 for _, rs, rr in res if all(a[0] >= b[0] - 0.005 for a, b in zip(rs, base)) and rr[0] >= br[0] - 0.01)
    L.append(f"27 組全期年化：最低 {cs[0]:.1%}、中位 {cs[13]:.1%}、最高 {cs[-1]:.1%}；回檔最深 {min(x[1][0][1] for x in res):.1%}")
    L.append(f"各段都不低於 v3 0.5 點以上、真實不低於 1 點以上：{good}/27")
    for p, rs, rr in sorted(res, key=lambda x: -x[1][0][0]):
        L.append(f"  偏離 {p[0]:.1%} z {p[1]} 回補 {p[2]:.1%}  " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%}")
    out = "\n".join(L) + "\n"
    print("\n".join(L[:4]))
    open(os.path.join(HERE, "結果_研究88_v3參數聯合.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
