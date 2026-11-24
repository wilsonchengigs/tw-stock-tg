"""研究 104：有目標年限（6 年）的存錢計畫——最後幾年降槓桿（glide path）是否值得
情境：起始 100 萬，每月存 100/12 萬，6 年；v3 策略（2002～2026，2015-09 起真實價格無法分槓桿，這裡全用模擬價格以便比較各槓桿）
比較：
- 全程 2x
- 第 6 年 1x（前 5 年 2x）
- 第 5 年 1.5x、第 6 年 1x
- 全程 1.5x、全程 1x
每個月初起算的 6 年窗口（2002-01～2020-11），看期末資產分布（中位、最差 5%、最差）與期末前 1 年內最大的帳面回檔
用法：python -X utf8 backtest/research_104_目標期降槓桿.py
"""
import importlib.util
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("v3", os.path.join(HERE, "strategy_v3.py"))
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)
DAYS = V.DAYS
i0 = next(i for i, d in enumerate(DAYS) if d >= "2002-01-01")
CUR = {lev: V.run("2002-01-01", "2026-12-31", lev=lev, curve=True)[2] for lev in (1.0, 1.5, 2.0)}
n = min(len(c) for c in CUR.values())
days = DAYS[i0:i0 + n]
month_starts = [k for k in range(1, n) if days[k][:7] != days[k - 1][:7]]
PLANS = {
    "全程 2x": [2.0] * 6,
    "第 6 年 1x": [2.0] * 5 + [1.0],
    "第 5 年 1.5x、第 6 年 1x": [2.0] * 4 + [1.5, 1.0],
    "最後 2 年 1x": [2.0] * 4 + [1.0, 1.0],
    "全程 1.5x": [1.5] * 6,
    "全程 1x": [1.0] * 6,
}


def simulate(k0, plan):
    """回傳 (期末資產, 最後一年內的最大帳面回檔)"""
    val = 100.0
    peak_last, mdd_last = 0.0, 0.0
    end = k0 + 6 * 245
    ms = [k for k in month_starts if k0 <= k < end]
    for k in range(k0 + 1, end + 1):
        yr = min((k - k0) // 245, 5)
        c = CUR[plan[yr]]
        val *= c[k] / c[k - 1]
        if k in ms:
            val += 100 / 12
        if yr == 5:
            peak_last = max(peak_last, val)
            mdd_last = min(mdd_last, val / peak_last - 1)
    return val, mdd_last


def main():
    starts = [k for k in month_starts if k + 6 * 245 < n]
    L = [f"研究 104：6 年存錢計畫（100 萬起、每月 8.33 萬，總投入 700 萬；{len(starts)} 個起點 {days[starts[0]][:7]}～{days[starts[-1]][:7]}）",
         "計畫 | 期末中位 | 最差 5% | 最差 | 低於 700 萬機率 | 最後一年帳面回檔（中位／最差）"]
    for nm, plan in PLANS.items():
        res = [simulate(k, plan) for k in starts]
        vals = sorted(v for v, _ in res)
        dds = sorted(d for _, d in res)
        L.append(f"{nm:22s} | {vals[len(vals) // 2]:6.0f} 萬 | {vals[int(.05 * len(vals))]:6.0f} | {vals[0]:6.0f} | {sum(v < 700 for v in vals) / len(vals):4.0%} | {dds[len(dds) // 2]:6.1%}／{dds[0]:6.1%}")
        print(L[-1], flush=True)
    out = "\n".join(L) + "\n"
    open(os.path.join(HERE, "結果_研究104_目標期降槓桿.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
