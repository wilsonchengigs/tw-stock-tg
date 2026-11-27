"""研究 553：在場＋VIX≥28 隔夜 1x 與 P／V／D 同時持有的名目合計（主策略在場時期貨帳戶只有 15% 現金，研究 243 上限約 1.5x）
P：前晚 S&P ≤-2% → 當天 08:45～隔天 08:45，倍數依 VIX（C2：<25 在場 1x、25～35 1x、≥35 1.5x）
V：v3 在場＋爆量收黑 → 隔天起抱 10 天 1x；D：背離 0.5x 抱 5 天（近似）
統計隔夜訊號的每一夜，當晚已有的期貨名目（不含隔夜本身）分布；+1x 後 >1.5x 的夜數
用法：python -X utf8 backtest/research_553_overnight_margin_overlap.py
"""
import io, contextlib, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
with contextlib.redirect_stdout(io.StringIO()):
    import research_411_實際配置含V as A
from research_514_pattern_regime import yahoo
import research_138_金字塔加碼與分段停損 as S138


def main():
    ds = list(A.ds); n = len(ds); pos = {d: i for i, d in enumerate(ds)}
    vix = yahoo("VIX.json"); vk = np.array(sorted(vix)); spx = yahoo("GSPC.json"); sk = np.array(sorted(spx))
    dd = [str(x)[:10] for x in S138.DAYS]; st = dict(zip(dd, S138.ST)); keys = np.array(sorted(st))
    def vprev(d): return vix[vk[np.searchsorted(vk, d) - 1]]
    def state(d): return st[keys[np.searchsorted(keys, d) - 1]]
    exp = np.zeros(n)  # 第 k 天收盤後到隔天開盤之間，已持有的期貨名目
    for k, d in enumerate(ds):
        j = np.searchsorted(sk, d) - 1
        if j >= 1 and spx[sk[j]] / spx[sk[j - 1]] - 1 <= -0.02:
            v = vprev(d); s0 = state(d)
            size = (1.0 if s0 == 1 else 0.0) if v < 25 else (1.0 if v < 35 else 1.5)
            exp[k] += size  # P 從 d 08:45 抱到 d+1 08:45，d 收盤後仍持有
    for k, (sg, s0) in enumerate(zip(A.vsig, A.st)):
        if sg and s0 == 1:
            exp[k + 1:min(k + 11, n)] += 1.0
    out = [__doc__]
    nights = [k for k, d in enumerate(ds) if d >= "2002" and state(d) == 1 and vprev(d) >= 28]
    e = exp[nights]
    out.append(f"在場＋VIX≥28 的夜 {len(nights)} 個；當晚已有 P／V 名目：0x {np.mean(e==0)*100:.0f}%、0.5～1x {np.mean((e>0)&(e<=1))*100:.0f}%、>1x {np.mean(e>1)*100:.0f}%；加隔夜 1x 後 >1.5x 的夜 {np.sum(e+1>1.5)}（{np.mean(e+1>1.5)*100:.0f}%）、>2x {np.sum(e+1>2)}")
    out.append("建議：已有 P／V 持倉的夜，隔夜加碼只補到合計 1.5x（例：已有 1x 就只加 0.5x）")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究553_隔夜名目重疊.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
