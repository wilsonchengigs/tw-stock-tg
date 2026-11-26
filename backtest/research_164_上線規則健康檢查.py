"""研究 164：上線規則健康檢查（每月 1 日由 .github/workflows/health.yml 自動跑、結果寄 TG；也可手動跑）

檢查三條期貨規則（台指期真實價、扣成本）：
  P 恐慌隔天做多（研究 145、170）：最近 N＝20 筆
  V 爆量收黑加碼（研究 172b，v3 在場、抱 10 天）：最近 N＝8 筆
  F 外資期貨加碼（研究 128／172，v3 在場、抱 5 天，2018-06～）：最近 N＝10 筆
  D 台美背離加碼（研究 204～211，加權 20 日 − S&P 20 日 ≤-10% → 隔天開盤進、抱 5 天，不分 v3 狀態）：最近 N＝8 筆
  Y 年底加碼（研究 262～263，12 月最後交易日前 3 天收盤（≈隔天開盤）進、1 月第 5 個交易日收盤出）：最近 N＝6 筆
每條：全部筆數／勝率／每筆；最近 N 筆的平均，在「歷史上所有連續 N 筆平均」的分位
  < 10 分位 → ⚠️ 近期偏弱（不代表失效，但要留意）；< 3 分位 → 🚨 明顯偏弱，考慮暫停或降倍數
資料：tx_daily_ohlc.csv、turnover_daily.csv、tx_inst_oi.csv、GSPC.json、margin_tw.csv（workflow 會先更新）
用法：python -X utf8 backtest/research_164_上線規則健康檢查.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def check(name, dates, rets, N):
    r = np.asarray(rets)
    if len(r) < N + 5:
        return [f"{name}：只有 {len(r)} 筆，樣本不足"]
    roll = np.convolve(r, np.ones(N) / N, mode="valid")
    cur = roll[-1]
    pct = np.mean(roll[:-1] <= cur)
    flag = "🚨 明顯偏弱（考慮暫停或降倍數）" if pct < 0.03 else "⚠️ 近期偏弱，留意" if pct < 0.10 else "✅ 正常"
    return [f"{name}",
            f"・全部 {len(r)} 筆（{dates[0]}～{dates[-1]}）：勝率 {np.mean(r > 0):.0%}、每筆 {r.mean():+.2%}",
            f"・最近 {N} 筆（{dates[-N]} 起）：勝率 {np.mean(r[-N:] > 0):.0%}、每筆 {cur:+.2%}；在歷史所有連續 {N} 筆中第 {pct:.0%} 分位 → {flag}"]


def main():
    R148 = load("r148", "research_148_恐慌連續觸發.py")
    R175 = load("r175", "research_175_加碼規則停損.py")
    R141, R139, R138, bt = R175.R141, R175.R139, R175.R138, R175.bt
    out = ["🩺 每月規則健康檢查（研究 164）", ""]
    rows = [x for x in R148.build() if x["sig"]]
    out += check("恐慌隔天做多（1 倍、隔天開盤出）", [x["d"] for x in rows], [x["r"] for x in rows], 20)
    out.append("")
    dates, day, night, near = R139.load_tx()
    bi = {d: k for k, d in enumerate(R138.DAYS)}
    ds = [d for d in dates if d in bi]
    n = len(ds)
    st = np.array([R138.ST[bi[d]] for d in ds])
    vsig = np.zeros(n, bool)
    for k, d in enumerate(ds):
        i = bi[d]
        amts = [R139.AMT.get(R138.DAYS[j]) for j in range(i - 20, i)]
        amts = [a for a in amts if a]
        a0 = R139.AMT.get(d)
        vsig[k] = bool(a0 and len(amts) >= 16 and a0 / (sum(amts) / len(amts)) >= 1.5 and bt.PX[i] < bt.PX[i - 1])
    fset = {t["d"] for t in R141.build() if t["fsig"]}
    fsig = np.array([d in fset for d in ds])

    def events(sig, H):
        ev, k = [], 0
        while k < n - 2:
            if sig[k] and st[k] == 1:
                j = k + 1
                last = j
                for h in range(H):
                    last = min(j + h, n - 1)
                    if st[last] == 0:
                        break
                ev.append((j, near[ds[k]], (last, "close")))
                k = last + 1
            else:
                k += 1
        return ev

    for nm, sig, H, N in (("爆量收黑加碼（1 倍、抱 10 天）", vsig, 10, 8), ("外資期貨加碼（0.5 倍、抱 5 天）", fsig, 5, 10)):
        ev = events(sig, H)
        rs = [R175.trade(day, night, ds, j, m, hl, None) for j, m, hl in ev]
        out += check(nm, [ds[j] for j, _, _ in ev], rs, N)
        out.append("")
    R205 = load("r205", "research_205_台美背離台指期部位.py")
    g = np.array([R205.GAP.get(d, np.nan) for d in ds])
    ev, k = [], 0
    while k < n - 2:
        if g[k] <= -0.10:
            j = k + 1
            last = min(j + 4, n - 1)
            ev.append((j, near[ds[k]], (last, "close")))
            k = last + 1
        else:
            k += 1
    rs = [R175.trade(day, night, ds, j, m, hl, None) for j, m, hl in ev]
    out += check("台美背離加碼（0.5 倍、抱 5 天）", [ds[j] for j, _, _ in ev], rs, 8)
    out.append("")
    ye = [k for k in range(3, n - 5) if ds[k][5:7] == "12" and ds[k + 1][:4] != ds[k][:4]]
    ev = [(k - 2, near[ds[k - 3]], (k + 5, "close")) for k in ye]
    rs = [R175.trade(day, night, ds, j, m, hl, None) for j, m, hl in ev]
    out += check("年底加碼（0.5 倍、跨年約 8 天）", [ds[j] for j, _, _ in ev], rs, 6)
    out.append("")
    out.append("（分位＝最近 N 筆平均在歷史上所有連續 N 筆平均中的位置；< 10% 才需要留意。樣本少的規則波動本來就大）")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究164_上線規則健康檢查.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
