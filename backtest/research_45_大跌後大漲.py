"""研究 45：大跌後單日大漲（例：2026-11-24 +8.8%）——之後走勢與 P/C、融資、成交量的關係
事件：前一天距 250 日高點跌 ≥ 15%、當天漲 ≥ 4%（去叢集 10 日）
依事件當天（或前 10 日最高）的 P/C 未平倉百分位、融資比值偏離、成交量比分組，看 20／60／120 日報酬
用法：python -X utf8 backtest/research_45_大跌後大漲.py
"""
import csv
import importlib.util
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r32", os.path.join(HERE, "research_32_PC比提早進場.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
bt, PX, DAYS, N, PR = R.bt, R.PX, R.DAYS, R.N, R.PR
spec = importlib.util.spec_from_file_location("r30", os.path.join(HERE, "research_30_底部爆量.py"))
R30 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R30)
hi = [max(PX[max(0, i - 249):i + 1]) for i in range(N)]


def fwd(i, h):
    return PX[i + h] / PX[i] - 1 if i + h < N else None


def main():
    ev, last = [], -99
    for i in range(1, N):
        if PX[i] / PX[i - 1] - 1 >= 0.04 and PX[i - 1] / hi[i - 1] - 1 <= -0.15 and i - last > 10:
            ev.append(i)
            last = i
    L = ["研究 45：大跌後單日大漲 ≥4%（前一天距高點 ≥15%）的後續，依當時指標分組",
         "日期 | 當天漲幅 | 距高點 | 近 10 日 P/C 最高百分位 | 量比 | 20／60／120 日 | 之後 120 日最低"]
    rows = []
    for i in ev:
        pc = max((PR[j] for j in range(i - 10, i + 1) if PR[j] is not None), default=None)
        vr = R30.VR[i]
        f = [fwd(i, h) for h in (20, 60, 120)]
        lo = min(PX[i:i + 121]) / PX[i] - 1 if i + 121 < N else None
        rows.append((i, pc, vr, f, lo))
        L.append(f"{DAYS[i]} | {PX[i] / PX[i - 1] - 1:+.1%} | {PX[i - 1] / hi[i - 1] - 1:.0%} | {'—' if pc is None else f'{pc:.0%}'} | {'—' if vr is None else f'{vr:.2f}'} | "
                 + "／".join("—" if x is None else f"{x:+.1%}" for x in f) + f" | {'—' if lo is None else f'{lo:+.1%}'}")

    def grp(nm, sel):
        xs = [r for r in rows if sel(r)]
        L.append(f"\n{nm}（{len(xs)} 次）")
        for k, h in enumerate((20, 60, 120)):
            v = [r[3][k] for r in xs if r[3][k] is not None]
            if v:
                L.append(f"  {h} 日：平均 {statistics.mean(v):+.1%}、上漲 {sum(x > 0 for x in v) / len(v):.0%}")
        lo = [r[4] for r in xs if r[4] is not None]
        if lo:
            L.append(f"  之後 120 日內再跌超過 10% 的比例：{sum(x < -0.10 for x in lo) / len(lo):.0%}")

    grp("全部", lambda r: True)
    grp("P/C 近 10 日曾 ≥ 80 百分位（法人留倉賣權多）", lambda r: r[1] is not None and r[1] >= 0.8)
    grp("P/C 近 10 日最高 < 30 百分位（今天的情況）", lambda r: r[1] is not None and r[1] < 0.3)
    grp("量比 ≥ 1.3", lambda r: r[2] is not None and r[2] >= 1.3)
    grp("量比 < 1.3", lambda r: r[2] is not None and r[2] < 1.3)
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究45_大跌後大漲.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
