"""研究 302：52 週高點選股——含息（還原除權息）版

還原：`exright.csv`（build_exright.py，證交所 TWT49U）除權息日的日報酬改用 收盤 ÷ 參考價 − 1；
其他日子 收盤 ÷ 前收 − 1；把每檔重建成還原價序列（起點＝第一筆收盤），再套研究 301b 的格點與對照（等權全市場也變含息）。
0050（Yahoo 調整價，含息）同期比較。
用法：python -X utf8 backtest/research_302_52週高點含息.py
"""
import csv
import importlib.util
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r301b", os.path.join(HERE, "research_301b_52週高點穩健性.py"))
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
raw_load = B.R.load


def adjusted_load():
    px = raw_load()
    ex = {}
    for r in csv.DictReader(open(os.path.join(HERE, "exright.csv"), encoding="utf-8")):
        ex[(r["code"], r["date"])] = float(r["ref"])
    adj = defaultdict(dict)
    n_adj = 0
    for c, m in px.items():
        ds = sorted(m)
        lv = m[ds[0]]
        adj[c][ds[0]] = lv
        for a, b in zip(ds, ds[1:]):
            base = ex.get((c, b))
            if base and base > 0:
                n_adj += 1
            else:
                base = m[a]
            lv *= m[b] / base
            adj[c][b] = lv
    print(f"還原除權息 {n_adj} 筆", flush=True)
    return adj


def main():
    B.R.load = adjusted_load
    B.main()
    # 改名輸出
    src = os.path.join(HERE, "結果_研究301b_52週高點穩健性.txt")
    txt = open(src, encoding="utf-8").read().replace("研究 301b：52 週高點穩健性", "研究 302：52 週高點含息版").replace("未還原股利", "已還原除權息")
    open(os.path.join(HERE, "結果_研究302_52週高點含息.txt"), "w", encoding="utf-8").write(txt)
    # 還原 301b 原檔（避免覆蓋未還原版結果）
    B.R.load = raw_load


if __name__ == "__main__":
    main()
