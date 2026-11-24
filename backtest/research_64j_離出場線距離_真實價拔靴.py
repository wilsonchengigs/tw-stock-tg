"""研究 64j：研究 64i 的降風險選項（離出場線 ≥ m% 才加碼）的真實價格與拔靴驗證

1. 真實價格（同研究 64c：00631L＋台指期近月，2015-10～）：m＝0／3／5%
2. 拔靴（同研究 64d：500 條 20 年、平均區塊 250 天）：m＝0／3／5%，距離用路徑自己的 MA80 計算
k 1.5；加 0.5x 抱 5 天、加 1x 抱 10 天
用法：python -X utf8 backtest/research_64j_離出場線距離_真實價拔靴.py
"""
import contextlib
import importlib.util
import io
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


c = load("r64c", "research_64c_在場加碼真實價.py")
d = load("r64d", "research_64d_在場加碼拔靴.py")
bt = d.bt


def real_part(L):
    R, PX, VR = c.r64.R, c.r64.PX, c.VR
    orig = list(VR)
    for mg in (0.0, 0.03, 0.05):
        VR[:] = [v if (v is not None and R.M80[i] is not None and PX[i] >= R.M80[i] * 0.975 * (1 + mg)) else (0.0 if v is not None else None)
                 for i, v in enumerate(orig)]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            c.main()
        lines = [x for x in buf.getvalue().splitlines() if "加" in x or "現行" in x]
        L.append(f"-- 距出場線 ≥{mg:.0%} --")
        L += ["  " + x.strip() for x in lines]
    VR[:] = orig
    with contextlib.redirect_stdout(io.StringIO()):
        c.main()  # 還原研究 64c 的結果檔


def run_path(rets, sigs, add, H, mg):
    px = [100.0]
    for r in rets:
        px.append(px[-1] * (1 + r))
    m60, m80 = d.sma(px, 60), d.sma(px, 80)
    eq = peak = 1.0
    mdd, on, lev, pend, extra, until = 0.0, False, 0.0, None, 0.0, -1
    for i in range(261, len(px)):
        r1 = px[i] / px[i - 1] - 1 + bt.DIV / bt.TD
        Lv = lev + extra
        eq *= 1 + ((Lv * r1 - max(Lv - 1, 0) * bt.DRAG / bt.TD) if Lv > 0 else bt.RC)
        eq = max(eq, 1e-9)
        if pend is not None:
            eq *= 1 - bt.COST * abs(pend - lev)
            lev, pend = pend, None
            if lev == 0:
                extra, until = 0.0, -1
        if i % 5 == 0:
            on = (not px[i] < m80[i] * 0.975) if on else (px[i] > m60[i] * 1.01)
            want = 2.0 if on else 0.0
            if want != lev:
                pend = want
        if extra and i >= until:
            extra, until = 0.0, -1
        if add and lev == 2.0 and pend is None and not extra and sigs[i - 1] and px[i] >= m80[i] * 0.975 * (1 + mg):
            extra, until = add, i + H
            eq *= 1 - 0.0001 * add
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
    return eq ** (1 / d.YEARS) - 1, mdd


def boot_part(L):
    r64, PX, VR, N = d.r64, d.PX, d.VR, d.N
    i0 = next(i for i, x in enumerate(r64.DAYS) if x >= "1998-09-01")
    RET = [PX[i] / PX[i - 1] - 1 for i in range(i0, N)]
    SIG = [bool(VR[i] is not None and VR[i] >= 1.5 and PX[i] < PX[i - 1]) for i in range(i0, N)]
    T = len(RET)
    rng = random.Random(64)  # 與研究 64d 同種子
    paths = []
    for _ in range(500):
        idx, i = [], rng.randrange(T)
        while len(idx) < d.LEN:
            idx.append(i)
            i += 1
            if i >= T or rng.random() < 1 / 250:
                i = rng.randrange(T)
        paths.append(idx)
    base = [run_path([RET[j] for j in p], [False] * d.LEN, 0, 0, 0) for p in paths]

    def summ(res):
        cs = sorted(r[0] for r in res)
        return cs[250], cs[25], sum(r[1] < -0.5 for r in res) / 500, sum(r[1] < -0.6 for r in res) / 500

    b = summ(base)
    L.append(f"現行                    中位 {b[0]:6.1%}  最差5% {b[1]:6.1%}  P(<-50%) {b[2]:4.0%}  P(<-60%) {b[3]:4.0%}")
    for add, H in ((1.0, 10), (0.5, 5)):
        for mg in (0.0, 0.03, 0.05):
            res = [run_path([RET[j] for j in p], [SIG[j] for j in p], add, H, mg) for p in paths]
            s = summ(res)
            win = sum(r[0] > bb[0] for r, bb in zip(res, base)) / 500
            L.append(f"加{add}x 抱{H:2d}天 距≥{mg:.0%}    中位 {s[0]:6.1%}  最差5% {s[1]:6.1%}  P(<-50%) {s[2]:4.0%}  P(<-60%) {s[3]:4.0%}  勝過現行 {win:.0%}")


def main():
    L = ["研究 64j：離出場線 ≥ m% 才加碼——真實價格與拔靴（k 1.5）", "\n== 1. 真實價格（00631L＋台指期，2015-10～）=="]
    real_part(L)
    L.append("\n== 2. 拔靴（500 條 20 年；不含融資濾網）==")
    boot_part(L)
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究64j_離出場線距離驗證.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
