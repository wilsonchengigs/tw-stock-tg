"""研究 550：主策略在場＋高 VIX 日，白天用台指期空單避險（08:45 空、13:45 平），晚上照抱
- 研究 411 完整配置（主策略 1.7x＋P＋D＋V），在「v3 前一天在場＋開盤前最後美國 VIX ≥ 門檻」的日子，加 -k× 台指期日盤報酬（開→收），每次成本 3 點
- 門檻 25／28／30／35，k 0.5／1／1.7（1.7＝白天完全不曝險）
- 2002～ 年化、回檔、逐年較好比例
用法：python -X utf8 backtest/research_550_day_hedge_highvix.py
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
    m = np.array([d >= "2002-01-01" for d in D]); yrs = np.array([d[:4] for d in D])
    def stat(r):
        x = r[m]; eq = np.cumprod(1 + x)
        return eq[-1] ** (bt.TD / len(x)) - 1, (eq / np.maximum.accumulate(eq) - 1).min()
    b0 = stat(base); out = [__doc__, f"現行（2002～）：年化 {b0[0]:.1%} 回檔 {b0[1]:.1%}"]
    for th in (25, 28, 30, 35):
        day = np.zeros(len(D)); n = 0
        for d in ds:
            if d not in idx:
                continue
            j = np.searchsorted(vk, d) - 1; i = np.searchsorted(keys, d) - 1
            if j >= 0 and i >= 0 and st[keys[i]] == 1 and vix[vk[j]] >= th:
                o, c = b[d][2], b[d][3]
                day[idx[d]] = c / o - 1; n += 1
        for k in (0.5, 1.0, 1.7):
            add = np.where(day != 0, -k * day - k * 3 / np.where(day != 0, 1, 1) / 30000, 0.0)
            # 成本：3 點 ÷ 當天價位，用近似（價位差異小，改用實際開盤價）
            add = np.zeros(len(D))
            for d in ds:
                if d in idx and day[idx[d]] != 0:
                    add[idx[d]] = -k * day[idx[d]] - k * 3 / b[d][2]
            s1 = stat(base + add)
            better = sum(1 for y in sorted(set(yrs[m])) if np.prod(1 + (base + add)[m & (yrs == y)]) >= np.prod(1 + base[m & (yrs == y)]))
            out.append(f"  VIX≥{th} 白天空 {k}x（{n} 天）：年化 {s1[0]:.1%}（{(s1[0]-b0[0])*100:+.1f} 點）回檔 {s1[1]:.1%}（{(s1[1]-b0[1])*100:+.1f} 點）｜較好的年 {better}/{len(set(yrs[m]))}")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究550_高VIX白天避險.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
