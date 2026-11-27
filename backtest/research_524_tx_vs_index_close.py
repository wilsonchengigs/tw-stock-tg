"""研究 524：日內順勢訊號日，台指期（13:45 收）是否拿得到加權 13:25～13:30 收盤競價那段
方法：訊號日方向 s，算 s×(台指期近月日盤收盤報酬 − 加權收盤報酬)，以前一日收盤為基準（兩者都 close-to-close）
若台指期拿得到，平均 ≈0；若拿不到，平均為負且接近 -(13:25→13:30 的順勢幅度)
另：s×(加權 13:30 / 13:25 − 1) 當參照；排除結算日（第 3 個週三）與隔天（換月）
用法：python -X utf8 backtest/research_524_tx_vs_index_close.py
"""
import os, sys, csv, datetime as dt
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M


def tx_close():
    best = {}
    for r in csv.DictReader(open(os.path.join(HERE, "tx_daily_ohlc.csv"), encoding="utf-8")):
        if r["session"] != "day" or r["close"] in ("-", ""):
            continue
        v = int(r["volume"] or 0)
        if r["date"] not in best or v > best[r["date"]][0]:
            best[r["date"]] = (v, float(r["close"]), r.get("month", ""))
    return {d: (c, m) for d, (v, c, m) in best.items()}


def settle_like(d):
    x = dt.date.fromisoformat(d)
    return x.weekday() == 2 and 15 <= x.day <= 21


def main():
    days = M.load_idx(); ds = sorted(days); tx = tx_close()
    out = [__doc__]
    sig = {"D30": {}, "E": {}}
    for d in ds:
        a = days[d]; o = M.at(a, 5)
        tr = M.at(a, 90) / o - 1
        if abs(tr) >= 0.005:
            sig["D30"][d] = 1 if tr > 0 else -1
        for mm, cl in a:
            if 6 <= mm <= 240 and abs(cl / o - 1) >= 0.01:
                sig["E"][d] = 1 if cl > o else -1; break
    for k, S in sig.items():
        diff = []; auc = []; skip = 0
        for i in range(1, len(ds)):
            d, p = ds[i], ds[i - 1]
            if d not in S or d not in tx or p not in tx:
                continue
            if settle_like(d) or settle_like(p) or tx[d][1] != tx[p][1]:
                skip += 1; continue
            s = S[d]
            ri = M.at(days[d], 270) / M.at(days[p], 270) - 1
            rt = tx[d][0] / tx[p][0] - 1
            diff.append(s * (rt - ri)); auc.append(s * (M.at(days[d], 270) / M.at(days[d], 265) - 1))
        diff = np.array(diff) * 100; auc = np.array(auc) * 100
        allp = []
        for i in range(1, len(ds)):
            d, p = ds[i], ds[i - 1]
            if d in tx and p in tx and not (settle_like(d) or settle_like(p)) and tx[d][1] == tx[p][1]:
                allp.append(tx[d][0] / tx[p][0] - M.at(days[d], 270) / M.at(days[p], 270))
        out.append(f"{k}：{len(diff)} 天（跳過換月／結算 {skip}）")
        out.append(f"  s×(台指期日報酬 − 加權日報酬) 平均 {diff.mean():+.3f}% t {diff.mean()/(diff.std(ddof=1)/np.sqrt(len(diff))):+.2f}（≈{diff.mean()*390:+.0f} 點）")
        out.append(f"  參照 s×(加權 13:25→13:30) 平均 {auc.mean():+.3f}%（≈{auc.mean()*390:+.0f} 點）")
        out.append(f"  所有日子 台指期−加權 日報酬差 平均 {np.mean(allp)*100:+.3f}%（基差逐日收斂的部分）")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究524_台指期收盤對加權.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
