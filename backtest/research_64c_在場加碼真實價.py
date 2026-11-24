"""研究 64c：研究 64b（在場時爆量收黑加碼台指期）的真實價格驗證

- 現行部位：00631L 真實還原價（Yahoo 00631L.TW），狀態用研究 64 的 state_series（週五判斷，下一交易日收盤成交，換手成本 0.25%）
- 加碼部位：台指期真實價（tx_daily_ohlc.csv 近月），訊號日當晚夜盤開盤進（2017-05 前沒有夜盤 → 隔天日盤開盤），
  第 H 個交易日日盤收盤出；現行出場則在出場日收盤一起平；成本 3 點；名目 = 資金 × a
- 期間：2015-10～2026-11（00631L 早期 Yahoo 資料有錯價）
用法：python -X utf8 backtest/research_64c_在場加碼真實價.py
"""
import importlib.util
import json
import os
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r64", os.path.join(HERE, "research_64_爆量收黑加碼現行策略.py"))
r64 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r64)
spec = importlib.util.spec_from_file_location("r63d", os.path.join(HERE, "research_63d_爆量收黑_台指期真實價.py"))
r63d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r63d)
DAYS, PX, VR, N = r64.DAYS, r64.PX, r64.VR, r64.N
COST_ETF, COST_FUT = 0.0025, 3.0


def etf():
    r = json.load(open(os.path.join(HERE, "00631L.TW.json")))
    a = r["indicators"]["adjclose"][0]["adjclose"]
    return {datetime.fromtimestamp(t, timezone(timedelta(hours=8))).strftime("%Y-%m-%d"): v for t, v in zip(r["timestamp"], a) if v}


def main():
    E = etf()
    fdates, fday, fnight, near = r63d.load()
    fidx = {d: i for i, d in enumerate(fdates)}
    st = r64.state_series()
    days = [i for i in range(N) if DAYS[i] in E and DAYS[i] in fidx and DAYS[i] >= "2015-10-01"]  # 00631L 早期 Yahoo 錯價（2015-01、2015-08），與專案慣例一致從 2015-10 起
    L = ["研究 64c：在場時爆量收黑加碼——真實價格（00631L＋台指期近月）"]
    for k, add, H in ((None, 0, 0), (1.5, 0.5, 5), (1.5, 1.0, 5), (1.5, 0.5, 10), (1.5, 1.0, 10), (1.3, 1.0, 10)):
        eq = peak = 1.0
        mdd = 0.0
        pos = False          # 00631L 持有
        fut = None           # (進場價, 契約月, 出場 index)
        n_add, wins = 0, 0
        prev_i = None
        for i in days:
            d = DAYS[i]
            if prev_i is not None:
                r = 0.0
                if pos:
                    r += E[d] / E[DAYS[prev_i]] - 1
                if fut is not None:
                    m = fut[1]
                    b = fday[d].get(m)
                    if b is None:  # 原契約已到期 → 改用新近月，以其前一日收盤接續
                        m = near[d]
                        b = fday[d].get(m)
                    pb = fday[DAYS[prev_i]].get(m) if fut[3] != "entry" else None
                    if b:
                        base_px = fut[0] if fut[3] == "entry" else (pb[3] if pb else b[3])
                        r += add * (b[3] / base_px - 1)
                        fut = (fut[0], m, fut[2], "hold", fut[4])
                eq *= 1 + r
            # 現行狀態：st[i] 是「週五判斷後」的狀態，下一交易日收盤成交 → 今天的持有＝st[i-1]
            want = st[i - 1] if i > 0 else False
            if want != pos:
                eq *= 1 - COST_ETF * 2
                pos = want
            # 加碼平倉
            if fut is not None and (i >= fut[2] or not pos):
                ret_total = None
                eq *= 1 - add * COST_FUT / fday[d].get(fut[1], (0, 0, 0, 40000))[3]
                n_add += 1
                wins += 1 if (fday[d].get(fut[1], (0, 0, 0, fut[0]))[3] > fut[4]) else 0
                fut = None
            # 加碼訊號：今天收盤確定 → 今晚夜盤（記在下一交易日的 night）開盤進；沒有夜盤就隔天日盤開盤
            if k is not None and fut is None and pos and st[i] and VR[i] is not None and VR[i] >= k and PX[i] < PX[i - 1]:
                j = fidx.get(d)
                if j is not None and j + 1 < len(fdates):
                    d1 = fdates[j + 1]
                    m = near[d1]
                    nb = fnight[d1].get(m)
                    entry = nb[0] if nb else fday[d1][m][0]
                    # 用「訊號日收盤 → 今晚進場價」修正：明天的報酬從進場價起算
                    fut = (entry, m, i + H, "entry", entry)
            peak = max(peak, eq)
            mdd = min(mdd, eq / peak - 1)
            prev_i = i
        yrs = (len(days) - 1) / 245
        nm = "現行（00631L 真實）" if k is None else f"k{k} 加{add}x 抱{H}天"
        L.append(f"  {nm:20s} 年化 {eq ** (1 / yrs) - 1:6.1%}  最大回檔 {mdd:6.1%}" + (f"  加碼 {n_add} 次、勝 {wins}" if k else ""))
    L.append(f"\n期間：{DAYS[days[0]]}～{DAYS[days[-1]]}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究64c_在場加碼真實價.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
