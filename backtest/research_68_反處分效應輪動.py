"""研究 68：馬克羊「反處分效應」持股輪動——定期賣掉虧損的、留下賺錢的（≈ 個股動能）

宇宙：台股 50 大權值股（backtest/tw50，2026-11 的 0050 主要成分＝存活者名單；**存活者偏差**：絕對報酬偏高，只看策略間相對差異）
資料清理：Yahoo 還原價，單日 |報酬| > 11% 視為錯價改 0（台股有漲跌幅限制）
每次調整日（每季或每半年最後一個交易日）只納入已有 ≥ 126 個交易日歷史的股票；收盤成交
做法：
  EW     ：全部等權重（基準）
  反處分 ：持有「過去 L 個月報酬 > 0」的股票等權重（賣虧損留獲利）；全部都虧 → 現金
  動能前N：過去 L 個月報酬前 N 名等權重（N＝10、20）
  處分   ：過去 L 個月報酬後 N 名（一般散戶「賣贏留輸」的對照）
L＝3、6、12 個月；成本：每單位換手 0.6%（證交稅 0.3%＋手續費）；現金年息 1%
期間：2003-2026、2003-2012、2013-2026；另列 ^TWII＋3% 配息（≈0050）
用法：python -X utf8 backtest/research_68_反處分效應輪動.py
"""
import json
import math
import os
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
TW = timezone(timedelta(hours=8))
COST, CASH, TD = 0.006, 0.01, 245


def load_all():
    px = {}
    for f in sorted(os.listdir(os.path.join(HERE, "tw50"))):
        r = json.load(open(os.path.join(HERE, "tw50", f)))
        q = r["indicators"]["quote"][0]
        adj = r["indicators"]["adjclose"][0]["adjclose"]
        s = {}
        for t, a, v in zip(r["timestamp"], adj, q["volume"]):
            if a and v:
                s[datetime.fromtimestamp(t, TW).strftime("%Y-%m-%d")] = a
        px[f[:-5]] = s
    r = json.load(open(os.path.join(HERE, "TWII.json")))
    q = r["indicators"]["quote"][0]
    twii = {datetime.fromtimestamp(t, TW).strftime("%Y-%m-%d"): c for t, c in zip(r["timestamp"], q["close"]) if c}
    return px, twii


