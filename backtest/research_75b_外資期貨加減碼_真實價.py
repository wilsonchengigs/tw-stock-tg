"""研究 75b：研究 75 的真實價格版（研究 75 用加權收盤 13:30，但台指期 13:45 收、法人資料 15:00 公布 → 偷看了 13:30～13:45，作廢）

現行部位：00631L 真實還原價（狀態同研究 64：週五判斷、下一交易日收盤成交）
加減碼：台指期近月真實價；訊號日 d（法人 15:00 公布）→ 當晚夜盤開盤（期交所記在下一交易日的 night 列）進場，
        第 H 個交易日日盤收盤出；現行出場則一起平；換月接續；成本 3 點
A 加碼 a 倍：外資 Δz > +x；B 減碼（空 1 倍台指期）：Δz < −x；C A＋B；另與研究 64b（爆量收黑）並列與合併
期間：2018-06-05～2026-11-20
用法：python -X utf8 backtest/research_75b_外資期貨加減碼_真實價.py
"""
import importlib.util
import json
import os
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


r75 = load("r75", "research_75_在場時外資期貨加減碼.py")
r63d = load("r63d", "research_63d_爆量收黑_台指期真實價.py")
ENTRY = 'night_open'
r64 = r75.m.r64
DAYS, PX, VR = r64.DAYS, r64.PX, r64.VR


def main():
    Z = r75.zseries()
    r = json.load(open(os.path.join(HERE, "00631L.TW.json")))
    E = {datetime.fromtimestamp(t, timezone(timedelta(hours=8))).strftime("%Y-%m-%d"): v
         for t, v in zip(r["timestamp"], r["indicators"]["adjclose"][0]["adjclose"]) if v}
    fdates, fday, fnight, near = r63d.load()
    fidx = {d: i for i, d in enumerate(fdates)}
    st = r64.state_series()
    idx = [i for i in range(len(DAYS)) if DAYS[i] in E and DAYS[i] in fidx and DAYS[i] >= "2018-06-05"]

    def fut_path(d, H, side):
        """訊號日 d：當晚夜盤開盤進，回傳 [(日期, 當日報酬)] 共 H 個日盤"""
        j = fidx[d]
        if j + H >= len(fdates):
            return []
        d1 = fdates[j + 1]
        m = near[d1]
        nb = fnight[d1].get(m)
        px = (nb[0] if nb else fday[d1][m][0]) if ENTRY == 'night_open' else ((nb[3] if nb else fday[d1][m][0]) if ENTRY == 'night_close' else fday[d1][m][0])
        out, prev = [], px
        for k in range(j + 1, j + H + 1):
            dk = fdates[k]
            b = fday[dk].get(m)
            if b is None:  # 換月
                m = near[dk]
                b = fday[dk][m]
                pb = fday[fdates[k - 1]].get(m)
                prev = pb[3] if pb else b[0]
            out.append((dk, side * (b[3] / prev - 1) - (3 / px if k == j + 1 else 0)))
            prev = b[3]
        return out

    def run(x=None, add=0.0, Hadd=5, cut=False, Hcut=5, vol=0.0, Hvol=10):
        eq = peak = 1.0
        mdd = 0.0
        pos = False
        legs = []  # [(剩餘報酬 dict, 倍數, 結束日)]
        prev_i = None
        for i in idx:
            d = DAYS[i]
            if prev_i is not None:
                rr = E[d] / E[DAYS[prev_i]] - 1 if pos else 0.0  # 00631L 本身就是 2x
                for path, a, _end, _k in legs:
                    rr += a * path.get(d, 0.0)
                eq *= 1 + rr
            want = st[i - 1]
            if want != pos:
                eq *= 1 - 0.0025 * 2
                pos = want
            legs = [lg for lg in legs if lg[2] > d and pos]
            if pos and st[i]:
                z = Z.get(d)
                busy_z = any(lg[3] == "z" for lg in legs)
                if x is not None and z is not None and not busy_z:
                    if add and z > x:
                        p = fut_path(d, Hadd, 1)
                        if p:
                            legs.append((dict(p), add, p[-1][0], "z"))
                    elif cut and z < -x:
                        p = fut_path(d, Hcut, -1)
                        if p:
                            legs.append((dict(p), 1.0, p[-1][0], "z"))
                if vol and not any(lg[3] == "v" for lg in legs) and VR[i] is not None and VR[i] >= 1.5 and PX[i] < PX[i - 1]:
                    p = fut_path(d, Hvol, 1)
                    if p:
                        legs.append((dict(p), vol, p[-1][0], "v"))
            peak = max(peak, eq)
            mdd = min(mdd, eq / peak - 1)
            prev_i = i
        yrs = (len(idx) - 1) / 245
        return eq ** (1 / yrs) - 1, mdd

    L = [f"研究 75b：在場時外資台指期大變化加減碼——真實價（00631L＋台指期；{DAYS[idx[0]]}～{DAYS[idx[-1]]}）；進場時點 {ENTRY}"]
    b = run()
    L.append(f"現行（00631L 真實）       {b[0]:6.1%}／{b[1]:6.1%}")
    v = run(vol=1.0)
    L.append(f"研究 64b 爆量收黑加1x抱10  {v[0]:6.1%}／{v[1]:6.1%}（{v[0] - b[0]:+.1%}）")
    for x in (1.5, 2.0):
        for nm, kw in (("A 加0.5x抱5", dict(add=0.5)), ("A 加1x抱5", dict(add=1.0)), ("A 加1x抱10", dict(add=1.0, Hadd=10)),
                       ("B 空1x 5天", dict(cut=True)), ("C 加1x抱5＋空1x", dict(add=1.0, cut=True)), ("A 加1x抱5＋64b", dict(add=1.0, vol=1.0))):
            c, d_ = run(x=x, **kw)
            L.append(f"x{x} {nm:16s} {c:6.1%}／{d_:6.1%}（{c - b[0]:+.1%}）")
    return L


def run_all():
    global ENTRY
    out = []
    for e in ("night_open", "night_close", "day_open"):
        ENTRY = e
        out += main() + [""]
    txt = chr(10).join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究75b_外資期貨加減碼真實價.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    run_all()
