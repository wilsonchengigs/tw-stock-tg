"""研究 193：「現在算熊市嗎？」——加權從 250 日高點跌破 -20%（常見熊市定義）之後的歷史（使用者 2026-11-26 問）

事件：收盤首次 ≤ 近 250 日最高收盤 ×0.8（之後要先回到 -10% 以內才算新事件）；資料 1990～（taiex_1990_1997＋Yahoo）
看：之後再跌多少才見底、跌了多少天、事件後 1／3／6／12 月報酬、多久回到事件前高點；
分兩類：「V 轉」（事件後再跌 < 10%）vs「真熊市」（再跌 ≥ 10%）
用法：python -X utf8 backtest/research_193_跌破熊市線之後.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r187", os.path.join(HERE, "research_187_高波動來回刷.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
D, P = R.D, R.P0
N = len(P)


def main():
    L = ["研究 193：加權跌破「250 日高點 -20%」之後（1990～）"]
    hi = [max(P[max(0, i - 249):i + 1]) for i in range(N)]
    i = N - 1
    k = max(range(max(0, i - 249), i + 1), key=lambda j: P[j])
    L.append(f"現況 {D[i]}：收 {P[i]:,.0f}，250 日高點 {D[k]} {P[k]:,.0f}，跌 {P[i] / P[k] - 1:+.1%}")
    ev, armed = [], True
    for j in range(250, N):
        dd = P[j] / hi[j] - 1
        if armed and dd <= -0.2:
            ev.append(j)
            armed = False
        elif not armed and dd > -0.1:
            armed = True
    L.append(f"\n事件 {len(ev)} 次（日期｜當時跌幅｜之後再跌到底｜到底天數｜1/3/6/12 月｜回到前高天數）")
    rows = []
    for j in ev:
        pk = hi[j]
        # 底：回到前高之前的最低點（沒回到就到資料結束）
        back = next((t for t in range(j + 1, N) if P[t] >= pk), None)
        end = back if back else N - 1
        b = min(range(j, end + 1), key=lambda t: P[t])
        f = {m: (P[j + m * 21] / P[j] - 1 if j + m * 21 < N else None) for m in (1, 3, 6, 12)}
        more = P[b] / P[j] - 1
        rows.append((j, more, b - j, f, (back - j) if back else None))
        L.append(f"  {D[j]}  {P[j] / pk - 1:+.0%}｜再跌 {more:+5.0%}｜{b - j:>4} 天｜" + " ".join(f"{v:+5.0%}" if v is not None else "  —  " for v in f.values())
                 + f"｜{(str(back - j) + ' 天') if back else '還沒回到'}")
    done = [r for r in rows if r[0] < N - 260]
    for name, g in (("全部", done), ("V 轉（之後再跌 <10%）", [r for r in done if r[1] > -0.10]), ("真熊市（再跌 ≥10%）", [r for r in done if r[1] <= -0.10])):
        if not g:
            continue
        L.append(f"\n【{name}】{len(g)} 次")
        m = sorted(r[1] for r in g)
        L.append(f"  之後再跌：中位 {m[len(m) // 2]:+.0%}、最多 {m[0]:+.0%}；到底天數中位 {sorted(r[2] for r in g)[len(g) // 2]}")
        for mm in (1, 3, 6, 12):
            v = [r[3][mm] for r in g if r[3][mm] is not None]
            L.append(f"  {mm:>2} 個月後：上漲 {sum(x > 0 for x in v) / len(v):.0%}、中位 {sorted(v)[len(v) // 2]:+.0%}、最差 {min(v):+.0%}、最好 {max(v):+.0%}")
        bk = sorted(r[4] for r in g if r[4])
        L.append(f"  回到前高：{len(bk)}/{len(g)} 次有回到，天數中位 {bk[len(bk) // 2] if bk else '—'}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究193_跌破熊市線之後.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
