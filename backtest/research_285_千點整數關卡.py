"""研究 285：加權千點整數關卡

事件：收盤上穿（前一日收盤 < k×1000 ≤ 今日收盤）或下穿千點整數；事件後 1／5／20 個交易日加權報酬（bp）。
問題：整數關卡是否有「突破後追價」或「壓力／支撐」效果？
安慰劑：把格線平移 o 點（o＝10、20…990，即 k×1000＋o），同樣規則算一次——平移後的格線沒有心理意義，
  但事件頻率、所處行情都一樣。真正整數（o＝0）的統計量在 100 個偏移裡排第幾＝排名 p（雙尾）。
  千點級距在指數低時（2001 年 3,500 點）相對很寬、2026 年 4 萬點時很窄，所以另做「千點佔指數 ≥4%」（指數 <25,000）分段。
另測萬點（10,000／20,000／30,000…）只列事件，樣本太少不檢定。
用法：python -X utf8 backtest/research_285_千點整數關卡.py
"""
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strategy_v3 as s  # noqa: E402

DAYS, PX, N = s.DAYS, s.PX, s.N
HS = (1, 5, 20)


def events(off, step=1000, start="2000-01-01", cap=None):
    up, dn = [], []
    for i in range(1, N - 20):
        if DAYS[i] < start or (cap and PX[i] >= cap):
            continue
        a, b = PX[i - 1] - off, PX[i] - off
        if a // step < b // step:
            up.append(i)
        elif a // step > b // step:
            dn.append(i)
    return up, dn


def fwd(i, h):
    return (PX[i + h] / PX[i] - 1) * 1e4


def main():
    out = []
    p = out.append
    p("研究 285：加權千點整數關卡（2000～，收盤穿越當天收盤起算，bp）\n")
    base = {h: statistics.mean(fwd(i, h) for i in range(1, N - 20) if DAYS[i] >= "2000") for h in HS}
    p("全部日子基準：" + "  ".join(f"{h}日 {base[h]:+.1f}" for h in HS) + "\n")
    for label, cap in (("全部", None), ("指數 <25,000（千點 ≥4%）", 25000)):
        p(f"【{label}】")
        stat = {}  # off -> {(dir,h): mean}
        for off in range(0, 1000, 10):
            up, dn = events(off, cap=cap)
            stat[off] = {("上穿", h): statistics.mean(fwd(i, h) for i in up) for h in HS}
            stat[off].update({("下穿", h): statistics.mean(fwd(i, h) for i in dn) for h in HS})
            stat[off]["n"] = (len(up), len(dn))
        n_up, n_dn = stat[0]["n"]
        p(f"整數格線事件：上穿 {n_up} 次、下穿 {n_dn} 次（各偏移次數 {min(v['n'][0] for v in stat.values())}～{max(v['n'][0] for v in stat.values())}）")
        p("方向 天期   整數(o=0)   平移格線 平均/最小/最大     排名(高→低)/100  雙尾 p")
        for d in ("上穿", "下穿"):
            for h in HS:
                vals = [stat[o][(d, h)] for o in stat]
                v0 = stat[0][(d, h)]
                others = vals[1:]
                rank = 1 + sum(x > v0 for x in others)
                p2 = min(1.0, 2 * min(rank, len(vals) + 1 - rank) / len(vals))
                p(f"{d} {h:>3}日   {v0:+8.1f}    {statistics.mean(others):+7.1f} {min(others):+7.1f} {max(others):+7.1f}        {rank:>2}            {p2:.2f}")
        p("")
    # 萬點
    up, dn = events(0, step=10000)
    p("萬點關卡（2000～）：")
    for d, lst in (("上穿", up), ("下穿", dn)):
        for i in lst:
            p(f"  {d} {DAYS[i]} 收 {PX[i]:,.0f}  " + "  ".join(f"{h}日 {fwd(i, h):+.0f}" for h in HS))
    text = "\n".join(out)
    print(text)
    with open(os.path.join(HERE, "結果_研究285_千點整數關卡.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
