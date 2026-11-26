"""研究 198：資料品質稽核（研究 192 發現 00631L 缺價日重複計算、Yahoo 價格停滯、11/24 台指期日盤怪 K 棒）

檢查日報（data/）與回測（backtest/）用的資料：
1. 加權：Yahoo TWII vs 證交所官方（data/taiex_daily.csv、data/margin_ratio.csv 的 taiex 欄）——差 >0.1% 或缺日
2. 00631L／0050（Yahoo）：缺日、停滯（連 ≥3 天同價但加權有動）、日報酬與 2x／1x 加權差 >3%／>1.5%（已知分割日另列）
3. 台指期日盤近月（成交量最大）：價差 |收盤/加權−1| >2.5%、日報酬與加權差 >2.5%、成交量 < 20 日中位 30%、交易日缺日盤
4. 融資（backtest/margin_tw.csv、data/margin_ratio.csv）：缺日、單日變化 >±8%、兩檔不一致
5. 成交金額（turnover_daily.csv）：0、或 >3 倍／<0.3 倍 20 日中位
6. 外資台指期未平倉（tx_inst_oi.csv）：交易日缺外資列
每項列總數與 2025 年起的明細（實盤相關）
用法：python -X utf8 backtest/research_198_資料品質稽核.py
"""
import csv
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import data  # noqa: E402

TW, E50, E631 = data.series()
TODAY = __import__("datetime").datetime.now(data.TW).strftime("%Y-%m-%d")
DAYS = sorted(d for d in TW if d < TODAY)  # Yahoo 盤中就有今天的資料，期貨日盤要收盤後才有：今天不檢查
PX = {d: TW[d][0] for d in DAYS}
R = {DAYS[i]: PX[DAYS[i]] / PX[DAYS[i - 1]] - 1 for i in range(1, len(DAYS))}
PREV = {DAYS[i]: DAYS[i - 1] for i in range(1, len(DAYS))}
RECENT = "2025-01-01"


def ymd(s):
    return f"{s[:4]}-{s[4:6]}-{s[6:]}" if len(s) == 8 and "-" not in s else s


def rd(path):
    return list(csv.DictReader(open(path, encoding="utf-8")))


SECTIONS = []  # (標題, 明細)；給每月健康檢查（health_main.py）讀


def section(L, title, items, recent_only_detail=True, cap=25):
    SECTIONS.append((title, items))
    rec = [x for x in items if x[0] >= RECENT]
    L.append(f"\n【{title}】共 {len(items)} 筆（2025 起 {len(rec)} 筆）")
    for x in (rec if recent_only_detail else items)[-cap:]:
        L.append("  " + "  ".join(str(v) for v in x))


