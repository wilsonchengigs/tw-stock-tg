"""研究 139：台指期日夜盤報酬拆解＋當夜操作的條件效果（使用者：研究當夜期貨的操作）

資料：backtest/tx_daily_ohlc.csv（期交所 TX 日行情，2017-05 起有夜盤；近月與換月規則同研究 63d）
期交所把 D-1 15:00 開始的夜盤記在 D 的 night 列。交易日 D 拆成四段（同一契約）：
- G1：D-1 日盤收盤 13:45 → 夜盤開盤 15:00
- N ：夜盤開盤 15:00 → 夜盤收盤 05:00
- G2：夜盤收盤 05:00 → D 日盤開盤 08:45
- DY：D 日盤開盤 08:45 → 收盤 13:45
當夜操作＝D-1 收盤後就知道的條件 → 夜盤開盤進場，出場兩種：
- 「夜收」＝夜盤收盤出（N），不留到早上
- 「早開」＝隔天日盤開盤出（N＋G2），抱過美股收盤
條件（D-1 收盤時已知）：日盤漲跌（開→收）、收盤對收盤漲跌、證交所成交金額倍數、v3 在場／空手、星期、結算日前後
顯著性：
- 無條件四段平均：定態區塊拔靴（平均區塊 20 天），p＝雙尾
- 條件效果：條件序列對報酬序列環狀平移 400 次（避開 ±20 天），比「條件日平均 − 全體平均」的絕對值；家族 p＝最小 p 值法（每次平移重算全家族的最小單組 p）
成本：每筆來回 3 點（手續費＋期交稅＋滑價，與研究 63d 相同）
用法：python -X utf8 backtest/research_139_日夜盤報酬拆解.py   （R139_SHIFTS 控制平移次數，預設 400）
"""
import importlib.util
import os
import sys
from datetime import date

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


import csv  # noqa: E402
from collections import defaultdict  # noqa: E402


def _num(x):
    try:
        return float(x)
    except ValueError:
        return None


def load_tx():
    """同研究 63d 的 load()：近月＝當天日盤量最大的月份，結算日改次月"""
    day, night = defaultdict(dict), defaultdict(dict)
    for r in csv.DictReader(open(os.path.join(HERE, "tx_daily_ohlc.csv"), encoding="utf-8")):
        o, h, lo, c, v = (_num(r[k]) for k in ("open", "high", "low", "close", "volume"))
        if c is None or o is None:
            continue
        (day if r["session"] == "day" else night)[r["date"]][r["month"]] = (o, h, lo, c, v or 0)
    dates = sorted(day)
    last_day = {}
    for d in dates:
        for m in day[d]:
            last_day[m] = d
    near = {}
    for d in dates:
        ms = sorted(day[d], key=lambda m: -day[d][m][4])
        m = ms[0]
        if last_day.get(m) == d and len(ms) > 1 and any(x > m for x in day[d]):
            m = sorted(x for x in day[d] if x > m)[0]
        near[d] = m
    return dates, day, night, near


_tv = list(csv.DictReader(open(os.path.join(HERE, "turnover_daily.csv"), encoding="utf-8")))
_amtcol = [k for k in _tv[0] if k != "date"][0]
AMT = {r["date"]: _num(r[_amtcol]) for r in _tv}
R138 = _load("r138", "research_138_金字塔加碼與分段停損.py")
COST = 3.0
V3 = dict(zip(R138.DAYS, R138.ST))


def build():
    dates, day, night, near = load_tx()
    rows = []
    for i in range(1, len(dates)):
        d, pd_ = dates[i], dates[i - 1]
        m = near[pd_]  # 夜盤開始時（D-1 收盤）的近月
        nb, prev, today = night[d].get(m), day[pd_].get(m), day[d].get(m)
        if nb is None or prev is None or today is None or nb[4] < 1000:
            continue
        pc, no, nc, do, dc = prev[3], nb[0], nb[3], today[0], today[3]
        pp = day[dates[i - 2]].get(m) if i >= 2 else None
        rows.append(dict(
            d=d, pd=pd_, pc=pc,
            G1=no / pc - 1, N=nc / no - 1, G2=do / nc - 1, DY=dc / do - 1,
            pday=prev[3] / prev[0] - 1,                         # D-1 日盤開→收
            pcc=(prev[3] / pp[3] - 1) if pp else None,          # D-1 收盤對收盤
            amt=AMT.get(pd_), v3=V3.get(pd_),
            wd=date.fromisoformat(pd_).weekday(),               # 夜盤開始那天的星期
            settle_eve=near[d] != m,                            # D 是 m 的結算日（隔天換月）
        ))
    # 成交金額倍數（前 20 日均）
    amts = [r["amt"] for r in rows]
    for k, r in enumerate(rows):
        xs = [a for a in amts[max(0, k - 20):k] if a]
        r["amtx"] = r["amt"] / (sum(xs) / len(xs)) if r["amt"] and len(xs) >= 16 else None
    return rows


