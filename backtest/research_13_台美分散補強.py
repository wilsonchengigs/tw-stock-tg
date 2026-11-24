"""研究 13：研究 09 候選「台股趨勢 2x ＋ Nasdaq-100 趨勢」的補強檢查（待研究 18）

1. 用台灣掛牌的 00670L（富邦 NASDAQ 正2，台幣計價、2017-02～）做真實價格驗證：台灣投資人不用複委託、沒有美股股利預扣稅
2. 美股腿改 1x（00662 富邦 NASDAQ 這類），權重 20～40%
3. 美股腿加 0.3%／年稅費拖累（若用複委託買 QLD：股利 30% 預扣＋較高費用）
4. 美股腿 S&P／NDX 各半（降低「事後選 Nasdaq」的偏誤）
5. 所有版本都跟現行比，並列 2017-03 起同期比較
用法：python -X utf8 backtest/research_13_台美分散補強.py
"""
import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r09", os.path.join(HERE, "research_09_多市場分散.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
bt = R.bt
N, DAYS, WE, ME = R.N, R.DAYS, R.WE, R.ME
TW = timezone(timedelta(hours=8))


def leg_variant(base, lev=2.0, drag=0.0):
    """用 base（USLeg）的美股資料做 lev 倍、額外年拖累 drag 的台幣日報酬"""
    ud = base.ud
    up = base.up
    div = 0.008 if base is NDX else 0.018
    r1 = [0.0] + [up[i] / up[i - 1] - 1 + div / R.TDUS for i in range(1, len(up))]
    rl = [0.0] + [lev * r1[i] - (max(lev - 1, 0) * 0.01 + drag) / R.TDUS for i in range(1, len(r1))]
    eq = [1.0]
    for i in range(1, len(rl)):
        eq.append(eq[-1] * (1 + rl[i]))
    out = [0.0]
    for i in range(1, N):
        a, b = base.idx[i - 1], base.idx[i]
        if a < 0 or a == b:
            out.append(0.0)
            continue
        r = eq[b] / eq[a] - 1
        fa, fb = R.fx_at(DAYS[i - 1]), R.fx_at(DAYS[i])
        if fa and fb:
            r = (1 + r) * fb / fa - 1
        out.append(r)
    return out


def tw_etf_ret(name, fallback):
    r = json.load(open(os.path.join(HERE, name + ".json")))
    adj = r["indicators"].get("adjclose", [{}])[0].get("adjclose") or r["indicators"]["quote"][0]["close"]
    m = {datetime.fromtimestamp(t, TW).strftime("%Y-%m-%d"): a for t, a in zip(r["timestamp"], adj) if a}
    px = [m.get(d) for d in DAYS]
    out, lp = [0.0], None
    for i in range(1, N):
        out.append(px[i] / lp - 1 if (px[i] and lp) else fallback[i])
        if px[i]:
            lp = px[i]
    return out, min(m)


def m10_signal(base, n=210):
    m = base.sma(n)
    st, out = False, []
    for i in range(N):
        k = base.idx[i]
        if k >= n and ME[i]:
            st = base.up[k] > m[k]
        out.append(st)
    return out


def run(wtw, legs, start, end, tw_r2=None):
    """legs＝[(權重, 日報酬, 訊號)]；台股腿＝現行；每月再平衡"""
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(DAYS) if d <= end)
    tr2 = tw_r2 or bt.R2
    w = [wtw] + [x[0] for x in legs]
    hold = list(w)
    pos = [0.0] * len(w)
    pend = [None] * len(w)
    peak, mdd, eq = 1.0, 0.0, 1.0
    for i in range(i0, i1 + 1):
        if i > i0:
            hold[0] *= 1 + pos[0] * tr2[i] + (1 - pos[0]) * bt.RC
            for k, (_, r, _) in enumerate(legs, 1):
                hold[k] *= 1 + pos[k] * r[i] + (1 - pos[k]) * bt.RC
        for k in range(len(w)):
            if pend[k] is not None:
                hold[k] *= 1 - bt.COST * 2 * abs(pend[k] - pos[k])
                pos[k], pend[k] = pend[k], None
        eq = sum(hold)
        if ME[i]:
            hold = [eq * x for x in w]
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if i >= 260:
            sigs = [R.TWSIG[i]] + [x[2][i] for x in legs]
            for k, s in enumerate(sigs):
                t = 1.0 if s else 0.0
                if t != pos[k]:
                    pend[k] = t
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


