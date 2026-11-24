"""研究 134：外資現貨單週大買加碼（研究 121，候選弱）的家族多重檢定——比照研究 129～131
- 家族：研究 121 格點 加 0.5／1x × 週 z > 1.5／2／2.5 × 抱 5／10／20 天共 18 組；2015-10～（00631L 真實價），v3 在場才加
- 虛無假設：外資週買賣超 z 與之後行情無關；週 z 序列（2004～ 全部週）環狀平移（避開 ±26 週）
- 家族 p：最小 p 值法
用法：python -X utf8 backtest/research_134_外資現貨週大買多重檢定.py（R134_SHIFTS 控制平移次數，預設 200）
"""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    r69 = load("r69", "research_69_外資週買賣超.py")
    z1 = r69.zscore(r69.FV, 1)
    weeks = [d for d, z in zip(r69.WD, z1) if z is not None]
    zs = [z for z in z1 if z is not None]
    S = load("r76", "research_76_加碼候選在v3重驗.py").v3_states()
    src = open(os.path.join(HERE, "research_75b_外資期貨加減碼_真實價.py"), encoding="utf-8").read()
    a = src.index("    for x in (1.5, 2.0):")
    zz = src.index("    return L")
    grid = '''    for add in (0.5, 1.0):
        for x in (1.5, 2.0, 2.5):
            for H in (5, 10, 20):
                c, d_ = run(x=x, add=add, Hadd=H)
                L.append(f"RES {add} {x} {H} {c} {d_}")
'''
    code = src[:a] + grid + src[zz:]
    code = code[:code.index("def run_all():")].replace('"2018-06-05"', '"2015-10-01"')
    ns = {"__file__": os.path.join(HERE, "research_75b_外資期貨加減碼_真實價.py"), "__name__": "r134"}
    exec(compile(code, "r134", "exec"), ns)
    ns["ENTRY"] = "day_open"
    ns["r64"].state_series = lambda: S

    def fam(shift):
        n = len(weeks)
        Zw = {weeks[p]: zs[(p - shift) % n] for p in range(n)}
        ns["r75"].zseries = lambda: Zw
        out = []
        for ln in ns["main"]():
            if ln.startswith("RES"):
                _, ad, x, H, c, d_ = ln.split()
                out.append((f"加{ad}x 週z>{x} 抱{H}", float(c), float(d_)))
        return out

    real = fam(0)
    n = len(weeks)
    K = int(os.environ.get("R134_SHIFTS", "200"))
    gap = 26
    shifts = [gap + round(k * (n - 2 * gap) / (K - 1)) for k in range(K)]
    allfam = []
    for k, s in enumerate(shifts):
        allfam.append([x[1] for x in fam(s)])
        if (k + 1) % 20 == 0:
            print(f"  平移 {k + 1}/{K}", flush=True)
    cols = list(zip(*allfam))

    def pval(v, col, skip=None):
        o = [c for i, c in enumerate(col) if i != skip]
        return (sum(c >= v for c in o) + 1) / (len(o) + 1)

    single = [pval(x[1], cols[g]) for g, x in enumerate(real)]
    L = [f"研究 134：外資現貨週大買加碼家族多重檢定（v3 在場、2015-10～、00631L＋台指期真實價；現行 37.5%／-27.1%）",
         f"家族 {len(real)} 組；週 z 序列環狀平移 {K} 次（{shifts[0]}～{shifts[-1]} 週，共 {n} 週）", ""]
    for g in sorted(range(len(real)), key=lambda g: -real[g][1]):
        L.append(f"  {real[g][0]:16s}：{real[g][1]:.1%}／{real[g][2]:.1%}｜平移中位 {sorted(cols[g])[K // 2]:.1%}｜單組 p {single[g]:.3f}")
    rm = min(single)
    nm = [min(pval(allfam[k][g], cols[g], skip=k) for g in range(len(real))) for k in range(K)]
    pm = (sum(v <= rm for v in nm) + 1) / (K + 1)
    L += ["", f"家族檢定（最小 p 值法）：實際最小單組 p {rm:.3f}；平移樣本家族最小 p 中位 {sorted(nm)[K // 2]:.3f}｜家族 p {pm:.3f}"]
    txt = "\n".join(L) + "\n"
    print(txt)
    open(os.path.join(HERE, "結果_研究134_外資現貨週大買多重檢定.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