def block_boot_mean(x, B=4000, L=20, seed=139):
    x = np.asarray(x)
    n = len(x)
    rng = np.random.default_rng(seed)
    mu = x.mean()
    out = np.empty(B)
    for b in range(B):
        new = rng.random(n) < 1.0 / L
        new[0] = True
        starts = rng.integers(0, n, n)
        seg = np.maximum.accumulate(np.where(new, np.arange(n), 0))
        out[b] = x[(starts[seg] + np.arange(n) - seg) % n].mean()
    p = (1 + np.sum(np.abs(out - mu) >= abs(mu))) / (B + 1)
    return mu, p


def main():
    S = int(os.environ.get("R139_SHIFTS", "400"))
    rows = build()
    n = len(rows)
    out = []
    p = out.append
    p(f"研究 139：台指期日夜盤報酬拆解＋當夜操作條件效果（{rows[0]['d']}～{rows[-1]['d']}，{n} 個有夜盤的交易日）")
    p("報酬為百分比；點數＝報酬×當時價位（約略）；成本每筆來回 3 點\n")

    p("== 一、無條件：四段各自的平均（區塊拔靴雙尾 p）==")
    halves = [("全期", rows), ("2017-2021", [r for r in rows if r["d"] < "2022"]), ("2022-2026", [r for r in rows if r["d"] >= "2022"])]
    for lab, rr in halves:
        parts = []
        for k in ("G1", "N", "G2", "DY"):
            mu, pv = block_boot_mean([r[k] for r in rr])
            pts = np.mean([r[k] * r["pc"] for r in rr])
            parts.append(f"{k} {mu:+.3%}（{pts:+.0f} 點, p {pv:.3f}）")
        p(f"{lab:10s} " + "  ".join(parts))
    for lab, rr in halves:
        on = [r for r in rr if r["v3"] == 1]
        off = [r for r in rr if r["v3"] == 0]
        p(f"{lab:10s} v3 在場 {len(on)} 天：" + "  ".join(f"{k} {np.mean([r[k] for r in on]):+.3%}" for k in ("G1", "N", "G2", "DY")) +
          f"｜空手 {len(off)} 天：" + "  ".join(f"{k} {np.mean([r[k] for r in off]):+.3%}" for k in ("G1", "N", "G2", "DY")))

    # 二、條件家族
    CONDS = {
        "前日盤跌≥1%": lambda r: r["pday"] <= -0.01,
        "前日盤跌≥2%": lambda r: r["pday"] <= -0.02,
        "前日盤漲≥1%": lambda r: r["pday"] >= 0.01,
        "前日盤漲≥2%": lambda r: r["pday"] >= 0.02,
        "前日收跌≥2%": lambda r: r["pcc"] is not None and r["pcc"] <= -0.02,
        "前日收漲≥2%": lambda r: r["pcc"] is not None and r["pcc"] >= 0.02,
        "爆量≥1.5x": lambda r: r["amtx"] is not None and r["amtx"] >= 1.5,
        "爆量≥1.5x且收黑": lambda r: r["amtx"] is not None and r["amtx"] >= 1.5 and r["pday"] < 0,
        "v3在場": lambda r: r["v3"] == 1,
        "v3空手": lambda r: r["v3"] == 0,
        "週五夜盤(跨週末)": lambda r: r["wd"] == 4,
        "結算日前夜": lambda r: r["settle_eve"],
    }
    TGT = {"夜收": lambda r: r["N"], "早開": lambda r: (1 + r["N"]) * (1 + r["G2"]) - 1}
    tests = [(c, t) for c in CONDS for t in TGT]
    Y = {t: np.array([f(r) for r in rows]) for t, f in TGT.items()}
    PX = np.array([r["pc"] for r in rows])
    Cm = {c: np.array([bool(f(r)) for r in rows]) for c, f in CONDS.items()}

    def stat(mask, y):
        return y[mask].mean() - y.mean() if mask.sum() else 0.0

    real = {(c, t): stat(Cm[c], Y[t]) for c, t in tests}
    rng = np.random.default_rng(139)
    shifts = rng.integers(20, n - 20, S)
    null = {k: np.empty(S) for k in tests}
    for s_i, s in enumerate(shifts):
        for c, t in tests:
            null[(c, t)][s_i] = stat(np.roll(Cm[c], s), Y[t])
    single = {k: (1 + np.sum(np.abs(null[k]) >= abs(real[k]))) / (S + 1) for k in tests}
    # 最小 p 值法：每次平移把該次的統計量當「實際」，算它在各自虛無分布的 p，取家族最小
    nullp = np.ones(S)
    for k in tests:
        a = np.abs(null[k])
        ranks = (1 + (a[None, :] >= a[:, None]).sum(axis=1)) / (S + 1)  # 每個平移在自己分布的 p
        nullp = np.minimum(nullp, ranks)
    fam = {k: (1 + np.sum(nullp <= single[k])) / (S + 1) for k in tests}

    p(f"\n== 二、當夜操作條件效果（夜盤開盤進；{len(tests)} 個檢定；環狀平移 {S} 次）==")
    p("欄位：次數｜條件日平均（扣成本前）｜比全體多（每筆點數，已扣 3 點成本後的做多/做空較佳方向）｜勝率｜單組 p｜家族 p")
    for c, t in tests:
        m = Cm[c]
        y = Y[t][m]
        pts = y * PX[m]
        side = 1 if y.mean() >= 0 else -1
        net = side * pts.mean() - COST
        win = np.mean(side * y > 0)
        sub = [Y[t][m & np.array([r["d"] < "2022" for r in rows])], Y[t][m & np.array([r["d"] >= "2022" for r in rows])]]
        p(f"{c:16s} {t} {m.sum():4d} 次  平均 {y.mean():+.3%}（全體 {Y[t].mean():+.3%}）  "
          f"{'做多' if side > 0 else '做空'}淨 {net:+6.1f} 點/筆  勝率 {win:.0%}  "
          f"前後段 {sub[0].mean() if len(sub[0]) else 0:+.3%}/{sub[1].mean() if len(sub[1]) else 0:+.3%}  "
          f"單組 p {single[(c, t)]:.3f}  家族 p {fam[(c, t)]:.3f}")

    # 三、夜盤內部：夜盤方向 → 隔天日盤（延續或反轉）
    p("\n== 三、夜盤走勢 → 隔天日盤（DY）==")
    for th in (0.005, 0.01, 0.02):
        up = [r["DY"] for r in rows if r["N"] >= th]
        dn = [r["DY"] for r in rows if r["N"] <= -th]
        p(f"夜盤漲≥{th:.1%}：{len(up)} 次，隔天日盤 {np.mean(up):+.3%}｜夜盤跌≥{th:.1%}：{len(dn)} 次，隔天日盤 {np.mean(dn):+.3%}（全體 {np.mean([r['DY'] for r in rows]):+.3%}）")
    g2 = np.array([r["G2"] for r in rows])
    nn = np.array([r["N"] for r in rows])
    dy = np.array([r["DY"] for r in rows])
    p(f"相關：N 對 G2 {np.corrcoef(nn, g2)[0, 1]:+.3f}、N 對 DY {np.corrcoef(nn, dy)[0, 1]:+.3f}、G2 對 DY {np.corrcoef(g2, dy)[0, 1]:+.3f}")

    # 三b、夜盤 → 隔天日盤反轉的家族檢定（隔天 08:45 開盤進、13:45 收盤出，逆夜盤方向）
    p("\n== 三b、夜盤大漲跌 → 隔天日盤逆勢（日盤開盤進收盤出；6 組；環狀平移家族檢定）==")
    fam3 = {}
    for th in (0.005, 0.01, 0.02):
        fam3[f"夜盤跌≥{th:.1%} 隔天日盤做多"] = (nn <= -th, 1)
        fam3[f"夜盤漲≥{th:.1%} 隔天日盤做空"] = (nn >= th, -1)
    real3 = {k: sd * (dy[m].mean() - dy.mean()) for k, (m, sd) in fam3.items()}
    null3 = {k: np.array([sd * (dy[np.roll(m, s)].mean() - dy.mean()) for s in shifts]) for k, (m, sd) in fam3.items()}
    single3 = {k: (1 + np.sum(null3[k] >= real3[k])) / (S + 1) for k in fam3}
    np3 = np.ones(S)
    for k in fam3:
        a = null3[k]
        np3 = np.minimum(np3, (1 + (a[None, :] >= a[:, None]).sum(axis=1)) / (S + 1))
    early = np.array([r["d"] < "2022" for r in rows])
    for k, (m, sd) in fam3.items():
        y = sd * dy[m]
        net = (y * PX[m]).mean() - COST
        fp = (1 + np.sum(np3 <= single3[k])) / (S + 1)
        p(f"{k:20s} {m.sum():4d} 次  每筆 {y.mean():+.3%}（淨 {net:+6.1f} 點）  勝率 {np.mean(y > 0):.0%}  "
          f"前後段 {(sd * dy[m & early]).mean():+.3%}/{(sd * dy[m & ~early]).mean():+.3%}  單組 p(單尾) {single3[k]:.3f}  家族 p {fp:.3f}")

    # 三c、夜盤大跌 → 隔天日盤做多 的穩健性
    p("\n== 三c、夜盤大跌 → 隔天日盤做多：鄰近門檻、去掉最大幾筆、逐年、依 v3 狀態 ==")
    v3a = np.array([r["v3"] == 1 for r in rows])
    yr = np.array([r["d"][:4] for r in rows])
    for th in (0.015, 0.02, 0.025, 0.03):
        m = nn <= -th
        y = dy[m]
        srt = np.sort(y)[::-1]
        p(f"夜盤跌≥{th:.1%}：{m.sum():3d} 次  每筆 {y.mean():+.3%}  中位 {np.median(y):+.3%}  勝率 {np.mean(y > 0):.0%}  "
          f"去掉最好 3 筆 {srt[3:].mean():+.3%}  v3在場 {dy[m & v3a].mean() if (m & v3a).any() else 0:+.3%}（{(m & v3a).sum()}）"
          f"  空手 {dy[m & ~v3a].mean() if (m & ~v3a).any() else 0:+.3%}（{(m & ~v3a).sum()}）")
    m = nn <= -0.02
    p("夜盤跌≥2% 逐年（次數／每筆）：" + "  ".join(f"{y_}:{(m & (yr == y_)).sum()}/{dy[m & (yr == y_)].mean():+.2%}" for y_ in sorted(set(yr[m]))))
    p("夜盤跌≥2% 明細：" + "  ".join(f"{rows[k]['d'][2:]}({nn[k]:+.1%}→{dy[k]:+.1%})" for k in np.where(m)[0]))
    # 對照：同一天開盤跳空（G2）與日盤，抄底是不是只是早上跳空的延續
    p(f"夜盤跌≥2% 隔天早上跳空 G2 平均 {g2[m].mean():+.3%}（全體 {g2.mean():+.3%}）")

    # 四、只抱夜盤 vs 只抱日盤 vs 全天（1 倍名目、每筆扣 3 點）
    p("\n== 四、1 倍名目資金曲線：只抱夜盤（15:00→05:00）／夜盤開→早開（15:00→08:45）／只抱日盤／全天抱 ==")
    G1a = np.array([r["G1"] for r in rows])
    cost = COST / PX
    yrs = n / 245
    for lab, rr in (("只抱夜盤", nn - cost), ("夜盤開→早開", (1 + nn) * (1 + g2) - 1 - cost), ("只抱日盤", dy - cost),
                    ("全天抱(不扣成本)", (1 + G1a) * (1 + nn) * (1 + g2) * (1 + dy) - 1)):
        eq = np.cumprod(1 + rr)
        mdd = (eq / np.maximum.accumulate(eq) - 1).min()
        sh = rr.mean() / rr.std() * np.sqrt(245)
        p(f"{lab:14s} 年化 {eq[-1] ** (1 / yrs) - 1:+6.1%}  最大回檔 {mdd:6.1%}  夏普 {sh:5.2f}")

    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究139_日夜盤報酬拆解.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
