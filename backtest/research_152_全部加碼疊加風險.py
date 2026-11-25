"""研究 152：三種台指期加碼（V 爆量收黑 1x、F 外資雙指標 0.5x、P 恐慌隔天做多 0.5x）全部疊加時的曝險與風險

研究 141 只看 V+F；這裡加上 P（研究 145），看最高曝險、最大回檔、最差單日，以及「P 只在 V+F 曝險 < 1 倍時才做」的上限版
引擎：研究 141 的 run 複製一份，多記每天收盤後的期貨曝險；P 的報酬同研究 145（D 開盤→D+1 開盤）
用法：python -X utf8 backtest/research_152_全部加碼疊加風險.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r145", os.path.join(HERE, "research_145_恐慌隔天做多聯集版.py"))
R145 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R145)
R141, R142, bt = R145.R141, R145.R142, R145.bt
COST = 3.0


def run_vf(T):
    """與 R141.run 相同（無上限），另回傳每天『開盤時』持有的期貨口數比例（V+F）"""
    base, hold, rets, fut_open = 0.0, {"V": None, "F": None}, [], []
    for k in range(1, len(T)):
        t, y = T[k], T[k - 1]
        fut_open.append(sum(h[0] for h in hold.values() if h is not None))
        r = base / 2 * t["r2"] + (1 - base / 2) * bt.RC
        for key, h in hold.items():
            if h is None:
                continue
            r += h[0] * (t["roc"] if h[2] else t["rcc"])
            if h[2]:
                r -= h[0] * COST / t["o"]
                h[2] = False
            h[1] -= 1
        for key in hold:
            h = hold[key]
            if h is not None and (h[1] <= 0 or t["st"] == 0):
                r -= h[0] * COST / t["c"]
                hold[key] = None
        nb = 2.0 * y["st"]
        if nb != base:
            r -= bt.COST * abs(nb - base)
            base = nb
        rets.append(r)
        for key, flag, add, H in (("V", t["vsig"], 1.0, 10), ("F", t["fsig"], 0.5, 5)):
            if flag and t["st"] == 1 and hold[key] is None:
                hold[key] = [add, H, True]
        fut_open[-1] = (fut_open[-1], base)
    return np.array(rets), fut_open


def main():
    T = R141.build()
    n = len(T)
    base_r, fo = run_vf(T)
    vf_units = np.array([x[0] for x in fo])
    NN, SP = R142.night_series(T), R145.sp_series(T)
    o = np.array([t["o"] for t in T])
    c = np.array([t["c"] for t in T])
    roc, gap = c / o - 1, np.r_[0.0, o[1:] / c[:-1] - 1]
    sig = (NN <= -0.02) | (SP <= -0.02)
    out = [f"研究 152：V＋F＋P 全部疊加（{T[0]['d']}～{T[-1]['d']}）", ""]
    for lab, allow in (("V+F（不含 P）", np.zeros(n, bool)), ("V+F+P（P 0.5x 全做）", sig),
                       ("V+F+P（V+F 期貨 <1x 才做 P）", sig & np.r_[True, vf_units < 1.0])):
        u = np.where(allow, 0.5, 0.0)
        ug = np.r_[0.0, u[:-1]]
        add = (ug * gap + u * roc - np.abs(u - ug) * COST / o)[1:]
        r = base_r + add
        e = np.cumprod(1 + r)
        cg = e[-1] ** (bt.TD / len(r)) - 1
        mdd = (e / np.maximum.accumulate(e) - 1).min()
        expo = np.array([b for _, b in fo]) + vf_units + u[1:]
        out.append(f"{lab:26s} 年化 {cg:6.1%}  最大回檔 {mdd:6.1%}  最差單日 {r.min():+.1%}  最高曝險 {expo.max():.1f}x  "
                   f"曝險 ≥3x 的天數 {(expo >= 3).sum()}  P 次數 {int(allow.sum())}")
    both = sig & np.r_[True, vf_units >= 1.0]
    out.append(f"\nP 觸發時 V+F 已持有 ≥1x 的次數：{both.sum()}；這些次 P 每筆（D 開→D+1 開）"
               f"{np.mean([(o[k + 1] / o[k] - 1) for k in np.where(both)[0] if k + 1 < n]):+.2%}")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究152_全部加碼疊加風險.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
