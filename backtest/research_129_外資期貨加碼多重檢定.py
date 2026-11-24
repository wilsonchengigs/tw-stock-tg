"""研究 129：外資台指期加碼家族的多重檢定（reality check：扣掉「試了很多組、挑最好的」的運氣）

研究 73～79、120、127、128 在同一份外資期貨資料上試了很多組變形，最好的是 128「雙指標都 > 1.5、加 1x 抱 5 天」58.8%。
單一變形的隨機對照 p 0.01 沒有算到「挑最好」這一步。這裡把整個變形家族一起檢定：
- 虛無假設：外資 z 序列與之後的行情無關
- 做法：把未平倉 z、交易淨額 z 兩條序列「一起」對交易日環狀平移 s 天（保留兩條序列彼此的相關、各自的自相關與訊號數），
  每個平移重跑全部變形，取家族中最好的年化（與最好的「年化增加 ÷ 回檔加深」），和實際的最好值比
- 家族：門檻 1.0／1.5／2.0 × 只看未平倉／只看交易淨額／兩者都過／任一過 × 加 0.5x／1x（24 組，抱 5 天、隔天開盤、排除結算日）
- 平移量避開 ±60 個交易日內（避免和原序列太像）
概念參考：White (2000) Reality Check、Romano–Wolf；Vibe-Trading 的 multipletesting／deflated significance
用法：python -X utf8 backtest/research_129_外資期貨加碼多重檢定.py（R129_SHIFTS 控制平移次數，預設 80）
"""
import csv
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    m127 = load("r127", "research_127_外資期貨交易淨額.py")
    flow, oi = {}, {}
    for r in csv.DictReader(open(os.path.join(HERE, "tx_inst_oi.csv"), encoding="utf-8")):
        if r["investor"] == "外資":
            flow[r["date"]] = int(r["long_vol"]) - int(r["short_vol"])
            oi[r["date"]] = int(r["long_oi"]) - int(r["short_oi"])
    ods = sorted(oi)
    doi = {ods[k]: oi[ods[k]] - oi[ods[k - 1]] for k in range(1, len(ods))}
    zo, zf = m127.zmap(doi), m127.zmap(flow)
    b = load("r63d", "research_63d_爆量收黑_台指期真實價.py")
    fdates, fday, _n, _near = b.load()
    last_day = {}
    for d in fdates:
        for m in fday[d]:
            last_day[m] = d
    settle = set(last_day.values())
    excl = settle | {fdates[i + 1] for i, d in enumerate(fdates[:-1]) if d in settle}
    S = load("r76", "research_76_加碼候選在v3重驗.py").v3_states()
    src = open(os.path.join(HERE, "research_75b_外資期貨加減碼_真實價.py"), encoding="utf-8").read()
    a = src.index("    for x in (1.5, 2.0):")
    zz = src.index("    return L")
    grid = '''    for add in (0.5, 1.0):
        c, d_ = run(x=1.0, add=add, Hadd=5)
        L.append(f"RES {add} {c} {d_}")
'''
    code = src[:a] + grid + src[zz:]
    code = code[:code.index("def run_all():")]
    ns = {"__file__": os.path.join(HERE, "research_75b_外資期貨加減碼_真實價.py"), "__name__": "r129"}
    exec(compile(code, "r129", "exec"), ns)
    ns["ENTRY"] = "day_open"
    ns["r64"].state_series = lambda: S

    def res(sig):
        ns["r75"].zseries = lambda: sig
        return {float(x.split()[1]): (float(x.split()[2]), float(x.split()[3])) for x in ns["main"]() if x.startswith("RES")}

    base_c, base_d = res({})[0.5]
    seq = [d for d in sorted(zo) if d in zf and zo[d] is not None and zf[d] is not None]
    n = len(seq)
    rules = (("只看未平倉", lambda o, f, t: o > t), ("只看交易淨額", lambda o, f, t: f > t),
             ("兩者都過", lambda o, f, t: o > t and f > t), ("任一過", lambda o, f, t: o > t or f > t))

    def family(shift):
        """平移 shift 天後跑全家族，回傳 [(名稱, 年化, 回檔, 訊號數)]"""
        out = []
        for th in (1.0, 1.5, 2.0):
            for nm, f in rules:
                sig = {}
                for k, d in enumerate(seq):
                    j = (k - shift) % n
                    if d not in excl and f(zo[seq[j]], zf[seq[j]], th):
                        sig[d] = 3.0
                r = res(sig)
                for add in (0.5, 1.0):
                    out.append((f"門檻 {th} {nm} 加{add}x", r[add][0], r[add][1], len(sig)))
        return out

    def eff(c, d):
        """年化增加 ÷ 回檔加深（回檔沒加深時當作加深 1 點）"""
        return (c - base_c) / max(base_d - d, 0.01)

    real = family(0)
    best_c = max(real, key=lambda x: x[1])
    best_e = max(real, key=lambda x: eff(x[1], x[2]))
    K = int(os.environ.get("R129_SHIFTS", "80"))
    gap = 60
    shifts = [gap + round(k * (n - 2 * gap) / (K - 1)) for k in range(K)]
    mc, me, pv_single, allfam = [], [], {x[0]: 0 for x in real}, []
    for k, s in enumerate(shifts):
        fam = family(s)
        allfam.append([y[1] for y in fam])
        mc.append(max(x[1] for x in fam))
        me.append(max(eff(x[1], x[2]) for x in fam))
        for x, y in zip(real, fam):
            pv_single[x[0]] += y[1] >= x[1]
        print(f"  平移 {k + 1}/{K}（{s} 天）：家族最好 {mc[-1]:.1%}", flush=True)

    L = [f"研究 129：外資台指期加碼家族多重檢定（v3 在場、隔天開盤、抱 5 天、排除結算日；2018-06～；不加碼 {base_c:.1%}／{base_d:.1%}）",
         f"家族 {len(real)} 組；環狀平移 {K} 次（{shifts[0]}～{shifts[-1]} 交易日，共 {n} 天）",
         "", "實際結果（單組平移 p＝平移後該組年化 ≥ 實際的比例）："]
    for x in sorted(real, key=lambda x: -x[1]):
        p = (pv_single[x[0]] + 1) / (K + 1)
        L.append(f"  {x[0]:18s} 訊號 {x[3]:3d}：{x[1]:.1%}／{x[2]:.1%}｜效率 {eff(x[1], x[2]):+.2f}｜單組 p {p:.2f}")
    pc = (sum(v >= best_c[1] for v in mc) + 1) / (K + 1)
    pe = (sum(v >= eff(best_e[1], best_e[2]) for v in me) + 1) / (K + 1)
    mc_s, me_s = sorted(mc), sorted(me)
    L += ["", "家族檢定（每次平移取家族最好的一組，和實際最好的比）：",
          f"  年化：實際最好 {best_c[0]} {best_c[1]:.1%}；平移後家族最好 中位 {mc_s[K // 2]:.1%}、90 分位 {mc_s[int(K * 0.9)]:.1%}、最大 {mc_s[-1]:.1%}｜家族 p {pc:.3f}",
          f"  效率：實際最好 {best_e[0]} {eff(best_e[1], best_e[2]):+.2f}；平移後 中位 {me_s[K // 2]:+.2f}、90 分位 {me_s[int(K * 0.9)]:+.2f}、最大 {me_s[-1]:+.2f}｜家族 p {pe:.3f}"]
    # 最小 p 值（Romano–Wolf 精神）：每組先和自己的平移分布比成 p，再取家族最小 p；平移樣本同樣算一次（留一），看實際最小 p 落在哪
    cols = list(zip(*allfam))

    def pval(v, col, skip=None):
        others = [c for i, c in enumerate(col) if i != skip]
        return (sum(c >= v for c in others) + 1) / (len(others) + 1)

    real_minp = min(pval(x[1], cols[i]) for i, x in enumerate(real))
    null_minp = [min(pval(allfam[k][i], cols[i], skip=k) for i in range(len(real))) for k in range(K)]
    pm = (sum(v <= real_minp for v in null_minp) + 1) / (K + 1)
    L.append(f"  最小 p 值：實際家族最小單組 p {real_minp:.3f}；平移樣本的家族最小 p 中位 {sorted(null_minp)[K // 2]:.3f}｜家族 p {pm:.3f}（各組先和自己的分布比，不偏袒訊號多的組）")
    txt = "\n".join(L) + "\n"
    print(txt)
    open(os.path.join(HERE, "結果_研究129_外資期貨加碼多重檢定.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
