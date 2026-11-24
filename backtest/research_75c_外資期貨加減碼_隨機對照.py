"""研究 75c：研究 75b（外資期貨大變化加減碼，真實價、隔天開盤進）的隨機對照
把外資 Δz 的「訊號日」換成隨機日期（同樣多的 > +x 與 < −x 次數、只從有資料的日子抽），200 次，看真實訊號的年化排第幾
用法：python -X utf8 backtest/research_75c_外資期貨加減碼_隨機對照.py
"""
import importlib.util
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r75b", os.path.join(HERE, "research_75b_外資期貨加減碼_真實價.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def pick(L, key):
    for ln in L:
        if ln.startswith(key):
            return float(ln.split()[-1].split("／")[0].rstrip("%").split("（")[0].replace("%", "")) if False else ln
    return None


def cagr_of(L, key):
    ln = next(x for x in L if x.startswith(key))
    v = ln[len(key):].strip().split("／")[0].strip().rstrip("%")
    return float(v) / 100


def main():
    m.ENTRY = "day_open"
    real_Z = m.r75.zseries()
    keys = ("x1.5 C 加1x抱5＋空1x", "x1.5 A 加1x抱5", "x1.5 B 空1x 5天")
    real = m.main()
    rv = {k: cagr_of(real, k) for k in keys}
    days = [d for d, z in real_Z.items() if z is not None]
    n_up = sum(1 for z in real_Z.values() if z is not None and z > 1.5)
    n_dn = sum(1 for z in real_Z.values() if z is not None and z < -1.5)
    rng = random.Random(753)
    sims = {k: [] for k in keys}
    orig = m.r75.zseries
    for _ in range(200):
        pick_ = rng.sample(days, n_up + n_dn)
        fake = {d: 0.0 for d in days}
        for d in pick_[:n_up]:
            fake[d] = 3.0
        for d in pick_[n_up:]:
            fake[d] = -3.0
        m.r75.zseries = lambda f=fake: f
        Lr = m.main()
        for k in keys:
            sims[k].append(cagr_of(Lr, k))
    m.r75.zseries = orig
    out = ["研究 75c：外資期貨加減碼的隨機對照（隔天開盤進；200 次隨機訊號日，同樣的多／空次數）",
           f"真實訊號次數：大回補 {n_up}、大加空 {n_dn}"]
    for k in keys:
        s = sorted(sims[k])
        p = (sum(x >= rv[k] for x in s) + 1) / 201
        out.append(f"{k:16s} 真實 {rv[k]:.1%}；隨機 中位 {s[100]:.1%}、95 分位 {s[190]:.1%}；p＝{p:.3f}")
    txt = "\n".join(out) + "\n"
    print(txt)
    open(os.path.join(HERE, "結果_研究75c_隨機對照.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