def main():
    px, twii = load_all()
    days = sorted(d for d in twii if d >= "2002-01-01")
    n = len(days)
    # 清理後的日報酬
    ret = {}
    for t, s in px.items():
        r = [None] * n
        last = None
        for i, d in enumerate(days):
            a = s.get(d)
            if a is None:
                if last is not None:
                    r[i] = 0.0  # 停牌視為 0
                continue
            if last is not None:
                x = a / last - 1
                r[i] = 0.0 if abs(x) > 0.11 else x
            last = a
        ret[t] = r
    cnt = {t: [0] * n for t in ret}
    for t, r in ret.items():
        c = 0
        for i in range(n):
            if r[i] is not None:
                c += 1
            cnt[t][i] = c
    tw_r = [0.0] + [twii[days[i]] / twii[days[i - 1]] - 1 + 0.03 / TD for i in range(1, n)]

    def growth(t, i0, i1):
        g = 1.0
        for k in range(i0 + 1, i1 + 1):
            x = ret[t][k]
            if x is None:
                return None
            g *= 1 + x
        return g - 1

    def rebal_days(freq):
        out = []
        for i in range(n - 1):
            m0, m1 = int(days[i][5:7]), int(days[i + 1][5:7])
            if m0 != m1 and m0 % freq == 0:
                out.append(i)
        return out

    def run(rule, L, freq, N, start, end):
        i0 = next(i for i, d in enumerate(days) if d >= start)
        i1 = max(i for i, d in enumerate(days) if d <= end)
        rb = set(rebal_days(freq))
        lb = int(L * 21)
        eq = peak = 1.0
        mdd = 0.0
        w = {}
        turn_total = 0.0
        for i in range(i0, i1 + 1):
            if i > i0:
                r = sum(wt * (ret[t][i] or 0.0) for t, wt in w.items()) + (1 - sum(w.values())) * CASH / TD
                eq *= 1 + r
                # 權重隨價格漂移
                tot = sum(wt * (1 + (ret[t][i] or 0.0)) for t, wt in w.items()) + (1 - sum(w.values())) * (1 + CASH / TD)
                w = {t: wt * (1 + (ret[t][i] or 0.0)) / tot for t, wt in w.items()}
            if i in rb or i == i0:
                elig = [t for t in ret if cnt[t][i] >= max(126, lb + 1) and ret[t][i] is not None]
                perf = {t: growth(t, i - lb, i) for t in elig}
                perf = {t: v for t, v in perf.items() if v is not None}
                if rule == "EW":
                    pick = list(perf)
                elif rule == "反處分":
                    pick = [t for t, v in perf.items() if v > 0]
                elif rule == "動能":
                    pick = sorted(perf, key=lambda t: -perf[t])[:N]
                else:  # 處分（輸家）
                    pick = sorted(perf, key=lambda t: perf[t])[:N]
                new = {t: 1 / len(pick) for t in pick} if pick else {}
                turn = sum(abs(new.get(t, 0) - w.get(t, 0)) for t in set(new) | set(w))
                turn_total += turn
                eq *= 1 - COST * turn / 2  # turn＝買＋賣權重變動合計；買賣一輪（turn＝2）扣 2×0.6%÷2… 即每賣出並買入 1 單位扣 0.6%
                w = new
            peak = max(peak, eq)
            mdd = min(mdd, eq / peak - 1)
        yrs = (i1 - i0) / TD
        return eq ** (1 / yrs) - 1, mdd, turn_total / yrs

    def twii_run(start, end):
        i0 = next(i for i, d in enumerate(days) if d >= start)
        i1 = max(i for i, d in enumerate(days) if d <= end)
        eq = peak = 1.0
        mdd = 0.0
        for i in range(i0 + 1, i1 + 1):
            eq *= 1 + tw_r[i]
            peak = max(peak, eq)
            mdd = min(mdd, eq / peak - 1)
        return eq ** (1 / ((i1 - i0) / TD)) - 1, mdd

    P = (("2003-01-01", "2026-12-31", "全期 2003-2026"), ("2003-01-01", "2012-12-31", "前段 2003-2012"), ("2013-01-01", "2026-12-31", "後段 2013-2026"))
    L = ["研究 68：反處分效應持股輪動（台股 50 大權值股，存活者名單——只看相對差異；成本每單位換手 0.6%）",
         "格式：年化／最大回檔；年換手（單位）",
         "\n加權指數＋3% 配息：" + "  ".join(f"{p[2]} {c:.1%}／{m:.1%}" for p in P for c, m in [twii_run(p[0], p[1])])]
    for freq, fn in ((3, "每季"), (6, "每半年")):
        L.append(f"\n==== 調整頻率：{fn} ====")
        base = {p[2]: run("EW", 6, freq, 0, p[0], p[1]) for p in P}
        L.append(f"{'EW 全部等權重':22s} " + " | ".join(f"{c:5.1%}／{m:6.1%}" for c, m, _t in base.values()) + f" | 換手 {list(base.values())[0][2]:.1f}")
        for lb in (3, 6, 12):
            for rule, N in (("反處分", 0), ("動能", 10), ("動能", 20), ("處分", 10)):
                res = [run(rule, lb, freq, N, p[0], p[1]) for p in P]
                nm = f"{rule}{'前' + str(N) if rule == '動能' else ('後' + str(N) if rule == '處分' else '')} 回看{lb}月"
                beat = all(r[0] > base[p[2]][0] for r, p in zip(res, P))
                L.append(f"{nm:22s} " + " | ".join(f"{c:5.1%}／{m:6.1%}" for c, m, _t in res) + f" | 換手 {res[0][2]:.1f}" + ("  ★三段都勝EW" if beat else ""))
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究68_反處分效應.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
