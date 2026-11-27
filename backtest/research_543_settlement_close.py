"""研究 543：台指期結算日（每月第 3 個週三）尾盤效應
加權 1 分 K：結算日 vs 非結算週三 vs 其他日子，各時段報酬 12:00→13:00、13:00→13:25、13:25→13:30（收盤競價）、09:05→13:30
另：結算日前一天（週二）、結算日後一天（週四）全日
用法：python -X utf8 backtest/research_543_settlement_close.py
"""
import os, sys, datetime as dt
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M


def is_settle(d):
    x = dt.date.fromisoformat(d)
    return x.weekday() == 2 and 15 <= x.day <= 21


def main():
    days = M.load_idx(); ds = sorted(days)
    seg = [("12:00→13:00", 180, 240), ("13:00→13:25", 240, 265), ("13:25→13:30", 265, 270), ("09:05→13:30", 5, 270)]
    groups = {"結算日": [], "非結算週三": [], "結算前一天": [], "結算後一天": [], "其他": []}
    for i, d in enumerate(ds):
        a = days[d]
        r = [(M.at(a, b) / M.at(a, s) - 1) * 100 for _, s, b in seg]
        x = dt.date.fromisoformat(d)
        if is_settle(d):
            groups["結算日"].append(r)
        elif i + 1 < len(ds) and is_settle(ds[i + 1]):
            groups["結算前一天"].append(r)
        elif i > 0 and is_settle(ds[i - 1]):
            groups["結算後一天"].append(r)
        elif x.weekday() == 2:
            groups["非結算週三"].append(r)
        else:
            groups["其他"].append(r)
    out = [__doc__]
    for k, v in groups.items():
        v = np.array(v)
        t = v.mean(0) / (v.std(0, ddof=1) / np.sqrt(len(v)))
        out.append(f"  {k:8s} {len(v):4d} 天｜" + "｜".join(f"{seg[j][0]} {v[:, j].mean():+.3f}%（t {t[j]:+.1f}）" for j in range(4)))
    # 結算日 13:00→13:30 方向與早盤方向的關係
    st = [d for d in ds if is_settle(d)]
    am = np.array([M.at(days[d], 240) / M.at(days[d], 5) - 1 for d in st]); pm = np.array([M.at(days[d], 270) / M.at(days[d], 240) - 1 for d in st])
    out.append(f"  結算日 早盤(09:05→13:00) 與尾盤(13:00→13:30) 相關 {np.corrcoef(am, pm)[0,1]:+.2f}；尾盤順早盤方向平均 {np.mean(np.sign(am)*pm)*100:+.3f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究543_結算日尾盤.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