PER = R.PER + [("2017-03～", "2017-03-01", "2026-12-31")]


def fmt(wtw, legs, real_legs):
    cells = [run(wtw, legs, a, b) for _, a, b in PER]
    rr = run(wtw, real_legs, "2017-03-01", "2026-12-31", tw_r2=R.TWR2_REAL)
    return " | ".join(f"{c * 100:5.1f}%/{m * 100:6.1f}%" for c, m in cells) + f" | 真實 {rr[0] * 100:5.1f}%/{rr[1] * 100:6.1f}%"


NDX = R.USLeg("NDX", 0.008, "QLD")
SPX = R.USLeg("GSPC", 0.018, "SSO")


def main():
    n2 = leg_variant(NDX, 2.0)
    n2t = leg_variant(NDX, 2.0, 0.003)
    n1 = leg_variant(NDX, 1.0)
    s2 = leg_variant(SPX, 2.0)
    s1 = leg_variant(SPX, 1.0)
    real670, d670 = tw_etf_ret("00670L", n2)
    real662, d662 = tw_etf_ret("00662", n1)
    # 00662 在 2026-11-09 有未調整的分割（113.35 → 22.88），那天改用模擬報酬
    for i, d in enumerate(DAYS):
        if d == "2026-11-09":
            real662[i] = n1[i]
    sn = m10_signal(NDX)
    ss = m10_signal(SPX)
    sn200 = NDX.signal("ma200")
    L = [f"研究 13：台美分散補強（全期 1998- | 前段 -2012 | 後段 2013- | 2017-03～ 模擬 | 真實 2017-03～ 00631L＋00670L／00662；年化/最大回檔）",
         f"00670L 資料起 {d670}、00662 起 {d662}；美股訊號用 NDX／S&P 指數月底 10 個月線（210 日）"]

    def add(name, wtw, legs, real_legs):
        L.append(f"{name:36s} {fmt(wtw, legs, real_legs)}")
        print(L[-1], flush=True)

    add("現行（100% 台股）", 1.0, [], [])
    L.append("\n== NDX 2x 10 月線（真實用 00670L）==")
    for w in (0.8, 0.75, 0.7):
        add(f"台 {int(w*100)}%＋NDX 2x {int(round((1-w)*100))}%", w, [(1 - w, n2, sn)], [(1 - w, real670, sn)])
    add("台 80%＋NDX 2x 20%（200 日線）", 0.8, [(0.2, n2, sn200)], [(0.2, real670, sn200)])
    L.append("\n== 加 0.3%/年 稅費拖累（複委託 QLD）==")
    for w in (0.8, 0.7):
        add(f"台 {int(w*100)}%＋NDX 2x {int(round((1-w)*100))}% 拖累", w, [(1 - w, n2t, sn)], [(1 - w, real670, sn)])
    L.append("\n== 美股腿 1x（真實用 00662）==")
    for w in (0.8, 0.7, 0.6):
        add(f"台 {int(w*100)}%＋NDX 1x {int(round((1-w)*100))}%", w, [(1 - w, n1, sn)], [(1 - w, real662, sn)])
    L.append("\n== 美股腿 S&P／NDX 各半（降低事後選 Nasdaq 的偏誤；真實 S&P 腿用模擬）==")
    for w in (0.8, 0.7):
        h = (1 - w) / 2
        add(f"台 {int(w*100)}%＋S&P 2x {h*100:.0f}%＋NDX 2x {h*100:.0f}%", w, [(h, s2, ss), (h, n2, sn)], [(h, s2, ss), (h, real670, sn)])
    L.append("\n== 美股腿不看趨勢（買進持有）==")
    add("台 80%＋NDX 2x 20% 長抱", 0.8, [(0.2, n2, [True] * N)], [(0.2, real670, [True] * N)])
    add("台 80%＋NDX 1x 20% 長抱", 0.8, [(0.2, n1, [True] * N)], [(0.2, real662, [True] * N)])
    add("台 70%＋S&P 1x 30% 長抱", 0.7, [(0.3, s1, [True] * N)], [(0.3, s1, [True] * N)])
    out = "\n".join(L) + "\n"
    open(os.path.join(HERE, "結果_研究13_台美分散補強.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
