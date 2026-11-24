"""研究 79：研究 75 的外資期貨訊號是否來自「結算日」的機械性未平倉變化？
法人未平倉是全部月份合計，結算日（每月第三個星期三，台指期近月最後交易日）到期部位消失，可能產生大 Δ。
排除結算日與其後 1 個交易日的訊號，重跑研究 75b（隔天開盤進；舊版與 v3 現行）
用法：python -X utf8 backtest/research_79_外資期貨訊號_排除結算日.py
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
    after = {fdates[i + 1] for i, d in enumerate(fdates[:-1]) if d in settle}
    excl = settle | after
    Z = b.r75.zseries()
    n_sig = sum(1 for z in Z.values() if z is not None and abs(z) > 1.5)
    n_ex = sum(1 for d, z in Z.items() if z is not None and abs(z) > 1.5 and d in excl)
    Zx = {d: (None if d in excl else z) for d, z in Z.items()}
    S = load("r76", "research_76_加碼候選在v3重驗.py").v3_states()
    out = [f"研究 79：排除結算日與次日的外資期貨訊號（|z|>1.5 訊號 {n_sig} 個，其中 {n_ex} 個在結算日或次日）"]
    old_state = b.r64.state_series
    for lab, st in (("舊版現行", None), ("v3 現行", S)):
        if st is not None:
            b.r64.state_series = lambda s=st: s
        b.r75.zseries = lambda z=Z: z
        out.append(f"\n== {lab}：全部訊號 ==")
        out += [x for x in b.main()[1:] if x.startswith(("現行", "x1.5"))]
        b.r75.zseries = lambda z=Zx: z
        out.append(f"== {lab}：排除結算日與次日 ==")
        out += [x for x in b.main()[1:] if x.startswith(("現行", "x1.5"))]
        b.r64.state_series = old_state
    txt = "\n".join(out) + "\n"
    print(txt)
    open(os.path.join(HERE, "結果_研究79_排除結算日.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
