"""研究 137b：研究 137 的逐筆版——停利／停損只有幾點時，1 分 K 判斷不出同一分鐘先碰到哪邊（研究 137 兩種假設結果相反）

- 訊號：台指期近月 1 分 K 量 ≥ V 口、收紅做多／收黑做空（研究 137）
- 進場：訊號那分鐘結束後的第一筆成交（爆量後跳價就自然反映，例：100 爆量 → 105 才成交）
- 出場：逐筆成交價第一次碰到 進場 ± TP（停利）或 ∓ SL（停損）就以該筆價格成交；時段最後一筆強制平倉
- 成本：每筆來回 C 點（預設 2：手續費約 0.5＋期交稅約 1.5；不另加滑價，因為進出都用實際成交價）
- 資料：backtest/tx_ticks/*.csv.gz（每天排程累積）；樣本很短，只看方向
用法：python -X utf8 backtest/research_137b_夜盤爆量當沖_逐筆.py
"""
import csv
import gzip
import os
import random
from collections import defaultdict
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
TICK_DIR = os.path.join(HERE, "tx_ticks")
COST = float(os.environ.get("R137_COST", "2"))


def load():
    bars = defaultdict(list)
    for r in csv.DictReader(open(os.path.join(HERE, "tx_1min.csv"), encoding="utf-8")):
        bars[(r["trade_day"], r["session"])].append((r["ts"], float(r["open"]), float(r["close"]), float(r["volume"])))
    ticks = {}
    for fn in sorted(os.listdir(TICK_DIR)):
        day = fn[:10]
        rows = []
        for ln in gzip.open(os.path.join(TICK_DIR, fn), "rt", encoding="utf-8"):
            t, px, q = ln.strip().split(",")
            hm = int(t[8:12])
            rows.append((t, float(px), "day" if 845 <= hm <= 1345 else "night"))
        for sess in ("day", "night"):
            ticks[(day, sess)] = [(t, px) for t, px, s in rows if s == sess]
    return {k: sorted(v) for k, v in bars.items() if k in ticks}, ticks


def trades(bars, ticks, V, TP, SL, direction="follow", sig_idx=None, window=None):
    out = []
    ti = 0
    n = len(ticks)
    busy_until = ""
    for k, (ts, o, c, v) in enumerate(bars):
        ok = (v >= V) if sig_idx is None else (k in sig_idx)
        if not ok or c == o:
            continue
        if window and not (window[0] <= ts[11:16] < window[1]):
            continue
        nxt = (datetime.strptime(ts, "%Y-%m-%d %H:%M") + timedelta(minutes=1)).strftime("%Y%m%d%H%M00")
        if nxt <= busy_until:
            continue  # 一次只做一筆
        while ti < n and ticks[ti][0] < nxt:
            ti += 1
        if ti >= n:
            break
        side = 1 if c > o else -1
        if direction == "fade":
            side = -side
        entry = ticks[ti][1]
        tp, sl = entry + side * TP, entry - side * SL
        j = ti + 1
        pnl = None
        while j < n:
            px = ticks[j][1]
            if (side > 0 and px >= tp) or (side < 0 and px <= tp) or (side > 0 and px <= sl) or (side < 0 and px >= sl):
                pnl = side * (px - entry)
                break
            j += 1
        if pnl is None:
            j = n - 1
            pnl = side * (ticks[-1][1] - entry)
        busy_until = ticks[j][0]
        out.append((ts, side, pnl - COST, ticks[ti][1] - c))
    return out


def summary(tr):
    if not tr:
        return "0 筆"
    p = [x[2] for x in tr]
    w = sum(x > 0 for x in p)
    jump = sum(x[1] * x[3] for x in tr) / len(tr)
    return f"{len(p):3d} 筆、勝率 {w / len(p):4.0%}、每筆 {sum(p) / len(p):+6.1f} 點、合計 {sum(p):+7.0f} 點（進場比訊號收盤平均差 {jump:+.1f} 點）"


def run_all(B, T, sess, V, TP, SL, **kw):
    return [t for k, b in B.items() if k[1] == sess for t in trades(b, T[k], V, TP, SL, **kw)]


def main():
    B, T = load()
    days = sorted({d for d, _ in B})
    L = [f"研究 137b：爆量當沖逐筆版（{days[0]}～{days[-1]}，{len(days)} 個交易日；進場＝訊號分鐘後第一筆、出場＝第一筆碰到的成交價、成本 {COST:g} 點／筆）", ""]
    grid = ((5, 1), (10, 1), (5, 5), (10, 5), (10, 10), (20, 10), (30, 15), (50, 25), (100, 50))
    for sess, vols in (("night", (300, 400, 600)), ("day", (800, 1200, 2000))):
        L.append(f"【{'夜盤' if sess == 'night' else '日盤'}】順勢：")
        for V in vols:
            for TP, SL in grid:
                L.append(f"  量≥{V:4d} 停利 {TP:3d}／停損 {SL:2d}：{summary(run_all(B, T, sess, V, TP, SL))}")
        L.append("")
    L.append("夜盤 400 口 反向做：")
    for TP, SL in ((10, 1), (10, 10), (30, 15)):
        L.append(f"  停利 {TP}／停損 {SL}：{summary(run_all(B, T, 'night', 400, TP, SL, direction='fade'))}")
    L.append("夜盤 400 口 只看 21:00～24:00（美股開盤前後）：")
    for TP, SL in ((10, 1), (10, 10), (30, 15), (50, 25)):
        L.append(f"  停利 {TP}／停損 {SL}：{summary(run_all(B, T, 'night', 400, TP, SL, window=('21:00', '24:00')))}")
    # 隨機時點對照：每個時段抽同樣數目的 1 分 K 當訊號
    rng = random.Random(137)
    L.append("")
    for TP, SL in ((10, 1), (30, 15)):
        real = sum(x[2] for x in run_all(B, T, "night", 400, TP, SL))
        R, beat = 200, 0
        for _ in range(R):
            tot = 0
            for k, b in B.items():
                if k[1] != "night":
                    continue
                m = sum(1 for x in b if x[3] >= 400)
                idx = set(rng.sample(range(len(b)), min(m, len(b))))
                tot += sum(x[2] for x in trades(b, T[k], 0, TP, SL, sig_idx=idx))
            beat += tot >= real
        L.append(f"夜盤 400 口 停利 {TP}／停損 {SL} 合計 {real:+.0f} 點；同筆數隨機時點對照 p {(beat + 1) / (R + 1):.3f}")
    txt = "\n".join(L) + "\n"
    print(txt)
    open(os.path.join(HERE, "結果_研究137b_夜盤爆量當沖_逐筆.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
