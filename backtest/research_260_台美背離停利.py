"""研究 260：D 台美背離加碼（背離 ≤-10% → 隔天 08:45 開盤進、抱 5 個交易日收盤出、持有中不重複）的停利／提前出場
方法同研究 211（台指期近月真實價、換月銜接、每筆扣 6 點）
出場變體：
  基準    抱 5 天收盤
  TPx     碰 +x%（日盤高點或當晚夜盤高點觸價、跳空開高用開盤價）就出；x＝2／3／4／5／7%
  CONV    持有中某天收盤背離 > -5%（已收斂）就當天收盤出，否則第 5 天
  EXT     抱到背離收斂（> -5%）的那天收盤，最少 5 天、最多 10 天
比較：每筆、勝率、累積；與基準的逐筆配對差（拔靴 5,000 次 p、只看 6 個變體的最小 p 要再 ×6 Bonferroni）
用法：python -X utf8 backtest/research_260_台美背離停利.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


R175 = load("r175", "research_175_加碼規則停損.py")
R205 = load("r205", "research_205_台美背離台指期部位.py")
COST = 3.0


def path(day, night, ds, j, m, last):
    """逐日回傳 (日索引, 開, 高, 低, 收, 夜盤高 or None)，價格換算成相對進場價的累積倍數"""
    e = day[ds[j]][m][0]
    acc, cost = 1.0, 2 * COST / e
    rows = []
    for t in range(j, last + 1):
        b = day[ds[t]].get(m)
        if not b:
            nm = next((x for x in sorted(day[ds[t]]) if x > m), None)
            pb = day[ds[t - 1]].get(m)
            if nm is None or pb is None or not day[ds[t - 1]].get(nm):
                break
            acc *= pb[3] / e
            m, e = nm, day[ds[t - 1]][nm][3]
            cost += 2.0 / e
            b = day[ds[t]][m]
        f = acc / e
        nh = None
        if t + 1 < len(ds):
            nb = night[ds[t + 1]].get(m)
            if nb and nb[4] >= 1000:
                nh = (nb[0] * f, nb[1] * f)
        rows.append((t, b[0] * f, b[1] * f, b[2] * f, b[3] * f, nh, cost))
    return rows


def run_tp(rows, tp, H=5):
    for k, (t, o, h, lo, c, nh, cost) in enumerate(rows[:H]):
        if tp:
            lvl = 1 + tp
            if k > 0 and o >= lvl:
                return o - 1 - cost
            if h >= lvl:
                return lvl - 1 - cost
        if k == min(H, len(rows)) - 1:
            return c - 1 - cost
        if tp and nh:
            if nh[0] >= lvl:
                return nh[0] - 1 - cost
            if nh[1] >= lvl:
                return lvl - 1 - cost
    t, o, h, lo, c, nh, cost = rows[-1]
    return c - 1 - cost


def run_conv(rows, g, ds, minH, maxH):
    for k, (t, o, h, lo, c, nh, cost) in enumerate(rows[:maxH]):
        if (k + 1 >= minH and g.get(ds[t], -1) > -0.05) or k == min(maxH, len(rows)) - 1:
            return c - 1 - cost, k + 1
    return rows[-1][4] - 1 - rows[-1][6], len(rows)


def main():
    dates, day, night, near = R175.R139.load_tx()
    bi = set(R175.R138.DAYS)
    ds = [d for d in dates if d in bi]
    n = len(ds)
    G = R205.GAP
    g = np.array([G.get(d, np.nan) for d in ds])
    ev, k = [], 0
    while k < n - 2:
        if g[k] <= -0.10:
            j = k + 1
            ev.append((j, near[ds[k]]))
            k = min(j + 4, n - 1) + 1
        else:
            k += 1
    V = {}
    hold = {}
    for j, m in ev:
        rows = path(day, night, ds, j, m, min(j + 9, n - 1))
        V.setdefault("基準 抱 5 天", []).append(run_tp(rows, None))
        for x in (0.02, 0.03, 0.04, 0.05, 0.07):
            V.setdefault(f"TP {x:.0%}", []).append(run_tp(rows, x))
        r, h = run_conv(rows, G, ds, 1, 5)
        V.setdefault("CONV 收斂就出", []).append(r)
        hold.setdefault("CONV", []).append(h)
        r, h = run_conv(rows, G, ds, 5, 10)
        V.setdefault("EXT 延長到收斂≤10天", []).append(r)
        hold.setdefault("EXT", []).append(h)
    V = {k: np.array(v) for k, v in V.items()}
    base = V["基準 抱 5 天"]
    rng = np.random.default_rng(260)
    out = [f"研究 260：D 台美背離加碼的停利／提前出場（{len(ev)} 筆，{ds[ev[0][0]]}～{ds[ev[-1][0]]}；台指期真實價、每筆扣 6 點）", ""]
    segs = (("全部", np.ones(len(ev), bool)), ("1998～2018-05", np.array([ds[j] < "2018-06" for j, _ in ev])), ("2018-06～", np.array([ds[j] >= "2018-06" for j, _ in ev])))
    for lab, msk in segs:
        out.append(f"== {lab}：{msk.sum()} 筆 ==")
        out.append(f"{'出場':<18s} {'每筆':>7s} {'勝率':>5s} {'最差':>7s} {'累積1x':>7s} {'配對差':>7s} {'p(較好)':>7s}")
        for nm, v in V.items():
            x = v[msk]
            d = x - base[msk]
            if nm.startswith("基準"):
                p = float("nan")
            else:
                bs = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(5000)])
                p = np.mean(bs <= 0)
            out.append(f"{nm:<18s} {x.mean():+7.2%} {np.mean(x > 0):5.0%} {x.min():+7.1%} {np.prod(1 + x) - 1:+7.0%} {d.mean():+7.2%} {p:7.3f}")
        out.append("")
    out.append(f"CONV 平均持有 {np.mean(hold['CONV']):.1f} 天、EXT 平均 {np.mean(hold['EXT']):.1f} 天")
    out.append("（p 是單一變體的單尾拔靴；6 個變體要看最小 p×6）")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究260_台美背離停利.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
