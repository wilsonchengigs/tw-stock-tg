"""研究 141：現行加碼疊加時的總曝險上限（投顧簡報「單一部位上限」觀念，研究 138 的延伸）

現行：v3 在場 2x（00631L）＋爆量收黑加 1x 台指期抱 10 天（V）＋外資雙指標加 0.5x 抱 5 天（F），同時觸發時總曝險可到 3.5x。
測：總曝險上限 cap ∈ {無, 3.0, 2.5}，以及「V、F 同時持有時只留一個」；加碼在進場時依剩餘額度縮小
引擎（精簡版，與研究 135 同規則）：2018-06-05～；00631L 真實價（v3 狀態同研究 138）；台指期近月真實價（研究 139 load_tx）
- V：證交所成交金額 ≥ 前 20 日均 1.5 倍且加權收黑、v3 在場 → 隔天日盤開盤進、第 10 個日盤收盤出
- F：外資台指期淨未平倉變化 z 與交易淨額 z 都 > 1.5（250 日 z）、排除結算日與次日、v3 在場 → 隔天開盤進、抱 5 天
- 持有中同一條訊號再出現略過；v3 出場當天一起平；成本每次進出 3 點×口數比例
另：區塊拔靴（平均區塊 60 日，2000 次）看各 cap 的年化差、最大回檔差分布
用法：python -X utf8 backtest/research_141_加碼總曝險上限.py
"""
import csv
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


R139 = _load("r139", "research_139_日夜盤報酬拆解.py")
R127 = _load("r127", "research_127_外資期貨交易淨額.py")
R138 = R139.R138
V, bt = R138.V, R138.bt
COST = 3.0


def build():
    dates, day, night, near = R139.load_tx()
    last_day = {}
    for d in dates:
        for m in day[d]:
            last_day[m] = d
    settle = set(last_day.values())
    excl = settle | {dates[k + 1] for k, d in enumerate(dates[:-1]) if d in settle}
    flow, oi = {}, {}
    for r in csv.DictReader(open(os.path.join(HERE, "tx_inst_oi.csv"), encoding="utf-8")):
        if r["investor"] == "外資":
            flow[r["date"]] = int(r["long_vol"]) - int(r["short_vol"])
            oi[r["date"]] = int(r["long_oi"]) - int(r["short_oi"])
    ods = sorted(oi)
    doi = {ods[k]: oi[ods[k]] - oi[ods[k - 1]] for k in range(1, len(ods))}
    zo, zf = R127.zmap(doi), R127.zmap(flow)
    bi = {d: k for k, d in enumerate(R138.DAYS)}
    seq = [d for d in dates if d >= "2018-06-05" and d in bi]
    T = []
    for k, d in enumerate(seq):
        i = bi[d]
        m = near[d]
        o, c = day[d][m][0], day[d][m][3]
        pm = near[seq[k - 1]] if k else m
        prev = day[seq[k - 1]].get(m) if k else None
        rcc = (c / prev[3] - 1) if prev else 0.0
        if k and m != pm:
            rcc -= 2.0 / c
        amts = [R139.AMT.get(R138.DAYS[j]) for j in range(i - 20, i)]
        amts = [a for a in amts if a]
        a0 = R139.AMT.get(d)
        vr = a0 / (sum(amts) / len(amts)) if a0 and len(amts) >= 16 else None
        T.append(dict(d=d, i=i, o=o, c=c, rcc=rcc, roc=c / o - 1, st=R138.ST[i], r2=V.R2R[i],
                      vsig=vr is not None and vr >= 1.5 and bt.PX[i] < bt.PX[i - 1],
                      fsig=d not in excl and (zo.get(d) or 0) > 1.5 and (zf.get(d) or 0) > 1.5))
    return T


