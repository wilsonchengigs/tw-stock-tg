"""研究 135：爆量收黑（V）＋外資期貨雙指標（F）同時加碼的組合（研究 122 候選 4）——兩條訊號各自平移的家族檢定

研究 122 顯示兩條加碼規則同時用，年化大致相加。研究 129（F）、130（V）各自做過家族檢定，但沒檢定過「組合」：
- H0-雙：兩條訊號都與之後報酬無關 → V、F 用不同的平移量各自環狀平移（拆掉兩者之間的關係與各自的資訊）
- H0-F｜V：V 是真的、F 沒有額外資訊 → 只平移 F（看 F 在已有 V 的情況下還有沒有貢獻）
- H0-V｜F：F 是真的、V 沒有額外資訊 → 只平移 V
家族：V 加 0.5／1x × 抱 5／10 天 × F 加 0.5／1x（F 固定研究 128「未平倉 z 與交易淨額 z 都 > 1.5」抱 5 天、排除結算日）＝ 8 組
引擎：研究 75b（v3 狀態、00631L＋台指期真實價、隔天開盤進、成本 3 點）；2018-06～
家族 p：最小 p 值法（研究 129）
用法：python -X utf8 backtest/research_135_爆量收黑加外資期貨組合多重檢定.py（R135_SHIFTS 控制每種 H0 的平移次數，預設 150）
"""
import csv
import importlib.util
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GRID = [(va, vh, fa) for va in (0.5, 1.0) for vh in (5, 10) for fa in (0.5, 1.0)]


def build():
    m127 = load("r127", "research_127_外資期貨交易淨額.py")
    flow, oi = {}, {}
    for r in csv.DictReader(open(os.path.join(HERE, "tx_inst_oi.csv"), encoding="utf-8")):
        if r["investor"] == "外資":
            flow[r["date"]] = int(r["long_vol"]) - int(r["short_vol"])
            oi[r["date"]] = int(r["long_oi"]) - int(r["short_oi"])
    ods = sorted(oi)
    doi = {ods[k]: oi[ods[k]] - oi[ods[k - 1]] for k in range(1, len(ods))}
    zo, zf = m127.zmap(doi), m127.zmap(flow)
    b63 = load("r63d", "research_63d_爆量收黑_台指期真實價.py")
    fdates, fday, _n, _near = b63.load()
    last_day = {}
    for d in fdates:
        for m in fday[d]:
            last_day[m] = d
    settle = set(last_day.values())
    excl = settle | {fdates[i + 1] for i, d in enumerate(fdates[:-1]) if d in settle}
    S = load("r76", "research_76_加碼候選在v3重驗.py").v3_states()

    src = open(os.path.join(HERE, "research_75b_外資期貨加減碼_真實價.py"), encoding="utf-8").read()
    old = "VR[i] is not None and VR[i] >= 1.5 and PX[i] < PX[i - 1]"
    assert old in src
    src = src.replace(old, "i in VSIG")
    a = src.index("    for x in (1.5, 2.0):")
    zz = src.index("    return L")
    grid = '''    for va, vh, fa in GRID:
        c, d_ = run(x=1.0, add=fa, Hadd=5, vol=va, Hvol=vh)
        L.append(("RES", (va, vh, fa), c, d_))
    for va, vh in ((0.5, 5), (0.5, 10), (1.0, 5), (1.0, 10)):
        L.append(("V", (va, vh), *run(vol=va, Hvol=vh)))
    for fa in (0.5, 1.0):
        L.append(("F", fa, *run(x=1.0, add=fa, Hadd=5)))
    L.append(("BASE", None, *run()))
'''
    code = src[:a] + grid + src[zz:]
    code = code[:code.index("def run_all():")]
    # 只要格點結果：把 main 開頭兩行基準輸出拿掉（下面自己算 BASE）
    code = code.replace('    b = run()\n    L.append(f"現行', '    b = (0, 0)\n    0 and L.append(f"現行', 1)
    code = code.replace('    v = run(vol=1.0)\n    L.append(', '    v = (0, 0)\n    0 and L.append(', 1)
    ns = {"__file__": os.path.join(HERE, "research_75b_外資期貨加減碼_真實價.py"), "__name__": "r135", "GRID": GRID, "VSIG": set()}
    exec(compile(code, "r135", "exec"), ns)
    ns["ENTRY"] = "day_open"
    ns["r64"].state_series = lambda: S

    # V 訊號的交易日序列：和 75b 的 idx 同一段（2018-06-05 起、00631L 與台指期都有資料）
    import json
    from datetime import datetime, timedelta, timezone
    r = json.load(open(os.path.join(HERE, "00631L.TW.json")))
    E = {datetime.fromtimestamp(t, timezone(timedelta(hours=8))).strftime("%Y-%m-%d") for t, v in
         zip(r["timestamp"], r["indicators"]["adjclose"][0]["adjclose"]) if v}
    fidx = set(fdates)
    DAYS, PX, VR = ns["DAYS"], ns["PX"], ns["VR"]
    vdays = [i for i in range(len(DAYS)) if DAYS[i] in E and DAYS[i] in fidx and DAYS[i] >= "2018-06-05"]
    vflag = [VR[i] is not None and VR[i] >= 1.5 and PX[i] < PX[i - 1] for i in vdays]
    fseq = [d for d in sorted(zo) if d in zf and zo[d] is not None and zf[d] is not None]
    fflag = [zo[d] > 1.5 and zf[d] > 1.5 for d in fseq]

    def vsig(s):
        n = len(vdays)
        return {vdays[p] for p in range(n) if vflag[(p - s) % n]}

    def fsig(s):
        n = len(fseq)
        return {d: 3.0 for p, d in enumerate(fseq) if d not in excl and fflag[(p - s) % n]}

    def run(sv, sf):
        ns["VSIG"] = vsig(sv)
        Z = fsig(sf)
        ns["r75"].zseries = lambda: Z
        return ns["main"]()

    return run, len(vdays), len(fseq)


