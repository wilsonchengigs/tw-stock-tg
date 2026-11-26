"""研究 241：D 台美背離加碼的凱利部位（比照研究 170 對 P 的做法）
(A) 單看規則：台指期真實價 1998～ 64 筆（研究 211 的逐筆，無停損）f*＝argmax E[log(1+f·r)]；拔靴 1,000 次的分位；1998–2018／2018～ 兩段
(B) 組合內：V+F+P(1x) 上加 D 0／0.25／0.5／0.75／1／1.5x（研究 214 引擎）的年化、回檔、最差 5 日
用法：python -X utf8 backtest/research_241_背離凱利部位.py
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
R214 = load("r214", "research_214_全部規則合計.py")
FS = np.arange(0, 12.01, 0.25)


def kelly(r):
    g = [np.mean(np.log(np.maximum(1 + f * r, 1e-9))) for f in FS]
    return FS[int(np.argmax(g))]


def main():
    dates, day, night, near = R175.R139.load_tx()
    bi = set(R175.R138.DAYS)
    ds = [d for d in dates if d in bi]
    n = len(ds)
    g = np.array([R205.GAP.get(d, np.nan) for d in ds])
    ev, k = [], 0
    while k < n - 2:
        if g[k] <= -0.10:
            j = k + 1
            last = min(j + 4, n - 1)
            ev.append((ds[j], R175.trade(day, night, ds, j, near[ds[k]], (last, "close"), None)))
            k = last + 1
        else:
            k += 1
    r = np.array([x for _, x in ev])
    L = ["研究 241：D 台美背離加碼的凱利部位", f"(A) 單看規則：{len(r)} 筆 每筆 {r.mean():+.2%}、標準差 {r.std():.2%}、最差 {r.min():+.1%}"]
    rng = np.random.default_rng(241)
    for lab, sel in (("全部", np.ones(len(r), bool)), ("1998～2018-05", np.array([d < "2018-06" for d, _ in ev])), ("2018-06～", np.array([d >= "2018-06" for d, _ in ev]))):
        x = r[sel]
        bs = [kelly(rng.choice(x, len(x))) for _ in range(1000)]
        L.append(f"  {lab}：{sel.sum()} 筆 f* {kelly(x):.2f}x；拔靴 10／25／50 分位 {np.quantile(bs, 0.1):.2f}／{np.quantile(bs, 0.25):.2f}／{np.quantile(bs, 0.5):.2f}x")
    L.append("  （f*＝讓長期複利最大的每筆名目倍數；實務常用 1/4～1/2 凱利）")
    # (B) 組合內
    B = R214.B
    T = B.R141.build()
    nT = len(T)
    vf_r, fo = B.R152.run_vf(T)
    NN, SP = B.R142.night_series(T), B.R145.sp_series(T)
    o = np.array([t["o"] for t in T])
    c = np.array([t["c"] for t in T])
    rcc = np.array([t["rcc"] for t in T])
    roc, gap = c / o - 1, np.r_[0.0, o[1:] / c[:-1] - 1]
    pu = np.where((NN <= -0.02) | (SP <= -0.02), 1.0, 0.0)
    pug = np.r_[0.0, pu[:-1]]
    base = vf_r + (pug * gap + pu * roc - np.abs(pu - pug) * 3 / o)[1:]
    gg = np.nan_to_num(np.array([B.R205.GAP.get(t["d"], np.nan) for t in T]), nan=0.0)
    unit = np.zeros(nT)
    k = 0
    while k < nT:
        if gg[k] <= -0.10 and k + 1 < nT:
            unit[k + 1] += roc[k + 1] - 3 / o[k + 1]
            end = min(nT - 1, k + 5)
            for j in range(k + 2, end + 1):
                unit[j] += rcc[j]
            unit[end] -= 3 / c[end]
            k = end + 1
        else:
            k += 1
    L.append(f"\n(B) 疊在 V+F+P(1x) 上（{T[0]['d']}～{T[-1]['d']}）")
    for u in (0, 0.25, 0.5, 0.75, 1.0, 1.5):
        rr = base + u * unit[1:]
        e = np.cumprod(1 + rr)
        L.append(f"  D {u}x：{e[-1] ** (B.bt.TD / len(rr)) - 1:6.1%}／{(e / np.maximum.accumulate(e) - 1).min():6.1%}  最差 5 日 {(e[5:] / e[:-5] - 1).min():+.1%}")
    worst3 = np.sort(r)[:3]
    L.append(f"\n最差 3 筆（1x）：{', '.join(f'{x:+.1%}' for x in worst3)}；0.5x 時資金約 {worst3[0] / 2:+.1%}，1x 時 {worst3[0]:+.1%}")
    txt = "\n".join(L)
    print(txt)
    open(os.path.join(HERE, "結果_研究241_背離凱利部位.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
