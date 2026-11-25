"""研究 159：v3 空手時，每晚 15:00 夜盤開盤買台指期、隔天 08:45 開盤平（只吃夜盤＋早上跳空），閒置資金能不能賺

研究 139：夜盤 N 每天 +0.05%、G2 +0.02%，日盤≈0；空手時 N +0.054%、G2 -0.011%
做法：v3 前一天收盤為空手 → 當晚 15:00 進 u 倍、隔天 08:45 出；每晚來回成本 3 點（另測 6 點）
指標：年化、最大回檔、區塊拔靴（平均區塊 20 天）平均每晚報酬 p；分段 2017–2021／2022–2026；對照：在場時同樣做
用法：python -X utf8 backtest/research_159_空手時只抱夜盤.py
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
    rows = R139.build()
    nn = np.array([(1 + r["N"]) * (1 + r["G2"]) - 1 for r in rows])
    px = np.array([r["pc"] for r in rows])
    off = np.array([r["v3"] == 0 for r in rows])
    on = np.array([r["v3"] == 1 for r in rows])
    early = np.array([r["d"] < "2022" for r in rows])
    out = [f"研究 159：只抱夜盤（15:00→隔天 08:45），{rows[0]['d']}～{rows[-1]['d']}", ""]
    for cost in (3.0, 6.0):
        for lab, msk in (("v3 空手時", off), ("v3 在場時", on), ("每天", np.ones(len(rows), bool))):
            r = np.where(msk, nn - cost / px, 0.0)
            e = np.cumprod(1 + r)
            yrs = len(r) / 245
            mdd = (e / np.maximum.accumulate(e) - 1).min()
            mu, p = R139.block_boot_mean(r[msk])
            seg = f"2017–21 {r[msk & early].mean():+.3%}／2022–26 {r[msk & ~early].mean():+.3%}"
            out.append(f"成本 {cost:.0f} 點  {lab:6s} {msk.sum():4d} 晚  1x 年化 {e[-1] ** (1 / yrs) - 1:+6.1%}  最大回檔 {mdd:6.1%}  每晚 {mu:+.3%}（p {p:.3f}）  {seg}")
        out.append("")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究159_空手時只抱夜盤.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
