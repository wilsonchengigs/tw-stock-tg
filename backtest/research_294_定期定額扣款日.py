"""研究 294：定期定額扣款日的台股報酬

假說：券商定期定額常見扣款日每月 6／16／26 日（遇假日順延到下一個交易日），2021 年後 0050／高股息 ETF 定期定額帳戶暴增，
扣款日（或隔天）可能有固定買盤、加權偏強；若是真的，效應應該只在 2021 後出現。
做法：D＝每月 k、k+10、k+20 日當天或之後的第一個交易日（k＝6 為真正的扣款日格線）；看 D 當天、D+1 的加權日報酬（收盤對收盤，bp）
  與非 D 日的差；安慰劑＝k＝1～10 共 10 條格線（同樣每 10 天一次），真格線 k＝6 的排名；
  也看 k＝3、8（另一批券商：3／13／23、8／18／28）。分 2000–2012、2013–2020、2021～
用法：python -X utf8 backtest/research_294_定期定額扣款日.py
"""
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strategy_v3 as s  # noqa: E402

DAYS, PX, N = s.DAYS, s.PX, s.N
R = [None] + [(PX[i] / PX[i - 1] - 1) * 1e4 for i in range(1, N)]


def anchors(k, lo, hi):
    """每月 k、k+10、k+20 日當天或之後第一個交易日的索引（同月內）"""
    out = set()
    months = sorted({d[:7] for d in DAYS if lo <= d[:4] <= hi})
    for m in months:
        for dd in (k, k + 10, k + 20):
            if dd > 28:
                continue
            tgt = f"{m}-{dd:02d}"
            i = next((i for i, d in enumerate(DAYS) if d >= tgt), None)
            if i is not None and DAYS[i][:7] == m:
                out.add(i)
    return out


def main():
    out = []
    p = out.append
    p("研究 294：定期定額扣款日（每月 k／k+10／k+20 日起第一個交易日）加權日報酬（bp）\n")
    for lo, hi in (("2000", "2012"), ("2013", "2020"), ("2021", "2026")):
        idx = [i for i in range(1, N) if lo <= DAYS[i][:4] <= hi]
        base = statistics.mean(R[i] for i in idx)
        p(f"【{lo}–{hi}】全部日子平均 {base:+.1f} bp（{len(idx)} 天）")
        p("  k   D 當天 平均(差)       D+1 平均(差)      D 與 D+1 合計差")
        res = {}
        for k in range(1, 11):
            a = anchors(k, lo, hi)
            d0 = [R[i] for i in a if lo <= DAYS[i][:4] <= hi]
            d1 = [R[i + 1] for i in a if i + 1 < N and lo <= DAYS[i + 1][:4] <= hi]
            res[k] = (statistics.mean(d0) - base, statistics.mean(d1) - base)
            tag = "  ← 6／16／26" if k == 6 else ("  ← 3／13／23" if k == 3 else ("  ← 8／18／28" if k == 8 else ""))
            p(f"  {k:>2}  {statistics.mean(d0):+6.1f}({res[k][0]:+5.1f})    {statistics.mean(d1):+6.1f}({res[k][1]:+5.1f})    {res[k][0] + res[k][1]:+6.1f}{tag}")
        tot = {k: v[0] + v[1] for k, v in res.items()}
        rank = 1 + sum(tot[k] > tot[6] for k in tot if k != 6)
        p(f"  k＝6 合計差排名 {rank}/10\n")
    text = "\n".join(out)
    print(text)
    with open(os.path.join(HERE, "結果_研究294_定期定額扣款日.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
