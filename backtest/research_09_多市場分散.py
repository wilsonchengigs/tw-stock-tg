"""研究 09：多市場分散：台股趨勢正2 ＋ 美股（S&P 500／Nasdaq-100）趨勢 2x，能否降低回檔又不犧牲報酬

做法來源：
- Faber (2007) "A Quantitative Approach to Tactical Asset Allocation"：多資產各自用 10 個月均線，站上持有、跌破轉現金，等權重，
  回檔大幅降低 https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461
- Antonacci GEM（研究 02 已測，相對動能全押單一市場較差），這裡改成「各自趨勢＋固定權重」分散

模擬：
- 台股腿：現行策略（週五 MA60x1.01 進／MA80x0.98 出，全押 2x，bt.py 同假設）
- 美股腿：指數價格＋配息（S&P 1.8%／NDX 0.8% 年）模擬 1x、2x＝2x1x−1%（同台股假設）；規則可選
  (a) 同台股 MA60x1.01／MA80x0.98、(b) 200 日均線（美股常見）、(c) 10 個月均線（Faber，月底判斷）
- 美股報酬換算台幣：TWD=X 2004-03 起；之前沒有匯率資料，直接用美元報酬（1998～2004 台幣 32～34，影響小）
- 對齊：台股第 i 天用「台股該日之前最後一個美股收盤」的報酬（美股收盤晚於台股，不偷看）；
  美股腿也在台股週五判斷，用的是前一晚美股收盤
- 兩腿權重每月底（或每年）再平衡，各腿空手時那部分放現金 1%
- 成本：各腿換手 0.25%/單位曝險（美股 ETF 實際更低，保守）
真實價格：2015-09 後台股用 00631L、美股用 SSO／QLD（ProShares 2x，美元）×匯率
用法：python -X utf8 backtest/research_09_多市場分散.py
"""
import bisect
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402
import data  # noqa: E402

NY = timezone(timedelta(hours=-5))
PER = [("全期", "1998-01-01", "2026-12-31"), ("前段", "1998-01-01", "2012-12-31"), ("後段", "2013-01-01", "2026-12-31")]
REAL = ("2015-09-01", "2026-12-31")
DAYS, PX, WE = bt.DAYS, bt.PX, bt.WEEK_END
N = len(DAYS)
ME = [i == N - 1 or DAYS[i][:7] != DAYS[i + 1][:7] for i in range(N)]
TDUS = 252


def yload(name, tz=NY):
    r = json.load(open(os.path.join(HERE, name + ".json")))
    q = r["indicators"]["quote"][0]
    adj = r["indicators"].get("adjclose", [{}])[0].get("adjclose") or q["close"]
    out = {}
    for t, c, a in zip(r["timestamp"], q["close"], adj):
        if c and a and c > 0:
            out[datetime.fromtimestamp(t, tz).strftime("%Y-%m-%d")] = a
    return out


def us_series(name, div):
    s = yload(name)
    d = sorted(s)
    p = [s[k] for k in d]
    r1 = [0.0] + [p[i] / p[i - 1] - 1 + div / TDUS for i in range(1, len(p))]
    return d, p, r1


