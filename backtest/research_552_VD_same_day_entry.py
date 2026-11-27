"""研究 552：V（爆量收黑）與 D（台美背離）改成訊號當天 13:44 進台指期（多吃一個隔夜），vs 現行隔天 08:45
- V：研究 411 的 vsig（v3 在場、成交金額 ≥1.5 倍 20 日均、收黑）
- D：加權 20 日報酬 − S&P 20 日報酬（前一晚） ≤ -10%（研究 204～211，持有中不重複）
- 隔夜報酬：訊號日台指期近月 13:45 收 → 隔天 08:45 開（換月剔除）；正＝提早進場多賺
用法：python -X utf8 backtest/research_552_VD_same_day_entry.py
"""
import io, contextlib, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_411_實際配置含V as A
from research_514_pattern_regime import yahoo
from research_544_overnight_vs_day import load


def main():
    b = load(); ds = sorted(b); nxt = dict(zip(ds, ds[1:]))
    def night(p):
        d = nxt.get(p)
        if d is None or b[p][1] != b[d][1]:
            return None
        return (b[d][2] / b[p][3] - 1) * 100
    out = [__doc__]
    vdays = [d for d, sgl, s in zip(A.ds, A.vsig, A.st) if sgl and s == 1]
    x = np.array([v for d in vdays if d in b and (v := night(d)) is not None])
    out.append(f"V 訊號日 {len(vdays)} 天（有台指期隔夜 {len(x)}）：隔夜 每次 {x.mean():+.3f}% t {x.mean()/(x.std(ddof=1)/np.sqrt(len(x))):+.2f} 正的比例 {(x>0).mean()*100:.0f}%")
    tw = yahoo("TWII.json"); spx = yahoo("GSPC.json"); tk = sorted(tw); sk = np.array(sorted(spx))
    dsig = []; hold_until = ""
    for i in range(20, len(tk)):
        d = tk[i]
        if d <= hold_until:
            continue
        j = np.searchsorted(sk, d) - 1
        if j < 20:
            continue
        r_tw = tw[d] / tw[tk[i - 20]] - 1; r_sp = spx[sk[j]] / spx[sk[j - 20]] - 1
        if r_tw - r_sp <= -0.10:
            dsig.append(d); hold_until = tk[min(i + 5, len(tk) - 1)]
    y = np.array([v for d in dsig if d in b and (v := night(d)) is not None])
    out.append(f"D 訊號日 {len(dsig)} 天（有台指期隔夜 {len(y)}）：隔夜 每次 {y.mean():+.3f}% t {y.mean()/(y.std(ddof=1)/np.sqrt(len(y))):+.2f} 正的比例 {(y>0).mean()*100:.0f}%")
    out.append(f"對照：所有日子隔夜平均 {np.mean([v for d in ds if (v := night(d)) is not None]):+.3f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究552_VD當天進場.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
