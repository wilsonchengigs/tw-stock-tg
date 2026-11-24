"""研究 127：外資台指期「交易口數淨額」（當天多方交易 − 空方交易）vs「未平倉變化」（研究 73／120）當在場加碼訊號
兩者都轉成相對過去 250 日 z，排除結算日與次日；v3 在場時隔天開盤加 0.5／1x 抱 5 天；00631L＋台指期真實價 2018-06～；隨機對照 150 次
用法：python -X utf8 backtest/research_127_外資期貨交易淨額.py
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


def zmap(series):
    ds = sorted(series)
    out, hist = {}, []
    for d in ds:
        v = series[d]
        if len(hist) >= 120:
            h = hist[-250:]
            m = sum(h) / len(h)
            sd = (sum((x - m) ** 2 for x in h) / len(h)) ** 0.5
            out[d] = (v - m) / sd if sd > 0 else None
        hist.append(v)
    return out


def main():
    flow, oi = {}, {}
    for r in csv.DictReader(open(os.path.join(HERE, "tx_inst_oi.csv"), encoding="utf-8")):
        if r["investor"] == "外資":
            flow[r["date"]] = int(r["long_vol"]) - int(r["short_vol"])
            oi[r["date"]] = int(r["long_oi"]) - int(r["short_oi"])
    ods = sorted(oi)
    doi = {ods[k]: oi[ods[k]] - oi[ods[k - 1]] for k in range(1, len(ods))}
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
    grid = '''    for x in (1.5, 2.0):
        for add in (0.5, 1.0):
            c, d_ = run(x=x, add=add, Hadd=5)
            L.append(f"RES {x} {add} {c} {d_}")
'''
    code = src[:a] + grid + src[zz:]
    code = code[:code.index("def run_all():")]
    ns = {"__file__": os.path.join(HERE, "research_75b_外資期貨加減碼_真實價.py"), "__name__": "r127"}
    exec(compile(code, "r127", "exec"), ns)
    ns["ENTRY"] = "day_open"
    ns["r64"].state_series = lambda: S

    def results(Z):
        ns["r75"].zseries = lambda: Z
        out = {}
        for ln in ns["main"]():
            if ln.startswith("RES"):
                _, x, add, c, d_ = ln.split()
                out[(float(x), float(add))] = (float(c), float(d_))
        return out

    L = ["研究 127：外資台指期 交易口數淨額 vs 未平倉變化（v3 在場加碼、隔天開盤、抱 5 天、排除結算日；2018-06～）"]
    rng = random.Random(127)
    for nm, ser in (("未平倉變化（研究 120）", doi), ("交易口數淨額", flow)):
        Z = {d: (None if d in excl else z) for d, z in zmap(ser).items()}
        res = results(Z)
        k_up = sum(1 for z in Z.values() if z is not None and z > 1.5)
        days = [d for d, z in Z.items() if z is not None]
        sims = []
        for _ in range(150):
            fake = {d: 3.0 for d in rng.sample(days, k_up)}
            sims.append(results(fake)[(1.5, 0.5)][0])
        sims.sort()
        real = res[(1.5, 0.5)][0]
        p = (sum(s >= real for s in sims) + 1) / 151
        L.append(f"\n== {nm}（z>1.5 訊號 {k_up} 天）==")
        for (x, add), (c, d_) in sorted(res.items()):
            L.append(f"  x{x} 加{add}x 抱5天：{c:.1%}／{d_:.1%}")
        L.append(f"  隨機對照（x1.5 加 0.5x）：真實 {real:.1%}；隨機中位 {sims[75]:.1%}、95 分位 {sims[142]:.1%}；p＝{p:.3f}")
    txt = "\n".join(L) + "\n"
    print(txt)
    open(os.path.join(HERE, "結果_研究127_外資期貨交易淨額.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
