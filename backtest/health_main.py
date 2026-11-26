"""每月健康檢查（第二則 TG）：主策略燈號（研究 199）＋ 資料稽核（研究 198，只列近 40 天新出現的異常）

使用者 2026-11-26 同意加入 health.yml。
- 燈號：近 36 個月 v3（模型價）年化 − 1x 加權含息年化（≈0050）
  🔴 < -10%／年：統計上異常（策略照歷史方式運作時約 1% 機率；2002 以來從未發生）→ 重新檢討策略
  🟡 -10%～-5%：正常低潮（2012～2018 曾在這裡，之後恢復）
  🟢 ≥ -5%
- 資料稽核：研究 198 的各項檢查，只列最近 40 天的項目；漲跌停鎖死、崩跌斷頭等真實事件也會列出，附說明
用法：python -X utf8 backtest/health_main.py（印出並寫 backtest/結果_每月主策略健檢.txt）
"""
import importlib.util
import os
import sys
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def light():
    V3 = load("v3", "strategy_v3.py")
    bt = V3.bt
    _, _, e = V3.run("2002-01-01", "2026-12-31" if bt.DAYS[-1] < "2027" else bt.DAYS[-1], curve=True)
    i0 = next(i for i, d in enumerate(bt.DAYS) if d >= "2002-01-01")
    days = bt.DAYS[i0:i0 + len(e)]
    end = len(e) - 1
    start_day = (date.fromisoformat(days[end]) - timedelta(days=365 * 3)).isoformat()
    s = next(k for k, d in enumerate(days) if d >= start_day)
    yrs = (end - s) / bt.TD
    v = (e[end] / e[s]) ** (1 / yrs) - 1
    b = 1.0
    for k in range(s + 1, end + 1):
        b *= 1 + bt.R1[i0 + k]
    b = b ** (1 / yrs) - 1
    ex = v - b
    icon = "🔴" if ex < -0.10 else ("🟡" if ex < -0.05 else "🟢")
    note = {"🔴": "統計上異常（約 1% 機率），建議重新檢討主策略",
            "🟡": "正常低潮（2012～2018 曾在這裡，之後恢復），維持策略",
            "🟢": "正常"}[icon]
    return [f"{icon} 主策略燈號：近 36 個月 v3 年化 {v:+.1%}、0050（加權含息）{b:+.1%}、超額 {ex:+.1%}／年 → {note}",
            f"　（紅燈 < -10%、黃燈 < -5%；資料到 {days[end]}；研究 199）"]


def audit(days_back=40):
    R = load("r198", "research_198_資料品質稽核.py")
    R.main()
    since = (date.fromisoformat(R.DAYS[-1]) - timedelta(days=days_back)).isoformat()
    out = []
    for title, items in R.SECTIONS:
        rec = [x for x in items if x[0] >= since]
        if rec:
            out.append(f"・{title}：" + "；".join(" ".join(str(v) for v in x) for x in rec[-5:]))
    hint = "　（台指期近月量很小多半是漲跌停鎖死、融資單日 -8% 以上多半是崩跌斷頭，屬真實事件；ETF 停滯／缺日是 Yahoo 資料問題，只影響回測）"
    return (["🔎 資料稽核（近 40 天）："] + out + [hint]) if out else ["🔎 資料稽核（近 40 天）：✅ 沒有異常"]


def trend_vr(years=8, q=26):
    """台股趨勢性（研究 217）：近 years 年加權週報酬的變異數比 VR(q)；> 1 趨勢延續（均線策略的前提），< 1 均值回歸。
    歷史：8 年窗 2010～2014 結束時 1.7～1.8，2016～2020 結束時 0.66～0.95（＝主策略 2011～2017 長期水下），2026 1.10"""
    import numpy as np
    bt = load("bt_vr", "bt.py")
    days, px = bt.DAYS, bt.PX
    wk = [date.fromisoformat(d).isocalendar()[:2] for d in days]
    idx = [k for k in range(len(days) - 1) if wk[k + 1] != wk[k]] + [len(days) - 1]
    cut = (date.fromisoformat(days[-1]) - timedelta(days=365 * years)).isoformat()
    w = np.array([px[k] for k in idx if days[k] >= cut])
    r = np.diff(np.log(w))
    rq = np.array([r[i:i + q].sum() for i in range(len(r) - q + 1)])
    vr = rq.var() / (q * r.var())
    icon = "🟢" if vr >= 1.0 else "🟡"
    return [f"{icon} 台股趨勢性：近 {years} 年週報酬 VR({q}) {vr:.2f}（> 1 有趨勢、均線策略的前提；< 1 時主策略容易長期落後，2016～2020 曾 0.66～0.95；研究 217，僅供參考）"]


def main():
    L = [f"🩺 主策略月檢（{date.today():%m/%d}）"] + light() + trend_vr() + [""] + audit()
    txt = "\n".join(L)
    print(txt)
    open(os.path.join(HERE, "結果_每月主策略健檢.txt"), "w", encoding="utf-8").write(txt + "\n")


if __name__ == "__main__":
    main()
