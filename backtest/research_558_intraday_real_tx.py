"""研究 558：最終版日內順勢（D30＋E 09:30～12:30、反向 0.75% 停損、13:25 出、成本 3 點）用台指期真實 1 分 K 驗證
tx_1min.csv 日盤（2026-10～11，約 31 天；這段主策略空手、台指 VIX 高＝候選規則的條件格）；同日加權 1 分 K 對照
逐日列出：方向、進場時間、台指期報酬、加權報酬
用法：python -X utf8 backtest/research_558_intraday_real_tx.py
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_522_intraday_trend_robust as M
from research_531_intraday_by_main_state import trade


def detail(a):
    o = M.at(a, 5); mins = a[:, 0].astype(int); cl = a[:, 1]; cand = []
    tr = M.at(a, 90) / o - 1
    if abs(tr) >= 0.005:
        cand.append((90, 1 if tr > 0 else -1))
    idx = np.nonzero((mins >= 30) & (mins <= 210) & (np.abs(cl / o - 1) >= 0.01))[0]
    if len(idx):
        cand.append((int(mins[idx[0]]), 1 if cl[idx[0]] > o else -1))
    return min(cand) if cand else None


def main():
    tx = M.load_tx(); idx = M.load_idx()
    out = [__doc__]
    rt = []; ri = []
    for d in sorted(tx):
        a = tx[d]; t = trade(a); di = detail(a)
        b = idx.get(d); ti = trade(b) if b is not None else None
        if t or ti:
            mm = f"{(di[0]+540)//60:02d}:{(di[0]+540)%60:02d}" if di else "-"
            out.append(f"  {d} 台指期：{('多' if t and t[0]>0 else '空') if t else '－'} {mm} {t[1] if t else 0:+.2f}%｜加權：{('多' if ti and ti[0]>0 else '空') if ti else '－'} {ti[1] if ti else 0:+.2f}%")
            if t: rt.append(t[1])
            if ti: ri.append(ti[1])
    rt = np.array(rt); ri = np.array(ri)
    out.append(f"台指期 {len(tx)} 天：{len(rt)} 筆 每筆 {rt.mean():+.3f}% 勝率 {(rt>0).mean()*100:.0f}% 合計 {rt.sum():+.2f}%")
    out.append(f"同期加權：{len(ri)} 筆 每筆 {ri.mean():+.3f}% 勝率 {(ri>0).mean()*100:.0f}% 合計 {ri.sum():+.2f}%")
    out.append(f"對照：回測期望（空手＋VIX≥18）每筆 +0.24%、勝率 61%；31 天、約 20 筆的標準誤約 ±0.2%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究558_日內台指期實測.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
