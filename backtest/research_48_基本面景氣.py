"""研究 48：基本面／景氣（使用者提議：AI 帶動營收好，下跌可能只是暫時）

資料：國發會「景氣指標及燈號」（data.gov.tw 6099，1982～2026-09）：景氣對策信號分數（9～45；≥38 紅燈、32～37 黃紅、23～31 綠、17～22 黃藍、≤16 藍）、
領先指標不含趨勢指數、海關出口值（台灣出口＝企業營收的總體代理，含 AI 伺服器）
公布延遲：第 M 月資料在 M+1 月月底公布 → 回測從 M+2 月 1 日起才使用（保守）
1. 事件研究：深跌（距高點 ≥15%）當下，依「當時已知」的燈號分數／出口年增分組，看之後 60／120 日報酬與再跌 10% 機率
2. 策略：空手時，若深跌 ≥ d、基本面強（燈號 ≥ s 或出口 3 個月年增 ≥ g）、從近 10 日低點反彈 3% → 提早進場（停損近期低點，站上進場線轉正常）
   另測：基本面弱（燈號 ≤ 22 或出口年增 < 0）時不進場
   基準＝新版（出場 2.5%＋融資過熱）；平移安慰劑
用法：python -X utf8 backtest/research_48_基本面景氣.py
"""
import csv
import importlib.util
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r41", os.path.join(HERE, "research_41_總經濾網.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)
bt, DAYS, PX, N, WE = R.bt, R.DAYS, R.PX, R.N, R.WE
M60, M80, HOT = R.M60, R.M80, R.HOT
RR = R.R40.R32.R
HI = [max(PX[max(0, i - 249):i + 1]) for i in range(N)]
DASH = "—"


def monthly(path, col):
    out = {}
    for r in csv.DictReader(open(os.path.join(HERE, path), encoding="utf-8-sig")):
        try:
            out[r["Date"]] = float(r[col])
        except (ValueError, KeyError):
            pass
    return out


SCORE = monthly("ndc_signal.csv", "景氣對策信號綜合分數")
LEAD = monthly("ndc_signal.csv", "領先指標不含趨勢指數")
EXP = monthly("ndc_components.csv", "海關出口值(十億元)")


def ym_add(ym, k):
    y, m = int(ym[:4]), int(ym[4:])
    m += k
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{y}{m:02d}"


def exp_yoy3(ym):
    try:
        a = sum(EXP[ym_add(ym, -k)] for k in range(3))
        b = sum(EXP[ym_add(ym, -12 - k)] for k in range(3))
        return a / b - 1
    except KeyError:
        return None


def lead6(ym):
    if ym in LEAD and ym_add(ym, -6) in LEAD:
        return LEAD[ym] / LEAD[ym_add(ym, -6)] - 1
    return None


def known(fn):
    """每個台股日能知道的最新月份值（第 M 月 → M+2 月 1 日起可用）"""
    return [fn(ym_add(d[:4] + d[5:7], -2)) for d in DAYS]


SC = known(lambda ym: SCORE.get(ym))
EX = known(exp_yoy3)
LD6 = known(lead6)


def fwd(i, h):
    return PX[i + h] / PX[i] - 1 if i + h < N else None


def fmt_pct(x, spec="+.1%"):
    return DASH if x is None else format(x, spec)


def event_study(L):
    ev, last = [], -99
    for i in range(260, N):
        if PX[i] / HI[i] - 1 <= -0.15 and i - last > 40:
            ev.append(i)
            last = i
    L.append("\n== 1. 事件研究：剛跌破距高點 -15% 的時點（去叢集 40 日），依當時已知的基本面分組 ==")
    L.append("日期 | 燈號分數 | 出口 3 月年增 | 領先指標 6 月變化 | 60 日 | 120 日 | 之後 120 日最低")
    for i in ev:
        lo = min(PX[i:i + 121]) / PX[i] - 1 if i + 121 < N else None
        sc = DASH if SC[i] is None else f"{SC[i]:.0f}"
        L.append(" | ".join([DAYS[i], sc, fmt_pct(EX[i], "+.0%"), fmt_pct(LD6[i]), fmt_pct(fwd(i, 60)), fmt_pct(fwd(i, 120)), fmt_pct(lo)]))

    def grp(nm, sel):
        xs = [i for i in ev if sel(i)]
        if not xs:
            return
        line = f"{nm}（{len(xs)} 次）："
        for h in (60, 120):
            v = [fwd(i, h) for i in xs if fwd(i, h) is not None]
            if v:
                line += f" {h} 日平均 {statistics.mean(v):+.1%}、上漲 {sum(x > 0 for x in v) / len(v):.0%}；"
        lo = [min(PX[i:i + 121]) / PX[i] - 1 for i in xs if i + 121 < N]
        if lo:
            line += f" 再跌 >10% 比例 {sum(x < -0.10 for x in lo) / len(lo):.0%}"
        L.append(line)

    L.append("")
    grp("燈號 ≥ 32（黃紅／紅）", lambda i: SC[i] is not None and SC[i] >= 32)
    grp("燈號 23～31（綠）", lambda i: SC[i] is not None and 23 <= SC[i] <= 31)
    grp("燈號 ≤ 22（黃藍／藍）", lambda i: SC[i] is not None and SC[i] <= 22)
    grp("出口 3 月年增 ≥ 10%", lambda i: EX[i] is not None and EX[i] >= 0.10)
    grp("出口 3 月年增 0～10%", lambda i: EX[i] is not None and 0 <= EX[i] < 0.10)
    grp("出口 3 月年增 < 0", lambda i: EX[i] is not None and EX[i] < 0)
    grp("領先指標 6 月上升", lambda i: LD6[i] is not None and LD6[i] > 0)
    grp("領先指標 6 月下降", lambda i: LD6[i] is not None and LD6[i] <= 0)


