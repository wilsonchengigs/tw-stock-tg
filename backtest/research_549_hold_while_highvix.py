"""研究 549：主策略在場＋VIX≥門檻 → 加 1x 台指期「持續持有」（日盤＋夜都抱），條件消失隔天 08:45 平；vs 只抱隔夜（研究 546）
- 進場：條件成立那天 13:45 收盤買（與 546 相同時點）；持有期間每天收→收報酬；條件消失那天的隔天 08:45 開盤賣
- 成本：持續版只在進出時扣 3 點；隔夜版每夜 3 點
- 換月：近月切換日以兩個合約的收盤價差近似連續（用每天成交量最大合約的報酬，換月日用前一天同月份的收盤）
- 完整配置（研究 411，2002～）加 1x 的年化／回檔
用法：python -X utf8 backtest/research_549_hold_while_highvix.py
"""
import io, contextlib, os, sys, csv
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_411_實際配置含V as A
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138


def load_all():
    """{date: {month: (open, close)}}（日盤）"""
    out = {}
    for r in csv.DictReader(open(os.path.join(HERE, "tx_daily_ohlc.csv"), encoding="utf-8")):
        if r["session"] != "day" or r["open"] in ("-", "") or r["close"] in ("-", ""):
            continue
        out.setdefault(r["date"], {})[r["month"]] = (float(r["open"]), float(r["close"]), int(r["volume"] or 0))
    return out


def main():
    R = A.R; bt = A.bt
    base = R.main + R.padd + R.dadd + A.vadd
    D = [str(x)[:10] for x in R.D]; idx = {d: i for i, d in enumerate(D)}
    allb = load_all(); ds = sorted(allb)
    near = {d: max(allb[d], key=lambda m: allb[d][m][2]) for d in ds}
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    def on(p):
        j = np.searchsorted(vk, p) - 1; i = np.searchsorted(keys, p) - 1
        return j >= 0 and i >= 0 and st[keys[i]] == 1 and vix[vk[j]]
    out = [__doc__]
    def stat(r):
        m = np.array([d >= "2002-01-01" for d in D]); r = r[m]; eq = np.cumprod(1 + r)
        return eq[-1] ** (bt.TD / len(r)) - 1, (eq / np.maximum.accumulate(eq) - 1).min()
    b0 = stat(base); out.append(f"現行（2002～）：年化 {b0[0]:.1%} 回檔 {b0[1]:.1%}")
    for th in (25, 28, 30):
        hold = np.zeros(len(D)); night = np.zeros(len(D)); pos = None; trades = 0; days_in = 0
        for k in range(1, len(ds)):
            p, d = ds[k - 1], ds[k]
            v = on(p); sigp = bool(v) and v >= th
            mp = near[p]
            if mp in allb[d]:
                o_d, c_d = allb[d][mp][0], allb[d][mp][1]
                cp = allb[p][mp][1]
                if sigp and d in idx:
                    night[idx[d]] += o_d / cp - 1 - 3 / cp
                if d in idx:
                    if pos is not None:  # 已持有：今天決定是否續抱
                        if sigp:
                            hold[idx[d]] += c_d / cp - 1; days_in += 1
                        else:
                            hold[idx[d]] += o_d / cp - 1 - 1.5 / cp; pos = None
                    if pos is None and sigp:
                        # p 收盤買（今天 d 之前），今天 d 的收→收
                        hold[idx[d]] += c_d / cp - 1 - 1.5 / cp; pos = cp; trades += 1; days_in += 1
        for lab, add in (("持續持有", hold), ("只抱隔夜", night)):
            s1 = stat(base + add)
            out.append(f"  VIX≥{th} {lab}：年化 {s1[0]:.1%}（{(s1[0]-b0[0])*100:+.1f} 點）回檔 {s1[1]:.1%}" + (f"｜進出 {trades} 次、持有 {days_in} 天" if lab == "持續持有" else ""))
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究549_高VIX持續持有.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
