"""研究 171：恐慌做多改 1 倍後，全部加碼疊在一起的壓力測試（「少輸」）

組合：v3 00631L（2 倍）＋ V 爆量收黑 1x 抱 10 天 ＋ F 外資期貨 0.5x 抱 5 天 ＋ P 恐慌隔天做多 1x（D 開→D+1 開）
理論最大曝險 2＋1＋0.5＋1＝4.5 倍。研究 141 只測了 V＋F 的上限；這裡把 P 放進去
(A) 每天曝險分布、≥3／3.5／4 倍的天數；曝險最高的日子與當天報酬；最差 10 天的曝險
(B) 總曝險上限 無／4／3.5／3 倍（超過時 P 先被砍，因為 P 最後決定）：年化、最大回檔、最差單日
(C) 曝險 ≥3.5 倍的日子平均報酬（疊加時是不是特別危險）
引擎：研究 141（00631L＋台指期真實價，2018-06～），P 訊號用研究 142／145 的夜盤、S&P 序列
用法：python -X utf8 backtest/research_171_全部加碼疊加壓力測試.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r147", os.path.join(HERE, "research_147_恐慌依跌幅分級.py"))
R147 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R147)
R141, R142, R145, bt = R147.R141, R147.R142, R147.R145, R147.bt
COST = R141.COST


def run(T, P, cap=None, sizeP=1.0):
    eq, peak, mdd = 1.0, 1.0, 0.0
    base = 0.0
    hold = {"V": None, "F": None}
    uprev = 0.0
    rets, expo = [], []
    for k in range(1, len(T)):
        t, y = T[k], T[k - 1]
        r = base / 2 * t["r2"] + (1 - base / 2) * bt.RC
        fut = 0.0
        vf = 0.0
        for key, h in hold.items():
            if h is None:
                continue
            vf += h[0]
            fut += h[0] * (t["roc"] if h[2] else t["rcc"])
            if h[2]:
                r -= h[0] * COST / t["o"]
                h[2] = False
            h[1] -= 1
        r += fut
        # P：今天 08:45 開盤決定（昨晚夜盤／S&P），抱到明天開盤
        u = sizeP if P[k] else 0.0
        if cap is not None:
            u = max(0.0, min(u, cap - base - vf))
        gap = t["o"] / y["c"] - 1
        r += uprev * gap + u * t["roc"] - abs(u - uprev) * COST / t["o"]
        expo.append(base + vf + u)
        uprev = u
        for key in hold:
            h = hold[key]
            if h is not None and (h[1] <= 0 or t["st"] == 0):
                r -= h[0] * COST / t["c"]
                hold[key] = None
        nb = 2.0 * y["st"]
        if nb != base:
            r -= bt.COST * abs(nb - base)
            base = nb
        eq *= 1 + r
        rets.append(r)
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        for key, flag, add, H in (("V", t["vsig"], 1.0, 10), ("F", t["fsig"], 0.5, 5)):
            if not flag or t["st"] != 1 or hold[key] is not None:
                continue
            other = sum(h[0] for kk, h in hold.items() if h is not None and kk != key)
            a = add if cap is None else max(0.0, min(add, cap - 2.0 - other))
            if a > 0:
                hold[key] = [a, H, True]
    yrs = len(rets) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, np.array(rets), np.array(expo)


def main():
    T = R141.build()
    NN, SP = R142.night_series(T), R145.sp_series(T)
    P = np.maximum(-NN, -SP) >= 0.02
    ds = [t["d"] for t in T][1:]
    out = [f"研究 171：全部加碼疊加壓力測試（{T[0]['d']}～{T[-1]['d']}；v3 2x＋V 1x＋F 0.5x＋P 1x）", ""]
    cg, mdd, r, e = run(T, P)
    out.append("== (A) 每天曝險分布（無上限）==")
    for th in (2.5, 3, 3.5, 4, 4.5):
        out.append(f"≥{th} 倍：{(e >= th - 1e-9).sum()} 天（{(e >= th - 1e-9).mean():.1%}）")
    out.append(f"最高 {e.max():.1f} 倍")
    top = np.argsort(-e)[:8]
    out.append("曝險最高的日子：" + "；".join(f"{ds[i]} {e[i]:.1f}x 當天 {r[i]:+.1%}" for i in sorted(top)))
    worst = np.argsort(r)[:10]
    out.append("最差 10 天：" + "；".join(f"{ds[i]} {r[i]:+.1%}（{e[i]:.1f}x）" for i in sorted(worst)))
    out.append("")
    out.append("== (B) 總曝險上限 ==")
    out.append(f"{'上限':>8s} {'年化':>7s} {'最大回檔':>8s} {'最差單日':>8s} {'≥3.5x 天數':>9s}")
    for cap in (None, 4.0, 3.5, 3.0):
        a, b, rr, ee = run(T, P, cap)
        out.append(f"{'無' if cap is None else f'{cap}x':>8s} {a:7.1%} {b:8.1%} {rr.min():8.1%} {(ee >= 3.5 - 1e-9).sum():9d}")
    a, b, rr, ee = run(T, P, None, 0.5)
    out.append(f"{'(P 0.5x)':>8s} {a:7.1%} {b:8.1%} {rr.min():8.1%} {(ee >= 3.5 - 1e-9).sum():9d}")
    out.append("")
    out.append("== (C) 疊加日的報酬 ==")
    for lo, hi in ((0, 0.01), (0.01, 2.01), (2.01, 3.01), (3.01, 3.51), (3.51, 9)):
        m = (e >= lo) & (e < hi)
        if m.sum():
            out.append(f"曝險 {lo:.1f}～{hi:.1f}x：{m.sum():4d} 天  平均 {r[m].mean():+.2%}  標準差 {r[m].std():.2%}  最差 {r[m].min():+.1%}  每單位曝險平均 {np.mean(r[m] / np.maximum(e[m], 1e-9)) if lo > 0 else 0:+.3%}")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究171_全部加碼疊加壓力測試.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
