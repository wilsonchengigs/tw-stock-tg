"""研究 194：恐慌隔天做多（P，已上線 1x）在熊市裡還一樣好嗎？（2026-11 P 連續觸發：11/20、11/23、11/25）

研究 148：連續觸發照做；研究 156：六段都正；研究 147：依跌幅分級沒資訊。沒拆過的是「市場已經跌多深」：
分組（訊號日前一天的加權收盤 vs 250 日最高收盤）：> -10%｜-10～-20%｜≤ -20%（熊市）；另依 20 日波動三分位
每組：筆數、每筆、中位、勝率、最差、比同波動非訊號日（研究 156 的對照法）、每單位風險（平均／標準差）、
單看凱利 f*≈平均／變異數（研究 170 的簡化版，只看相對大小）
交易：D 08:45 開盤進、D+1 08:45 開盤出、扣 3 點（研究 148 的 build）
用法：python -X utf8 backtest/research_194_恐慌做多在熊市.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r148", os.path.join(HERE, "research_148_恐慌連續觸發.py"))
R148 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R148)
import bt  # noqa: E402


def main():
    rows = R148.build()
    n = len(rows)
    px = dict(zip(bt.DAYS, bt.PX))
    days = bt.DAYS
    pos = {d: i for i, d in enumerate(days)}
    dd = np.full(n, np.nan)
    for k, x in enumerate(rows):
        i = pos.get(x["d"])
        if i is None or i < 251:
            continue
        p = bt.PX[i - 1]  # 訊號日（D）08:45 前已知的是前一天收盤
        dd[k] = p / max(bt.PX[i - 251:i]) - 1
    cc = np.array([0.0] + [rows[k]["c"] / rows[k - 1]["c"] - 1 for k in range(1, n)])
    vol = np.array([np.std(cc[max(1, k - 20):k]) if k > 5 else np.nan for k in range(n)])
    ok = ~np.isnan(vol) & ~np.isnan(dd)
    dec = np.digitize(vol, np.nanpercentile(vol, np.arange(10, 100, 10)))
    sig = np.array([x["sig"] for x in rows])
    r = np.array([x["r"] for x in rows])
    rng = np.random.default_rng(194)
    L = ["研究 194：恐慌隔天做多 依市場深度／波動分組（D 開→D+1 開、扣 3 點；1998～）"]

    def group(name, mask):
        idx = np.where(sig & ok & mask)[0]
        if len(idx) < 3:
            L.append(f"  {name}：{len(idx)} 筆（太少）")
            return
        pools = {k: np.where(~sig & ok & (dec == dec[k]))[0] for k in idx}
        diff = np.mean([r[k] - r[pools[k]].mean() for k in idx])
        null = np.array([np.mean([r[rng.choice(pools[k])] - r[pools[k]].mean() for k in idx]) for _ in range(2000)])
        pv = (1 + np.sum(null >= diff)) / 2001
        m, s = r[idx].mean(), r[idx].std()
        L.append(f"  {name}：{len(idx):3d} 筆  每筆 {m:+.2%}  中位 {np.median(r[idx]):+.2%}  勝率 {np.mean(r[idx] > 0):.0%}  "
                 f"最差 {r[idx].min():+.1%}  最好 {r[idx].max():+.1%}  標準差 {s:.2%}  平均/標準差 {m / s:+.2f}  f*≈{m / s ** 2:.1f}x  "
                 f"比同波動 {diff:+.2%}（p {pv:.3f}）")

    for seg, segmask in (("全期 1998～", np.ones(n, bool)), ("2017-05～（有夜盤）", np.array([x["d"] >= "2017-05-15" for x in rows])),
                         ("1998～2017-05", np.array([x["d"] < "2017-05-15" for x in rows]))):
        L.append(f"\n【{seg}】依離 250 日高")
        group("> -10%（正常）", segmask & (dd > -0.10))
        group("-10～-20%（修正）", segmask & (dd <= -0.10) & (dd > -0.20))
        group("≤ -20%（熊市）", segmask & (dd <= -0.20))
        q1, q2 = np.nanpercentile(vol[sig & ok], [33, 67])
        L.append(f"  依 20 日波動（訊號日三分位）")
        group("低波動", segmask & (vol <= q1))
        group("中波動", segmask & (vol > q1) & (vol <= q2))
        group("高波動", segmask & (vol > q2))
    idx = np.where(sig & ok & (dd <= -0.20))[0]
    L.append("\n熊市（≤-20%）每筆：" + "、".join(f"{rows[k]['d']} {r[k]:+.1%}" for k in idx))
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究194_恐慌做多在熊市.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
