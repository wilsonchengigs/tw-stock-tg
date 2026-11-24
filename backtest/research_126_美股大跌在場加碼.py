"""研究 126：v3 現行在場時，美股前一晚大跌（^NDX 或 ^GSPC ≤ −x%）→ 台股當天開盤加台指期 a 倍抱 H 天（多頭中被美股拖累的急跌）
訊號對應：美國日期 E 大跌 → 台灣下一個交易日 t 開盤進；在研究 75b 引擎中「訊號日」＝ t 的前一個台灣交易日（引擎於訊號日隔天開盤進）
真實價：00631L＋台指期近月，2015-10～；另跑 2018-06～；隨機對照（同次數隨機日期，200 次）
用法：python -X utf8 backtest/research_126_美股大跌在場加碼.py
"""
import importlib.util
import json
import os
import random
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def us_ret(fn):
    r = json.load(open(os.path.join(HERE, fn)))
    c = r["indicators"]["quote"][0]["close"]
    rows = [(datetime.fromtimestamp(t, timezone(timedelta(hours=-5))).strftime("%Y-%m-%d"), x) for t, x in zip(r["timestamp"], c) if x]
    return {rows[i][0]: rows[i][1] / rows[i - 1][1] - 1 for i in range(1, len(rows))}


def main():
    S = load("r76", "research_76_加碼候選在v3重驗.py").v3_states()
    src = open(os.path.join(HERE, "research_75b_外資期貨加減碼_真實價.py"), encoding="utf-8").read()
    a = src.index("    for x in (1.5, 2.0):")
    zz = src.index("    return L")
    grid = '''    for add in (0.5, 1.0):
        cells = []
        for H in (5, 10):
            c, d_ = run(x=1.0, add=add, Hadd=H)
            cells.append(f"H{H} {c:5.1%}／{d_:6.1%}")
        L.append(f"加{add}x  " + " ｜ ".join(cells))
    c, d_ = run(x=1.0, add=1.0, Hadd=10)
    L.append(f"RES {c} {d_}")
'''
    code = src[:a] + grid + src[zz:]
    code = code[:code.index("def run_all():")]
    b = load("r63d", "research_63d_爆量收黑_台指期真實價.py")
    tw = [d for d in b.load()[0]]
    out = ["研究 126：美股前一晚大跌 → v3 在場時台股開盤加台指期（00631L＋台指期真實價）"]
    for usnm, fn in (("NDX", "NDX.json"), ("S&P500", "GSPC.json")):
        U = us_ret(fn)
        for th in (0.02, 0.03):
            sig = {}
            for E, r in U.items():
                if r <= -th:
                    t = next((d for d in tw if d > E), None)
                    if t:
                        k = tw.index(t)
                        if k > 0:
                            sig[tw[k - 1]] = 3.0
            for start in ("2015-10-01", "2018-06-05"):
                ns = {"__file__": os.path.join(HERE, "research_75b_外資期貨加減碼_真實價.py"), "__name__": "r126"}
                exec(compile(code.replace('"2018-06-05"', f'"{start}"'), "r126", "exec"), ns)
                ns["ENTRY"] = "day_open"
                ns["r64"].state_series = lambda: S
                ns["r75"].zseries = lambda s=sig: s
                res = ns["main"]()
                real = [float(x.split()[1]) for x in res if x.startswith("RES")][0]
                lines = [x for x in res[1:] if not x.startswith(("RES", "研究 64b"))]
                # 隨機對照（只跑 1x 抱 10）
                rng = random.Random(126)
                pool = [d for d in tw if d >= start]
                sims = []
                for _ in range(150):
                    fake = {d: 3.0 for d in rng.sample(pool, len([d for d in sig if d >= start]))}
                    ns["r75"].zseries = lambda f=fake: f
                    sims.append([float(x.split()[1]) for x in ns["main"]() if x.startswith("RES")][0])
                sims.sort()
                p = (sum(s >= real for s in sims) + 1) / 151
                out.append(f"\n== {usnm} ≤ -{th:.0%}，起點 {start}（訊號 {len([d for d in sig if d >= start])} 天，含空手日）==")
                out += lines
                out.append(f"  隨機對照（加 1x 抱 10）：真實 {real:.1%}；隨機中位 {sims[75]:.1%}、95 分位 {sims[142]:.1%}；p＝{p:.3f}")
    txt = "\n".join(out) + "\n"
    print(txt)
    open(os.path.join(HERE, "結果_研究126_美股大跌在場加碼.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
