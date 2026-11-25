"""研究 138：投顧簡報「金字塔加碼＋動態停利＋分段停損」套到 v3（使用者提問）

v3 的進出場訊號（含每天檢查融資過熱）完全不動，只改「在場時押多少」：
- P 金字塔進場：訊號成立先押 f1（佔滿倉 2x 的比例），正2 價格比上一手漲 a 才加下一手，共 3 手（f1、(1-f1)/2、(1-f1)/2）
- R 移動停利：跌破「最近一次加碼價」×(1-r) 就退掉最後一手（停止加碼），之後再漲回 a 可重新加
- S 分段停損：正2 價格相對平均成本虧 s1／s2／s3 → 部位降到 3/4、1/2、0（本輪訊號內不再補回，直到 v3 出場後重新進場）
- T 分段停利：相對第一手成本漲 t1 賣 1/4、漲 t2 再賣 1/4（賣掉的放現金到本輪結束）；"本金" 版＝漲 t1 時賣到收回原始投入
規則每天收盤檢查、隔天收盤成交，成本同 v3（每換手 1 單位曝險 0.25%）

顯著性：
- 每組與 v3 的「每日報酬差」做定態區塊拔靴（Politis–Romano，平均區塊 60 日，B 次），單組 p＝P(差的平均 ≤ 0)
- 家族：全部組一起拔靴（同一組區塊索引），Romano–Wolf / White 最大 t 統計 → 家族 p
- 另外比「同平均曝險的 v3」（v3 lev 縮到該組平均曝險）：看是規則本身有用，還是只是押比較少
用法：python -X utf8 backtest/research_138_金字塔加碼與分段停損.py   （R138_B 控制拔靴次數，預設 2000）
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strategy_v3 as V  # noqa: E402

bt, DAYS, PX, N, WE = V.bt, V.DAYS, V.PX, V.N, V.WE
M60, M80, DEV, Z = V.M60, V.M80, V.DEV, V.Z
PER = V.PER + [V.REAL]


def v3_states():
    """每天收盤後 v3 的目標狀態（1 在場／0 空手），與 V.run 預設參數一致"""
    st = [0] * N
    state, heat_out = 0, False
    for i in range(N):
        if i >= 260 and not WE[i] and state == 1 and V.hot_at(i):
            state, heat_out = 0, True
        elif WE[i] and i >= 260:
            hot = V.hot_at(i)
            p = PX[i]
            above = p >= M80[i] * 0.975
            if state == 0:
                if heat_out and not above:
                    heat_out = False
                cooled = DEV[i] is None or (DEV[i] < 0.125 and Z[i] <= 2.0)
                if (p > M60[i] * 1.01 and not hot) or (heat_out and cooled and above):
                    state, heat_out = 1, False
            elif hot:
                state, heat_out = 0, True
            elif not above:
                state, heat_out = 0, False
        st[i] = state
    return st


ST = v3_states()


def make_sizer(f1=1.0, a=None, r=None, stops=None, tps=None, principal=None):
    """回傳 sizer(i, on, px, ctx) -> 目標曝險佔滿倉比例（0～1）；px＝正2 價格指數"""
    tr = [f1, (1 - f1) / 2, (1 - f1) / 2] if a is not None else [1.0]

    def f(i, on, px, ctx):
        if not on:
            ctx.clear()
            return 0.0
        if not ctx:  # 新一輪進場
            ctx.update(k=1, last=px, adds=[px], cost=px, first=px, cut=1.0, sold=0.0, tpn=0, units=tr[0] / px)
        # 金字塔加碼／移動停利
        if a is not None:
            if ctx["k"] < len(tr) and px >= ctx["last"] * (1 + a):
                ctx["units"] += tr[ctx["k"]] / px
                ctx["k"] += 1
                ctx["last"] = px
                ctx["adds"].append(px)
            elif r is not None and ctx["k"] > 1 and px < ctx["last"] * (1 - r):
                ctx["k"] -= 1
                ctx["units"] -= tr[ctx["k"]] / ctx["adds"].pop()
                ctx["last"] = ctx["adds"][-1]  # 退回上一手的加碼價
            base = sum(tr[:ctx["k"]])
            ctx["cost"] = base / ctx["units"] if ctx["units"] > 0 else px
        else:
            base = 1.0
        # 分段停損（相對平均成本）
        if stops:
            loss = px / ctx["cost"] - 1
            for th, keep in zip(stops, (0.75, 0.5, 0.0)):
                if loss <= -th:
                    ctx["cut"] = min(ctx["cut"], keep)
        # 分段停利（相對第一手成本）
        if tps:
            g = px / ctx["first"] - 1
            while ctx["tpn"] < len(tps) and g >= tps[ctx["tpn"]]:
                ctx["sold"] += 0.25
                ctx["tpn"] += 1
        if principal is not None and ctx["tpn"] == 0 and px / ctx["first"] - 1 >= principal:
            ctx["sold"] = 1 / (1 + principal)  # 賣出市值＝原始投入
            ctx["tpn"] = 1
        return max(0.0, base * ctx["cut"] * (1 - ctx["sold"]))
    return f


def run(sizer, start, end, real=False, lev=2.0):
    """回傳 (年化, 最大回檔, 每日報酬 list, 平均曝險)"""
    r1 = V.R1R if real else bt.R1
    r2 = V.R2R if real else bt.R2
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, cur, pend, px2, ctx = 0.0, 0.0, None, 1.0, {}
    rets, expo = [], 0.0

    def ret(i, L):
        if L <= 0:
            return bt.RC
        if L <= 1:
            return L * r1[i] + (1 - L) * bt.RC
        return (L - 1) * r2[i] + (2 - L) * r1[i]

    for i in range(i0, i1 + 1):
        px2 *= 1 + r2[i]
        d = 1.0
        if i > i0:
            d *= 1 + ret(i, cur)
        if pend is not None:
            d *= 1 - bt.COST * abs(pend - cur)
            cur, pend = pend, None
        eq *= d
        rets.append(d - 1)
        expo += cur
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        t = round(lev * sizer(i, ST[i] == 1, px2, ctx), 6)
        if abs(t - cur) > 1e-9:
            pend = t
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, rets, expo / (i1 - i0 + 1)


FULL = make_sizer()
FAMILY = {}
for f1 in (1 / 3, 0.5):
    for a in (0.03, 0.05, 0.10):
        for r in (None, 0.0, 0.03):
            FAMILY[f"P f1={f1:.2f} a={a:.0%} r={'無' if r is None else f'{r:.0%}'}"] = make_sizer(f1, a, r)
for s in ((0.08, 0.15, 0.25), (0.10, 0.20, 0.30), (0.05, 0.10, 0.15)):
    FAMILY[f"S 停損 {'/'.join(f'{x:.0%}' for x in s)}"] = make_sizer(stops=s)
for t in ((0.40,), (0.40, 0.80), (0.20, 0.40)):
    FAMILY[f"T 停利 {'/'.join(f'{x:.0%}' for x in t)} 各賣1/4"] = make_sizer(tps=t)
FAMILY["T 漲40%收回本金"] = make_sizer(principal=0.40)
FAMILY["簡報全套 P1/3 a3% r0 S8/15/25 T40%本金"] = make_sizer(1 / 3, 0.03, 0.0, (0.08, 0.15, 0.25), principal=0.40)
FAMILY["簡報全套(正2版) P1/3 a6% r0 S14/30/50 T40/80"] = make_sizer(1 / 3, 0.06, 0.0, (0.14, 0.30, 0.50), (0.40, 0.80))


def boot(diffs, B, L=60, seed=138):
    """diffs: {name: 每日報酬差}；回傳 t, 單組 p, 家族 p（單尾）, 家族 p（雙尾）"""
    import numpy as np
    names = [k for k in diffs if any(abs(x) > 1e-15 for x in diffs[k])]  # 完全沒觸發的組不進家族
    D = np.array([diffs[k] for k in names])
    K, n = D.shape
    rng = np.random.default_rng(seed)
    mu = D.mean(axis=1)
    bm = np.empty((B, K))
    for b in range(B):
        # 定態區塊拔靴：每天以 1/L 機率換新起點
        new = rng.random(n) < 1.0 / L
        new[0] = True
        starts = rng.integers(0, n, n)
        seg = np.maximum.accumulate(np.where(new, np.arange(n), 0))
        idx = (starts[seg] + np.arange(n) - seg) % n
        bm[b] = D[:, idx].mean(axis=1)
    se = bm.std(axis=0, ddof=1)
    t = mu / se
    tb = (bm - mu) / se
    single = (1 + (tb >= t).sum(axis=0)) / (B + 1)
    mx = tb.max(axis=1)
    fam = (1 + (mx[:, None] >= t).sum(axis=0)) / (B + 1)
    mx2 = np.abs(tb).max(axis=1)
    fam2 = (1 + (mx2[:, None] >= np.abs(t)).sum(axis=0)) / (B + 1)
    return ({k: float(t[j]) for j, k in enumerate(names)}, {k: float(single[j]) for j, k in enumerate(names)},
            {k: float(fam[j]) for j, k in enumerate(names)}, {k: float(fam2[j]) for j, k in enumerate(names)})


def main():
    B = int(os.environ.get("R138_B", "2000"))
    out = []
    p = out.append
    p("研究 138：簡報的金字塔加碼／移動停利／分段停損／分段停利 套到 v3（訊號不變，只改部位大小）")
    p("欄位：全期 2002-2026 | 前段 2002-2012 | 後段 2013-2026 | 真實 2015-09～（年化/最大回檔）；曝險＝全期平均槓桿（v3＝在場 2x）")
    p("同曝險 v3＝把 v3 的槓桿縮到該組平均曝險，只是押比較少的對照\n")
    res = {}
    for nm, sz in [("v3（現行）", FULL)] + list(FAMILY.items()):
        rs = [run(sz, a, b, real=(k == 3)) for k, (a, b) in enumerate(PER)]
        res[nm] = rs
    base = res["v3（現行）"]
    expo_full = base[0][3]
    for nm, rs in res.items():
        line = " | ".join(f"{c:6.1%}/{m:6.1%}" for c, m, _, _ in rs)
        e = rs[0][3]
        if nm != "v3（現行）":
            lv = 2.0 * e / expo_full
            ctrl = run(FULL, *PER[0], lev=lv)
            line += f" | 曝險 {e:.2f}  同曝險v3 {ctrl[0]:5.1%}/{ctrl[1]:6.1%}"
        else:
            line += f" | 曝險 {e:.2f}"
        p(f"{nm:44s} {line}")

    for k, lab in ((0, "全期 2002-2026"), (2, "後段 2013-2026"), (3, "真實 2015-09～")):
        diffs = {nm: [x - y for x, y in zip(rs[k][2], base[k][2])] for nm, rs in res.items() if nm != "v3（現行）"}
        t, single, fam, fam2 = boot(diffs, B)
        p(f"\n== 每日報酬差 vs v3 的區塊拔靴（{lab}，B={B}，平均區塊 60 日）==")
        p("t＞0 代表比 v3 好；單組 p＝單尾（比 v3 好）；家族 p＝最大 t 法（扣掉挑選）；雙尾家族 p＝變好或變差都算")
        for nm in diffs:
            if nm not in t:
                p(f"{nm:44s} 這段完全沒觸發，與 v3 相同")
                continue
            ann = sum(diffs[nm]) / len(diffs[nm]) * bt.TD
            p(f"{nm:44s} 年化差 {ann:+6.2%}  t {t[nm]:+5.2f}  單組 p {single[nm]:.3f}  家族 p {fam[nm]:.3f}  雙尾家族 p {fam2[nm]:.3f}")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究138_金字塔加碼與分段停損.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
