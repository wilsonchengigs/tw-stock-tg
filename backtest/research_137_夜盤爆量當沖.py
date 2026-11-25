"""研究 137：馬克羊「夜盤當沖」——1 分 K 爆量（≥ 400 口）順著那根 K 的方向進場，固定點數停利／停損

規則來源：使用者轉述＋影片「【實戰覆盤】夜盤當沖交易手法公開」（Whisper 轉錄，research/videos/）
- 訊號：台指期近月 1 分 K 成交量 ≥ V 口（夜盤 400 口約是第 99 百分位，集中在 22:00～23:00 美股開盤前後）
- 方向：那根 K 收紅做多、收黑做空（平盤略過）
- 進場：下一根 1 分 K 開盤價（爆量後常直接跳價，例：100 爆量 → 105 才買到）
- 出場：進場價 ± TP 停利、∓ SL 停損；同一根 K 同時碰到時照 K 線路徑判斷（R137_PATH=0 改成一律先停損）；收盤前最後一根強制平倉
- 一次只有一筆部位；成本：每筆來回 C 點（手續費＋期交稅＋滑價，預設 2 點）
- 資料：backtest/tx_1min.csv（期交所近 30 個交易日逐筆，每天排程累積）；樣本很短，只能看方向，不能下結論
用法：python -X utf8 backtest/research_137_夜盤爆量當沖.py
"""
import csv
import os
import random
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.environ.get("R137_PATH", "1") == "1"  # 1＝照 K 線路徑判斷同根先後；0＝一律先停損（最保守）


def load():
    by = defaultdict(list)
    for r in csv.DictReader(open(os.path.join(HERE, "tx_1min.csv"), encoding="utf-8")):
        by[(r["trade_day"], r["session"])].append((r["ts"], float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), float(r["volume"])))
    for k in by:
        by[k].sort()
    return by


def trades(bars, V, TP, SL, cost, direction="follow", start_hm=None, end_hm=None, sig_override=None):
    """一個時段（日盤或夜盤）的所有交易，回傳 [(訊號時間, 方向, 損益點數)]"""
    out = []
    k = 0
    n = len(bars)
    while k < n - 1:
        ts, o, h, l, c, v = bars[k]
        hm = ts[11:16]
        ok = (v >= V and c != o) if sig_override is None else (k in sig_override and c != o)
        if start_hm and end_hm:
            inwin = (start_hm <= hm < end_hm) if start_hm < end_hm else (hm >= start_hm or hm < end_hm)
            ok = ok and inwin
        if not ok:
            k += 1
            continue
        side = 1 if c > o else -1
        if direction == "fade":
            side = -side
        entry = bars[k + 1][1]
        tp, sl = entry + side * TP, entry - side * SL
        pnl = None
        j = k + 1
        while j < n:
            _t, _o, hh, ll, cc, _v = bars[j]
            hit_sl = (ll <= sl) if side > 0 else (hh >= sl)
            hit_tp = (hh >= tp) if side > 0 else (ll <= tp)
            if hit_sl and hit_tp and PATH:
                # 同一根同時碰到：照 K 線路徑（紅 K 開→低→高→收、黑 K 開→高→低→收）判斷先碰哪個
                low_first = cc >= _o
                sl_first = low_first if side > 0 else not low_first
                if (side > 0 and _o <= sl) or (side < 0 and _o >= sl):
                    sl_first = True
                elif (side > 0 and _o >= tp) or (side < 0 and _o <= tp):
                    sl_first = False
                hit_sl, hit_tp = sl_first, not sl_first
            if hit_sl:  # 開盤就跳過停損時用開盤價
                px = min(_o, sl) if side > 0 else max(_o, sl)
                pnl = side * (px - entry)
                break
            if hit_tp:
                px = max(_o, tp) if side > 0 else min(_o, tp)
                pnl = side * (px - entry)
                break
            j += 1
        if pnl is None:
            j = n - 1
            pnl = side * (bars[-1][4] - entry)
        out.append((ts, side, pnl - cost))
        k = j + 1
    return out


def summary(tr):
    if not tr:
        return "0 筆"
    p = [x[2] for x in tr]
    w = sum(x > 0 for x in p)
    return f"{len(p):3d} 筆、勝率 {w / len(p):4.0%}、每筆 {sum(p) / len(p):+6.1f} 點、合計 {sum(p):+7.0f} 點"


def main():
    by = load()
    days = sorted({d for d, _ in by})
    L = [f"研究 137：夜盤爆量當沖（{days[0]}～{days[-1]}，{len(days)} 個交易日；下一根開盤進場、同根先後：{'K 線路徑' if PATH else '一律先停損'}、成本 2 點／筆）", ""]
    for sess in ("night", "day"):
        L.append(f"【{'夜盤' if sess == 'night' else '日盤'}】順勢，量門檻 × 停利／停損（點）：")
        for V in ((300, 400, 600) if sess == "night" else (800, 1200, 2000)):
            for TP, SL in ((5, 1), (10, 1), (10, 5), (10, 10), (20, 10), (30, 15), (50, 25)):
                tr = [t for (d, s), b in by.items() if s == sess for t in trades(b, V, TP, SL, 2.0)]
                L.append(f"  量≥{V:4d} 停利 {TP:2d}／停損 {SL:2d}：{summary(tr)}")
        L.append("")
    # 反向對照與隨機對照（夜盤 400 口、停利 10／停損 10）
    tr = [t for (d, s), b in by.items() if s == "night" for t in trades(b, 400, 10, 10, 2.0, "fade")]
    L.append(f"夜盤 400 口 反向做 停利 10／停損 10：{summary(tr)}")
    rng = random.Random(137)
    real = [t for (d, s), b in by.items() if s == "night" for t in trades(b, 400, 10, 10, 2.0)]
    rp = sum(x[2] for x in real)
    beat = 0
    R = 300
    for _ in range(R):
        tot = 0
        for (d, s), b in by.items():
            if s != "night":
                continue
            m = sum(1 for x in b if x[5] >= 400)
            idx = set(rng.sample(range(len(b) - 1), min(m, len(b) - 1)))
            tot += sum(x[2] for x in trades(b, 0, 10, 10, 2.0, sig_override=idx))
        beat += tot >= rp
    L.append(f"夜盤 400 口 順勢 停利 10／停損 10 合計 {rp:+.0f} 點；同筆數隨機時點對照 p {(beat + 1) / (R + 1):.3f}")
    txt = "\n".join(L) + "\n"
    print(txt)
    open(os.path.join(HERE, f"結果_研究137_夜盤爆量當沖{'' if PATH else '_保守'}.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
