"""研究 121：外資「現貨」單週大買（研究 69 的週資料 z）→ 在場時下週一開盤加台指期 a 倍抱 H 天（v3 現行；00631L＋台指期真實價）
訊號：單週外資買賣超相對過去 52 週 z > x（週五收盤後已知；BFI82U 週報）；沿用研究 75b 的引擎（隔天開盤進），把日訊號換成週訊號
期間：2018-06～（與研究 75 同期，方便比較）；另跑 2015-10～（00631L 真實價起點）
用法：python -X utf8 backtest/research_121_外資現貨週大買加碼.py
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
    Zw = {d: z for d, z in zip(r69.WD, z1) if z is not None}
    S = load("r76", "research_76_加碼候選在v3重驗.py").v3_states()
    src = open(os.path.join(HERE, "research_75b_外資期貨加減碼_真實價.py"), encoding="utf-8").read()
    a = src.index("    for x in (1.5, 2.0):")
    zz = src.index("    return L")
    grid = '''    for add in (0.5, 1.0):
        for x in (1.5, 2.0, 2.5):
            cells = []
            for H in (5, 10, 20):
                c, d_ = run(x=x, add=add, Hadd=H)
                cells.append(f"H{H} {c:5.1%}／{d_:6.1%}")
            L.append(f"加{add}x 週z>{x}  " + " ｜ ".join(cells))
'''
    code = src[:a] + grid + src[zz:]
    code = code[:code.index("def run_all():")]
    out = ["研究 121：外資現貨單週大買 → 在場時下週一開盤加碼（v3 現行；00631L＋台指期真實價）",
           f"單週 z>1.5 的週數 {sum(1 for z in Zw.values() if z > 1.5)}、z>2 {sum(1 for z in Zw.values() if z > 2)}（2004～）"]
    for start in ("2018-06-05", "2015-10-01"):
        ns = {"__file__": os.path.join(HERE, "research_75b_外資期貨加減碼_真實價.py"), "__name__": "r121"}
        exec(compile(code.replace('"2018-06-05"', f'"{start}"'), "r121", "exec"), ns)
        ns["ENTRY"] = "day_open"
        ns["r64"].state_series = lambda: S
        ns["r75"].zseries = lambda: Zw
        out.append(f"\n== 起點 {start} ==")
        out += ns["main"]()[1:]
    txt = "\n".join(out) + "\n"
    print(txt)
    open(os.path.join(HERE, "結果_研究121_外資現貨週大買加碼.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()


def random_control(reps=200):
    """隨機對照：把「週大買」換成同樣多的隨機週（週五），在 2015-10 起、加 1x、z>2 → 1 次訊號＝隨機週，抱 20 天"""
    import random
    r69 = load("r69", "research_69_外資週買賣超.py")
    z1 = r69.zseries if False else r69.zscore(r69.FV, 1)
    Zw = {d: z for d, z in zip(r69.WD, z1) if z is not None}
    S = load("r76", "research_76_加碼候選在v3重驗.py").v3_states()
    src = open(os.path.join(HERE, "research_75b_外資期貨加減碼_真實價.py"), encoding="utf-8").read()
    a = src.index("    for x in (1.5, 2.0):")
    zz = src.index("    return L")
    grid = '''    c, d_ = run(x=2.0, add=1.0, Hadd=20)
    L.append(f"RES {c} {d_}")
'''
    code = src[:a] + grid + src[zz:]
    code = code[:code.index("def run_all():")].replace('"2018-06-05"', '"2015-10-01"')
    ns = {"__file__": os.path.join(HERE, "research_75b_外資期貨加減碼_真實價.py"), "__name__": "r121r"}
    exec(compile(code, "r121r", "exec"), ns)
    ns["ENTRY"] = "day_open"
    ns["r64"].state_series = lambda: S

    def res_of(Zmap):
        ns["r75"].zseries = lambda: Zmap
        ln = [x for x in ns["main"]() if x.startswith("RES")][0].split()
        return float(ln[1]), float(ln[2])
    real = res_of(Zw)
    weeks = [d for d in Zw if d >= "2015-09-01"]
    k = sum(1 for d in weeks if Zw[d] > 2.0)
    rng = random.Random(121)
    sims = []
    for _ in range(reps):
        pick = set(rng.sample(weeks, k))
        sims.append(res_of({d: (3.0 if d in pick else 0.0) for d in weeks})[0])
    sims.sort()
    p = (sum(s >= real[0] for s in sims) + 1) / (reps + 1)
    line = f"隨機對照（2015-10～、加 1x、週 z>2、抱 20 天；{k} 個訊號週）：真實 {real[0]:.1%}；隨機 中位 {sims[reps // 2]:.1%}、95 分位 {sims[int(reps * 0.95)]:.1%}；p＝{p:.3f}"
    print(line)
    with open(os.path.join(HERE, "結果_研究121_外資現貨週大買加碼.txt"), "a", encoding="utf-8") as f:
        f.write("\n" + line + "\n")


if __name__ == "__main__" and os.environ.get("R121_RANDOM"):
    random_control()
