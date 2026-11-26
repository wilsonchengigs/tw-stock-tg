"""研究 192：進場時買台指期會不會比買 00631L 好？（使用者 2026-11-26 問；接研究 23、191）

研究 23（舊版訊號）：2015-09 後期貨 33.0% vs 00631L 33.0% 打平，不建議改。研究 191 發現 2024～2026 期貨轉正價差、00631L 落後模型。
期貨一樣吃價差，所以在 v3（含融資過熱）上逐年重比：
- 部位：v3 每天的持有槓桿（0 或 2，研究 186 引擎，含每日過熱檢查）
- 00631L：真實價（strategy_v3.R2R），換手成本 0.25%/單位（手續費＋證交稅 0.1%）
- 台指期：研究 23 的連續近月真實價（成交量最大月份），2 倍名目、每天重設（研究 188：與每週／每月調整差不多）；
  進出與換約 0.02%×名目；保證金現金 收 1%（放銀行／期貨商超額保證金）或 0%（不計息）兩種
用法：python -X utf8 backtest/research_192_期貨vs正2_v3.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


R186 = load("r186", "research_186_主策略全面健檢.py")
R23 = load("r23", "research_23_台指期取代正2.py")
V3 = R186.V3
bt, DAYS, N = R186.bt, R186.DAYS, R186.N
FR, ROLL = R23.futures_returns(R23.load_tx())


def positions():
    tr = []
    R186.run("2002-01-01", "2026-12-31", trades=tr)
    tm = {d: b for d, a, b, _ in tr}
    pos, cur = [], 0.0
    for d in DAYS:
        cur = tm.get(d, cur)
        pos.append(cur)
    return pos


POS = positions()


def run(kind, start, end, cash=bt.RC, yearly=False):
    i0 = next(i for i, d in enumerate(DAYS) if d >= start)
    i1 = max(i for i, d in enumerate(DAYS) if d <= end)
    eq = peak = 1.0
    mdd, ys = 0.0, {}
    for i in range(i0, i1 + 1):
        if i > i0:
            L = POS[i - 1]
            if L > 0:
                eq *= 1 + (L * FR[i] + cash if kind == "fut" else V3.R2R[i])
                if kind == "fut" and ROLL[i]:
                    eq *= 1 - 0.0002 * L
            else:
                eq *= 1 + bt.RC
            if POS[i] != POS[i - 1]:
                eq *= 1 - (0.0002 if kind == "fut" else bt.COST) * abs(POS[i] - POS[i - 1])
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        ys[DAYS[i][:4]] = eq
    yrs = (i1 - i0) / bt.TD
    if yearly:
        prev, out = 1.0, {}
        for y in sorted(ys):
            out[y] = ys[y] / prev - 1
            prev = ys[y]
        return out
    return eq ** (1 / yrs) - 1, mdd


def main():
    L = ["研究 192：v3 訊號下 台指期 2x vs 00631L（真實價）"]
    for a, b in (("2015-09-01", "2026-12-31"), ("2015-09-01", "2020-12-31"), ("2021-01-01", "2026-12-31"), ("2024-01-01", "2026-12-31")):
        e = run("etf", a, b)
        f1 = run("fut", a, b)
        f0 = run("fut", a, b, cash=0.0)
        L.append(f"  {a[:7]}～{b[:4]}：00631L {e[0]:5.1%}/{e[1]:6.1%}｜期貨(保證金收 1%) {f1[0]:5.1%}/{f1[1]:6.1%}｜期貨(不計息) {f0[0]:5.1%}/{f0[1]:6.1%}")
    ye, yf = run("etf", "2015-09-01", "2026-12-31", yearly=True), run("fut", "2015-09-01", "2026-12-31", yearly=True)
    L.append("\n逐年（00631L｜期貨收 1%｜差）：")
    for y in ye:
        L.append(f"  {y}：{ye[y]:+7.1%}｜{yf[y]:+7.1%}｜{yf[y] - ye[y]:+6.1%}")
    L.append(f"  期貨較好 {sum(yf[y] > ye[y] for y in ye)}／{len(ye)} 年")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究192_期貨vs正2_v3.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()


def decompose():
    """全年持有（不看訊號）的 2x：模型（2×(加權+配息)−1%）｜期貨 2x（+現金 1%）｜00631L 真實；拆出 價差效果＝期貨−模型、ETF 自身＝00631L−期貨"""
    L = ["\n【拆解】全年持有 2x：模型｜期貨｜00631L｜價差效果（期貨−模型）｜00631L 自身（00631L−期貨）"]
    for y in [str(x) for x in range(2016, 2027)]:
        idx = [i for i, d in enumerate(DAYS) if d[:4] == y and i > 0]
        m = f = e = 1.0
        for i in idx:
            m *= 1 + bt.R2[i]
            f *= 1 + 2 * FR[i] + bt.RC
            e *= 1 + V3.R2R[i]
        L.append(f"  {y}：{m - 1:+7.1%}｜{f - 1:+7.1%}｜{e - 1:+7.1%}｜{f - m:+6.1%}｜{e - f:+6.1%}")
    return L


if __name__ == "__main__":
    add = decompose()
    print("\n".join(add))
    open(os.path.join(HERE, "結果_研究192_期貨vs正2_v3.txt"), "a", encoding="utf-8").write("\n".join(add) + "\n")
