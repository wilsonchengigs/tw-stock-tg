"""研究 143：研究 142「夜盤跌 ≥x% → D 08:45 開盤做多」的出場時點

出場：(1) D 13:45 日盤收盤（研究 142）(2) D 當晚夜盤收盤（隔天 05:00）(3) D+1 開盤 (4) D+1 收盤 (5) D+3 收盤 (6) D+5 收盤
另：D 日盤內停損（開盤價 −1%／−2%，用日盤最低價判斷，觸發以停損價出；無法判斷先後時保守視為先觸發）
同契約（D 前一天收盤時的近月），成本來回 3 點；對照＝全部日子同樣進出的平均
用法：python -X utf8 backtest/research_143_夜盤大跌出場時點.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r139", os.path.join(HERE, "research_139_日夜盤報酬拆解.py"))
R139 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R139)


def main():
    dates, day, night, near = R139.load_tx()
    rows = []
    for k in range(1, len(dates) - 6):
        d = dates[k]
        m = near[dates[k - 1]]
        nb, dd = night[d].get(m), day[d].get(m)
        if not nb or not dd or nb[4] < 1000:
            continue
        o, lo = dd[0], dd[2]
        ex = {"D收": dd[3]}
        n1 = night[dates[k + 1]].get(m)
        ex["當晚夜收"] = n1[3] if n1 and n1[4] >= 100 else None
        for lab, j, col in (("D+1開", 1, 0), ("D+1收", 1, 3), ("D+3收", 3, 3), ("D+5收", 5, 3)):
            b = day[dates[k + j]].get(m)
            ex[lab] = b[col] if b else None
        rows.append(dict(d=d, n=nb[3] / nb[0] - 1, o=o, lo=lo, ex=ex, dc=dd[3]))
    out = [f"研究 143：夜盤大跌隔天做多的出場時點（{rows[0]['d']}～{rows[-1]['d']}）", "每筆報酬（已扣 3 點）｜勝率｜對照＝所有日子同樣進出", ""]
    labs = ["D收", "當晚夜收", "D+1開", "D+1收", "D+3收", "D+5收"]

    def r(x, lab):
        e = x["ex"][lab]
        return None if e is None else e / x["o"] - 1 - 3.0 / x["o"]

    for th in (0.02, 0.025, 0.03):
        sig = [x for x in rows if x["n"] <= -th]
        parts = []
        for lab in labs:
            v = [r(x, lab) for x in sig if r(x, lab) is not None]
            a = [r(x, lab) for x in rows if r(x, lab) is not None]
            parts.append(f"{lab} {np.mean(v):+.2%}/{np.mean(np.array(v) > 0):.0%}（對照 {np.mean(a):+.2%}）")
        out.append(f"夜跌≥{th:.1%} {len(sig)} 次：" + "  ".join(parts))
        for sl in (0.01, 0.02):
            v = []
            for x in sig:
                if x["lo"] <= x["o"] * (1 - sl):
                    v.append(-sl - 3.0 / x["o"])
                else:
                    v.append(x["dc"] / x["o"] - 1 - 3.0 / x["o"])
            out.append(f"    日盤停損 −{sl:.0%}：每筆 {np.mean(v):+.2%}  勝率 {np.mean(np.array(v) > 0):.0%}  觸發 {sum(x['lo'] <= x['o'] * (1 - sl) for x in sig)} 次")
    out.append("\n== 反向：夜盤漲 ≥x% → D 開盤做空（扣 3 點）==")
    for th in (0.02, 0.025, 0.03):
        sig = [x for x in rows if x["n"] >= th]
        parts = []
        for lab in labs:
            v = [-(r(x, lab) + 3.0 / x["o"]) - 3.0 / x["o"] for x in sig if r(x, lab) is not None]
            parts.append(f"{lab} {np.mean(v):+.2%}/{np.mean(np.array(v) > 0):.0%}")
        out.append(f"夜漲≥{th:.1%} {len(sig)} 次：" + "  ".join(parts))
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究143_夜盤大跌出場時點.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
