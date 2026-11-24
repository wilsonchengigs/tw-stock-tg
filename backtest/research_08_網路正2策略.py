"""研究 08：台灣網路上常見的「正2」公開做法逐一回測

來源（做法整理，非完整回測報告）：
- 今周刊 2026-08「0050、正2、現金這樣搭」：一半正2＋一半現金（曝險約 100%），回檔時用現金加碼
  https://www.businesstoday.com.tw/article/category/183013/post/202608270026/
- 優分析 2026-08：正2 定期定額／長抱、重紀律 https://uanalyze.com.tw/articles/3451052835
- LINE Today：MA3／MA10 死亡交叉出場（小台）https://today.line.me/tw/v3/article/Ggzan6Z
- PTT／Dcard 常見：季線（MA60）、半年線（MA120）、年線（MA240）上持有、跌破出場；正2＋0050 混搭；跌深加碼

引擎：權重 (w2, w1, 現金) 每日隨漲跌漂移；決策日改目標權重，下一交易日收盤成交；
成本 0.25% x (2|dw2| + |dw1|)（同 bt.py 以曝險計）。真實＝2015-09 後 00631L／0050 實際價格。
用法：python -X utf8 backtest/research_08_網路正2策略.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402
import data  # noqa: E402

PER = [("全期", "1998-01-01", "2026-12-31"), ("前段", "1998-01-01", "2012-12-31"), ("後段", "2013-01-01", "2026-12-31")]
REAL = ("2015-09-01", "2026-12-31")
PX, DAYS, WE = bt.PX, bt.DAYS, bt.WEEK_END
N = len(PX)
_, l1, l2 = data.series()
ME = [i == N - 1 or DAYS[i][:7] != DAYS[i + 1][:7] for i in range(N)]


def real_ret(src, sim):
    px = [src.get(d, (None, None))[1] for d in DAYS]
    out, lp = [0.0], None
    for i in range(1, N):
        out.append(px[i] / lp - 1 if (px[i] and lp) else sim[i])
        if px[i]:
            lp = px[i]
    return out


R2R, R1R = real_ret(l2, bt.R2), real_ret(l1, bt.R1)
MA = {n: bt.get_sma(n) for n in (3, 10, 20, 60, 80, 120, 240)}
HI250 = [max(PX[max(0, i - 249):i + 1]) for i in range(N)]


def run(make, start, end, real=False):
    """make() 產生 strat(i, w) -> 目標 (w2, w1) 或 None（不動）"""
    strat = make()
    r2, r1 = (R2R, R1R) if real else (bt.R2, bt.R1)
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(DAYS) if d <= end)
    h2, h1, hc = 0.0, 0.0, 1.0
    peak, mdd, pend, trades = 1.0, 0.0, None, 0
    eq = 1.0
    for i in range(i0, i1 + 1):
        if i > i0:
            h2 *= 1 + r2[i]
            h1 *= 1 + r1[i]
            hc *= 1 + bt.RC
        eq = h2 + h1 + hc
        if pend is not None:
            w2, w1 = h2 / eq, h1 / eq
            to = 2 * abs(pend[0] - w2) + abs(pend[1] - w1)
            if to > 1e-9:
                eq *= 1 - bt.COST * to
                trades += 1
            h2, h1 = pend[0] * eq, pend[1] * eq
            hc = eq - h2 - h1
            pend = None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if i >= 260:
            t = strat(i, (h2 / eq, h1 / eq))
            if t is not None and (abs(t[0] - h2 / eq) > 1e-9 or abs(t[1] - h1 / eq) > 1e-9):
                pend = t
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, trades / yrs


def fmt(make):
    out = []
    for _, a, b in PER:
        c, m, _ = run(make, a, b)
        out.append(f"{c * 100:5.1f}%/{m * 100:6.1f}%")
    c, m, _ = run(make, *REAL, real=True)
    tpy = run(make, PER[0][1], PER[0][2])[2]
    return " | ".join(out) + f" | 真實 {c * 100:5.1f}%/{m * 100:6.1f}% | 年交易 {tpy:4.1f}"


# ---------- 策略（每個都是 make 函式，回測時重建狀態）----------
def hold(w2, w1=0.0):
    return lambda: (lambda i, w: (w2, w1) if (w[0] == 0 and w[1] == 0) else None)


def rebal(w2, w1=0.0, mode="month", band=0.10):
    def s(i, w):
        if w[0] == 0 and w[1] == 0:
            return (w2, w1)
        if mode == "month" and ME[i]:
            return (w2, w1)
        if mode == "quarter" and ME[i] and DAYS[i][5:7] in ("03", "06", "09", "12"):
            return (w2, w1)
        if mode == "year" and ME[i] and DAYS[i][5:7] == "12":
            return (w2, w1)
        if mode == "band" and (abs(w[0] - w2) > band or abs(w[1] - w1) > band):
            return (w2, w1)
        return None
    return lambda: s


def ma_cross(n, weekly=True, off=(0.0, 0.0), on=(1.0, 0.0)):
    m = MA[n]

    def s(i, w):
        if weekly and not WE[i]:
            return None
        return on if PX[i] > m[i] else off
    return lambda: s


def ma_xx(f, sl):
    a, b = MA[f], MA[sl]
    return lambda: (lambda i, w: (1.0, 0.0) if a[i] > b[i] else (0.0, 0.0))


def cur(on=(1.0, 0.0), off=(0.0, 0.0)):
    """現行 MA60x1.01 進／MA80x0.98 出；off 可改持 0050 或部分正2"""
    def make():
        st = {"on": False}

        def s(i, w):
            if not WE[i]:
                return None
            if st["on"]:
                if PX[i] < MA[80][i] * 0.98:
                    st["on"] = False
            elif PX[i] > MA[60][i] * 1.01:
                st["on"] = True
            return on if st["on"] else off
        return s
    return make


def dip_buy(base=0.5, dd=0.2, back=0.0):
    """平時 base 正2＋現金（每月再平衡）；指數距 250 日高點跌超過 dd 改全押正2；回到距高點 back 以內再回 base"""
    def make():
        st = {"full": False}

        def s(i, w):
            if w[0] == 0 and w[1] == 0:
                return (base, 0.0)
            if not WE[i]:
                return None
            d = PX[i] / HI250[i] - 1
            if not st["full"] and d < -dd:
                st["full"] = True
                return (1.0, 0.0)
            if st["full"] and d > -back:
                st["full"] = False
                return (base, 0.0)
            if not st["full"] and ME[i]:
                return (base, 0.0)
            return None
        return s
    return make


def bias240(lo=-0.10, hi=0.20):
    """年線乖離：低於年線 lo 以下全押正2；高於 hi 以上出場；中間維持"""
    def make():
        st = {"on": False}

        def s(i, w):
            if not WE[i]:
                return None
            b = PX[i] / MA[240][i] - 1
            if b < lo:
                st["on"] = True
            elif b > hi:
                st["on"] = False
            return (1.0, 0.0) if st["on"] else (0.0, 0.0)
        return s
    return make


def main():
    L = ["研究 08：網路常見正2 做法（格式：全期 | 前段 1998-2012 | 後段 2013-2026 | 真實 2015-09～；年化/最大回檔）"]
    rows = [
        ("== 基準 ==", None),
        ("0050 買進持有（大盤）", hold(0, 1)),
        ("正2 買進持有", hold(1)),
        ("現行 MA60x1.01 進／MA80x0.98 出", cur()),
        ("== 均線上持有（週五判斷）==", None),
        ("季線 MA60 上持有", ma_cross(60)),
        ("半年線 MA120 上持有", ma_cross(120)),
        ("年線 MA240 上持有", ma_cross(240)),
        ("月線 MA20 上持有", ma_cross(20)),
        ("季線 MA60 每天判斷", ma_cross(60, weekly=False)),
        ("MA3／MA10 交叉（每天）", ma_xx(3, 10)),
        ("MA20／MA60 交叉（每天）", ma_xx(20, 60)),
        ("== 正2＋現金 固定比例 ==", None),
    ]
    for w2 in (0.3, 0.4, 0.5, 0.6, 0.7):
        rows.append((f"正2 {int(w2 * 100)}%＋現金 每月再平衡", rebal(w2)))
    rows.append(("正2 50%＋現金 每季再平衡", rebal(0.5, mode="quarter")))
    rows.append(("正2 50%＋現金 每年再平衡", rebal(0.5, mode="year")))
    for b in (0.05, 0.10, 0.15):
        rows.append((f"正2 50%＋現金 偏離 {int(b * 100)}% 再平衡", rebal(0.5, mode="band", band=b)))
    rows.append(("== 正2＋0050 混搭（每月再平衡）==", None))
    for w2 in (0.3, 0.5):
        rows.append((f"正2 {int(w2 * 100)}%＋0050 {100 - int(w2 * 100)}%", rebal(w2, 1 - w2)))
    rows.append(("== 跌深加碼（平時半倉正2）==", None))
    for dd in (0.15, 0.20, 0.25, 0.30):
        for back in (0.0, 0.05):
            rows.append((f"跌 {int(dd * 100)}% 全押、回到高點-{int(back * 100)}% 內回半倉", dip_buy(0.5, dd, back)))
    rows.append(("== 年線乖離 ==", None))
    for lo in (-0.05, -0.10, -0.15):
        for hi in (0.15, 0.25):
            rows.append((f"乖離 < {int(lo * 100)}% 全押、> +{int(hi * 100)}% 出場", bias240(lo, hi)))
    rows += [
        ("== 現行的變形（網路常見：出場不空手）==", None),
        ("現行，出場改持 0050", cur(off=(0.0, 1.0))),
        ("現行，出場改持 50% 0050", cur(off=(0.0, 0.5))),
        ("現行，出場改持 30% 正2", cur(off=(0.3, 0.0))),
        ("現行，進場只押 50% 正2＋50% 0050", cur(on=(0.5, 0.5))),
        ("季線 MA60 上正2、下 0050", ma_cross(60, off=(0.0, 1.0))),
        ("年線 MA240 上正2、下 0050", ma_cross(240, off=(0.0, 1.0))),
    ]
    for name, s in rows:
        if s is None:
            L.append("\n" + name)
            print(L[-1], flush=True)
            continue
        L.append(f"{name:30s} {fmt(s)}")
        print(L[-1], flush=True)
    open(os.path.join(HERE, "結果_研究08_網路正2策略.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
