"""研究 554：在場＋VIX≥28 隔夜加碼，受「期貨名目合計 ≤1.5x」限制（研究 553）後放進研究 411 配置（2002～）
隔夜加碼倍數＝min(1, 1.5 − 當晚已有 P／V 名目)，≤0 不做
用法：python -X utf8 backtest/research_554_overnight_capped.py
"""
import io, contextlib, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_411_實際配置含V as A
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138
from research_544_overnight_vs_day import load


def main():
    R = A.R; bt = A.bt
    base = R.main + R.padd + R.dadd + A.vadd
    D = [str(x)[:10] for x in R.D]; idx = {d: i for i, d in enumerate(D)}
    ds = list(A.ds); n = len(ds); pos = {d: k for k, d in enumerate(ds)}
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix)); spx = yahoo("GSPC.json"); sk = np.array(sorted(spx))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    def vprev(d): return vix[vk[np.searchsorted(vk, d) - 1]]
    def state(d): return st[keys[np.searchsorted(keys, d) - 1]]
    exp = np.zeros(n)
    for k, d in enumerate(ds):
        j = np.searchsorted(sk, d) - 1
        if j >= 1 and spx[sk[j]] / spx[sk[j - 1]] - 1 <= -0.02:
            v = vprev(d); exp[k] += (1.0 if state(d) == 1 else 0.0) if v < 25 else (1.0 if v < 35 else 1.5)
    for k, (sg, s0) in enumerate(zip(A.vsig, A.st)):
        if sg and s0 == 1:
            exp[k + 1:min(k + 11, n)] += 1.0
    b = load(); bd = sorted(b)
    full = np.zeros(len(D)); capd = np.zeros(len(D)); used = []
    for p, d in zip(bd, bd[1:]):
        if b[p][1] != b[d][1] or d not in idx or p not in pos:
            continue
        if state(p) == 1 and vprev(p) >= 28:
            r = b[d][2] / b[p][3] - 1 - 3 / b[p][3]
            k = min(1.0, max(0.0, 1.5 - exp[pos[p]]))
            full[idx[d]] += r; capd[idx[d]] += k * r; used.append(k)
    m = np.array([d >= "2002-01-01" for d in D])
    def stat(r):
        x = r[m]; eq = np.cumprod(1 + x)
        return eq[-1] ** (bt.TD / len(x)) - 1, (eq / np.maximum.accumulate(eq) - 1).min()
    out = [__doc__]
    for lab, r in (("現行", base), ("＋隔夜 1x（不限）", base + full), ("＋隔夜（合計 ≤1.5x）", base + capd)):
        s1 = stat(r); out.append(f"  {lab:18s} 年化 {s1[0]:.1%} 回檔 {s1[1]:.1%}")
    u = np.array(used); out.append(f"  限制後平均倍數 {u.mean():.2f}x；1x {np.mean(u==1)*100:.0f}%、0.5x {np.mean(u==0.5)*100:.0f}%、0 {np.mean(u==0)*100:.0f}% 的夜")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究554_隔夜限名目.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
