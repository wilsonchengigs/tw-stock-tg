"""研究 154：恐慌訊號（P）出現後的中期報酬——v3 空手時，P 是不是「底部附近」的訊號（能否用來提早回場）

事件：P 觸發日 D（夜盤或 S&P 跌 ≥2%；1998–2017 只有 S&P）、且 v3 前一天收盤是空手；叢集只取第一次（間隔 >20 天才算新事件）
前瞻：加權指數 D 收盤 → D+5／20／60 收盤
對照：v3 空手、非 P 的日子，同波動度十分位；2000 次抽樣單尾 p
用法：python -X utf8 backtest/research_154_恐慌後中期報酬.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("r148", os.path.join(HERE, "research_148_恐慌連續觸發.py"))
R148 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R148)
R138 = R148.R144.R139.R138


def main():
    rows = R148.build()
    bi = {d: k for k, d in enumerate(R138.DAYS)}
    PX, ST = R138.PX, R138.ST
    keep = [x for x in rows if x["d"] in bi]
    I = np.array([bi[x["d"]] for x in keep])
    P = np.array([x["sig"] for x in keep])
    off = np.array([ST[i - 1] == 0 for i in I])
    N = len(PX)
    cc = np.array([0.0] + [PX[i] / PX[i - 1] - 1 for i in range(1, N)])
    vol = np.array([np.std(cc[max(1, i - 20):i]) for i in I])
    dec = np.digitize(vol, np.nanpercentile(vol, np.arange(10, 100, 10)))
    first = np.zeros(len(keep), bool)
    last = -999
    for k in range(len(keep)):
        if P[k] and off[k]:
            if k - last > 20:
                first[k] = True
            last = k
    rng = np.random.default_rng(154)
    out = ["研究 154：v3 空手時恐慌訊號後的中期報酬（加權指數，D 收盤起算）", ""]
    for per, lo, hi in (("2017-05～", "2017-05-15", "2099"), ("1998～2017-05", "1998", "2017-05-15"), ("全部", "1998", "2099")):
        inp = np.array([lo <= x["d"] < hi for x in keep])
        ev = np.where(first & inp)[0]
        parts = []
        for H in (5, 20, 60):
            fr = np.array([PX[min(i + H, N - 1)] / PX[i] - 1 for i in I])
            valid = np.array([i + H < N for i in I])
            evv = [k for k in ev if valid[k]]
            ctrl = off & ~P & inp & valid
            pools = {k: np.where(ctrl & (dec == dec[k]))[0] for k in evv}
            diff = np.mean([fr[k] - fr[pools[k]].mean() for k in evv])
            null = np.array([np.mean([fr[rng.choice(pools[k])] - fr[pools[k]].mean() for k in evv]) for _ in range(2000)])
            parts.append(f"{H} 日 {np.mean(fr[evv]):+.1%}（勝 {np.mean(fr[evv] > 0):.0%}，比同波動空手日 {diff:+.1%}，p {(1 + np.sum(null >= diff)) / 2001:.3f}）")
        out.append(f"{per}：{len(ev)} 個事件  " + "  ".join(parts))
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究154_恐慌後中期報酬.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
