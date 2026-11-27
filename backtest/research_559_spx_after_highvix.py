"""研究 559：機制檢查——VIX 高之後 S&P 隔天報酬，依 S&P 自身趨勢（站上／跌破 200 日線，類比台股主策略在場／空手）
S&P 收盤→隔天收盤、收盤→隔天開盤（隔夜）、開盤→收盤；1990～；VIX 門檻 20／25／28／30／35
用法：python -X utf8 backtest/research_559_spx_after_highvix.py
"""
import os, sys, json, datetime as dt
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def ohlc(name):
    d = json.load(open(os.path.join(HERE, name), encoding="utf-8"))
    off = d["meta"].get("gmtoffset", 0); q = d["indicators"]["quote"][0]
    out = {}
    for t, o, c in zip(d["timestamp"], q["open"], q["close"]):
        if o and c:
            out[dt.datetime.utcfromtimestamp(t + off).strftime("%Y-%m-%d")] = (o, c)
    return out


def main():
    sp = ohlc("GSPC.json"); vx = ohlc("VIX.json")
    ds = [d for d in sorted(sp) if d in vx and d >= "1990"]
    c = np.array([sp[d][1] for d in ds]); o = np.array([sp[d][0] for d in ds]); v = np.array([vx[d][1] for d in ds])
    ma = np.array([c[max(0, i - 199):i + 1].mean() for i in range(len(c))])
    out = [__doc__]
    t = lambda y: y.mean() / (y.std(ddof=1) / np.sqrt(len(y)))
    cc = (c[1:] / c[:-1] - 1) * 100; on = (o[1:] / c[:-1] - 1) * 100; dy = (c[1:] / o[1:] - 1) * 100
    up = (c[:-1] > ma[:-1]); vv = v[:-1]; ok = np.arange(len(cc)) >= 200
    # 1990～2000 的開盤價常等於前收（Yahoo 舊資料），隔夜／日盤只看 2001～
    new = np.array([d >= "2001" for d in ds[:-1]])
    for th in (0, 20, 25, 28, 30, 35):
        for lab, m in (("200 日線上", up), ("200 日線下", ~up)):
            q = ok & m & (vv >= th); qn = q & new
            out.append(f"  VIX≥{th:2d} {lab}：{q.sum():5d} 天 收→收 {cc[q].mean():+.3f}%（t {t(cc[q]):+.1f}）｜2001～ 隔夜 {on[qn].mean():+.3f}%（t {t(on[qn]):+.1f}）日盤 {dy[qn].mean():+.3f}%（t {t(dy[qn]):+.1f}）")
    txt = "\n".join(out)
    open(os.path.join(HERE, "結果_研究559_SPX高VIX後.txt"), "w", encoding="utf-8").write(txt)
    print(txt)


if __name__ == "__main__":
    main()
