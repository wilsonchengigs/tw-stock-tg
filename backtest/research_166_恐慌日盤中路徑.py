"""研究 166：恐慌觸發日（候選 6）當天的盤中路徑——08:45 開盤進是否最好（台指期近月 1 分 K，期交所近 30 個交易日）

觸發：該交易日的夜盤（tx_1min 的 night session，前一晚 15:00～05:00）開→收 ≤ −2%（S&P 部分略，資料太短）
看：08:45 開盤 → 08:50／09:00／09:30／10:00／13:45 收盤 的報酬；盤中最低點出現時間與幅度；各進場時點 → 隔天 08:45 開盤 的報酬
樣本只有近 30 天的幾次，只當描述
用法：python -X utf8 backtest/research_166_恐慌日盤中路徑.py
"""
import csv
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    S = defaultdict(list)
    for r in csv.DictReader(open(os.path.join(HERE, "tx_1min.csv"), encoding="utf-8")):
        S[(r["trade_day"], r["session"])].append((r["ts"][-5:], float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])))
    days = sorted({d for d, _ in S})
    out = ["研究 166：恐慌觸發日盤中路徑（台指期 1 分 K，近 30 個交易日）", ""]
    for k, d in enumerate(days):
        nb, db = S.get((d, "night")), S.get((d, "day"))
        if not nb or not db:
            continue
        nr = nb[-1][4] / nb[0][1] - 1
        if nr > -0.02:
            continue
        o = db[0][1]
        at = {t: c for t, _, _, _, c in db}

        def p(t):
            ks = [x for x in at if x <= t]
            return at[max(ks)] if ks else None
        lo = min(db, key=lambda x: x[3])
        nxt = S.get((days[k + 1], "day")) if k + 1 < len(days) else None
        o1 = nxt[0][1] if nxt else None
        line = f"{d} 夜盤 {nr:+.1%}  開 {o:,.0f}：" + "  ".join(f"{t} {p(t) / o - 1:+.1%}" for t in ("08:50", "09:00", "09:30", "10:00", "13:44"))
        line += f"  盤中最低 {lo[3] / o - 1:+.1%}@{lo[0]}"
        if o1:
            line += "  ｜到隔天開盤：" + "  ".join(f"{t}進 {o1 / (p(t) if t != '08:45' else o) - 1:+.1%}" for t in ("08:45", "09:00", "09:30", "10:00"))
        out.append(line)
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究166_恐慌日盤中路徑.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
