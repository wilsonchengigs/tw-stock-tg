"""研究 123：外資期貨大回補加碼（研究 120 最終版：排除結算日；v3 現行；隔天開盤進）逐年拆解——好處是否集中在少數年
每年各自從 1/1 起跑（現行狀態沿用 v3 全歷史），比較 現行 vs 加 0.5x 抱 5 天 vs 加 1x 抱 10 天；另列爆量收黑 1x 抱 10 天
用法：python -X utf8 backtest/research_123_外資期貨加碼逐年.py
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
    b = load("r75b", "research_75b_外資期貨加減碼_真實價.py")
    fdates, fday, _n, _near = b.r63d.load()
    last_day = {}
    for d in fdates:
        for m in fday[d]:
            last_day[m] = d
    settle = set(last_day.values())
    excl = settle | {fdates[i + 1] for i, d in enumerate(fdates[:-1]) if d in settle}
    Z = {d: (None if d in excl else z) for d, z in b.r75.zseries().items()}
    S = load("r76", "research_76_加碼候選在v3重驗.py").v3_states()
    src = open(os.path.join(HERE, "research_75b_外資期貨加減碼_真實價.py"), encoding="utf-8").read()
    a = src.index("    for x in (1.5, 2.0):")
    zz = src.index("    return L")
    grid = '''    for nm, kw in (("base", {}), ("z05", dict(x=1.5, add=0.5, Hadd=5)), ("z10", dict(x=1.5, add=1.0, Hadd=10)), ("vol", dict(vol=1.0))):
        c, d_ = run(**kw)
        L.append(f"RES {nm} {c} {d_}")
'''
    code = src[:a] + grid + src[zz:]
    code = code[:code.index("def run_all():")]
    out = ["研究 123：外資期貨加碼逐年（v3 現行；年報酬／年內最大回檔）", "年份   現行            外資0.5x抱5      外資1x抱10       爆量收黑1x抱10"]
    better = {"z05": 0, "z10": 0, "vol": 0}
    worse = {"z05": 0, "z10": 0, "vol": 0}
    for y in range(2019, 2027):
        c2 = code.replace('"2018-06-05"', f'"{y}-01-01"').replace("DAYS[i] >= \"{y}-01-01\"", "")
        c2 = c2.replace("and DAYS[i] >= \"" + f"{y}-01-01" + "\"]", f"and \"{y}-01-01\" <= DAYS[i] <= \"{y}-12-31\"]")
        ns = {"__file__": os.path.join(HERE, "research_75b_外資期貨加減碼_真實價.py"), "__name__": "r123"}
        exec(compile(c2, "r123", "exec"), ns)
        ns["ENTRY"] = "day_open"
        ns["r64"].state_series = lambda: S
        ns["r75"].zseries = lambda: Z
        res = {}
        for ln in ns["main"]():
            if ln.startswith("RES"):
                _, k, c, d_ = ln.split()
                res[k] = (float(c), float(d_))
        # 年化 → 年報酬（期間約 1 年，近似）
        cells = [f"{res[k][0]:+6.1%}／{res[k][1]:6.1%}" for k in ("base", "z05", "z10", "vol")]
        for k in better:
            better[k] += res[k][0] > res["base"][0] + 1e-6
            worse[k] += res[k][0] < res["base"][0] - 1e-6
        out.append(f"{y}  " + "  ".join(cells))
    out.append(f"\n較好／較差年數：外資0.5x {better['z05']}／{worse['z05']}、外資1x {better['z10']}／{worse['z10']}、爆量收黑 {better['vol']}／{worse['vol']}（共 8 年；2026 至 11/20）")
    txt = "\n".join(out) + "\n"
    print(txt)
    open(os.path.join(HERE, "結果_研究123_外資期貨加碼逐年.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
