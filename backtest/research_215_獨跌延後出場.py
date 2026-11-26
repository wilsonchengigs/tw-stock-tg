"""研究 215：主策略（v3）週五跌破出場線（MA80×0.975）時，如果是「台股獨跌」（加權 20 日 − S&P 20 日 ≤ −x），延後出場
依研究 204～206：台股獨跌之後 5 日有補漲，出場賣在獨跌低點可能是假訊號
變體：x＝5／8／10%；A 延後 1 週（下週五再檢查，屆時仍跌破就出，不再看背離）；B 延後到背離回到 > −x/2 或最多 4 週
融資過熱出場不受影響；進場規則不變
比較：全期 2002–2026、兩段、真實價（2015-09～）；背離序列平移 200 次的安慰劑（同變體）；觸發次數與每次的差
用法：python -X utf8 backtest/research_215_獨跌延後出場.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import research_138_金字塔加碼與分段停損 as R138  # noqa: E402

V, bt, DAYS, PX, N, WE = R138.V, R138.bt, R138.DAYS, R138.PX, R138.N, R138.WE
M60, M80, DEV, Z = R138.M60, R138.M80, R138.DEV, R138.Z
spec = importlib.util.spec_from_file_location("r205", os.path.join(HERE, "research_205_台美背離台指期部位.py"))
R205 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R205)
GAP0 = np.array([R205.GAP.get(d, np.nan) for d in DAYS])


def states(gapv, x=None, mode="A"):
    st = [0] * N
    state, heat_out, delay, waited, trig = 0, False, False, 0, []
    for i in range(N):
        if i >= 260 and not WE[i] and state == 1 and V.hot_at(i):
            state, heat_out, delay = 0, True, False
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
                state, heat_out, delay = 0, True, False
            elif not above:
                g = gapv[i]
                if x is None:
                    state = 0
                elif mode == "A":
                    if not delay and not np.isnan(g) and g <= -x:
                        delay = True
                        trig.append(i)
                    else:
                        state, delay = 0, False
                else:  # B
                    if not delay and not np.isnan(g) and g <= -x:
                        delay, waited = True, 0
                        trig.append(i)
                    elif delay and waited < 3 and not np.isnan(g) and g <= -x / 2:
                        waited += 1
                    else:
                        state, delay = 0, False
            else:
                delay = False
        st[i] = state
    return st, trig


def perf(st):
    R138.ST = st
    out = []
    for a, b in V.PER:
        cg, mdd, _, _ = R138.run(R138.FULL, a, b)
        out.append((cg, mdd))
    cg, mdd, _, _ = R138.run(R138.FULL, *V.REAL, real=True)
    out.append((cg, mdd))
    return out


def fmt(p):
    return "  ".join(f"{c:5.1%}／{m:6.1%}" for c, m in p)


base_st, _ = states(GAP0)
base = perf(base_st)
L = ["研究 215：台股獨跌時延後主策略出場（欄位：全期 2002～｜2002–2012｜2013～｜真實價 2015-09～，年化／回檔）",
     f"現行 v3：{fmt(base)}", ""]
rng = np.random.default_rng(215)
shifts = rng.integers(250, N - 250, 200)
for mode in ("A", "B"):
    for x in (0.05, 0.08, 0.10):
        st, trig = states(GAP0, x, mode)
        p = perf(st)
        null = []
        for s in shifts:
            st2, _ = states(np.roll(GAP0, s), x, mode)
            R138.ST = st2
            null.append(R138.run(R138.FULL, *V.PER[0])[0])
        pv = (1 + np.sum(np.array(null) >= p[0][0])) / (len(null) + 1)
        L.append(f"{'A 延後 1 週' if mode == 'A' else 'B 延後到背離消失（≤4 週）'} x {x:.0%}：{fmt(p)}  觸發 {len(trig)} 次  平移 p {pv:.3f}（平移中位 {np.median(null):.1%}）")
        L.append("   觸發日：" + "、".join(DAYS[i] for i in trig[-10:]))
R138.ST = base_st
out = "\n".join(L) + "\n"
print(out)
open(os.path.join(HERE, "結果_研究215_獨跌延後出場.txt"), "w", encoding="utf-8").write(out)
