"""研究 547：完整配置（研究 411）＋「在場＋VIX≥門檻 → 台指期收盤買、隔天開盤賣」k 倍名目
門檻 25／28／30；k 0.5／1；期間 2002～（與研究 411 一致）；另列再加日內順勢 1x（研究 537，2010～ 才有）
用法：python -X utf8 backtest/research_547_portfolio_overnight.py
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
    b = load(); ds = sorted(b)
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    out = [__doc__]
    def stat(r, m):
        r = r[m]; eq = np.cumprod(1 + r)
        return eq[-1] ** (bt.TD / len(r)) - 1, (eq / np.maximum.accumulate(eq) - 1).min()
    m02 = np.array([d >= "2002-01-01" for d in D])
    b0 = stat(base, m02)
    out.append(f"現行（2002～）：年化 {b0[0]:.1%} 回檔 {b0[1]:.1%}")
    for th in (25, 28, 30):
        add = np.zeros(len(D)); n = 0
        for p, d in zip(ds, ds[1:]):
            if b[p][1] != b[d][1] or d not in idx:
                continue
            j = np.searchsorted(vk, p) - 1; i = np.searchsorted(keys, p) - 1
            if j >= 0 and i >= 0 and st[keys[i]] == 1 and vix[vk[j]] >= th:
                add[idx[d]] += b[d][2] / b[p][3] - 1 - 3 / b[p][3]; n += 1
        for k in (0.5, 1.0):
            s1 = stat(base + k * add, m02)
            yrs = np.array([d[:4] for d in D])
            better = sum(1 for y in sorted(set(yrs[m02])) if np.prod(1 + (base + k * add)[m02 & (yrs == y)]) >= np.prod(1 + base[m02 & (yrs == y)]))
            out.append(f"  VIX≥{th} {k}x（{n} 夜）：年化 {s1[0]:.1%}（{(s1[0]-b0[0])*100:+.1f} 點）回檔 {s1[1]:.1%}｜不變或較好的年 {better}/{len(set(yrs[m02]))}")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究547_完整配置加隔夜.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