def pval(v, col, skip=None):
    others = [c for i, c in enumerate(col) if i != skip]
    return (sum(c >= v for c in others) + 1) / (len(others) + 1)


def main():
    run, nv, nf = build()
    real = run(0, 0)
    res = [x for x in real if x[0] == "RES"]
    base = next(x for x in real if x[0] == "BASE")
    vonly = {x[1]: x[2:] for x in real if x[0] == "V"}
    fonly = {x[1]: x[2:] for x in real if x[0] == "F"}
    K = int(os.environ.get("R135_SHIFTS", "150"))
    gap = 60
    sv_list = [gap + round(k * (nv - 2 * gap) / (K - 1)) for k in range(K)]
    sf_list = [gap + round(k * (nf - 2 * gap) / (K - 1)) for k in range(K)]
    rng = random.Random(135)
    sf_pair = sf_list[:]
    rng.shuffle(sf_pair)
    nulls = {"H0-雙（V、F 各自平移）": [(sv_list[k], sf_pair[k]) for k in range(K)],
             "H0-F｜V（只平移 F）": [(0, sf_list[k]) for k in range(K)],
             "H0-V｜F（只平移 V）": [(sv_list[k], 0) for k in range(K)]}
    L = [f"研究 135：爆量收黑（V）＋外資期貨雙指標（F）組合加碼的家族檢定（v3、00631L＋台指期真實價、2018-06～、隔天開盤、排除結算日）",
         f"不加碼 {base[2]:.1%}／{base[3]:.1%}；家族 {len(GRID)} 組；每種虛無假設平移 {K} 次（V 序列 {nv} 天、F 序列 {nf} 天）", "",
         "單獨：" + "；".join(f"V 加{k[0]}x抱{k[1]} {v[0]:.1%}／{v[1]:.1%}" for k, v in vonly.items()),
         "      " + "；".join(f"F 加{k}x {v[0]:.1%}／{v[1]:.1%}" for k, v in fonly.items()), ""]
    allnull = {}
    for name, pairs in nulls.items():
        fam = []
        for k, (sv, sf) in enumerate(pairs):
            fam.append([x[2] for x in run(sv, sf) if x[0] == "RES"])
            if (k + 1) % 25 == 0:
                print(f"  {name} {k + 1}/{K}", flush=True)
        allnull[name] = fam
    L.append("實際結果（組合年化／回檔｜組合增量 vs V、F 單獨增量相加｜三種 H0 的單組 p）：")
    for g, x in enumerate(res):
        va, vh, fa = x[1]
        add_sum = (vonly[(va, vh)][0] - base[2]) + (fonly[fa][0] - base[2])
        ps = [pval(x[2], [f[g] for f in allnull[nm]]) for nm in nulls]
        L.append(f"  V加{va}x抱{vh:2d} ＋ F加{fa}x：{x[2]:.1%}／{x[3]:.1%}｜增量 {x[2] - base[2]:+.1%} vs 相加 {add_sum:+.1%}｜p 雙 {ps[0]:.3f}、F｜V {ps[1]:.3f}、V｜F {ps[2]:.3f}")
    L += ["", "家族檢定（最小 p 值法）："]
    for nm in nulls:
        fam = allnull[nm]
        cols = list(zip(*fam))
        real_minp = min(pval(x[2], cols[g]) for g, x in enumerate(res))
        null_minp = [min(pval(fam[k][g], cols[g], skip=k) for g in range(len(res))) for k in range(K)]
        pm = (sum(v <= real_minp for v in null_minp) + 1) / (K + 1)
        med = sorted(max(f) for f in fam)[K // 2]
        L.append(f"  {nm}：實際最小單組 p {real_minp:.3f}｜平移後家族最好年化中位 {med:.1%}｜家族 p {pm:.3f}")
    txt = "\n".join(L) + "\n"
    print(txt)
    open(os.path.join(HERE, "結果_研究135_爆量收黑加外資期貨組合多重檢定.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
