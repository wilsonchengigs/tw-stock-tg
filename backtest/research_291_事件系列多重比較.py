"""研究 291：事件／日曆系列（研究 280～290）多重比較彙整

一個 session 連做 11 題，每題各自挑最好的窗格，整體一定會有「看起來顯著」的。這裡把每題的「主要 p 值」
（每題的家族 p；沒有家族 p 的用最小單項 p × 該題檢定數，上限 1）列出，再做 Benjamini–Hochberg（FDR 10%）
與 Bonferroni，看哪些在全系列層級還站得住。p 值手抄自各題結果檔（見每列註）。
用法：python -X utf8 backtest/research_291_事件系列多重比較.py
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
# (研究, 主題, 主要發現, 主要 p, 來源說明)
ROWS = [
    (280, "國安基金進場", "5 日反彈（同急跌基準超額 +4.7%）", 0.0032, "同急跌安慰劑 p；只測 5 日一個主要窗格"),
    (281, "台海軍演", "5 日偏弱", min(1, 0.078 * 4), "4 窗格最小 p 0.078 ×4"),
    (282, "央行理監事會", "無", 1.0, "家族 p ≈1"),
    (283, "颱風休市", "休市前一天 -54 bp", 0.115, "家族 p"),
    (284, "MSCI 季度調整", "2013 後調整前一週偏強", 0.168, "全期家族 p（2013～ 0.068 為事後切段）"),
    (285, "千點整數關卡", "突破後略弱", min(1, 0.08 * 6), "6 檢定最小 p 0.08 ×6"),
    (286, "創新高之後", "與同動能日無差", 1.0, "無顯著窗格"),
    (287, "美國任期週期", "選後第 1 年 9/9 上漲", 0.020, "週期全距置換家族 p"),
    (288, "中國十一黃金週", "10 月 1～7 日偏強", 0.083, "12 個月份排名第 1 ≈1/12"),
    (289, "Fed 首次升降息", "首次升息後 20 日偏弱", min(1, 0.03 * 8), "8 檢定最小 p 0.03 ×8"),
    (290, "重大地震", "20 日偏弱", min(1, 0.097 * 4), "4 窗格最小 p 0.097 ×4"),
]


def main():
    m = len(ROWS)
    srt = sorted(ROWS, key=lambda r: r[3])
    # BH 調整後 q 值
    q = [0.0] * m
    prev = 1.0
    for k in range(m - 1, -1, -1):
        prev = min(prev, srt[k][3] * m / (k + 1))
        q[k] = prev
    out = ["研究 291：事件／日曆系列（280～290）多重比較\n",
           "研究  主題              主要 p    BH q    Bonferroni   發現（p 來源）"]
    for k, r in enumerate(srt):
        bonf = min(1, r[3] * m)
        flag = "✓" if q[k] <= 0.10 else " "
        out.append(f"{r[0]}  {r[1]:<14} {r[3]:7.4f}  {q[k]:6.3f}   {bonf:6.3f}     {flag} {r[2]}（{r[4]}）")
    out.append(f"\nBH FDR 10% 通過：{sum(x <= 0.10 for x in q)} 題；Bonferroni 0.05 通過：{sum(min(1, r[3] * m) <= 0.05 for r in srt)} 題（共 {m} 題）")
    text = "\n".join(out)
    print(text)
    with open(os.path.join(HERE, "結果_研究291_事件系列多重比較.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
