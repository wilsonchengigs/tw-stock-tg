"""研究 188：2 倍部位的「再平衡頻率」——每天重設（00631L）vs 固定名目、定期調回（台指期）

動機：研究 187 指出高波動、來回刷的世界對 2x 最傷。00631L 每天收盤把曝險重設回 2 倍：漲了加碼、跌了減碼，
來回刷時會「高買低賣」（波動耗損，約 σ²/年）；趨勢走時反而有複利加成。台指期可以固定名目、只定期調回 2 倍。
問題：同一套 v3 進出場訊號下，再平衡頻率 每天／每週／每月／只在進場時 哪個好？高波動世界裡差異會不會變大？

模型（所有方式用同一套成本，差異只來自再平衡頻率）：
- 每天：權益 E、名目 X；當天損益 X×(r1 − rf) ＋ E×rf，r1＝加權＋3% 配息、rf＝1%／年（期貨隱含資金成本；保證金現金收 rf）
- 每天／每週五／每月底／只在進場時 把 X 調回 2×E（「只在進場時」＝進場那天設 2×E，之後不動，直到出場）
- 調整成本：|ΔX| × 0.02%（台指期 6 點來回約 0.016%）；另每年 0.2% 轉倉成本×名目
- 安全上限：槓桿漂移超過 3 倍時強制調回 2 倍（保證金風險）
訊號：
(1) v3 現行（含融資過熱，真實加權 2002～2026）
(2) 核心均線（研究 187 的壓力模擬路徑：1998～ 日報酬波動 ×1／1.5／2，漂移不變）
用法：python -X utf8 backtest/research_188_兩倍部位再平衡頻率.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


R186 = load("r186", "research_186_主策略全面健檢.py")
R187 = load("r187", "research_187_高波動來回刷.py")
bt = R186.bt
TD = 245
RF, DIV = 0.01 / TD, 0.03 / TD
TC, ROLL = 0.0002, 0.002 / TD
MODES = ("daily", "weekly", "monthly", "entry")
MODE_N = {"daily": "每天（≈00631L）", "weekly": "每週五", "monthly": "每月底", "entry": "只在進場時"}


def simulate(p, days, we, target, i0, i1, mode, cap=3.0):
    """target[i]＝第 i 天收盤後要持有的槓桿（0 或 2）；回傳 年化、最大回檔、平均槓桿、調整次數"""
    me = [k == len(days) - 1 or days[k][:7] != days[k + 1][:7] for k in range(len(days))]
    E, X = 1.0, 0.0
    peak, mdd, levsum, n_in, n_reb = 1.0, 0.0, 0.0, 0, 0
    for i in range(i0, i1 + 1):
        if i > i0:
            r1 = p[i] / p[i - 1] - 1 + DIV
            E += X * (r1 - RF) + E * RF - X * ROLL
            X *= 1 + r1 - RF * 0  # 名目跟著指數走
            if X > 0:
                levsum += X / E
                n_in += 1
        peak = max(peak, E)
        mdd = min(mdd, E / peak - 1)
        if E <= 0:
            return -1.0, -1.0, 0, n_reb
        t = target[i]
        want = None
        if t == 0 and X != 0:
            want = 0.0
        elif t > 0 and X == 0:
            want = t * E
        elif t > 0:
            lev = X / E
            if lev > cap or mode == "daily" or (mode == "weekly" and we[i]) or (mode == "monthly" and me[i]):
                want = t * E
        if want is not None and abs(want - X) > 1e-12:
            E -= abs(want - X) * TC
            X = want
            n_reb += 1
    yrs = (i1 - i0) / TD
    return E ** (1 / yrs) - 1, mdd, (levsum / n_in if n_in else 0), n_reb


def v3_target():
    tr = []
    R186.run("2002-01-01", "2026-12-31", trades=tr)
    DAYS = R186.DAYS
    pos = {d: b for d, a, b, _ in tr}
    tgt, cur = [], 0.0
    for d in DAYS:
        if d in pos:
            cur = pos[d]
        tgt.append(cur)
    return tgt


def core_target(p, we):
    m60, m80 = R187.sma(p, 60), R187.sma(p, 80)
    st, pend, cur, out = False, None, 0.0, []
    for i in range(len(p)):
        if pend is not None:
            cur, pend = pend, None
        out.append(cur)
        if we[i] and i >= 260:
            st = (not p[i] < m80[i] * 0.975) if st else (p[i] > m60[i] * 1.01)
            t = 2.0 if st else 0.0
            if t != cur:
                pend = t
    return out


def main():
    L = ["研究 188：2 倍部位再平衡頻率（同訊號、同成本；年化／最大回檔／在場平均槓桿／調整次數）"]
    DAYS, PX, WE = R186.DAYS, R186.PX, R186.WE
    tgt = v3_target()
    L.append("\n【1】v3 現行訊號、真實加權")
    for a, b in (("2002-01-01", "2026-12-31"), ("2002-01-01", "2012-12-31"), ("2013-01-01", "2026-12-31"), ("2026-01-01", "2026-12-31")):
        i0 = next(i for i, d in enumerate(DAYS) if d >= a)
        i1 = max(i for i, d in enumerate(DAYS) if d <= b)
        L.append(f"  {a[:4]}～{b[:4]}：" + "｜".join(
            "{}: {:5.1%}/{:6.1%} 槓桿{:.2f} {}次".format(MODE_N[m], *simulate(PX, DAYS, WE, tgt, i0, i1, m)) for m in MODES))
    # 逐年：每天 vs 每月
    i0 = next(i for i, d in enumerate(DAYS) if d >= "2002-01-01")
    ys = sorted({d[:4] for d in DAYS if d >= "2002"})
    rows = []
    for y in ys:
        a = next(i for i, d in enumerate(DAYS) if d[:4] == y)
        b = max(i for i, d in enumerate(DAYS) if d[:4] == y)
        r = {m: simulate(PX, DAYS, WE, tgt, a - 1 if a > 0 else a, b, m)[0] for m in ("daily", "monthly", "entry")}
        idx = [k for k in range(a, b + 1)]
        rr = [PX[k] / PX[k - 1] - 1 for k in idx]
        mu = sum(rr) / len(rr)
        vol = (sum((x - mu) ** 2 for x in rr) / len(rr) * TD) ** 0.5
        rows.append((y, vol, r))
    L.append("  逐年（年化≈當年報酬）：每天 vs 每月 vs 只在進場；當年波動")
    for y, vol, r in rows:
        L.append(f"    {y} 波動 {vol:4.0%}：每天 {r['daily']:+6.1%}  每月 {r['monthly']:+6.1%}  只進場 {r['entry']:+6.1%}")
    hi = [r for y, v, r in rows if v >= 0.2]
    lo = [r for y, v, r in rows if v < 0.2]
    for name, g in (("波動 ≥20% 的年", hi), ("波動 <20% 的年", lo)):
        if g:
            L.append(f"  {name}（{len(g)} 年）平均：每天 {sum(x['daily'] for x in g) / len(g):+.1%}、每月 {sum(x['monthly'] for x in g) / len(g):+.1%}、只進場 {sum(x['entry'] for x in g) / len(g):+.1%}")

    L.append("\n【2】壓力模擬（研究 187 的放大波動路徑、核心均線訊號、1999～2026）")
    for k in (1.0, 1.5, 2.0):
        p, days = R187.scaled_path(k)
        we = R187.weekend(days)
        t = core_target(p, we)
        i0 = next(i for i, d in enumerate(days) if d >= "1999-01-01")
        L.append(f"  波動 ×{k}：" + "｜".join(
            "{}: {:5.1%}/{:6.1%} 槓桿{:.2f}".format(MODE_N[m], *simulate(p, days, we, t, i0, len(p) - 1, m)[:3]) for m in MODES))
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究188_兩倍部位再平衡頻率.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
