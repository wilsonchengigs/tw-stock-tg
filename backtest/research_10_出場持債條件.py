"""研究 10：出場時「有條件」持美國公債：債券自身趨勢向上、或近一年股債負相關才持債，否則現金

背景：研究 02b 出場一律持中債全期較好（20.5%／-41.7%），但 2013 後與真實價格較差（2022 股債雙殺、2025 台幣升值）。
做法來源：
- 股債相關性會隨通膨 regime 翻轉（2000～2020 負相關、2022 後轉正）：AQR "Stock-Bond Correlation"
  https://www.aqr.com/Insights/Research/Alternative-Thinking/A-Changing-Stock-Bond-Correlation
- 債券自身趨勢濾網（Faber 10 個月線用在債券上；Antonacci GEM 的債券腿）
資料：VFITX（中債，1991～）、VUSTX（長債）、真實價格 IEF；美元兌台幣用 Yahoo TWD=X 清洗版（2004-03～，之前不計匯率）
變形：出場防守資產每週五依「前一天」資料決定是否持債；切換防守資產收 0.25%
用法：python -X utf8 backtest/research_10_出場持債條件.py
"""
import importlib.util
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bt  # noqa: E402
import data  # noqa: E402

spec = importlib.util.spec_from_file_location("r02b", os.path.join(HERE, "research_02b_出場持債.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

N, WE = len(bt.DAYS), bt.WEEK_END
PER = R.PER


def index_from(rets):
    out, v = [], 1.0
    for r in rets:
        v *= 1 + r
        out.append(v)
    return out


def sma(x, n):
    out, s = [None] * len(x), 0.0
    for i, p in enumerate(x):
        s += p
        if i >= n:
            s -= x[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def corr_series(a, b, n):
    out = [None] * len(a)
    for i in range(n, len(a)):
        if not WE[i]:
            continue
        xa, xb = a[i - n + 1:i + 1], b[i - n + 1:i + 1]
        ma, mb = sum(xa) / n, sum(xb) / n
        cov = sum((p - ma) * (q - mb) for p, q in zip(xa, xb))
        va = sum((p - ma) ** 2 for p in xa)
        vb = sum((q - mb) ** 2 for q in xb)
        out[i] = cov / math.sqrt(va * vb) if va and vb else 0.0
    return out


def gated(bond, gate):
    """gate[i]＝週五決定、下一天起生效；回傳每日防守報酬（含切換成本）"""
    out, cur, pend = [bt.RC], False, None
    for i in range(1, N):
        if pend is not None and pend != cur:
            cur = pend
            sw = bt.COST
        else:
            sw = 0.0
        pend = None
        out.append((bond[i] if cur else bt.RC) - sw)
        if WE[i] and gate[i] is not None:
            pend = gate[i]
    return out


def trend_gate(bond, n):
    idx = index_from(bond)
    m = sma(idx, n)
    return [None if m[i] is None else idx[i] > m[i] for i in range(N)]


def corr_gate(bond, n, th=0.0):
    c = corr_series(bt.R1, bond, n)
    return [None if c[i] is None else c[i] < th for i in range(N)]


def both_gate(g1, g2):
    return [None if (a is None or b is None) else (a and b) for a, b in zip(g1, g2)]


def cell(d_ret, r2=None, real=False):
    if real:
        c, m, _ = R.run("2015-09-01", "2026-12-31", 60, 80, d_ret=d_ret, r2=r2)
        return f"真實 {c:5.1%}/{m:6.1%}"
    return " | ".join(f"{p} {c:5.1%}/{d:6.1%}" for p, (a, b) in PER.items() for c, d, _ in [R.run(a, b, 60, 80, d_ret=d_ret)])


def main():
    it, lt = R.A["it"], R.A["lt"]
    ief = R.rets("IEF")
    _, _, l2 = data.series()
    px = [l2.get(d, (None, None))[1] for d in bt.DAYS]
    r2r, lp = [0.0], None
    for i in range(1, N):
        r2r.append(px[i] / lp - 1 if (px[i] and lp) else bt.R2[i])
        if px[i]:
            lp = px[i]
    L = ["研究 10：出場防守資產有條件持債（格式：全期 | 前段 | 後段 年化/回檔；真實＝2015-09 後 00631L＋IEF 台幣）"]

    def add(name, d, d_real):
        L.append(f"{name:30s} {cell(d)} | {cell(d_real, r2r, True)}")
        print(L[-1], flush=True)

    L.append("\n== 基準 ==")
    add("現金", R.A["cash"], R.A["cash"])
    add("一律中債", it, ief)
    add("一律長債", lt, R.rets("TLT"))
    L.append("\n== 債券自身趨勢（債券台幣淨值 > n 日均線才持）==")
    for n in (40, 60, 100, 150, 200, 250):
        add(f"中債 趨勢 MA{n}", gated(it, trend_gate(it, n)), gated(ief, trend_gate(ief, n)))
    for n in (100, 200):
        add(f"長債 趨勢 MA{n}", gated(lt, trend_gate(lt, n)), gated(R.rets("TLT"), trend_gate(R.rets("TLT"), n)))
    L.append("\n== 股債相關性（近 n 日 台股日報酬 vs 債券台幣日報酬 相關係數 < 門檻才持）==")
    for n in (120, 250, 500):
        for th in (0.0, -0.1):
            add(f"中債 相關 {n}日 <{th}", gated(it, corr_gate(it, n, th)), gated(ief, corr_gate(ief, n, th)))
    L.append("\n== 兩者都成立 ==")
    for n in (100, 200):
        add(f"中債 趨勢 MA{n} 且 相關 250日<0", gated(it, both_gate(trend_gate(it, n), corr_gate(it, 250))),
            gated(ief, both_gate(trend_gate(ief, n), corr_gate(ief, 250))))
    open(os.path.join(HERE, "結果_研究10_出場持債條件.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
