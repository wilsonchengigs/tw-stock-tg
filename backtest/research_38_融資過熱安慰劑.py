"""研究 38：研究 03 C 類「融資／指數比值高於 250 日均值 y 就出場且不進」的安慰劑檢定（出場緩衝用新版 2.5%）
把「比值偏離度」序列整段循環平移 200 次（位移 ≥ 250 日），看真實序列的全期年化贏過幾成
資料：backtest/margin_tw.csv（上市融資金額，2001～，salmonmisosoup/leverage-dashboard 鏡像）
用法：python -X utf8 backtest/research_38_融資過熱安慰劑.py
"""
import importlib.util
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.argv = [sys.argv[0], os.path.join(HERE, "margin_tw.csv")]
spec = importlib.util.spec_from_file_location("r03", os.path.join(HERE, "research_03_融資濾網.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
bt = R.bt
N = len(bt.DAYS)
DEV = [R.ratio_dev(i, 250) if i >= 250 else None for i in range(N)]
_, _, l2 = R.data.series() if hasattr(R, "data") else __import__("data").series()
_px = [l2.get(d, (None, None))[1] for d in bt.DAYS]
R2R, _lp = [0.0], None
for _i in range(1, N):
    R2R.append(_px[_i] / _lp - 1 if (_px[_i] and _lp) else bt.R2[_i])
    if _px[_i]:
        _lp = _px[_i]


def kw_for(dev, y):
    return dict(entry_ok=lambda i: dev[i] is None or dev[i] < y, force_exit=lambda i: dev[i] is not None and dev[i] > y, bout=0.025)


def main():
    rng = random.Random(9)
    L = ["研究 38：融資／指數比值過熱濾網的安慰劑檢定（2002-2026 全期年化；200 次平移）"]
    base = R.run("2002-01-01", "2026-12-31", bout=0.025)
    base_r = R.run("2015-09-01", "2026-12-31", bout=0.025, r2=R2R)
    L.append(f"現行（出場 2.5%）：全期 {base['cagr']:.1%}／{base['mdd']:.1%}、真實 {base_r['cagr']:.1%}／{base_r['mdd']:.1%}")
    i0 = next(i for i in range(N) if DEV[i] is not None)
    seg = DEV[i0:]
    for y in (0.10, 0.125, 0.15, 0.20):
        real = R.run("2002-01-01", "2026-12-31", **kw_for(DEV, y))
        post = R.run("2013-01-01", "2026-12-31", **kw_for(DEV, y))
        rr = R.run("2015-09-01", "2026-12-31", r2=R2R, **kw_for(DEV, y))
        sims = []
        for _ in range(200):
            k = rng.randrange(250, len(seg) - 250)
            sh = [None] * i0 + seg[k:] + seg[:k]
            sims.append(R.run("2002-01-01", "2026-12-31", **kw_for(sh, y))["cagr"])
        sims.sort()
        p = (sum(x >= real["cagr"] for x in sims) + 1) / 201
        L.append(f"y={y:.1%}：全期 {real['cagr']:.1%}／{real['mdd']:.1%}、後段 {post['cagr']:.1%}、真實 {rr['cagr']:.1%}／{rr['mdd']:.1%}｜平移中位 {sims[100]:.1%}、90 分位 {sims[180]:.1%}｜p＝{p:.3f}")
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究38_融資過熱安慰劑.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