_FXRAW = yload("TWD", timezone(timedelta(hours=8)))
FXD = sorted(_FXRAW)
# Yahoo TWD=X 有錯價（2011-10-25 1.80、2014-12-31 3.67）且 2011～2016 常有單日 ±3～4% 來回跳，用前後各 2 天中位數清洗
_v = [_FXRAW[d] for d in FXD]
FX = {d: sorted(_v[max(0, k - 2):k + 3])[len(_v[max(0, k - 2):k + 3]) // 2] for k, d in enumerate(FXD)}


def fx_at(day):
    k = bisect.bisect_right(FXD, day) - 1
    return FX[FXD[k]] if k >= 0 else None


class USLeg:
    """把美股日序列映射到台股交易日"""
    def __init__(self, name, div, real_etf=None):
        self.ud, self.up, r1 = us_series(name, div)
        self.ur2 = [0.0] + [2 * r1[i] - 0.01 / TDUS for i in range(1, len(r1))]
        self.ma = {}
        # 台股第 i 天對應的「最後一個嚴格早於該日的美股交易日」索引
        self.idx = [bisect.bisect_left(self.ud, d) - 1 for d in DAYS]
        # 累積 2x 淨值（美元）以便計算區間報酬
        eq = [1.0]
        for i in range(1, len(self.ur2)):
            eq.append(eq[-1] * (1 + self.ur2[i]))
        self.eq2 = eq
        self.real = None
        if real_etf:
            s = yload(real_etf)
            self.real = s
        self.r2tw = self._tw_ret(False)
        self.r2tw_real = self._tw_ret(True) if real_etf else None

    def _val(self, k, real):
        if k < 0:
            return None
        if real and self.real is not None:
            d = self.ud[k]
            v = self.real.get(d)
            return v
        return self.eq2[k]

    def _tw_ret(self, real):
        out = [0.0]
        for i in range(1, N):
            a, b = self.idx[i - 1], self.idx[i]
            if a < 0 or a == b:
                out.append(0.0)
                continue
            va, vb = self._val(a, real), self._val(b, real)
            if not va or not vb:
                va, vb = self.eq2[a], self.eq2[b]
            r = vb / va - 1
            fa, fb = fx_at(DAYS[i - 1]), fx_at(DAYS[i])
            if fa and fb:
                r = (1 + r) * fb / fa - 1
            out.append(r)
        return out

    def sma(self, n):
        if n not in self.ma:
            out, s = [None] * len(self.up), 0.0
            for i, p in enumerate(self.up):
                s += p
                if i >= n:
                    s -= self.up[i - n]
                if i >= n - 1:
                    out[i] = s / n
            self.ma[n] = out
        return self.ma[n]

    def signal(self, rule):
        """回傳每個台股日的 on/off（只在週五／月底更新）"""
        st, out = False, []
        m60, m80, m200 = self.sma(60), self.sma(80), self.sma(200)
        m210 = self.sma(210)  # 10 個月 ≈ 210 日
        for i in range(N):
            k = self.idx[i]
            if k >= 210:
                p = self.up[k]
                if rule == "cur" and WE[i]:
                    st = (not p < m80[k] * 0.98) if st else (p > m60[k] * 1.01)
                elif rule == "ma200" and WE[i]:
                    st = p > m200[k]
                elif rule == "m10" and ME[i]:
                    st = p > m210[k]
                elif rule == "hold":
                    st = True
            out.append(st)
        return out


def tw_signal():
    st, out = False, []
    m60, m80 = bt.get_sma(60), bt.get_sma(80)
    for i in range(N):
        if WE[i] and i >= 260:
            st = (not PX[i] < m80[i] * 0.98) if st else (PX[i] > m60[i] * 1.01)
        out.append(st)
    return out


_, _l1, L2 = data.series()


def tw_real():
    px = [L2.get(d, (None, None))[1] for d in DAYS]
    out, lp = [0.0], None
    for i in range(1, N):
        out.append(px[i] / lp - 1 if (px[i] and lp) else bt.R2[i])
        if px[i]:
            lp = px[i]
    return out


TWR2_REAL = tw_real()
TWSIG = tw_signal()


def run(wtw, leg, rule, start, end, real=False, reb="month", sig_override=None):
    """wtw＝台股腿權重；leg＝USLeg 或 None"""
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(DAYS) if d <= end)
    tr2 = TWR2_REAL if real else bt.R2
    ur2 = (leg.r2tw_real if real else leg.r2tw) if leg else None
    usig = sig_override or (leg.signal(rule) if leg else None)
    a, b = wtw, 1 - wtw   # 兩腿資金
    pa = pb = 0.0          # 各腿當前曝險（0 或 1）
    pend_a = pend_b = None
    peak, mdd, eq, ys = 1.0, 0.0, 1.0, {}
    for i in range(i0, i1 + 1):
        if i > i0:
            a *= 1 + pa * tr2[i] + (1 - pa) * bt.RC
            if leg:
                b *= 1 + pb * ur2[i] + (1 - pb) * bt.RC
            else:
                b *= 1 + bt.RC
        if pend_a is not None:
            a *= 1 - bt.COST * 2 * abs(pend_a - pa)
            pa, pend_a = pend_a, None
        if pend_b is not None:
            b *= 1 - bt.COST * 2 * abs(pend_b - pb)
            pb, pend_b = pend_b, None
        eq = a + b
        if (reb == "month" and ME[i]) or (reb == "year" and ME[i] and DAYS[i][5:7] == "12"):
            # 再平衡：兩腿都有部位時換手成本
            ta = eq * wtw
            cost = abs(ta - a) * (pa + pb) * bt.COST  # 粗估
            eq -= cost
            a, b = eq * wtw, eq * (1 - wtw)
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        ys[DAYS[i][:4]] = eq
        if i >= 260:
            t = 1.0 if TWSIG[i] else 0.0
            if t != pa:
                pend_a = t
            if leg:
                u = 1.0 if usig[i] else 0.0
                if u != pb:
                    pend_b = u
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, ys


def fmt(*args, **kw):
    out = []
    for _, s, e in PER:
        c, m, _ = run(*args, s, e, **kw)
        out.append(f"{c * 100:5.1f}%/{m * 100:6.1f}%")
    c, m, _ = run(*args, *REAL, real=True, **kw)
    return " | ".join(out) + f" | 真實 {c * 100:5.1f}%/{m * 100:6.1f}%"


def main():
    spx = USLeg("GSPC", 0.018, "SSO")
    ndx = USLeg("NDX", 0.008, "QLD")
    L = ["研究 09：多市場分散（格式：全期 1998-2026 | 前段 1998-2012 | 後段 2013-2026 | 真實 2015-09～；年化/最大回檔，台幣計價）"]

    def add(name, *a, **k):
        L.append(f"{name:40s} {fmt(*a, **k)}")
        print(L[-1], flush=True)

    L.append("\n== 基準 ==")
    add("現行（100% 台股趨勢 2x）", 1.0, None, None)
    for nm, leg in (("S&P", spx), ("NDX", ndx)):
        for rule, rn in (("hold", "買進持有"), ("cur", "MA60/80 同規則"), ("ma200", "200 日線"), ("m10", "10 月線")):
            add(f"100% 美股 {nm} 2x {rn}", 0.0, leg, rule)
    L.append("\n== 台股趨勢 2x ＋ 美股趨勢 2x（每月再平衡）==")
    for nm, leg in (("S&P", spx), ("NDX", ndx)):
        for rule, rn in (("cur", "MA60/80"), ("ma200", "200日線"), ("m10", "10月線")):
            for w in (0.8, 0.7, 0.5):
                add(f"台 {int(w*100)}%＋{nm} {int(round((1-w)*100))}% {rn}", w, leg, rule)
    L.append("\n== 再平衡頻率（台 70%＋S&P 30% 200 日線）==")
    add("每月", 0.7, spx, "ma200", reb="month")
    add("每年", 0.7, spx, "ma200", reb="year")
    add("不再平衡", 0.7, spx, "ma200", reb="none")
    L.append("\n== 對照：美股腿改成現金（只是降槓桿的效果有多少）==")
    for w in (0.8, 0.7, 0.5):
        add(f"台 {int(w*100)}%＋現金 {int(round((1-w)*100))}%", w, None, None)
    open(os.path.join(HERE, "結果_研究09_多市場分散.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
