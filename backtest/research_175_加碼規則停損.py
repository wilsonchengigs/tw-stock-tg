"""研究 175：每條期貨進場規則的停損（使用者要求每個進場都要有退場／停損）

規則（訊號與研究 172／172b 相同，台指期真實價）：
  V 爆量收黑加碼：v3 在場、1.5 倍量收黑 → 隔天開盤買，抱 10 天收盤出（v3 出場提前出）；1998～
  V5 爆量收黑獨立短線：同訊號、抱 5 天（v3 在場當作「多頭」近似）；1998～
  F 外資期貨加碼：v3 在場、外資未平倉 z 與交易淨額 z 都 >1.5 → 隔天開盤買，抱 5 天；2018-06～
  P 恐慌隔天做多：夜盤或 S&P 跌 ≥2% → 當天開盤買，隔天開盤出（研究 143 已測：停損有害，這裡用同方法重驗）
停損：無／2／3／4／5／7%（相對進場價）；盤中觸價：日盤低點與當晚夜盤低點（2017-05 後）碰到停損價就出，
      開盤就跳空在停損價之下則用開盤價出（滑價）；不觸價則照原規則出場
比較：每筆平均、勝率、最差一筆、累積（1 倍名目複利）；成本每筆來回 6 點
用法：python -X utf8 backtest/research_175_加碼規則停損.py
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


R141 = load("r141", "research_141_加碼總曝險上限.py")
R148 = load("r148", "research_148_恐慌連續觸發.py")
R139, R138, bt = R141.R139, R141.R138, R141.bt
COST = 3.0
STOPS = (None, 0.02, 0.03, 0.04, 0.05, 0.07)


def trade(day, night, ds, j, m, hold_last, stop):
    """j＝進場日索引（開盤進），hold_last＝(原規則出場日索引, 'close' 或 'open')；
    契約到期（之後沒有該月份資料）就在最後一天收盤換到當天近月（多扣一次換月 2 點），停損價依累積報酬換算"""
    last, how = hold_last
    e = day[ds[j]][m][0]
    acc = 1.0          # 已實現的換月前報酬（倍數）
    cost = 2 * COST / e
    floor = (1 - stop) if stop else None

    def done(px):
        return acc * px / e - 1 - cost

    for t in range(j, last + 1):
        b = day[ds[t]].get(m)
        if not b:      # 換月：前一天已到期，改用今天近月、以昨天收盤價銜接
            nm = next((x for x in sorted(day[ds[t]]) if x > m), None)
            pb = day[ds[t - 1]].get(m)
            if nm is None or pb is None or not day[ds[t - 1]].get(nm):
                break
            acc *= pb[3] / e
            m, e = nm, day[ds[t - 1]][nm][3]
            cost += 2.0 / e
            b = day[ds[t]][m]
        sp = e * floor / acc if floor else None   # 讓「累積」跌到 −stop 的價
        if how == "open" and t == last:
            return done(b[0])
        if sp:
            if t > j and b[0] <= sp:
                return done(b[0])
            if b[2] <= sp:
                return done(sp)
        if t == last:
            return done(b[3])
        if sp and t + 1 < len(ds):
            nb = night[ds[t + 1]].get(m)
            if nb and nb[4] >= 1000:
                if nb[0] <= sp:
                    return done(nb[0])
                if nb[2] <= sp:
                    return done(sp)
    b = day[ds[min(last, len(ds) - 1)]].get(m)
    return done(b[3]) if b else acc - 1 - cost


def main():
    dates, day, night, near = R139.load_tx()
    bi = {d: k for k, d in enumerate(R138.DAYS)}
    ds = [d for d in dates if d in bi]
    n = len(ds)
    st = np.array([R138.ST[bi[d]] for d in ds])
    vsig = np.zeros(n, bool)
    for k, d in enumerate(ds):
        i = bi[d]
        amts = [R139.AMT.get(R138.DAYS[j]) for j in range(i - 20, i)]
        amts = [a for a in amts if a]
        a0 = R139.AMT.get(d)
        vsig[k] = bool(a0 and len(amts) >= 16 and a0 / (sum(amts) / len(amts)) >= 1.5 and bt.PX[i] < bt.PX[i - 1])
    T = R141.build()
    fset = {t["d"] for t in T if t["fsig"]}
    fsig = np.array([d in fset for d in ds])
    psig_d = {x["d"] for x in R148.build() if x["sig"]}
    psig = np.array([d in psig_d for d in ds])
    k_of = {d: k for k, d in enumerate(ds)}

    def events(sig, H, need_st, entry_same_day=False, exit_open=False):
        ev, k = [], 0
        while k < n - 2:
            if sig[k] and (not need_st or st[k] == 1):
                j = k if entry_same_day else k + 1
                last = j
                if exit_open:
                    last = min(j + 1, n - 1)
                else:
                    for h in range(H):
                        last = min(j + h, n - 1)
                        if need_st and st[last] == 0:
                            break
                ev.append((j, near[ds[k if not entry_same_day else max(k - 1, 0)]], (last, "open" if exit_open else "close")))
                k = last + (0 if exit_open else 1)
            else:
                k += 1
        return ev

    rules = [("V 爆量收黑加碼（1x、抱 10 天）", events(vsig, 10, True)),
             ("V5 爆量收黑獨立短線（抱 5 天）", events(vsig, 5, True)),
             ("F 外資期貨加碼（0.5x、抱 5 天，2018～）", events(fsig, 5, True)),
             ("P 恐慌隔天做多（1x、隔天開盤出）", events(psig, 1, False, entry_same_day=True, exit_open=True))]
    out = ["研究 175：期貨進場規則的停損（日盤＋夜盤低點觸價；跳空用開盤價；每筆扣 6 點）", ""]
    for nm, ev in rules:
        out.append(f"== {nm}：{len(ev)} 筆（{ds[ev[0][0]]}～{ds[ev[-1][0]]}）==")
        out.append(f"{'停損':>6s} {'每筆':>7s} {'勝率':>5s} {'最差':>7s} {'觸發停損':>8s} {'累積(1x)':>9s}")
        base = None
        for s in STOPS:
            rs = np.array([trade(day, night, ds, j, m, hl, s) for j, m, hl in ev])
            hit = int(np.sum(rs <= -s - 0.0002)) if s else 0
            cum = np.prod(1 + rs) - 1
            if base is None:
                base = rs.mean()
            out.append(f"{'無' if s is None else f'{s:.0%}':>6s} {rs.mean():+7.2%} {np.mean(rs > 0):5.0%} {rs.min():+7.1%} {hit:8d} {cum:+9.0%}")
        out.append("")
    txt = "\n".join(out)
    print(txt)
    open(os.path.join(HERE, "結果_研究175_加碼規則停損.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
