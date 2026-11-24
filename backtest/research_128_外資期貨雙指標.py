"""研究 128：外資台指期「未平倉變化 z」與「交易口數淨額 z」同時 > x 才加碼（雙指標確認）vs 任一 vs 單一（研究 120／127）
v3 在場、隔天開盤、加 0.5／1x 抱 5 天、排除結算日；00631L＋台指期真實價 2018-06～；隨機對照 150 次
用法：python -X utf8 backtest/research_128_外資期貨雙指標.py
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
    ns = {"__file__": os.path.join(HERE, "research_75b_外資期貨加減碼_真實價.py"), "__name__": "r128"}
    exec(compile(code, "r128", "exec"), ns)
    ns["ENTRY"] = "day_open"
    ns["r64"].state_series = lambda: S

    def res(sig):
        ns["r75"].zseries = lambda: sig
        return {float(x.split()[1]): (float(x.split()[2]), float(x.split()[3])) for x in ns["main"]() if x.startswith("RES")}

    days = [d for d in zo if d in zf and zo[d] is not None and zf[d] is not None and d not in excl]
    rng = random.Random(128)
    L = ["研究 128：外資台指期雙指標確認（v3 在場加碼、隔天開盤、抱 5 天、排除結算日；2018-06～；現行 48.2%／-27.1%）"]
    for th in (1.0, 1.5):
        for nm, f in (("只看未平倉", lambda d: zo[d] > th), ("只看交易淨額", lambda d: zf[d] > th),
                      ("兩者都過", lambda d: zo[d] > th and zf[d] > th), ("任一過", lambda d: zo[d] > th or zf[d] > th)):
            sig = {d: 3.0 for d in days if f(d)}
            r = res(sig)
            sims = sorted(res({d: 3.0 for d in rng.sample(days, len(sig))})[0.5][0] for _ in range(100))
            p = (sum(s >= r[0.5][0] for s in sims) + 1) / 101
            L.append(f"門檻 {th} {nm:8s} 訊號 {len(sig):3d} 天：加0.5x {r[0.5][0]:.1%}／{r[0.5][1]:.1%}｜加1x {r[1.0][0]:.1%}／{r[1.0][1]:.1%}｜隨機 p {p:.2f}")
    txt = "\n".join(L) + "\n"
    print(txt)
    open(os.path.join(HERE, "結果_研究128_外資期貨雙指標.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