def main():
    L = ["研究 198：資料品質稽核（Yahoo TWII 交易日為基準）", f"TWII {DAYS[0]}～{DAYS[-1]}，{len(DAYS)} 天"]

    # 1 加權 Yahoo vs 官方
    off = {ymd(r["date"]): float(r["close"]) for r in rd(os.path.join(ROOT, "data", "taiex_daily.csv"))}
    for r in rd(os.path.join(ROOT, "data", "margin_ratio.csv")):
        off.setdefault(ymd(r["date"]), float(r["taiex"]))
    bad = [(d, f"Yahoo {PX[d]:,.2f}", f"官方 {off[d]:,.2f}", f"{PX[d] / off[d] - 1:+.2%}") for d in sorted(off) if d in PX and abs(PX[d] / off[d] - 1) > 0.001]
    miss_y = [(d, "官方有、Yahoo 沒有") for d in sorted(off) if d not in PX and d >= DAYS[0]]
    miss_o = [(d, "Yahoo 有、官方沒有") for d in DAYS if d >= min(off) and d not in off]
    section(L, "1a 加權 Yahoo vs 官方 差 >0.1%", bad)
    section(L, "1b 加權缺日（官方有 Yahoo 無）", miss_y)
    section(L, "1c 加權缺日（Yahoo 有、官方 csv 無；官方檔從 " + min(off) + "）", miss_o)

    # 2 ETF
    for name, E, k, tol in (("00631L", E631, 2, 0.03), ("0050", E50, 1, 0.015)):
        ds = [d for d in DAYS if d >= min(E)]
        miss = [(d, "缺") for d in ds if d not in E]
        stale, run = [], 0
        jump = []
        for i in range(1, len(ds)):
            a, b = ds[i - 1], ds[i]
            if a in E and b in E:
                if E[b][0] == E[a][0] and abs(R[b]) > 0.005:
                    run += 1
                    if run >= 2:
                        stale.append((b, f"{name} 連續同價 {E[b][0]}", f"加權 {R[b]:+.2%}"))
                else:
                    run = 0
                er = E[b][1] / E[a][1] - 1
                if abs(er - k * R[b]) > tol:
                    jump.append((b, f"{name} {er:+.2%}", f"{k}x加權 {k * R[b]:+.2%}", f"差 {er - k * R[b]:+.2%}"))
        section(L, f"2a {name} 缺日", miss)
        section(L, f"2b {name} 停滯（加權動 >0.5% 但價格不變，連 ≥3 天）", stale)
        section(L, f"2c {name} 日報酬與 {k}x 加權差 >{tol:.1%}（可能是分割、除息、錯價或日期錯位）", jump)

    # 3 台指期日盤近月
    by = defaultdict(dict)
    for r in rd(os.path.join(HERE, "tx_daily_ohlc.csv")):
        if r["session"] != "day":
            continue
        try:
            c, v = float(r["close"]), float(r["volume"] or 0)
        except ValueError:
            continue
        if c > 0:
            by[r["date"]][r["month"]] = (c, v)
    fd = sorted(d for d in by if d in PX)
    near = {d: max(by[d].items(), key=lambda kv: kv[1][1]) for d in fd}
    basis, fj, lowv = [], [], []
    vols = []
    for i, d in enumerate(fd):
        m, (c, v) = near[d]
        vols.append(v)
        if abs(c / PX[d] - 1) > 0.025:
            basis.append((d, f"近月 {m} {c:,.0f}", f"加權 {PX[d]:,.0f}", f"{c / PX[d] - 1:+.2%}"))
        if i and fd[i - 1] == PREV.get(d) and m in by[fd[i - 1]]:
            fr = c / by[fd[i - 1]][m][0] - 1
            if abs(fr - R[d]) > 0.025:
                fj.append((d, f"期貨 {fr:+.2%}", f"加權 {R[d]:+.2%}"))
        if i >= 20:
            med = statistics.median(vols[-21:-1])
            if v < 0.3 * med:
                lowv.append((d, f"近月量 {v:,.0f}", f"20 日中位 {med:,.0f}"))
    nod = [(d, "交易日沒有台指期日盤") for d in DAYS if d >= fd[0] and d not in by]
    section(L, "3a 台指期近月 價差 >2.5%", basis)
    section(L, "3b 台指期近月 日報酬與加權差 >2.5%", fj)
    section(L, "3c 台指期近月 成交量 < 20 日中位 30%", lowv)
    section(L, "3d 交易日缺台指期日盤", nod)

    # 4 融資
    mb = {r["date"]: float(r["balance"]) for r in rd(os.path.join(HERE, "margin_tw.csv"))}
    md = sorted(mb)
    mj = [(md[i], f"{mb[md[i]] / mb[md[i - 1]] - 1:+.1%}") for i in range(1, len(md)) if abs(mb[md[i]] / mb[md[i - 1]] - 1) > 0.08]
    mm = [(d, "缺融資") for d in DAYS if d >= md[0] and d <= md[-1] and d not in mb]
    mr = {ymd(r["date"]): float(r["amount"]) for r in rd(os.path.join(ROOT, "data", "margin_ratio.csv"))}
    mx = [(d, f"backtest {mb[d]:,.0f}", f"data {mr[d]:,.0f}") for d in sorted(mr) if d in mb and abs(mb[d] / mr[d] - 1) > 0.002]
    section(L, "4a 融資單日變化 >±8%", mj)
    section(L, "4b 交易日缺融資（backtest/margin_tw.csv）", mm)
    section(L, "4c 融資兩檔不一致 >0.2%（backtest vs data/margin_ratio）", mx)

    # 5 成交金額
    tv = [(r["date"], float(r["amount"])) for r in rd(os.path.join(HERE, "turnover_daily.csv"))]
    tj = []
    for i in range(20, len(tv)):
        med = statistics.median(v for _, v in tv[i - 20:i])
        d, v = tv[i]
        if v <= 0 or v > 3 * med or v < 0.3 * med:
            tj.append((d, f"{v / 1e8:,.0f} 億", f"20 日中位 {med / 1e8:,.0f} 億"))
    tvd = {d for d, _ in tv}
    tm = [(d, "缺成交金額") for d in DAYS if tv[0][0] <= d <= tv[-1][0] and d not in tvd]
    section(L, "5a 成交金額 0 或 >3 倍／<0.3 倍 20 日中位", tj)
    section(L, "5b 交易日缺成交金額", tm)

    # 6 外資台指期未平倉
    oi = {r["date"] for r in rd(os.path.join(HERE, "tx_inst_oi.csv")) if r["investor"] == "外資"}
    om = [(d, "缺外資台指期未平倉") for d in DAYS if min(oi) <= d <= max(oi) and d not in oi]
    section(L, "6 交易日缺外資台指期未平倉", om)

    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究198_資料品質稽核.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()


def impact():
    """把 00631L／0050 可疑日（停滯、與 k 倍加權差超過門檻）的報酬換成模型值，看 v3 真實價格結果差多少"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("v3", os.path.join(HERE, "strategy_v3.py"))
    V3 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(V3)
    bt = V3.bt
    base = V3.run(*V3.REAL, real=True)
    r2, r1 = list(V3.R2R), list(V3.R1R)
    n2 = n1 = 0
    for i in range(1, len(bt.DAYS)):
        ri = bt.PX[i] / bt.PX[i - 1] - 1
        if bt.DAYS[i] >= "2015-09-01" and (abs(r2[i] - 2 * ri) > 0.03 or (r2[i] == 0 and abs(ri) > 0.005)):
            r2[i] = bt.R2[i]
            n2 += 1
        if bt.DAYS[i] >= "2015-09-01" and (abs(r1[i] - ri) > 0.015 or (r1[i] == 0 and abs(ri) > 0.005)):
            r1[i] = bt.R1[i]
            n1 += 1
    V3.R2R[:], V3.R1R[:] = r2, r1
    fixed = V3.run(*V3.REAL, real=True)
    return [f"\n【影響】可疑日換成模型值（00631L {n2} 天、0050 {n1} 天）後 v3 真實價：{base[0]:.1%}/{base[1]:.1%} → {fixed[0]:.1%}/{fixed[1]:.1%}"
            "（注意：「與 2x 差 >3%」也含真實的追蹤差與漲跌停，換成模型會抹掉一部分真實差異，只當上限估計）"]


if __name__ == "__main__":
    add = impact()
    print("\n".join(add))
    open(os.path.join(HERE, "結果_研究198_資料品質稽核.txt"), "a", encoding="utf-8").write("\n".join(add) + "\n")
