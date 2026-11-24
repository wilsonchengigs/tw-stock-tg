"""研究 72：新台幣單日急貶／急升之後的台股（AI-1：海外／匯率；資料：中央銀行 BP01D01，台灣 16:00 銀行間即期，1993～）

匯率在台股收盤（13:30）後才定，所以訊號日 t 只能「隔天開盤」進場（另列 t 收盤→之後，代表夜盤附近進的上限）
事件：USD/TWD 日變動 ≥ +x（台幣急貶，外資匯出？）或 ≤ −x（台幣急升，資金流入），x＝0.5／0.8／1.0%；去叢集 5 日
報酬：加權指數 隔天開盤 → 第 1／5／10／20 日收盤；對照：所有日子同樣算法；拔靴 p；分 1998-2012／2013-2026、多空（> MA60）
另：做成交易（急貶隔天開盤買抱 10 天）＋隨機進場對照
用法：python -X utf8 backtest/research_72_台幣急貶急升.py
"""
import csv
import importlib.util
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r61", os.path.join(HERE, "research_61_爆量順勢短線.py"))
r61 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r61)
DAYS, O, C = r61.DAYS, r61.O, r61.C
N = len(DAYS)


def fmean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def main():
    fx = {r["date"]: float(r["twd"]) for r in csv.DictReader(open(os.path.join(HERE, "twd_cbc.csv"), encoding="utf-8"))}
    fxd = sorted(fx)
    chg = {fxd[i]: fx[fxd[i]] / fx[fxd[i - 1]] - 1 for i in range(1, len(fxd))}
    idx = {d: i for i, d in enumerate(DAYS)}
    ma60 = [None] * N
    for i in range(59, N):
        ma60[i] = sum(C[i - 59:i + 1]) / 60
    rng = random.Random(72)
    start = next(i for i, d in enumerate(DAYS) if d >= "1998-09-01")

    def fwd(i, h):
        e, x = i + 1, i + h
        return C[x] / O[e] - 1 if x < N else None

    base = {h: [x for i in range(start, N) if (x := fwd(i, h)) is not None] for h in (1, 5, 10, 20)}
    bm = {h: fmean(v) for h, v in base.items()}
    L = ["研究 72：台幣單日急貶／急升（央行 16:00 匯率）→ 加權指數隔天開盤起的報酬",
         "所有日子：" + "  ".join(f"{h}日 {bm[h]:+.2%}" for h in base)]
    for x in (0.005, 0.008, 0.01):
        for sign, nm in ((1, "台幣急貶"), (-1, "台幣急升")):
            ev, last = [], -99
            for d in DAYS[start:]:
                c = chg.get(d)
                i = idx[d]
                if c is not None and sign * c >= x:
                    if i - last > 5:
                        ev.append(i)
                    last = i
            L.append(f"\n== {nm} ≥{x:.1%}：{len(ev)} 次 ==")
            for lab, sel in (("全部", ev), ("1998-2012", [i for i in ev if DAYS[i] < "2013"]), ("2013-2026", [i for i in ev if DAYS[i] >= "2013"]),
                             ("多頭", [i for i in ev if ma60[i] and C[i] > ma60[i]]), ("空頭", [i for i in ev if ma60[i] and C[i] <= ma60[i]])):
                cells = []
                for h in (1, 5, 10, 20):
                    v = [y for i in sel if (y := fwd(i, h)) is not None]
                    if len(v) >= 5:
                        m_ = fmean(v)
                        sims = [fmean(rng.choices(base[h], k=len(v))) for _ in range(2000)]
                        p = (sum(abs(s - bm[h]) >= abs(m_ - bm[h]) for s in sims) + 1) / 2001
                        cells.append(f"{h}日 {m_:+.2%}（{sum(y > 0 for y in v) / len(v):.0%}，p {p:.2f}）")
                L.append(f"  {lab:9s} {len(sel):3d}  " + "  ".join(cells))
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究72_台幣急貶急升.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
