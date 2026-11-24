"""研究 120：研究 75／79 修正後的最終版——「外資台指期大回補 → 在場時隔天開盤加 1x 台指期抱 H 天、排除結算日與次日」
在 v3 現行策略上的鄰近參數：x 1.25／1.5／1.75／2.0 × H 3／5／7／10 × 加碼 0.5／1x（00631L＋台指期真實價，2018-06～）
用法：python -X utf8 backtest/research_120_外資期貨加碼_最終版鄰近參數.py
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
    b.ENTRY = "day_open"
    fdates, fday, _n, _near = b.r63d.load()
    last_day = {}
    for d in fdates:
        for m in fday[d]:
            last_day[m] = d
    settle = set(last_day.values())
    excl = settle | {fdates[i + 1] for i, d in enumerate(fdates[:-1]) if d in settle}
    Z = b.r75.zseries()
    Zx = {d: (None if d in excl else z) for d, z in Z.items()}
    S = load("r76", "research_76_加碼候選在v3重驗.py").v3_states()
    b.r64.state_series = lambda: S
    b.r75.zseries = lambda: Zx
    # 借用 75b 的 main 取得現行基準，再直接用 x／H 格點：改寫 main 的格點太繁瑣 → 用 75d 的做法（換掉迴圈）
    src = open(os.path.join(HERE, "research_75b_外資期貨加減碼_真實價.py"), encoding="utf-8").read()
    a = src.index("    for x in (1.5, 2.0):")
    z = src.index("    return L")
    grid = '''    for add in (0.5, 1.0):
        for x in (1.25, 1.5, 1.75, 2.0):
            cells = []
            for H in (3, 5, 7, 10):
                c, d_ = run(x=x, add=add, Hadd=H)
                cells.append(f"H{H} {c:5.1%}／{d_:6.1%}")
            L.append(f"加{add}x x{x}  " + " ｜ ".join(cells))
'''
    ns = {"__file__": os.path.join(HERE, "research_75b_外資期貨加減碼_真實價.py"), "__name__": "r120_grid"}
    code = src[:a] + grid + src[z:]
    code = code[:code.index("def run_all():")]
    exec(compile(code, "r120_grid", "exec"), ns)
    ns["ENTRY"] = "day_open"
    ns["r64"].state_series = lambda: S
    ns["r75"].zseries = lambda: Zx
    L = ["研究 120：外資期貨大回補加碼（最終版：只加碼、排除結算日與次日）× v3 現行 鄰近參數（隔天開盤進）"] + ns["main"]()[1:]
    txt = "\n".join(L) + "\n"
    print(txt)
    open(os.path.join(HERE, "結果_研究120_外資期貨加碼最終版.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
