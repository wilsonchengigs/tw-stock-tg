"""研究 51：台積電 ADR 溢價（外資情緒）
溢價＝TSM（前一晚美股收盤）× USD/TWD ÷ 5 ÷ 2330（當天收盤）− 1（1 ADR＝5 股）；用過去 250 日百分位判斷高低（只用當時已知資料）
A 溢價百分位 ≤ q 時不進場（外資冷）；B 溢價百分位 ≤ q 時出場；C 空手時溢價百分位 ≥ q 且深跌反彈 → 提早進場
新版基準；100 次平移安慰劑
用法：python -X utf8 backtest/research_51_ADR溢價.py
"""
import bisect
import importlib.util
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r48", os.path.join(HERE, "research_48_基本面景氣.py"))
R48 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R48)
spec = importlib.util.spec_from_file_location("r50", os.path.join(HERE, "research_50_訊號標的.py"))
R50 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R50)
spec = importlib.util.spec_from_file_location("r09", os.path.join(HERE, "research_09_多市場分散.py"))
R09 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R09)
R = R48.R
DAYS, N = R.DAYS, R.N
NY = timezone(timedelta(hours=-5))


def tsm_prev_night():
    r = json.load(open(os.path.join(HERE, "TSM.json")))
    m = {datetime.fromtimestamp(t, NY).strftime("%Y-%m-%d"): c for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c}
    ks = sorted(m)
    return [m[ks[k]] if (k := bisect.bisect_left(ks, d) - 1) >= 0 else None for d in DAYS]


def main():
    tsm = tsm_prev_night()
    tw = [None] * N
    r = json.load(open(os.path.join(HERE, "2330.json")))
    raw = {datetime.fromtimestamp(t, timezone(timedelta(hours=8))).strftime("%Y-%m-%d"): c for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c}
    prem = []
    for i, d in enumerate(DAYS):
        fx = R09.fx_at(d)
        c = raw.get(d)
        prem.append(tsm[i] * fx / 5 / c - 1 if (tsm[i] and fx and c and d >= "2004-04-01") else None)
    # 錯價清理：溢價超過 ±60% 視為資料錯誤
    prem = [None if (p is None or abs(p) > 0.6) else p for p in prem]
    pr = [R48.R.R40.R32.R31.pct_rank(prem, i) if i >= 150 else None for i in range(N)]
    rng = random.Random(51)
    L = ["研究 51：台積電 ADR 溢價（全期 2002- | 前段 | 後段 | 真實；p＝100 次平移）"]
    vals = [p for p in prem if p is not None]
    L.append(f"溢價樣本 {len(vals)} 天，中位 {sorted(vals)[len(vals) // 2]:+.1%}，最新 {DAYS[-1]} {prem[-1] if prem[-1] is None else f'{prem[-1]:+.1%}'}")
    base = [R48.run(a, b) for a, b in R.PER]
    L.append("新版基準 " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in base))
    tests = []
    for q in (0.10, 0.20, 0.30):
        tests.append((f"A 溢價 ≤ {q:.0%} 分位不進場", "weak", (lambda v, q=q: v is not None and v <= q)))
    for q in (0.80, 0.90):
        tests.append((f"C 溢價 ≥ {q:.0%} 分位深跌反彈提早進", "strong", (lambda v, q=q: v is not None and v >= q)))
    for nm, kind, fn in tests:
        flag = [fn(v) for v in pr]
        rs = [R48.run(a, b, **{kind: flag}) for a, b in R.PER]
        rr = R48.run(*R.REAL, real=True, **{kind: flag})
        sims = []
        for _ in range(100):
            sh = R48.shifted(pr, rng)
            sims.append(R48.run(*R.PER[0], **{kind: [fn(v) for v in sh]})[0])
        p = (sum(x >= rs[0][0] for x in sims) + 1) / 101
        L.append(f"{nm:24s} " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%} | p {p:.2f}")
        print(L[-1], flush=True)
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究51_ADR溢價.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
