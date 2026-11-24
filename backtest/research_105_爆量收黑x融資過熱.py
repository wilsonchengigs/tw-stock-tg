"""研究 105：爆量收黑獨立短線 × 融資過熱狀態（使用者情境：10/15 主策略因過熱出場，同一天短線叫買）
訊號：證交所成交金額 ≥ 1.5 倍前 20 日平均且收黑（同日報）
交易：台指期（進場日到出場日都有交易的月份中，進場日成交量最大者）隔天日盤開盤買，第 H 個交易日日盤收盤平倉；5% 停損（以收盤檢查，隔天開盤出）；成本 3 點
分組（訊號當天）：
- 過熱：融資÷指數 偏離 > 17.5% 或 z > 2（v3 定義）
- 過熱後 20 日內（剛因過熱出場）
- 正常且多頭（指數 ≥ MA80×0.975）／正常且空頭
對照：同組內隨機日（同年份分布）
用法：python -X utf8 backtest/research_105_爆量收黑x融資過熱.py
"""
import csv
import importlib.util
import os
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("v3", os.path.join(HERE, "strategy_v3.py"))
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)
DAYS, PX, N = V.DAYS, V.PX, V.N
IDX = {d: i for i, d in enumerate(DAYS)}

AMT = {r["date"]: float(r["amount"]) for r in csv.DictReader(open(os.path.join(HERE, "turnover_daily.csv"), encoding="utf-8"))}
TX = defaultdict(dict)  # date -> month -> (open, close, volume)
for r in csv.DictReader(open(os.path.join(HERE, "tx_daily_ohlc.csv"), encoding="utf-8")):
    if r["session"] != "day" or r["open"] in ("-", "") or r["close"] in ("-", ""):
        continue
    TX[r["date"]][r["month"]] = (float(r["open"]), float(r["close"]), float(r["volume"] or 0))


def near(d):
    m = TX.get(d)
    return max(m, key=lambda k: m[k][2]) if m else None


def trade(i, H=5, stop=0.05, cost=3.0):
    """訊號日索引 i → 報酬（以進場價計）；資料不足回 None"""
    if i + H >= N:
        return None
    d1, dH = DAYS[i + 1], DAYS[i + H]
    ok = [m for m in TX.get(d1, {}) if m in TX.get(dH, {})]  # 持有到出場日都還在交易的月份（到期就換次月）
    if not ok:
        return None
    mo = max(ok, key=lambda k: TX[d1][k][2])
    entry = TX[d1][mo][0]
    for k in range(i + 1, i + H + 1):
        q = TX.get(DAYS[k], {}).get(mo)
        if q is None:  # 合約到期：用最後一天收盤出
            return None
        if k < i + H and q[1] <= entry * (1 - stop):
            nxt = TX.get(DAYS[k + 1], {}).get(mo)
            px = nxt[0] if nxt else q[1]
            return (px - entry - cost) / entry
    return (TX[DAYS[i + H]][mo][1] - entry - cost) / entry


def signals():
    out = []
    for i in range(21, N):
        d = DAYS[i]
        if d not in AMT or any(DAYS[k] not in AMT for k in range(i - 20, i)):
            continue
        base = sum(AMT[DAYS[k]] for k in range(i - 20, i)) / 20
        if AMT[d] >= 1.5 * base and PX[i] < PX[i - 1]:
            out.append(i)
    return out


def group(i):
    if V.DEV[i] is None:
        return None
    if V.hot_at(i):
        return "過熱當天"
    if any(V.hot_at(k) for k in range(max(0, i - 20), i)):
        return "過熱後 20 日內"
    return "正常·多頭" if PX[i] >= V.M80[i] * 0.975 else "正常·空頭"


def stats(rs):
    n = len(rs)
    if not n:
        return "0 筆"
    m = sum(rs) / n
    return f"{n:3d} 筆、勝率 {sum(r > 0 for r in rs) / n:4.0%}、每筆 {m:+.2%}、最差 {min(rs):+.1%}"


def main():
    random.seed(105)
    sig = signals()
    L = [f"研究 105：爆量收黑 × 融資過熱（台指期近月真實價，隔天開盤進、5% 停損；訊號 {len(sig)} 個 {DAYS[sig[0]]}～{DAYS[sig[-1]]}）"]
    allday = [i for i in range(260, N - 11) if group(i)]
    for H in (5, 10):
        L.append(f"\n== 抱 {H} 天 ==")
        G = defaultdict(list)
        for i in sig:
            g = group(i)
            r = trade(i, H)
            if g and r is not None:
                G[g].append((DAYS[i], r))
                G["全部"].append((DAYS[i], r))
        for g in ("全部", "過熱當天", "過熱後 20 日內", "正常·多頭", "正常·空頭"):
            rs = [r for _, r in G[g]]
            pool = [i for i in allday if g == "全部" or group(i) == g]
            # 隨機對照：同組非訊號日，抽同筆數 500 次
            base = [r for r in (trade(i, H) for i in pool) if r is not None]
            p = None
            if rs and len(base) > len(rs):
                m = sum(rs) / len(rs)
                hit = sum(sum(random.sample(base, len(rs))) / len(rs) >= m for _ in range(500))
                p = hit / 500
            L.append(f"{g:12s} {stats(rs)}" + (f"｜同組隨機日每筆 {sum(base) / len(base):+.2%}、p {p:.3f}" if p is not None else ""))
            if g in ("過熱當天", "過熱後 20 日內") and H == 5:
                L.append("    " + "、".join(f"{d} {r:+.1%}" for d, r in G[g]))
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究105_爆量收黑x融資過熱.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
