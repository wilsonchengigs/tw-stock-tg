"""研究 122：多個加碼規則同時用的組合風險（v3 現行；00631L＋台指期真實價；2018-06～；外資訊號排除結算日）
組合：爆量收黑（研究 64b）加 0.5／1x 抱 5／10 天 × 外資期貨大回補（研究 120）加 0.5／1x 抱 5 天；兩者可重疊（最多同時 +2x，總曝險 4x）
用法：python -X utf8 backtest/research_122_加碼規則組合風險.py
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
    grid = '''    for va, vh in ((0.0, 10), (0.5, 5), (1.0, 5), (1.0, 10)):
        cells = []
        for za in (0.0, 0.5, 1.0):
            c, d_ = run(x=1.5 if za else None, add=za, Hadd=5, vol=va, Hvol=vh)
            cells.append(f"外資+{za}x {c:5.1%}／{d_:6.1%}")
        L.append(f"爆量收黑 +{va}x 抱{vh:2d}  " + " ｜ ".join(cells))
'''
    code = src[:a] + grid + src[zz:]
    code = code[:code.index("def run_all():")]
    ns = {"__file__": os.path.join(HERE, "research_75b_外資期貨加減碼_真實價.py"), "__name__": "r122"}
    exec(compile(code, "r122", "exec"), ns)
    ns["ENTRY"] = "day_open"
    ns["r64"].state_series = lambda: S
    ns["r75"].zseries = lambda: Z
    out = ["研究 122：加碼規則組合（v3 現行；2018-06～；年化／最大回檔）"] + ns["main"]()[1:]
    txt = "\n".join(out) + "\n"
    print(txt)
    open(os.path.join(HERE, "結果_研究122_加碼組合風險.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