def run(T, cap=None, only_one=False, useV=True, useF=True):
    eq, peak, mdd = 1.0, 1.0, 0.0
    base = 0.0
    hold = {"V": None, "F": None}  # [單位, 剩餘天數, 是否進場日]
    rets, maxL = [], 0.0
    for k in range(1, len(T)):
        t, y = T[k], T[k - 1]
        # 今天報酬：00631L 用昨天收盤後持有的 base（v3 在收盤成交），期貨用持有部位
        r = base / 2 * t["r2"] + (1 - base / 2) * bt.RC
        fut = 0.0
        for key, h in hold.items():
            if h is None:
                continue
            fut += h[0] * (t["roc"] if h[2] else t["rcc"])
            if h[2]:
                r -= h[0] * COST / t["o"]
                h[2] = False
            h[1] -= 1
        r += fut
        # 收盤：期貨到期／v3 出場平倉
        for key in hold:
            h = hold[key]
            if h is not None and (h[1] <= 0 or t["st"] == 0):
                r -= h[0] * COST / t["c"]
                hold[key] = None
        # v3：昨天收盤的決定，今天收盤成交
        nb = 2.0 * y["st"]
        if nb != base:
            r -= bt.COST * abs(nb - base)
            base = nb
        eq *= 1 + r
        rets.append(r)
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
        # 今天收盤的訊號 → 明天開盤進
        for key, flag, add, H, use in (("V", t["vsig"], 1.0, 10, useV), ("F", t["fsig"], 0.5, 5, useF)):
            if not use or not flag or t["st"] != 1 or hold[key] is not None:
                continue
            other = sum(h[0] for kk, h in hold.items() if h is not None and kk != key)
            if only_one and other > 0:
                continue
            u = add
            if cap is not None:
                u = max(0.0, min(add, cap - 2.0 - other))
            if u > 0:
                hold[key] = [u, H, True]
        maxL = max(maxL, base + sum(h[0] for h in hold.values() if h is not None))
    yrs = len(rets) / bt.TD
    return eq ** (1 / yrs) - 1, mdd, np.array(rets), maxL


def boot_pair(a, b, B=2000, L=60, seed=141):
    n = len(a)
    rng = np.random.default_rng(seed)
    dc, dm = [], []
    for _ in range(B):
        new = rng.random(n) < 1.0 / L
        new[0] = True
        starts = rng.integers(0, n, n)
        seg = np.maximum.accumulate(np.where(new, np.arange(n), 0))
        idx = (starts[seg] + np.arange(n) - seg) % n
        out = []
        for x in (a, b):
            e = np.cumprod(1 + x[idx])
            out.append((e[-1] ** (bt.TD / n) - 1, (e / np.maximum.accumulate(e) - 1).min()))
        dc.append(out[0][0] - out[1][0])
        dm.append(out[0][1] - out[1][1])
    return np.array(dc), np.array(dm)


def main():
    T = build()
    out = []
    p = out.append
    p(f"研究 141：加碼疊加的總曝險上限（{T[0]['d']}～{T[-1]['d']}，00631L＋台指期真實價）")
    p(f"V 訊號 {sum(t['vsig'] and t['st'] == 1 for t in T)} 天、F 訊號 {sum(t['fsig'] and t['st'] == 1 for t in T)} 天（v3 在場時）\n")
    cases = [("不加碼（v3）", dict(useV=False, useF=False)), ("只 V", dict(useF=False)), ("只 F", dict(useV=False)),
             ("現行 V+F（無上限）", {}), ("上限 3.0x", dict(cap=3.0)), ("上限 2.5x", dict(cap=2.5)), ("同時只留一個", dict(only_one=True))]
    res = {}
    for nm, kw in cases:
        c, m, r, mx = run(T, **kw)
        res[nm] = r
        sh = r.mean() / r.std() * np.sqrt(bt.TD)
        p(f"{nm:16s} 年化 {c:6.1%}  最大回檔 {m:6.1%}  卡瑪 {c / -m:4.2f}  夏普 {sh:4.2f}  最高曝險 {mx:.1f}x")
    p("\n== 與現行 V+F 比（區塊拔靴 2000 次：年化差、回檔差的 5%～95% 區間；回檔差正＝較淺）==")
    for nm in ("上限 3.0x", "上限 2.5x", "同時只留一個"):
        dc, dm = boot_pair(res[nm], res["現行 V+F（無上限）"])
        p(f"{nm:12s} 年化差 中位 {np.median(dc):+.2%}（{np.percentile(dc, 5):+.2%}～{np.percentile(dc, 95):+.2%}）  "
          f"回檔差 中位 {np.median(dm):+.2%}（{np.percentile(dm, 5):+.2%}～{np.percentile(dm, 95):+.2%}）  回檔較淺機率 {np.mean(dm > 0):.0%}")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究141_加碼總曝險上限.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
