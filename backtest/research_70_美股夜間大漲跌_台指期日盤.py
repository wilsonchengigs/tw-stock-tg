"""研究 70：美股前一晚大漲跌 → 台指期隔天日盤（開盤→收盤）延續還是回補？（AI-1：海外／短線）

台股開盤會反映前一晚美股（跳空）；問題是開盤之後的日盤走勢：
  順勢＝美股大漲（跌）→ 台指期日盤開盤買（空）、收盤平；逆勢＝反過來（賭跳空回補）
美股：^GSPC、^NDX、^SOX、TSM（ADR）前一個美國交易日收盤漲跌；台指期：近月日盤開盤、收盤（tx_daily_ohlc.csv，1998～）
門檻：|美股漲跌| ≥ 1／2／3%；另看「跳空幅度」（台指期開盤 vs 前日收盤）與美股漲跌的比例：跳空不足／過度時的後續
成本：每筆 3 點；檢定：sign-flip（雙尾）；分段 1998-2012／2013-2026；台指期夜盤（2017-05～）開始後另看
用法：python -X utf8 backtest/research_70_美股夜間大漲跌_台指期日盤.py
"""
import importlib.util
import json
import os
import random
import statistics
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r63d", os.path.join(HERE, "research_63d_爆量收黑_台指期真實價.py"))
r63d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r63d)
COST = 3.0
NY = timezone(timedelta(hours=-5))


def us(fn):
    r = json.load(open(os.path.join(HERE, fn)))
    c = r["indicators"]["quote"][0]["close"]
    rows = [(datetime.fromtimestamp(t, NY).strftime("%Y-%m-%d"), x) for t, x in zip(r["timestamp"], c) if x]
    return {rows[i][0]: rows[i][1] / rows[i - 1][1] - 1 for i in range(1, len(rows))}


def main():
    dates, day, night, near = r63d.load()
    rng = random.Random(70)
    US = {nm: us(fn) for nm, fn in (("S&P500", "GSPC.json"), ("NDX", "NDX.json"), ("SOX", "SOX.json"), ("TSM ADR", "TSM.json"))}
    rows = []
    for i in range(1, len(dates)):
        d, pd = dates[i], dates[i - 1]
        m = near[d]
        b, pb = day[d].get(m), day[pd].get(m)
        if not b or not pb:
            continue
        # 前一個美國交易日：台灣日期 d 的前一天（含）往回找 ≤ 4 天
        rows.append(dict(d=d, o=b[0], c=b[3], gap=b[0] / pb[3] - 1, us={}))
        for nm, s in US.items():
            for back in range(1, 5):
                k = (datetime.fromisoformat(d) - timedelta(days=back)).strftime("%Y-%m-%d")
                if k in s:
                    rows[-1]["us"][nm] = s[k]
                    break

    def test(xs):
        m_ = statistics.mean(xs)
        sims = [statistics.mean(x * rng.choice((1, -1)) for x in xs) for _ in range(2000)]
        return m_, (sum(abs(s) >= abs(m_) for s in sims) + 1) / 2001

    L = ["研究 70：美股前一晚大漲跌 → 台指期隔天日盤（開盤→收盤；成本 3 點；1998～2026）"]
    allr = [r["c"] / r["o"] - 1 - COST / r["o"] for r in rows]
    L.append(f"所有日子：日盤開→收 平均 {statistics.mean(allr):+.3%}（做多）")
    for nm in US:
        L.append(f"\n== {nm} ==")
        for th in (0.01, 0.02, 0.03):
            for lab, lo, hi in (("全期", "1998", "2027"), ("1998-2012", "1998", "2013"), ("2013-2026", "2013", "2027")):
                sel = [r for r in rows if nm in r["us"] and abs(r["us"][nm]) >= th and lo <= r["d"] < hi]
                if len(sel) < 15:
                    continue
                xs = [(1 if r["us"][nm] > 0 else -1) * (r["c"] / r["o"] - 1) - COST / r["o"] for r in sel]
                m_, p = test(xs)
                up = [r["c"] / r["o"] - 1 for r in sel if r["us"][nm] > 0]
                dn = [r["c"] / r["o"] - 1 for r in sel if r["us"][nm] < 0]
                L.append(f"  |漲跌|≥{th:.0%} {lab:9s} {len(sel):4d} 天  順勢每筆 {m_:+.3%}（≈{m_ * 40000:+4.0f} 點）p＝{p:.3f}  "
                         f"｜美股漲後日盤 {statistics.mean(up) if up else float('nan'):+.2%}（{len(up)}）、美股跌後日盤 {statistics.mean(dn) if dn else float('nan'):+.2%}（{len(dn)}）")
    # 跳空不足／過度：用 SOX，比較跳空 vs 美股漲跌（β≈0.5 經驗值→用迴歸估）
    L.append("\n== 跳空反應不足／過度（以 NDX，|NDX|≥1.5%）==")
    sel = [r for r in rows if "NDX" in r["us"] and abs(r["us"]["NDX"]) >= 0.015]
    xs_ = [r["us"]["NDX"] for r in sel]
    ys_ = [r["gap"] for r in sel]
    mx, my = statistics.mean(xs_), statistics.mean(ys_)
    beta = sum((x - mx) * (y - my) for x, y in zip(xs_, ys_)) / sum((x - mx) ** 2 for x in xs_)
    L.append(f"  台指期開盤跳空 ≈ {beta:.2f} × NDX 前晚漲跌（{len(sel)} 天）")
    under = [r for r in sel if abs(r["gap"]) < abs(beta * r["us"]["NDX"]) * 0.5]
    over = [r for r in sel if abs(r["gap"]) > abs(beta * r["us"]["NDX"]) * 1.5]
    for nm2, ss in (("跳空不足（< 預期一半）", under), ("跳空過度（> 預期 1.5 倍）", over)):
        if len(ss) >= 15:
            xs = [(1 if r["us"]["NDX"] > 0 else -1) * (r["c"] / r["o"] - 1) - COST / r["o"] for r in ss]
            m_, p = test(xs)
            L.append(f"  {nm2}：{len(ss)} 天，順著美股方向做日盤 每筆 {m_:+.3%}（≈{m_ * 40000:+.0f} 點）p＝{p:.3f}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究70_美股夜間大漲跌.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
