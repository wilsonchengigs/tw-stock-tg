"""研究 170：恐慌隔天做多（候選 6）的部位大小——凱利公式（馬克羊「少輸」、凱利尺度控管）

(A) 單看這條規則的每筆報酬（D 開→D+1 開，扣 3 點）：凱利最適倍數 f*＝argmax E[log(1+f·r)]
    1998～2017（樣本外，S&P 代理）與 2017-05～ 各算；拔靴 2000 次看 f* 的分布（不確定性）；半凱利
(B) 疊在實際組合上（研究 145／147 引擎：v3＋V＋F，00631L＋台指期真實價，2018-06～）：加碼 0～4 倍各自的年化／最大回檔／log 成長
    ——組合本身已有約 2 倍曝險，組合內的最適加碼會比單看規則小
(C) 最壞情境：歷史最差一筆 × 倍數；連續 3 次觸發都虧的最壞累積
用法：python -X utf8 backtest/research_170_恐慌隔天做多凱利部位.py
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


R147 = load("r147", "research_147_恐慌依跌幅分級.py")
R148 = load("r148", "research_148_恐慌連續觸發.py")
R141, R142, R145, bt = R147.R141, R147.R142, R147.R145, R147.bt
COST = 3.0
FS = np.arange(0, 12.01, 0.25)


def kelly(r):
    g = np.array([np.mean(np.log1p(np.maximum(f * r, -0.99))) for f in FS])
    return FS[g.argmax()], g


def main():
    rng = np.random.default_rng(170)
    out = ["研究 170：恐慌隔天做多（候選 6）凱利部位", ""]
    rows = R148.build()
    out.append("== (A) 單看這條規則（每筆 D 開→D+1 開，扣 3 點）==")
    for per, lo, hi in (("1998-07～2017-05（樣本外）", "1998", "2017-05-15"), ("2017-05～", "2017-05-15", "2099"), ("全期", "1998", "2099")):
        r = np.array([x["r"] for x in rows if x["sig"] and lo <= x["d"] < hi])
        f, g = kelly(r)
        boots = np.array([kelly(rng.choice(r, len(r)))[0] for _ in range(500)])
        cont = r.mean() / r.var()
        out.append(f"{per:24s} {len(r):3d} 筆  平均 {r.mean():+.2%}  標準差 {r.std():.2%}  最差 {r.min():+.1%}")
        out.append(f"   凱利 f*＝{f:.2f} 倍（連續近似 μ/σ² {cont:.1f}）；拔靴 f* 10／50／90 分位 {np.percentile(boots, 10):.2f}／{np.percentile(boots, 50):.2f}／{np.percentile(boots, 90):.2f}")
        out.append(f"   每次觸發的 log 成長：0.5x {g[FS.searchsorted(0.5)]:+.3%}  1x {g[FS.searchsorted(1)]:+.3%}  2x {g[FS.searchsorted(2)]:+.3%}  半凱利 {g[FS.searchsorted(f / 2)]:+.3%}  凱利 {g.max():+.3%}")
    out.append("（單看規則的凱利假設「這筆錢只做這件事」；實際帳戶同時抱 00631L，要看 (B)）")
    out.append("")

    # (B) 組合內
    T = R141.build()
    n = len(T)
    _, _, base_r, _ = R141.run(T)
    NN, SP = R142.night_series(T), R145.sp_series(T)
    o = np.array([t["o"] for t in T])
    c = np.array([t["c"] for t in T])
    roc = c / o - 1
    gap = np.r_[0.0, o[1:] / c[:-1] - 1]
    s = np.maximum(-NN, -SP)
    out.append(f"== (B) 疊在現行組合上（v3＋V＋F，{T[0]['d']}～{T[-1]['d']}）==")
    out.append(f"{'加碼倍數':>6s} {'年化':>7s} {'最大回檔':>8s} {'log成長/年':>10s} {'最差單日':>8s}")
    best = None
    for size in (0, 0.5, 1, 1.5, 2, 2.5, 3, 4):
        u = np.where(s >= 0.02, size, 0.0)
        ug = np.r_[0.0, u[:-1]]
        add = ug * gap + u * roc - np.abs(u - ug) * COST / o
        r = base_r + add[1:]
        e = np.cumprod(1 + r)
        cg = e[-1] ** (bt.TD / len(r)) - 1
        dd = (e / np.maximum.accumulate(e) - 1).min()
        lg = np.mean(np.log1p(r)) * bt.TD
        if best is None or lg > best[1]:
            best = (size, lg)
        out.append(f"{size:6.1f}x {cg:7.1%} {dd:8.1%} {lg:10.1%} {r.min():8.1%}")
    out.append(f"組合內 log 成長最高：{best[0]}x（2018～2026 多頭期間，偏樂觀）")
    out.append("")

    # (C) 最壞情境
    allr = np.array([x["r"] for x in rows if x["sig"]])
    out.append("== (C) 最壞情境（全期 314 次觸發）==")
    worst = allr.min()
    seq = []
    sigs = [x for x in rows if x["sig"]]
    for i in range(len(sigs) - 2):
        seq.append(np.prod(1 + allr[i:i + 3]) - 1)
    w3 = min(seq)
    for size in (0.5, 1, 2):
        out.append(f"{size}x：最差一筆 {worst * size:+.1%}（資金）；連續 3 次觸發最差 {w3 * size:+.1%}")
    out.append("")
    out.append("解讀：凱利值是在「報酬分布已知」下的最大成長；實務上分布不確定（拔靴區間寬）＋肥尾，常用 1/4～1/2 凱利")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究170_恐慌隔天做多凱利部位.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