def run(start, end, strong=None, weak=None, d=0.15, real=False):
    r2 = RR.R2R if real else bt.R2
    i0 = next(i for i, x in enumerate(DAYS) if x >= start)
    i1 = max(i for i, x in enumerate(DAYS) if x <= end)
    eq = peak = 1.0
    mdd, st, pos, pend, stop = 0.0, 0, False, None, 0.0
    for i in range(i0, i1 + 1):
        if i > i0:
            eq *= 1 + (r2[i] if pos else bt.RC)
        if pend is not None:
            eq *= 1 - bt.COST * 2
            pos, pend = pend, None
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        if not WE[i] or i < 260:
            continue
        w = weak is not None and weak[i]
        if st == 0:
            if PX[i] > M60[i] * 1.01 and not HOT[i] and not w:
                st = 2
            elif strong is not None and strong[i] and not HOT[i] and min(PX[i - 10:i + 1]) / HI[i] - 1 <= -d:
                lo = min(PX[i - 10:i + 1])
                if PX[i] > lo * 1.03:
                    st, stop = 1, lo
        elif st == 1:
            if PX[i] > M60[i] * 1.01:
                st = 2
            elif PX[i] < stop:
                st = 0
        elif PX[i] < M80[i] * 0.975 or HOT[i]:
            st = 0
        if (st != 0) != pos:
            pend = st != 0
    yrs = (i1 - i0) / bt.TD
    return eq ** (1 / yrs) - 1, mdd


def shifted(arr, rng):
    i0 = next(i for i in range(N) if arr[i] is not None)
    seg = arr[i0:]
    k = rng.randrange(250, len(seg) - 250)
    return [None] * i0 + seg[k:] + seg[:k]


def main():
    L = ["研究 48：基本面／景氣（國發會燈號、出口、領先指標；資料延後 2 個月使用）"]
    event_study(L)
    L.append("\n== 2. 策略（新版基準；全期 2002- | 前段 | 後段 | 真實；p＝100 次平移，看全期）==")
    base = [run(a, b) for a, b in R.PER]
    br = run(*R.REAL, real=True)
    L.append("新版基準 " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in base) + f" | 真實 {br[0]:.1%}/{br[1]:.1%}")
    rng = random.Random(48)
    tests = []
    for s in (32, 35, 38):
        tests.append((f"燈號 ≥ {s} 時深跌反彈提早進", "strong", SC, (lambda v, s=s: v is not None and v >= s)))
    for g in (0.05, 0.10, 0.20):
        tests.append((f"出口年增 ≥ {g:.0%} 時深跌反彈提早進", "strong", EX, (lambda v, g=g: v is not None and v >= g)))
    tests.append(("領先指標上升時深跌反彈提早進", "strong", LD6, (lambda v: v is not None and v > 0)))
    tests.append(("燈號 ≤ 22 時不進場", "weak", SC, (lambda v: v is not None and v <= 22)))
    tests.append(("出口年增 < 0 時不進場", "weak", EX, (lambda v: v is not None and v < 0)))
    tests.append(("對照：不看基本面，深跌反彈就提早進", "strong", None, None))
    for nm, kind, raw, fn in tests:
        flag = [True] * N if raw is None else [fn(v) for v in raw]
        rs = [run(a, b, **{kind: flag}) for a, b in R.PER]
        rr = run(*R.REAL, real=True, **{kind: flag})
        p = DASH
        if raw is not None:
            sims = []
            for _ in range(100):
                sh = shifted(raw, rng)
                sims.append(run(*R.PER[0], **{kind: [fn(v) for v in sh]})[0])
            p = f"{(sum(x >= rs[0][0] for x in sims) + 1) / 101:.2f}"
        L.append(f"{nm:26s} " + " | ".join(f"{c:.1%}/{m:.1%}" for c, m in rs) + f" | 真實 {rr[0]:.1%}/{rr[1]:.1%} | p {p}")
        print(L[-1], flush=True)
    L.append(f"\n回測資料中最新可用值（{DAYS[-1]}）：燈號 {SC[-1]}、出口 3 月年增 {fmt_pct(EX[-1], '+.0%')}、領先指標 6 月變化 {fmt_pct(LD6[-1])}")
    L.append(f"國發會最新月份 2026-09：燈號 {SCORE.get('202609')}、出口 3 月年增 {fmt_pct(exp_yoy3('202609'), '+.0%')}、領先指標 6 月變化 {fmt_pct(lead6('202609'))}")
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究48_基本面景氣.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
