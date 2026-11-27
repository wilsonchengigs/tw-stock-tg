"""研究 555：V（抱 10 天）與 D（抱 5 天）持有期間報酬拆成「白天（08:45→13:45）」與「晚上（13:45→隔天 08:45）」
V：研究 411 的 vsig（在場）→ 隔天 08:45 進、抱 10 個交易日（不含停損，簡化）；D：研究 552 的訊號 → 隔天 08:45 進、第 5 天 13:45 出
用台指期近月（同一合約，遇換月就停在換月前）；只抱夜版本每晚成本 3 點、連抱版本進出一次 3 點
用法：python -X utf8 backtest/research_555_VD_night_day_split.py
"""
import io, contextlib, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_411_實際配置含V as A
from research_514_pattern_regime import yahoo
from research_544_overnight_vs_day import load


def split(b, ds, k0, n):
    """從 ds[k0] 08:45 進，抱 n 個交易日到 ds[k0+n-1] 13:45；回傳 (白天合計, 晚上合計, 連抱, 只抱夜扣成本, 只抱白天扣成本)"""
    seq = ds[k0:k0 + n]
    if len(seq) < n or len(set(b[x][1] for x in seq)) > 1:
        return None
    px0 = b[seq[0]][2]
    day = sum(b[x][3] / b[x][2] - 1 for x in seq)
    night = sum(b[seq[i + 1]][2] / b[seq[i]][3] - 1 for i in range(n - 1))
    hold = b[seq[-1]][3] / px0 - 1 - 3 / px0
    return day, night, hold, night - (n - 1) * 3 / px0, day - n * 3 / px0


def main():
    b = load(); ds = sorted(b); pos = {d: i for i, d in enumerate(ds)}
    out = [__doc__]
    vdays = [d for d, sg, s in zip(A.ds, A.vsig, A.st) if sg and s == 1]
    tw = yahoo("TWII.json"); spx = yahoo("GSPC.json"); tk = sorted(tw); sk = np.array(sorted(spx))
    dsig = []; hold_until = ""
    for i in range(20, len(tk)):
        d = tk[i]
        if d <= hold_until:
            continue
        j = np.searchsorted(sk, d) - 1
        if j >= 20 and tw[d] / tw[tk[i - 20]] - spx[sk[j]] / spx[sk[j - 20]] <= -0.10:
            dsig.append(d); hold_until = tk[min(i + 5, len(tk) - 1)]
    for name, sig, n in (("V（10 天）", vdays, 10), ("D（5 天）", dsig, 5)):
        rows = []
        for d in sig:
            if d in pos and pos[d] + 1 < len(ds):
                r = split(b, ds, pos[d] + 1, n)
                if r:
                    rows.append(r)
        x = np.array(rows) * 100
        out.append(f"{name}：{len(x)} 筆（換月的略過）")
        for j, lab in enumerate(("白天合計", "晚上合計", "連抱（現行）", "只抱夜（扣每晚成本）", "只抱白天（扣每天成本）")):
            out.append(f"   {lab:14s} 每筆 {x[:, j].mean():+.3f}% 標準差 {x[:, j].std():.2f}% 勝率 {(x[:, j]>0).mean()*100:.0f}%")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究555_VD日夜拆解.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
