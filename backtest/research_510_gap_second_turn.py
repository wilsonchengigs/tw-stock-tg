"""研究 510：開高等第二個底部轉折做多／開低等第二個高點轉折做空（日內）
- 開高／開低：台指期近月日盤開盤 vs 前一日日盤收盤（tx_daily_ohlc.csv，近月＝當日成交量最大月份）
- 日內路徑：加權指數 1 分 K（2010～2026，09:00～13:30）當台指期日盤近似；另用期交所近 30 日真實台指期 1 分 K 抽驗
- 轉折＝zigzag：從低點反彈 ≥ r 確認一個底部（高點同理）。第二個底部確認的那根收盤進場做多
- 出場：A 收盤 13:30；B 跌破第二個底部的低點停損、否則收盤
- 成本每筆 3 點；勝率＝扣成本後賺錢的比例
"""
import csv, gzip, glob, os, random, statistics as st
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
COST = 3.0

def tx_gaps():
    best = {}
    for r in csv.DictReader(open(os.path.join(HERE, "tx_daily_ohlc.csv"), encoding="utf-8")):
        if r["session"] != "day" or r["open"] in ("-", "") or r["close"] in ("-", ""):
            continue
        v = int(r["volume"] or 0)
        if r["date"] not in best or v > best[r["date"]][0]:
            best[r["date"]] = (v, float(r["open"]), float(r["close"]))
    ds = sorted(best)
    g = {}
    for a, b in zip(ds, ds[1:]):
        g[b] = best[b][1] / best[a][2] - 1
    return g

def load_index():
    days = defaultdict(list)
    for f in sorted(glob.glob(os.path.join(HERE, "taiex_1min", "*.csv.gz"))):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                days[r["date"]].append((r["time"], float(r["high"]), float(r["low"]), float(r["close"])))
    return days

def load_tx():
    days = defaultdict(list)
    for r in csv.DictReader(open(os.path.join(HERE, "tx_1min.csv"), encoding="utf-8")):
        if r["session"] == "day":
            days[r["trade_day"]].append((r["ts"][-5:], float(r["high"]), float(r["low"]), float(r["close"])))
    return days

def trade(bars, r, side, nth, stop):
    """side=+1 等第 nth 個底部做多；-1 等第 nth 個頭部做空。回傳 (損益點數, 進場時間) 或 None"""
    # 做空時把價格翻轉，邏輯統一成「找底部」
    s = side
    hi_ = lambda b: b[1] if s > 0 else -b[2]
    lo_ = lambda b: b[2] if s > 0 else -b[1]
    cl_ = lambda b: b[3] * s
    ext_low = None; count = 0; mode = "down"  # 一開始找底
    run_hi = None
    for i, b in enumerate(bars):
        h, l, c = hi_(b), lo_(b), cl_(b)
        if mode == "down":
            if ext_low is None or l < ext_low:
                ext_low = l
            if c >= ext_low * (1 + r) if ext_low > 0 else c >= ext_low + abs(ext_low) * r:
                count += 1
                if count == nth:
                    if i == len(bars) - 1:
                        return None
                    entry = c; stopv = ext_low
                    for b2 in bars[i + 1:]:
                        if stop and lo_(b2) <= stopv:
                            return (stopv - entry - COST, b[0])
                    return (cl_(bars[-1]) - entry - COST, b[0])
                mode = "up"; run_hi = h
        else:
            if h > run_hi:
                run_hi = h
            if c <= run_hi - abs(run_hi) * r:
                mode = "down"; ext_low = l
    return None

def summ(pnls):
    if not pnls:
        return "  0 筆"
    w = sum(p > 0 for p in pnls) / len(pnls)
    return f"{len(pnls):4d} 筆 勝率 {w*100:5.1f}% 平均 {st.mean(pnls):+7.1f} 點 中位 {st.median(pnls):+6.1f} 總和 {sum(pnls):+8.0f}"

def run(days, gaps, label, out):
    out.append(f"\n===== {label}（{min(days)}～{max(days)}，{len(days)} 天）=====")
    for gth in (0.0, 0.003, 0.005, 0.01):
        for side, name in ((1, "開高→第2底做多"), (-1, "開低→第2頭做空")):
            sel = [d for d in days if d in gaps and (gaps[d] > gth if side > 0 else gaps[d] < -gth)]
            out.append(f"\n[{name}] 跳空 {'>' if side>0 else '<'} {'+' if side>0 else '-'}{gth*100:.1f}%：{len(sel)} 天")
            for r in (0.002, 0.003, 0.005):
                for stop in (False, True):
                    res = [trade(days[d], r, side, 2, stop) for d in sel]
                    p = [x[0] for x in res if x]
                    out.append(f"  轉折 {r*100:.1f}% {'停損第2底' if stop else '收盤出  '}：{summ(p)}")
                # 對照：第 1 個轉折、同方向其他日子
                p1 = [x[0] for x in (trade(days[d], r, side, 1, False) for d in sel) if x]
                oth = [d for d in days if d in gaps and d not in sel]
                po = [x[0] for x in (trade(days[d], r, side, 2, False) for d in oth) if x]
                out.append(f"    對照 第1個轉折收盤出：{summ(p1)}")
                out.append(f"    對照 非此類日子 第2轉折收盤出：{summ(po)}")

if __name__ == "__main__":
    gaps = tx_gaps()
    out = [__doc__]
    run(load_index(), gaps, "加權指數 1 分 K 近似", out)
    tx = load_tx()
    # 抽驗：真實台指期只有近 30 天，只看 0% 門檻
    out.append(f"\n===== 真實台指期 1 分 K 抽驗（{min(tx)}～{max(tx)}，{len(tx)} 天，08:45 起）=====")
    for side, name in ((1, "開高→第2底做多"), (-1, "開低→第2頭做空")):
        sel = [d for d in tx if d in gaps and gaps[d] * side > 0]
        for r in (0.002, 0.003, 0.005):
            p = [x[0] for x in (trade(tx[d], r, side, 2, False) for d in sel) if x]
            out.append(f"[{name}] {len(sel)} 天 轉折 {r*100:.1f}% 收盤出：{summ(p)}")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究510_開高第二底.txt"), "w", encoding="utf-8").write(txt)
    print(txt)
