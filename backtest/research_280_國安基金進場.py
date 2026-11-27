"""研究 280：國安基金宣布進場（護盤）後的加權走勢

事件日（第一個「市場已知道要護盤」的交易日；以首次進場日為準，2026 第 10 次為 11/6 收盤後授權 → 11/9）：
  2000-03-16、2000-10-03、2004-05-20、2008-09-19、2011-12-20、2015-08-25、2020-03-19、2022-07-13、2025-04-09、2026-11-09
  來源：三立新聞 1884772（歷次進場區間）、旺得富 20230414900203（2022/7/13 起）、今周刊／中央社（2025/4/8 決議、4/9 進場；
  2026/11/6 第 131 次臨時委員會授權）
做法：
(1) 事件前一日收盤（E-1）→ E 後 1／5／20／60／120／250 個交易日加權報酬；事件前 20 日跌幅、離 250 日高點
(2) 基準：所有「離 250 日高點跌幅與事件日相差 ±3 個百分點」的交易日，同樣天期報酬的平均與中位（排除事件前後 60 日）
    → 事件超額＝事件報酬 − 同跌深基準平均；只有 9 次有完整 60 日以上，視為描述性（不做多重檢定）
(3) 主策略位置：事件日 PX 相對 MA60×1.01（進場線）、MA80×0.975（出場線）
用法：python -X utf8 backtest/research_280_國安基金進場.py
"""
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strategy_v3 as s  # noqa: E402

DAYS, PX, N = s.DAYS, s.PX, s.N
EVENTS = ["2000-03-16", "2000-10-03", "2004-05-20", "2008-09-19", "2011-12-20",
          "2015-08-25", "2020-03-19", "2022-07-13", "2025-04-09", "2026-11-09"]
HS = [1, 5, 20, 60, 120, 250]


def idx(d):
    return next(i for i, x in enumerate(DAYS) if x >= d)


def dd250(i):
    lo = max(0, i - 249)
    return PX[i] / max(PX[lo:i + 1]) - 1


def fwd(i0, h):
    """E-1 收盤 → E+h-1 收盤（h=1 即事件當天）"""
    j = i0 - 1 + h
    return PX[j] / PX[i0 - 1] - 1 if j < N else None


