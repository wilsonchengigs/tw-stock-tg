"""研究 220：D 台美背離加碼的進場時點——D 當天 15:00 夜盤開盤（14:40 收盤後提醒就能送）vs D 收盤 13:45 vs 隔天 08:45 開盤
出場都在第 5 個交易日（從 D+1 算）13:45 收盤；台指期近月真實價（研究 175 的 load_tx，夜盤 2017-05～）；每筆扣 6 點；不設停損
注意：D 的條件用加權 13:30 收盤與前一晚 S&P 收盤，14:40 都已知道
用法：python -X utf8 backtest/research_219_背離夜盤進場.py
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


R175 = load("r175", "research_175_加碼規則停損.py")
R205 = load("r205", "research_205_台美背離台指期部位.py")


def main():
    dates, day, night, near = R175.R139.load_tx()
    bi = set(R175.R138.DAYS)
    ds = [d for d in dates if d in bi]
    n = len(ds)
    g = np.array([R205.GAP.get(d, np.nan) for d in ds])
    rows, k = [], 0
    while k < n - 6:
        if g[k] <= -0.10:
            m = near[ds[k]]
            end = k + 5
            ce = day[ds[end]].get(m)
            if ce is None:  # 換月：用下一個月份
                m2 = next((x for x in sorted(day[ds[end]]) if x > m), None)
                ce = day[ds[end]].get(m2)
                adj = day[ds[k]][m2][3] / day[ds[k]][m][3] if m2 and day[ds[k]].get(m2) else 1
            else:
                adj = 1
            cl = day[ds[k]][m][3]
            nb = night.get(ds[k + 1], {}).get(m)
            ob = day[ds[k + 1]].get(m)
            cost = 6 / cl
            exitp = ce[3] / adj
            rows.append((ds[k], exitp / cl - 1 - cost, (exitp / nb[0] - 1 - cost) if nb and nb[4] >= 1000 else np.nan,
                         exitp / ob[0] - 1 - cost if ob else np.nan))
            k = end + 1
        else:
            k += 1
    L = ["研究 220：D 進場時點（出場＝第 5 個交易日收盤；台指期近月真實價；每筆扣 6 點）", "訊號日｜D 13:45 收盤進｜D 15:00 夜盤開盤進｜D+1 08:45 開盤進"]
    for d, a, b, c in rows:
        L.append(f"  {d}｜{a:+.1%}｜{b:+.1%}｜{c:+.1%}")
    arr = np.array([r[1:] for r in rows])
    for lab, sel in (("全部", np.ones(len(rows), bool)), ("2017-05～（有夜盤）", ~np.isnan(arr[:, 1]))):
        a = arr[sel]
        L.append(f"{lab} {sel.sum()} 筆：收盤進 {np.nanmean(a[:, 0]):+.2%}（勝率 {np.nanmean(a[:, 0] > 0):.0%}）、夜盤開盤進 {np.nanmean(a[:, 1]):+.2%}（{np.nanmean(a[:, 1] > 0):.0%}）、隔天開盤進 {np.nanmean(a[:, 2]):+.2%}（{np.nanmean(a[:, 2] > 0):.0%}）")
    sel = ~np.isnan(arr[:, 1])
    diff = arr[sel, 1] - arr[sel, 2]
    L.append(f"夜盤開盤進 − 隔天開盤進：平均 {diff.mean():+.2%}、中位 {np.median(diff):+.2%}、夜盤較好 {np.mean(diff > 0):.0%}（{sel.sum()} 筆）")
    txt = "\n".join(L)
    print(txt)
    open(os.path.join(HERE, "結果_研究220_背離夜盤進場.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
