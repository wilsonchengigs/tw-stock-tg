"""研究 140：v3 訊號「當晚夜盤用台指期先執行」vs 現行「隔天收盤才換 00631L」

背景：融資 21:00 公布、日報 21:30 發，看到訊號時夜盤（到 05:00）還開著；研究 103 顯示融資過熱出場延遲 1 天代價很大。
做法：訊號日 D 收盤決定（同 v3），新做法在 D 當晚夜盤用台指期把曝險調到目標（價格近似：夜盤收盤 05:00；
  另測「夜盤開盤 15:00」＝價格訊號 13:30 就知道、融資訊號其實要 21:00，只當上界參考），隔天收盤再把期貨換成 00631L（換手不影響曝險）。
差異只發生在轉換日：D 收盤 → 執行價 這段用舊曝險還是新曝險。
  增益（每次）≈ (L_new − L_old) × (執行價 / D 台指期日盤收盤 − 1) 的相反…精確寫法：
  現行：D→D+1 整天用 L_old；新：D→執行價 用 L_old、執行價→D+1 收盤 用 L_new
  → 差 ＝ (L_new − L_old) × (D+1 收盤 / 執行價 − 1)
期貨成本：多一次期貨來回約 3 點；現行 00631L 換手成本兩者都有
資料：台指期近月真實價（研究 139 的 load_tx），2017-05～；v3 狀態同研究 138（1997 起連續）
顯著性：轉換事件的差值 vs 「隨機選同樣多個日子、同樣方向」的差值（2000 次），分 價格訊號／融資過熱 兩類
用法：python -X utf8 backtest/research_140_訊號當晚夜盤執行.py
"""
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
R138 = R139.R138
V = R138.V
COST = 3.0


def main():
    dates, day, night, near = R139.load_tx()
    di = {d: k for k, d in enumerate(dates)}
    bi = {d: k for k, d in enumerate(R138.DAYS)}
    ST = R138.ST
    # 每個 TX 交易日 D（有隔天 D+1 與夜盤）：r_close＝D 收→D+1 收、r_nc＝夜收→D+1 收、r_no＝夜開→D+1 收（同契約）
    info = {}
    for k in range(len(dates) - 1):
        d, d1 = dates[k], dates[k + 1]
        m = near[d]
        a, b, nb = day[d].get(m), day[d1].get(m), night[d1].get(m)
        if not (a and b and nb) or nb[4] < 1000:
            continue
        info[d] = (b[3] / a[3] - 1, b[3] / nb[3] - 1, b[3] / nb[0] - 1, a[3])
    evs = []
    for d, (rc, rnc, rno, px) in info.items():
        i = bi.get(d)
        if i is None or i == 0:
            continue
        old, new = ST[i - 1], ST[i]
        if old == new:
            continue
        heat = new == 0 and V.hot_at(i)
        evs.append(dict(d=d, dl=2.0 * (new - old), rc=rc, rnc=rnc, rno=rno, px=px, kind="過熱出場" if heat else ("進場" if new else "價格出場")))
    out = []
    p = out.append
    p(f"研究 140：v3 訊號當晚夜盤用台指期先執行（{min(info)}～{max(info)}，轉換 {len(evs)} 次）")
    p("差＝(L_new−L_old)×(D+1 收盤 ÷ 執行價 − 1)，正＝新做法較好；已扣期貨來回 3 點×|ΔL|\n")
    allr = {k: np.array([v[j] for v in info.values()]) for j, k in enumerate(("rc", "rnc", "rno"))}
    rng = np.random.default_rng(140)
    for how, key in (("夜盤收盤執行（看完日報、05:00 前）", "rnc"), ("夜盤開盤執行（上界，融資訊號實際做不到）", "rno")):
        p(f"== {how} ==")
        for kind in ("進場", "價格出場", "過熱出場", "全部"):
            es = [e for e in evs if kind == "全部" or e["kind"] == kind]
            if not es:
                continue
            # 現行 L_old×rc；新 L_old×f + L_new×rX，(1+f)(1+rX)=1+rc → f≈rc−rX
            gain = np.array([e["dl"] * e[key] for e in es])  # 新 − 現行 ≈ (L_new−L_old)×rX
            gain = gain - np.array([abs(e["dl"]) * COST / e["px"] for e in es])
            # 對照：隨機日子、同方向
            dls = np.array([e["dl"] for e in es])
            null = np.array([(dls * rng.choice(allr[key], len(es))).mean() - (np.abs(dls) * COST / 20000).mean() for _ in range(2000)])
            pv = (1 + np.sum(null >= gain.mean())) / 2001
            pts = [g * e["px"] for g, e in zip(gain, es)]
            p(f"{kind:6s} {len(es):3d} 次  每次 {gain.mean():+.3%}（{np.mean(pts):+.0f} 點×1口曝險單位）  合計 {gain.sum():+.2%}  "
              f"勝 {np.mean(gain > 0):.0%}  隨機對照單尾 p {pv:.3f}")
        p("")
    p("明細（夜收執行）：" + "  ".join(f"{e['d'][2:]}{e['kind'][:2]}({e['dl'] * e['rnc']:+.1%})" for e in evs))
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究140_訊號當晚夜盤執行.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