def main():
    ev_idx = [idx(d) for d in EVENTS]
    dd = [dd250(i) if i >= 1 else None for i in range(N)]
    excl = set()
    for i in ev_idx:
        excl.update(range(i - 60, i + 61))
    out = []
    p = out.append
    p("研究 280：國安基金宣布進場後的加權走勢（E-1 收盤起算）\n")
    p("事件日      前20日   離250高  PX/進場線 PX/出場線 | " + "  ".join(f"{h:>4}日" for h in HS))
    rows = {h: [] for h in HS}
    exc = {h: [] for h in HS}
    for d, i in zip(EVENTS, ev_idx):
        pre20 = PX[i - 1] / PX[i - 21] - 1
        line_in = PX[i - 1] / (s.M60[i - 1] * 1.01)
        line_out = PX[i - 1] / (s.M80[i - 1] * 0.975)
        cells = []
        for h in HS:
            r = fwd(i, h)
            if r is None:
                cells.append("   —  ")
                continue
            rows[h].append(r)
            # 同跌深基準
            base = [fwd(k, h) for k in range(260, N) if k not in excl and dd[k - 1] is not None
                    and abs(dd[k - 1] - dd[i - 1]) <= 0.03 and fwd(k, h) is not None]
            b = statistics.mean(base) if base else 0.0
            exc[h].append(r - b)
            cells.append(f"{r * 100:+6.1f}%")
        p(f"{d}  {pre20 * 100:+6.1f}%  {dd[i - 1] * 100:+6.1f}%   {line_in:6.3f}   {line_out:6.3f}  | " + " ".join(cells))
    p("")
    p("天期  筆數  平均     中位     勝率   同跌深基準超額(平均)  超額>0")
    for h in HS:
        r, e = rows[h], exc[h]
        if not r:
            continue
        p(f"{h:>4}日 {len(r):>3}  {statistics.mean(r) * 100:+6.2f}%  {statistics.median(r) * 100:+6.2f}%  "
          f"{sum(x > 0 for x in r) / len(r) * 100:5.0f}%   {statistics.mean(e) * 100:+6.2f}%              {sum(x > 0 for x in e)}/{len(e)}")
    # 事件前後的低點：事件後 60 日內最低點相對 E-1
    p("\n事件後 60 日內最低收盤（相對 E-1）與落在第幾天；E-1 是否為 ±60 日內最低")
    for d, i in zip(EVENTS, ev_idx):
        seg = PX[i:min(N, i + 60)]
        k = min(range(len(seg)), key=lambda t: seg[t])
        win = PX[max(0, i - 61):min(N, i + 60)]
        p(f"{d}  最低 {seg[k] / PX[i - 1] * 100 - 100:+6.1f}%（第 {k + 1} 天）  E-1 是 ±60 日最低：{'是' if PX[i - 1] == min(win) else '否'}")
    # (4) 安慰劑：每個事件從「同跌深（±3pp）、非事件」日抽 1 天，10 天平均 5 日報酬 ≥ 實際的比例
    import random
    rnd = random.Random(280)
    pools = []
    for i in ev_idx:
        pools.append([k for k in range(260, N - 5) if k not in excl and dd[k - 1] is not None
                      and abs(dd[k - 1] - dd[i - 1]) <= 0.03])
    obs = statistics.mean(rows[5])
    hit = 0
    T = 5000
    for _ in range(T):
        m = statistics.mean(fwd(rnd.choice(pl), 5) for pl in pools)
        hit += m >= obs
    p(f"\n安慰劑（同跌深日隨機抽 10 天 × {T} 次）：5 日平均 ≥ {obs * 100:+.2f}% 的比例 p = {hit / T:.4f}"
      f"（各事件基準池 {min(len(x) for x in pools)}～{max(len(x) for x in pools)} 天）")
    # (4b) 基準改成「前 20 日跌幅 ±3pp」（急跌後本來就容易反彈）
    pre = [PX[k - 1] / PX[k - 21] - 1 if k >= 21 else None for k in range(N)]
    pools2 = [[k for k in range(260, N - 5) if k not in excl and pre[k] is not None
               and abs(pre[k] - pre[i]) <= 0.03] for i in ev_idx]
    base2 = [statistics.mean(fwd(k, 5) for k in pl) for pl in pools2]
    hit = 0
    for _ in range(T):
        hit += statistics.mean(fwd(rnd.choice(pl), 5) for pl in pools2) >= obs
    p(f"安慰劑（前 20 日跌幅相同 ±3pp 的日子）：基準 5 日平均 {statistics.mean(base2) * 100:+.2f}%、"
      f"事件超額 {(obs - statistics.mean(base2)) * 100:+.2f}%，p = {hit / T:.4f}（基準池 {min(len(x) for x in pools2)}～{max(len(x) for x in pools2)} 天）")
    # (5) 可操作版本：事件日台指期近月「開盤」進、第 5 天日盤收盤出，扣 3 點（宣布多在收盤後，E-1 收盤進不可行）
    import csv as _csv
    tx = {}
    for r in _csv.DictReader(open(os.path.join(HERE, "tx_daily_ohlc.csv"), encoding="utf-8")):
        if r["session"] != "day" or r["open"] in ("-", "") or r["close"] in ("-", ""):
            continue
        tx.setdefault(r["date"], {})[r["month"]] = (float(r["open"]), float(r["close"]), int(float(r["volume"] or 0)))
    txd = sorted(tx)
    p("\n可操作版：事件日台指期近月開盤進 → 第 1／5／20 個交易日日盤收盤出（同契約，扣 3 點）")
    acts = {1: [], 5: [], 20: []}
    for d in EVENTS:
        if d not in tx:
            p(f"{d}  無台指期資料")
            continue
        k = txd.index(d)
        m = max(tx[d], key=lambda x: tx[d][x][2])
        o = tx[d][m][0]
        # 逐日串接：當天用前一天持有的契約收盤對收盤；契約到期（隔天沒有）就換成當天量最大的契約
        eq = [(tx[d][m][1] - o) / o]
        for j in range(k + 1, min(len(txd), k + 20)):
            prev, cur = txd[j - 1], txd[j]
            if m not in tx[cur]:
                m = max(tx[prev], key=lambda x: (x in tx[cur], tx[prev][x][2]))
                if m not in tx[cur]:
                    break
            eq.append(tx[cur][m][1] / tx[prev][m][1] - 1)
        cells = []
        for h in (1, 5, 20):
            if len(eq) < h:
                cells.append("   —  ")
                continue
            g = 1.0
            for x in eq[:h]:
                g *= 1 + x
            r = g - 1 - 3 / o
            acts[h].append(r)
            cells.append(f"{r * 100:+6.1f}%")
        gap = o / PX[idx(d) - 1] - 1
        p(f"{d}  開盤 vs 加權 E-1 {gap * 100:+5.1f}%（含正逆價差）| " + " ".join(cells))
    for h, r in acts.items():
        if r:
            p(f"  {h:>2} 日：{len(r)} 筆 平均 {statistics.mean(r) * 100:+.2f}% 中位 {statistics.median(r) * 100:+.2f}% 勝 {sum(x > 0 for x in r)}/{len(r)}")
    text = "\n".join(out)
    print(text)
    with open(os.path.join(HERE, "結果_研究280_國安基金進場.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
