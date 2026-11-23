"""Yahoo 被雲端環境擋住時的備援：從 GitHub 上公開倉庫的 CSV（多為 Yahoo 匯出）組出 data.py／research 程式要的 json 快取

用法：python backtest/data_mirror.py  （會覆寫 backtest/*.json；json 被 .gitignore 忽略不進版控）

來源（第三方公開倉庫，非官方；已與另一份來源交叉比對加權指數，重疊 7199 天差異皆 < 0.2%）：
- 加權指數：yeomin1024/yeomin1024-ytb（1997-07-02～2026-11-18），之後用 culolom/culolom-backtest 補
- 0050、00631L、SPY、TLT、IEF：culolom/culolom-backtest/data（Close 為調整後價格）
- VUSTX：tradingquant-it/BackTrader（1986～2019-12-31），之後接 TLT 報酬
- VFITX：bennetwi92/macro-beans（1991～2026-08），之後接 IEF 報酬
- 美元兌台幣：FRED DEXTAUS（ethanl814/CIB 的備份，1983～2026-09-25，之後視為不變）
- 盤中未收盤、成交量 0 的最後一筆（當天）不採用

美國資產的日期一律往後移一天（美股收盤時台灣已是隔天早上），避免用到台股收盤時還不知道的價格。
"""
import csv
import io
import json
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
TW = timezone(timedelta(hours=8))
RAW = "https://raw.githubusercontent.com/"
CU = RAW + "culolom/culolom-backtest/HEAD/data/"
SRC = {
    "twii_a": RAW + "yeomin1024/yeomin1024-ytb/HEAD/stock/topics/titles_2026-11-18/data/_TWII.csv",
    "twii_b": CU + "%5ETWII.csv",
    "0050": CU + "0050.TW.csv",
    "00631L": CU + "00631L.TW.csv",
    "SPY": CU + "SPY.csv",
    "TLT": CU + "TLT.csv",
    "IEF": CU + "IEF.csv",
    "VUSTX": RAW + "tradingquant-it/BackTrader/HEAD/Backtrader%20Backtesting%20di%20un%20portafoglio%20di%20ETF%20a%20leva/VUSTX.csv",
    "VFITX": RAW + "bennetwi92/macro-beans/HEAD/data/rebalancing/cache/yahoo_vfitx.csv",
    "USDTWD": RAW + "ethanl814/CIB/HEAD/forex-drift-idea/data/raw/fred/DEXTAUS.csv",
}


def get(key, col=1, drop_zero_vol_last=True):
    txt = urllib.request.urlopen(SRC[key], timeout=60).read().decode("utf-8")
    rows = [r for r in csv.reader(io.StringIO(txt)) if r and r[0][:2] in ("19", "20")]
    if drop_zero_vol_last and len(rows[-1]) > 2 and float(rows[-1][2] or 0) == 0 and rows[-1][0] == date.today().isoformat():
        rows = rows[:-1]
    return {r[0]: float(r[col]) for r in rows if r[col] not in ("", "null", ".") and float(r[col]) > 0}


def splice(base, tail):
    """base 最後一天之後用 tail 的報酬接上"""
    out = dict(base)
    last = max(base)
    lv = base[last]
    keys = sorted(k for k in tail if k >= last)
    for a, b in zip(keys, keys[1:]):
        lv *= tail[b] / tail[a]
        out[b] = lv
    return out


def dump(name, series, shift_days=0, hour=13):
    ks = sorted(series)
    ts = [int((datetime.fromisoformat(k) + timedelta(days=shift_days, hours=hour)).replace(tzinfo=TW).timestamp()) for k in ks]
    v = [series[k] for k in ks]
    d = {"timestamp": ts, "indicators": {"quote": [{"close": v}], "adjclose": [{"adjclose": v}]}}
    json.dump(d, open(os.path.join(HERE, name + ".json"), "w"))
    print(f"{name}: {ks[0]}～{ks[-1]} {len(ks)} 筆")


if __name__ == "__main__":
    a, b = get("twii_a"), get("twii_b")
    tw = dict(a)
    tw.update({k: v for k, v in b.items() if k > max(a)})
    dump("TWII", tw)
    dump("0050.TW", get("0050"))
    dump("00631L.TW", get("00631L"))
    spy, tlt, ief = get("SPY"), get("TLT"), get("IEF")
    dump("ext_SPY", spy, shift_days=1)
    dump("ext_VUSTX", splice(get("VUSTX"), tlt), shift_days=1)
    dump("ext_VFITX", splice(get("VFITX"), ief), shift_days=1)
    dump("ext_TLT", tlt, shift_days=1)
    dump("ext_IEF", ief, shift_days=1)
    dump("ext_USDTWD", get("USDTWD"), shift_days=1)
