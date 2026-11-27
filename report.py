"""
每個交易日 21:30 傳台股日報到 Telegram（資料來源：臺灣證券交易所公開資料）

- 下午（REPORT_PART=close）：加權指數漲跌、日線進出場線（MA60×1.01／MA80×0.975）、成交量（成交金額）、三大法人買賣超（證交所約 15:00 公布）
- 晚上（REPORT_PART=margin）：大盤（上市）融資維持率、融資餘額增減（約 21:00 公布）、外資台指期淨未平倉（期交所）
- REPORT_PART=all（預設，排程用這個）：兩段一起
- REPORT_PART=alert（14:40 排程）：爆量收黑（研究 63／64b）觸發才送，附操作時間；21:30 日報有訊號時最上面列「今日有訊號觸發」與期限
- REPORT_PART=morning（07:20 排程，備援 07:45、08:10）：夜盤跌 ≥2% 或 S&P500 前一晚跌 ≥2% 才送（候選 6「恐慌隔天做多」，研究 139、142～145），附勝率與期望值
- 策略段落後附「觀察」：台指選擇權 Put/Call 未平倉比與研究 32 的提早進場條件（期交所，僅供觀察、未納入策略）
- 台美背離加碼（研究 204～205c）：台股 20 日落後 S&P500 ≥10% → 隔天開盤加 0.5 倍台指期、抱 5 個交易日
- 加快速度：過去的資料存在 data/（taiex_daily、pcratio、margin_ratio、taiex_hourly），每次只抓當天／當月，
  GitHub Actions 跑完把 data/*.csv commit 回來

融資維持率 = Σ(個股融資餘額張數 × 1000 × 收盤價) ÷ 融資餘額總金額（證交所不直接公布，一般網站也是這樣估算）

環境變數：TG_BOT_TOKEN、TG_CHAT_ID；REPORT_PART；REPORT_DATE（選填，YYYYMMDD，測試用）
只用 Python 標準函式庫。
"""
import math
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from tgio import DATA_DIR, UA, get_json, load_csv, num, save_csv, send, tables_of, urlopen_retry

TW = timezone(timedelta(hours=8))
# 資料還沒公布時每 5 分鐘再試一次，最多等 30 分鐘
RETRY_TIMES = 6
RETRY_WAIT_SEC = 300




def months_to_fetch(date: str, have: dict, max_months: int) -> list:
    """要重抓的月份（YYYYMM）：當月一定抓；之前的月份只有在快取缺資料時才抓（最多往回 max_months 個月）"""
    first = datetime.strptime(date[:6] + "01", "%Y%m%d")
    out = [first.strftime("%Y%m")]
    last_have = max(have) if have else "00000000"
    cur = first
    for _ in range(max_months - 1):
        cur = (cur - timedelta(days=1)).replace(day=1)
        month_end = (cur.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        if last_have >= month_end.strftime("%Y%m%d"):
            break  # 快取已經涵蓋這個月（之前的月份更早，也都有）
        out.append(cur.strftime("%Y%m"))
    return out


def taiex(date: str):
    """加權指數 {close, change, pct}；非交易日或還沒收盤回 None"""
    d = get_json(f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date}&type=IND&response=json")
    if d.get("stat") != "OK":
        return None
    for t in tables_of(d):
        for r in t.get("data", []):
            if str(r[0]).strip() == "發行量加權股價指數":
                # 欄位：指數, 收盤指數, 漲跌(+/-，可能是 HTML), 漲跌點數, 漲跌百分比(%)
                sign = -1 if "-" in re.sub(r"<[^>]+>", "", str(r[2])) else 1
                return {"close": num(r[1]), "change": sign * num(r[3]), "pct": sign * abs(num(r[4]))}
    return None


def turnover(date: str):
    """大盤成交金額（元）{today, prev}；非交易日回 None。資料是整個月一張表，日期是民國年（115/11/20）"""
    def month_rows(yyyymm: str) -> list:
        d = get_json(f"https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?date={yyyymm}01&response=json")
        rows = []
        for t in tables_of(d):
            f = t.get("fields", [])
            if "日期" in f and "成交金額" in f:
                idate, iamt = f.index("日期"), f.index("成交金額")
                for r in t.get("data", []):
                    y, m, dd = str(r[idate]).strip().split("/")
                    rows.append((f"{int(y) + 1911}{int(m):02d}{int(dd):02d}", num(r[iamt])))
        return rows

    rows = month_rows(date[:6])
    keys = [k for k, _ in rows]
    if date not in keys:
        return None
    i = keys.index(date)
    if i > 0:
        prev = rows[i - 1][1]
    else:
        first = datetime.strptime(date[:6] + "01", "%Y%m%d") - timedelta(days=1)
        last_month = month_rows(first.strftime("%Y%m"))
        prev = last_month[-1][1] if last_month else 0.0
    return {"today": rows[i][1], "prev": prev}


HOURLY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "taiex_hourly.csv")
# 小時 K：每天 5 根，收盤時間 10:00、11:00、12:00、13:00、13:30（看盤軟體的 60 分 K 也是這樣切）
HOUR_ENDS = ("10:00:00", "11:00:00", "12:00:00", "13:00:00", "13:30:00")
HOURLY_MAS = (20, 60, 240)


def hourly_bars(date: str):
    """當天加權指數小時 K 的收盤 [(收盤時間, 指數)]；非交易日回 None。來源：證交所每 5 秒指數"""
    d = get_json(f"https://www.twse.com.tw/rwd/zh/TAIEX/MI_5MINS_INDEX?date={date}&response=json")
    if d.get("stat") != "OK":
        return None
    ticks = []
    for t in tables_of(d):
        f = t.get("fields", [])
        if "時間" in f and "發行量加權股價指數" in f:
            it, iv = f.index("時間"), f.index("發行量加權股價指數")
            ticks = [(str(r[it]).strip(), num(r[iv])) for r in t.get("data", [])]
    # 09:00:00 那筆是前一天收盤，不算進今天
    ticks = [(tm, v) for tm, v in ticks if tm > "09:00:00" and v > 0]
    if not ticks or ticks[-1][0] < HOUR_ENDS[-1]:
        return None  # 還沒收盤或資料不完整
    bars = []
    for end in HOUR_ENDS:
        inside = [v for tm, v in ticks if tm <= end]
        if inside:
            bars.append((end[:5], inside[-1]))
    return bars


def load_hourly() -> list:
    if not os.path.exists(HOURLY_FILE):
        return []
    with open(HOURLY_FILE, encoding="utf-8") as fp:
        rows = [ln.strip().split(",") for ln in fp if ln.strip() and not ln.startswith("date")]
    return [(r[0], r[1], float(r[2])) for r in rows]


def save_hourly(rows: list):
    os.makedirs(os.path.dirname(HOURLY_FILE), exist_ok=True)
    with open(HOURLY_FILE, "w", encoding="utf-8") as fp:
        fp.write("date,time,close\n")
        for d, tm, v in rows:
            fp.write(f"{d},{tm},{v:.2f}\n")


def update_hourly(date: str) -> list:
    """把資料檔補到 date 為止（第一次會往回抓到夠算 MA240），回傳到 date 為止的所有小時 K"""
    rows = load_hourly()
    have = {r[0] for r in rows}
    need = max(HOURLY_MAS) // len(HOUR_ENDS) + 4  # 交易日數，多抓幾天當緩衝
    day = datetime.strptime(date, "%Y%m%d")
    if rows:
        stop = datetime.strptime(max(have), "%Y%m%d")
    else:
        stop = day - timedelta(days=int(need * 1.6) + 10)
    cur, added = day, False
    while cur > stop:
        key = cur.strftime("%Y%m%d")
        if cur.weekday() < 5 and key not in have:
            bars = hourly_bars(key)
            if bars:
                rows += [(key, tm, v) for tm, v in bars]
                added = True
        cur -= timedelta(days=1)
    if added:
        rows.sort()
        save_hourly(rows)
    return [r for r in rows if r[0] <= date]


def daily_ma_line(date: str):
    """日線：主策略用的進場線（MA60×1.01）與出場線（MA80×0.975），以及收盤離兩條線多遠"""
    closes = taiex_daily(date)
    if len(closes) < STRATEGY_EXIT_MA or closes[-1][0] != date:
        return None
    p = [c for _, c in closes]
    px = p[-1]
    up = sum(p[-STRATEGY_ENTRY_MA:]) / STRATEGY_ENTRY_MA * (1 + STRATEGY_ENTRY_BAND)
    dn = sum(p[-STRATEGY_EXIT_MA:]) / STRATEGY_EXIT_MA * (1 - STRATEGY_EXIT_BAND)
    return (f"日線（主策略用）：進場線 MA{STRATEGY_ENTRY_MA}×{1 + STRATEGY_ENTRY_BAND:g} {up:,.0f}（收盤{'已站上' if px > up else f'還差 {up / px - 1:+.1%}'}）"
            f"・出場線 MA{STRATEGY_EXIT_MA}×{1 - STRATEGY_EXIT_BAND:g} {dn:,.0f}（收盤{'在上方' if px >= dn else '在下方'} {px / dn - 1:+.1%}）｜週五收盤判斷")


def hourly_ma_line(date: str):
    rows = update_hourly(date)
    closes = [v for _, _, v in rows]
    if not closes or rows[-1][0] != date:
        return None
    last = closes[-1]
    parts = []
    for n in HOURLY_MAS:
        if len(closes) < n:
            parts.append(f"MA{n} 資料不足")
            continue
        ma = sum(closes[-n:]) / n
        parts.append(f"MA{n} {ma:,.0f}（{'上' if last >= ma else '下'} {abs(last - ma) / ma * 100:.1f}%）")
    return "小時K：" + "・".join(parts)


# ── 交易策略：每週最後一個交易日收盤判斷 ─────────────────────────────────────
# 出場：收盤跌破 80 日均線 ×0.975；進場：收盤站上 60 日均線 ×1.01（進場用較短的均線，大跌後回得比較快）
# 進場全押 00631L（2 倍）。回測（1998～2026，週頻、含交易成本）：年化約 19.2%、最大回檔約 -44%
# （大盤買進持有 8.6%、-65%；改持 50% 00631L＋50% 0050 是 15.3%、-34%）；
# 2015-09 之後真實價格：全押 00631L 年化 33.0%、最大回檔 -37.2%（0050 買進持有 20.2%、-33.8%）。
# 出場緩衝 2026-11-24 由 2% 改 2.5%（研究 11、24、29：歷史三段、真實價格、約 70% 拔靴模擬路徑都較好）。
# 風險提醒（研究 19）：拔靴模擬 20 年內回檔超過 50% 的機率約 75%，歷史 -44% 有運氣成分。
# 另外測過停損（8～20%）、每天檢查出場、帳戶回落降槓桿，最大回檔都沒有比較小（停損會被盤整反覆洗出場），所以不加
# 出場 80～90 日、進場 60～70 日的鄰近參數都在 14～15%／-31～-34%，不是單一參數湊出來的。
# 進場改用 10～20 日這類短均線反而更差（大跌途中的反彈會一直騙進場，最大回檔 > 58%）
STRATEGY_EXIT_MA, STRATEGY_EXIT_BAND = 80, 0.025
STRATEGY_ENTRY_MA, STRATEGY_ENTRY_BAND = 60, 0.01
# 2026-11-26 使用者選研究 216 的 (a)：00631L 只買 85%、留 15% 現金在期貨帳戶當台指期加碼的保證金（00631L 不能當保證金）
STRATEGY_ON = "85% 00631L（台灣50正2，約 1.7 倍）＋15% 現金放期貨帳戶當加碼保證金"
STRATEGY_OFF = "100% 現金（或定存）"
# 融資過熱濾網（2026-11-24 加入，研究 38／38b／40）：上市融資金額 ÷ 加權指數 高於近 250 個交易日平均 17.5% 以上
# → 週五判斷時出場且不進場。回測 2002～2026：全期 23.2%／-36.8%（無濾網 20.2%／-43.6%），前段、後段、真實價格都較好；
# 鄰近參數 14／18 組顯著、安慰劑 p≈0.01。歷史資料存在 data/margin_ratio.csv（每天抓到融資餘額就追加一列）
HEAT_N, HEAT_TH = 250, 0.175
# z 分數（2026-11-24 加入，研究 85／85b）：比值偏離 ÷ 近 250 日標準差 > HEAT_Z 也算過熱（與上面的百分比門檻任一成立）。
# 回測全期 23.2%→25.0%、前後段與真實價格都提高，真實價格回檔 -37.2%→-32.7%；250 日視窗下 z 1.5～3 都通過
HEAT_Z = 2.0
# 過熱出場後的回補（2026-11-24 加入，研究 81）：因過熱而出場的那段空手期，偏離降到 HEAT_REENTRY 以下、
# 且指數仍在出場線（MA80×0.975）之上就回補，不必等 MA60×1.01。回測全期 23.2%→23.7%、後段與真實價格都提高、回檔不變
HEAT_REENTRY = 0.125
# 融資過熱每天檢查（2026-11-24 加入，研究 90）：持有中任一天過熱就出場；價格進出場與回補仍每週五判斷。
# 回測全期 25.2%→27.6%、回檔 -37.1%→-33.1%，鄰近 9 組全期都提高；2015 後真實價格好壞參半
HEAT_DAILY = True
_TODAY_MARGIN = {}  # margin_lines 抓到的當天融資餘額，給策略段落存檔用


def taiex_daily(date: str, months: int = 14) -> list:
    """加權指數日收盤 [(YYYYMMDD, 收盤)]，往前 months 個月。歷史存在 data/taiex_daily.csv，只重抓當月（與快取缺的月份）"""
    cache = {d: float(v[0]) for d, v in load_csv("taiex_daily.csv").items()}
    for ym in months_to_fetch(date, cache, months):
        d = get_json(f"https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?date={ym}01&response=json")
        for t in tables_of(d):
            f = t.get("fields", [])
            if "日期" in f and "發行量加權股價指數" in f:
                idate, iv = f.index("日期"), f.index("發行量加權股價指數")
                for r in t.get("data", []):
                    y, m, dd = str(r[idate]).strip().split("/")
                    cache[f"{int(y) + 1911}{int(m):02d}{int(dd):02d}"] = num(r[iv])
    save_csv("taiex_daily.csv", "date,close", {k: [f"{v:.2f}"] for k, v in cache.items()})
    start = (datetime.strptime(date[:6] + "01", "%Y%m%d") - timedelta(days=31 * (months - 1))).strftime("%Y%m01")
    return sorted((k, v) for k, v in cache.items() if start <= k <= date)


def load_margin_ratio() -> list:
    """[(YYYYMMDD, 融資金額, 加權指數)]，依日期排序（data/margin_ratio.csv 另有第 4 欄融資維持率，可能空白）"""
    return sorted((d, float(v[0]), float(v[1])) for d, v in load_csv("margin_ratio.csv").items())


def save_margin_ratio(date: str, amount: float, taiex_close: float, maint=None):
    rows = load_csv("margin_ratio.csv")
    rows[date] = [str(int(amount)), f"{taiex_close:.2f}", f"{maint:.2f}" if maint is not None else ""]
    rows = {d: (v + [""])[:3] for d, v in rows.items()}
    save_csv("margin_ratio.csv", "date,amount,taiex,maint", rows)


def cached_maint(date: str):
    """data/margin_ratio.csv 裡某天的融資維持率；沒存過回 None"""
    v = load_csv("margin_ratio.csv").get(date)
    return float(v[2]) if v and len(v) > 2 and v[2] else None


def heat_series(rows: list) -> dict:
    """{YYYYMMDD: (偏離, z)}：融資/指數 比值 相對近 HEAT_N 日平均的偏離，與 (比值−平均)÷標準差"""
    ratio = [a / t for _, a, t in rows]
    out = {}
    for i in range(HEAT_N - 1, len(rows)):
        w = ratio[i + 1 - HEAT_N:i + 1]
        avg = sum(w) / HEAT_N
        sd = (sum((v - avg) ** 2 for v in w) / HEAT_N) ** 0.5
        out[rows[i][0]] = (ratio[i] / avg - 1, (ratio[i] - avg) / sd if sd else 0.0)
    return out


def heat_on(heat: dict, d: str):
    """d 當天（沒有就用之前最近一天）的 (偏離, z)；完全沒資料回 None"""
    keys = [k for k in heat if k <= d]
    return heat[max(keys)] if keys else None


def is_hot(v) -> bool:
    return v is not None and (v[0] > HEAT_TH or v[1] > HEAT_Z)


# ── 證交所休市日（研究 270：2026-12-25 週五休市，週訊號要在週四判斷；年底加碼的交易日也要扣休市）──────
_HOLIDAYS = {}


def twse_holidays(year: int) -> set:
    """證交所公告的休市日 {YYYYMMDD}（含「僅辦理結算交割」；不含「開始交易日／最後交易日」）；抓不到就只扣 1/1"""
    if year not in _HOLIDAYS:
        try:
            j = get_json(f"https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule?response=json&date={year}0101")
            _HOLIDAYS[year] = {r[0].replace("-", "") for r in j.get("data", [])
                               if r[0][:4] == str(year) and "開始交易" not in r[1] and "最後交易" not in r[1]}
        except Exception as e:  # noqa: BLE001
            print(f"休市日抓取失敗：{e}", file=sys.stderr)
            _HOLIDAYS[year] = set()
        _HOLIDAYS[year].add(f"{year}0101")
    return _HOLIDAYS[year]


def is_trading_day(d) -> bool:
    return d.weekday() < 5 and d.strftime("%Y%m%d") not in twse_holidays(d.year)


def is_week_end(date: str) -> bool:
    """date（YYYYMMDD）是否為本週最後一個交易日"""
    d = datetime.strptime(date, "%Y%m%d").date()
    nxt = d + timedelta(days=1)
    while not is_trading_day(nxt):
        nxt += timedelta(days=1)
    return nxt.isocalendar()[:2] != d.isocalendar()[:2]


def holiday_note(date: str) -> str:
    """下一個交易日不是明天（且不是一般週末）時的提示；研究 272：訊息裡的「明天／明早」都是指下一個交易日"""
    d = datetime.strptime(date, "%Y%m%d").date()
    nxt = d + timedelta(days=1)
    while not is_trading_day(nxt):
        nxt += timedelta(days=1)
    gap = (nxt - d).days
    if gap == 1 or (d.weekday() == 4 and gap == 3):
        return ""
    wk = "一二三四五六日"[nxt.weekday()]
    return f"📆 明天起休市，下一個交易日是 {nxt.month}/{nxt.day}（{wk}）：下面說的「明天／明早」都是指 {nxt.month}/{nxt.day}"


def strategy_state(closes: list, heat: dict = None):
    """依每週最後一個交易日的收盤跑一遍，回傳 (目前狀態, 上次切換日, 今天的出場均線, 今天的進場均線)
    heat：融資過熱偏離（heat_series）；過熱時出場且不進場"""
    state, switched, heat_out = False, None, False
    ma_x = ma_n = None
    need = max(STRATEGY_EXIT_MA, STRATEGY_ENTRY_MA)
    for i, (d, px) in enumerate(closes):
        if i + 1 < need:
            continue
        ma_x = sum(v for _, v in closes[i + 1 - STRATEGY_EXIT_MA:i + 1]) / STRATEGY_EXIT_MA
        ma_n = sum(v for _, v in closes[i + 1 - STRATEGY_ENTRY_MA:i + 1]) / STRATEGY_ENTRY_MA
        last_of_week = i == len(closes) - 1 or (
            datetime.strptime(d, "%Y%m%d").isocalendar()[:2]
            != datetime.strptime(closes[i + 1][0], "%Y%m%d").isocalendar()[:2]
        )
        dev = heat_on(heat, d) if heat else None
        hot = is_hot(dev)
        if state and hot and HEAT_DAILY:
            # 融資過熱每天檢查（研究 90）：任一天過熱就出場（下一個交易日收盤賣），不必等週五
            state, switched, heat_out = False, d, True
            continue
        if not last_of_week:
            continue
        if i == len(closes) - 1 and not is_week_end(d):
            continue  # 今天不是本週最後交易日（通常週五；週五休市則週四，研究 270）：價格規則不判斷
        above_exit = px >= ma_x * (1 - STRATEGY_EXIT_BAND)
        if not state:
            if heat_out and not above_exit:
                heat_out = False  # 過熱空手期間已跌破出場線：回到一般進場規則
            cooled = dev is None or (dev[0] < HEAT_REENTRY and dev[1] <= HEAT_Z)
            if (px > ma_n * (1 + STRATEGY_ENTRY_BAND) and not hot) or (heat_out and cooled and above_exit):
                state, switched, heat_out = True, d, False
        elif hot:
            state, switched, heat_out = False, d, True
        elif not above_exit:
            state, switched, heat_out = False, d, False
    return state, switched, ma_x, ma_n


REBAL_LOW, REBAL_TARGET = 0.12, 0.15


def rebalance_lines(date: str, closes: list, switched: str) -> list:
    """研究 478／479（2026-11-27 使用者選甲）：主策略在場時 00631L 上漲會稀釋 15% 現金（期貨加碼的保證金）；
    估計現金占比跌破 12% 就提醒賣一部分 00631L 補回 15%。00631L 以「每日 2 倍加權」近似，自進場（訊號後下一個交易日收盤買）起算，
    假設每次跌破 12% 都有照做；期貨加碼損益不計。2002～ 不再平衡時最低到 4.8%（2025-05～2026-05）"""
    ds = [d for d, _ in closes]
    if switched not in ds:
        return []
    k0 = ds.index(switched) + 1
    if k0 >= len(ds) - 1:
        return []
    a, c, last_rb = 1 - REBAL_TARGET, REBAL_TARGET, None
    hit_today = False
    for k in range(k0 + 1, len(ds)):
        a *= 1 + 2 * (closes[k][1] / closes[k - 1][1] - 1)
        if c / (a + c) < REBAL_LOW:
            sell = (a / (a + c)) - (1 - REBAL_TARGET)
            if ds[k] == date:
                hit_today = True
                break
            a, c = (1 - REBAL_TARGET) * (a + c), REBAL_TARGET * (a + c)
            last_rb = ds[k]
    cf = c / (a + c)
    if hit_today:
        return [f"🔔 再平衡（研究 478，你選的甲）：估計現金只剩約 {cf:.1%}（< 12%）→ 明天收盤前賣出約總資產 {sell:.0%} 的 00631L，轉進期貨帳戶，回到 85%／15%",
                "　原因：現金是期貨加碼的保證金，太少時恐慌做多、爆量收黑會放不下；實際比例以你的帳戶為準"]
    rb = f"，上次估計該再平衡 {int(last_rb[4:6])}/{int(last_rb[6:])}" if last_rb else ""
    return [f"　💵 現金占比估計約 {cf:.0%}（跌破 12% 時提醒再平衡{rb}；以 00631L≈2 倍加權估算，實際以帳戶為準）"]


def strategy_lines(date: str) -> list:
    closes = taiex_daily(date)
    if len(closes) < max(STRATEGY_EXIT_MA, STRATEGY_ENTRY_MA) + 5 or closes[-1][0] != date:
        return []
    if _TODAY_MARGIN.get("date") == date:
        save_margin_ratio(date, _TODAY_MARGIN["amount"], closes[-1][1], _TODAY_MARGIN.get("ratio"))
    heat = heat_series(load_margin_ratio())
    state, switched, ma_x, ma_n = strategy_state(closes, heat)
    px = closes[-1][1]
    up, dn = ma_n * (1 + STRATEGY_ENTRY_BAND), ma_x * (1 - STRATEGY_EXIT_BAND)
    is_friday = is_week_end(date)  # 本週最後交易日（週五休市時是週四，研究 270）
    # 2026-11-26 使用者要求：日報只講觸發了哪條規則、建議什麼操作；沒觸發的規則不逐條列
    lines = [""]
    hold = STRATEGY_ON if state else STRATEGY_OFF
    since = f"（{int(switched[4:6])}/{int(switched[6:])} 起）" if switched else ""
    dev = heat_on(heat, date)
    if dev is not None:
        last = max(k for k in heat if k <= date)
        stale = "" if last == date else f"（用 {int(last[4:6])}/{int(last[6:])} 的融資資料）"
        if is_hot(dev):
            lines.append(f"🔥 融資過熱濾網觸發：融資÷指數 比 {HEAT_N} 日平均 {dev[0]:+.1%}（門檻 +{HEAT_TH:.1%}）、z {dev[1]:+.2f}（門檻 {HEAT_Z:g}）→ 出場、不進場{stale}")
    lines.append(f"🧭 主策略應持有：{hold}{since}")
    if switched == date and not state and not is_friday:
        lines.append(f"⚠️ 融資過熱（每日檢查）：下一個交易日收盤 全部賣出 → {STRATEGY_OFF}")
        lines.append("　部位：00631L 全部賣出、轉現金｜歷史（1997～，55 段空手期）指數平均 -2.6%、2 倍部位等於避開約 -4.0%；約一半的空手期指數其實是漲的（假訊號），靠避開大跌取勝")
    elif is_friday and switched == date:
        action = f"買進 → {STRATEGY_ON}" if state else f"全部賣出 → {STRATEGY_OFF}"
        lines.append(f"⚠️ 本週訊號切換：下一個交易日收盤 {action}")
        lines.append("　部位：資金 85% 買 00631L（約 1.7 倍曝險）、15% 現金轉進期貨帳戶當加碼保證金（研究 216：在場時期貨加碼最多要約 20% 保證金，15% 時 77 段只有 1 段不夠）｜歷史（1997～，54 次）勝率 52%、期望值每次 +19.1%（中位 +0.3%）、平均賺 +43.6%／平均賠 -7.3%、平均抱約 53 個交易日——小賠多次、大賺少次｜退場（＝主策略的停損）：週五收盤跌破出場線（MA80 × 0.975），或融資過熱（每天檢查）就全部賣出" if state else "　部位：00631L 全部賣出、轉現金｜歷史（1997～，55 段空手期）指數平均 -2.6%、2 倍部位等於避開約 -4.0%；約一半的空手期指數其實是漲的（假訊號），靠避開大跌取勝")
    if state and switched:
        try:
            lines += rebalance_lines(date, closes, switched)
        except Exception as e:  # noqa: BLE001
            print(f"再平衡估算失敗：{e}", file=sys.stderr)
    try:
        lines += overlay_lines(date, closes, heat)
    except Exception as e:  # 加碼段落失敗不影響策略段落
        print(f"加碼訊號失敗：{e}", file=sys.stderr)
    try:
        lines += pc_lines(date, state, closes)
    except Exception as e:  # 觀察指標抓不到不影響策略段落
        print(f"P/C 失敗：{e}", file=sys.stderr)
    try:
        lines += divergence_lines(date, closes)
    except Exception as e:  # 觀察指標抓不到不影響策略段落
        print(f"台美背離加碼失敗：{e}", file=sys.stderr)
    try:
        lines += yearend_lines(date)
    except Exception as e:  # noqa: BLE001
        print(f"年底加碼失敗：{e}", file=sys.stderr)
    try:
        lines += lunar_lines(date)
    except Exception as e:  # noqa: BLE001
        print(f"春節加碼失敗：{e}", file=sys.stderr)
    try:
        lines += nsf_lines(date)
    except Exception as e:  # noqa: BLE001
        print(f"國安基金提醒失敗：{e}", file=sys.stderr)
    return lines


# ── 台美背離加碼（研究 204～205c，2026-11-26 依「更好就直接更新」納入）──────────────────
# 加權 20 日報酬 − S&P500 20 日報酬（用台股該日之前最後一個美股收盤）≤ -10% → 隔天 08:45 開盤加 0.5 倍台指期，
# 抱到第 5 個交易日收盤出；持有中再觸發不加碼、不延長。不分主策略狀態（38 次中 35 次主策略空手）。
# 1998～ 去叢集 38 次：比「台股跌一樣多但美股也跌」多 +2.0%（家族 p 0.001，兩段都正）；疊在 V+F+P 上（2018-06～）
# 11 筆、每筆 +3.2%、勝率 82%，年化 70.4%→73.8%、回檔不變（家族 p 0.002）；1998–2018 樣本外每筆約 +0.7%、勝率約 55%（較弱）。
# 不設停損（研究 211：3～10% 停損都讓每筆變差）
DIV_TH, DIV_N, DIV_ADD, DIV_H = 0.10, 20, 0.5, 5


def divergence_lines(date: str, closes: list) -> list:
    if len(closes) < DIV_N + 1 or closes[-1][0] != date:
        return []
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?range=1y&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen_retry(req) as res:
        r = json.loads(res.read().decode("utf-8"))["chart"]["result"][0]
    ny = timezone(timedelta(hours=-5))
    us = [(datetime.fromtimestamp(t, ny).strftime("%Y%m%d"), c)
          for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c]
    # 研究 426：S&P 單日 >15% 視為 Yahoo 壞值，整段不判斷（避免假背離）
    if any(abs(b / a - 1) > 0.15 for (_, a), (_, b) in zip(us, us[1:])):
        print("台美背離：S&P 資料有單日 >15% 的異常值，今天不判斷", file=sys.stderr)
        return []

    def us_before(d):
        prev = [c for k, c in us if k < d]
        return prev[-1] if prev else None

    def gap_at(k):  # closes 第 k 天（負索引）的背離
        u0, u1 = us_before(closes[k - DIV_N][0]), us_before(closes[k][0])
        if not u0 or not u1:
            return None
        tw = closes[k][1] / closes[k - DIV_N][1] - 1
        return tw, tw - (u1 / u0 - 1)

    # 從 30 天前往後模擬：觸發日 D → D+1 開盤進、D+DIV_H 收盤出，持有中再觸發不算
    span = min(30, len(closes) - DIV_N - 1)
    entry = None  # 進場訊號日的索引（負索引）
    for k in range(-span, 0):
        gk = gap_at(k)
        if entry is not None and k - entry > DIV_H:
            entry = None
        if entry is None and gk and gk[1] <= -DIV_TH:
            entry = k
    today = gap_at(-1)
    if not today:
        return []
    tw20, gap = today
    if entry == -1:
        return ["", f"🎯 台美背離加碼：台股 20 日 {tw20:+.1%}、落後 S&P500 {gap:+.1%}（門檻 -{DIV_TH:.0%}）→ 明早 08:45 開盤加 {DIV_ADD} 倍台指期，抱到第 {DIV_H} 個交易日收盤出（每 100 萬資金約微台 {DIV_ADD * 1e6 / (closes[-1][1] * 10):.1f} 口，研究 400）",
                f"　不設停損（研究 211：崩跌中盤中震幅大，3～10% 停損都讓每筆變差），退場＝第 {DIV_H} 天收盤｜"
                "台指期真實價 1998～ 64 筆每筆 +1.1%、勝率 59%、最差 -10.6%（0.5 倍＝資金約 -5%）；2018～ 11 筆 +3.2%、勝率 82%（研究 204～211）"]
    if entry is not None:
        held = -1 - entry  # 已過幾個交易日（進場日＝1）
        sd = closes[entry][0]
        if held == DIV_H - 1:
            return ["", f"📌 台美背離加碼（{int(sd[4:6])}/{int(sd[6:])} 觸發）：明天 13:45 收盤前平倉 {DIV_ADD} 倍台指期（第 {DIV_H} 個交易日）"]
        if held < DIV_H - 1:
            out = ["", f"👀 台美背離加碼持有中（{int(sd[4:6])}/{int(sd[6:])} 觸發，第 {held} 天／{DIV_H}；目前背離 {gap:+.1%}）：不加碼、不延長"]
            if held == 1:  # 研究 245、249：錯過今天 08:45 的補進參考，依今天漲幅分組（1998～ 67 次，補進＝第 1 天收盤→第 5 天收盤）
                d1 = closes[-1][1] / closes[-2][1] - 1
                ref = ("34 次 平均 +1.4%、勝率 62%" if d1 < 0 else "19 次 平均 +0.3%、勝率 58%" if d1 < 0.015
                       else "5 次 平均 +0.5%、勝率 40%（中位 -0.4%）→ 優勢不明確，可不補或只補一半" if d1 < 0.03
                       else "9 次 平均 +2.8%、勝率 78%")
                out.append(f"　錯過今天 08:45：可在今晚夜盤（15:00～隔天 05:00，收到日報時仍在交易）或明早 08:45 補進、一樣第 {DIV_H} 天收盤出（研究 220）｜"
                           f"今天加權 {d1:+.1%}，歷史上同樣漲跌時補進：{ref}（研究 249，各組樣本少）")
            return out
    return []


# ── 年底加碼（研究 262、262b、263；2026-11-26 使用者同意 0.5 倍）──────────────────
# 12 月最後交易日前 3 個交易日收盤進 0.5 倍台指期，1 月第 5 個交易日收盤出；不分主策略狀態、不設停損。
# 1998～2025 28 次：加權每筆 +2.1%、勝率 71%（家族 p 0.001）；台指期真實價 +2.2%、最差 -5.5%；2013 後較弱（約 +1.3%）。
# 疊在現行（85% 00631L＋V+F+P+D）上 2018-06～ 65.1%→66.4%、回檔與最差單日不變（研究 263）。
# 交易日用證交所休市日曆（研究 270；2026-12-25 休市、2027-12-24／12-31 休市）；颱風等臨時休市會差一天，影響很小
YE_ADD, YE_PRE, YE_POST = 0.5, 3, 5


def _tdays(start, end):
    d, out = start, []
    while d <= end:
        if is_trading_day(d):
            out.append(d)
        d += timedelta(days=1)
    return out


def yearend_lines(date: str) -> list:
    t = datetime.strptime(date, "%Y%m%d").date()
    if t.month not in (11, 12, 1):
        return []
    y = t.year - 1 if t.month == 1 else t.year
    dec = _tdays(datetime(y, 12, 1).date(), datetime(y, 12, 31).date())
    jan = _tdays(datetime(y + 1, 1, 1).date(), datetime(y + 1, 1, 20).date())
    entry, exit_ = dec[-1 - YE_PRE], jan[YE_POST - 1]
    cal = dec + jan
    md = lambda d: f"{d.month}/{d.day}"  # noqa: E731
    head = f"年底加碼（{md(entry)} 收盤進 {YE_ADD} 倍台指期 → {md(exit_)} 收盤出，研究 262）"
    stat = "　1998～2025 28 次：每筆 +2.1%、勝率 71%、最差 -5.5%（台指期真實價）；2013 後較弱約 +1.3%｜不設停損、不分主策略狀態（回測，可能偏樂觀）"
    if t < entry:
        left = len([d for d in cal if t < d <= entry]) if t >= dec[0] else None
        if left == 1:
            return ["", f"📅 {head}：下個交易日（{md(entry)}）13:45 收盤前加碼（來不及就當天 15:00 夜盤或隔天 08:45 開盤）", stat]
        if t.month == 12 and left and left <= 5:
            return ["", f"🗓️ {head}：再 {left} 個交易日進場"]
        return []
    if t == entry:
        return ["", f"🎯 {head}：今天收盤該進場；還沒進的今晚夜盤或明早 08:45 補進，一樣 {md(exit_)} 收盤出", stat]
    if t < exit_:
        rest = len([d for d in cal if t < d <= exit_])
        if rest == 1:
            return ["", f"📌 {head}：下個交易日（{md(exit_)}）13:45 收盤前平倉"]
        return ["", f"👀 {head}：持有中，還有 {rest} 個交易日"]
    return []


# ── 春節不抱過年加碼（研究 261、267、268；2026-11-27 使用者同意 0.5 倍）──────────────────
# 封關日（春節長假前最後交易日）前 3 個交易日收盤進 0.5 倍台指期，封關日收盤出（不抱過年，避開年後開紅盤的跳空風險）。
# 1998～2026 29 次：加權每筆 +1.1%、勝率 72%、最差 -2.6%（家族 p 0.001）；台指期真實價 +0.85%、勝率 61%；2013 後較弱約 +0.6%；
# 疊在現行＋年底上 2018-06～ 66.4%→67.3%、回檔與最差單日不變（研究 267）；其他市場同期沒有＝台股本地節前效應（研究 268）
LN_ADD, LN_PRE = 0.5, 3


def lunar_close_day(year: int):
    """year 年春節長假前最後交易日（1、2 月中下一個交易日隔 ≥6 個日曆天）"""
    days = _tdays(datetime(year, 1, 2).date(), datetime(year, 3, 10).date())
    for a, b in zip(days, days[1:]):
        if a.month in (1, 2) and (b - a).days >= 6:
            return a, days
    return None, days


def lunar_lines(date: str) -> list:
    t = datetime.strptime(date, "%Y%m%d").date()
    if t.month not in (1, 2):
        return []
    close_, days = lunar_close_day(t.year)
    if close_ is None:
        return []
    k = days.index(close_)
    entry = days[k - LN_PRE]
    md = lambda d: f"{d.month}/{d.day}"  # noqa: E731
    head = f"春節加碼（{md(entry)} 收盤進 {LN_ADD} 倍台指期 → {md(close_)} 封關日收盤出、不抱過年，研究 267）"
    stat = "　1998～2026 29 次：加權每筆 +1.1%、勝率 72%、最差 -2.6%；台指期真實價 28 筆 +0.85%、勝率 61%；2013 後較弱約 +0.6%｜不設停損、不分主策略狀態（回測，可能偏樂觀）"
    if t < entry:
        left = len([d for d in days if t < d <= entry])
        if left == 1:
            return ["", f"📅 {head}：下個交易日（{md(entry)}）13:45 收盤前加碼（來不及就當天 15:00 夜盤或隔天 08:45 開盤）", stat]
        if left <= 5:
            return ["", f"🗓️ {head}：再 {left} 個交易日進場"]
        return []
    if t == entry:
        return ["", f"🎯 {head}：今天收盤該進場；還沒進的今晚夜盤或明早 08:45 補進，一樣 {md(close_)} 收盤出", stat]
    if t < close_:
        rest = len([d for d in days if t < d <= close_])
        if rest == 1:
            return ["", f"📌 {head}：下個交易日（{md(close_)}，封關日）13:45 收盤前平倉，不要抱過年"]
        return ["", f"👀 {head}：持有中，還有 {rest} 個交易日"]
    return []


# ── 國安基金進場參考提醒（研究 280、291；2026-11-27 使用者同意加「參考提醒」，不改倉位）──────────────────
# 國安基金宣布進場後第一個交易日開盤進台指期 → 第 5 個交易日收盤：2000～2026 10 次全上漲、平均 +6.3%；
# 扣掉「急跌後本來就反彈」仍超額 +4.7%（p 0.003，研究 280～290 系列 BH q 0.035）；20 日以上不可靠（2000-10、2008 之後再跌 2 成以上）。
# 沒有可靠的自動資料源：宣布時把（宣布日, 第一個反應交易日, 說明）加進 NSF_EVENTS 即可，日報在宣布日～第 5 個交易日顯示
NSF_EVENTS = [
    ("20261106", "20261109", "第 10 次，第 131 次臨時委員會授權"),
]
NSF_H = 5


def nsf_lines(date: str) -> list:
    t = datetime.strptime(date, "%Y%m%d").date()
    md = lambda d: f"{d.month}/{d.day}"  # noqa: E731
    for ann, first, note in NSF_EVENTS:
        a = datetime.strptime(ann, "%Y%m%d").date()
        e = datetime.strptime(first, "%Y%m%d").date()
        if not (a <= t <= e + timedelta(days=14)):
            continue
        days = _tdays(e, e + timedelta(days=14))[:NSF_H]
        if t > days[-1]:
            continue
        head = f"🏛️ 國安基金 {md(a)} 宣布進場（{note}）— 參考提醒，不改倉位（研究 280）"
        stat = ("　歷史 10 次：宣布後第一個交易日開盤進台指期、第 5 天收盤出全部上漲、平均 +6.3%（扣急跌反彈後超額 +4.7%）；"
                "當天收盤出只有 -0.1%，20 日以上不可靠（2000-10、2008 之後再跌 2 成以上）｜"
                "ETF 版（研究 295，扣成本）：0050 5 次 5 日全漲、平均 +6.3%；00631L 4 次全漲、平均 +12.7%，但第一天曾跌 10%，要抱滿 5 天")
        if t < e:
            return ["", f"{head}：第一個反應交易日是 {md(e)}，到 {md(days[-1])} 收盤為歷史上偏多的 5 天", stat]
        k = days.index(t) + 1 if t in days else None
        if k is None:
            return []
        tail = "今天是第 5 天（最後一天）" if k == NSF_H else f"第 {k}／{NSF_H} 天，到 {md(days[-1])} 收盤"
        return ["", f"{head}：{tail}", stat]
    return nsf_news_hint(t)


# 研究 292：Google News RSS 偵測「新宣布」——標題同時有「國安基金」與啟動／宣布／決議／授權／臨時委員會，
# 3 天內、且離已登錄事件 >60 天才提示（在場期間天天有「已進場」報導，不能只看「進場」二字）。只提示，不自動當事件
NSF_NEWS_KEYS = ("啟動護盤", "宣布進場", "決議進場", "臨時委員會", "授權", "啟動進場", "宣布護盤")


def nsf_news_hint(t) -> list:
    if any(abs((t - datetime.strptime(a, "%Y%m%d").date()).days) <= 60 for a, _, _ in NSF_EVENTS):
        return []
    q = urllib.parse.quote("國安基金 進場")
    url = f"https://news.google.com/rss/search?q={q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen_retry(req) as res:
        x = res.read().decode("utf-8", "replace")
    hits = []
    for title, pub in re.findall(r"<item><title>(.*?)</title>.*?<pubDate>(.*?)</pubDate>", x, re.S):
        try:
            d = datetime.strptime(pub[5:16], "%d %b %Y").date()
        except ValueError:
            continue
        if 0 <= (t - d).days <= 3 and "國安基金" in title and any(k in title for k in NSF_NEWS_KEYS):
            hits.append(title.split(" - ")[0][:40])
    if not hits:
        return []
    return ["", f"📰 新聞疑似國安基金新宣布進場（{len(hits)} 則，例：「{hits[0]}」）→ 確認後把宣布日加進 report.py 的 NSF_EVENTS，"
                "日報就會顯示研究 280 的 5 日參考（歷史 10 次全上漲、平均 +6.3%）"]


# ── 52 週高點選股（研究 301～303；2026-11-27 使用者要求每月附清單，參考、不在主策略內）──────────────────
# 每天補抓最近交易日的上市個股收盤（`backtest/stock_closes`，缺幾天抓幾天、一天一次請求）；
# 每月第一個交易日依 nh_picks.py 規則出清單（前 10%，附新增／剔除），存 `data/nh_list.csv`


def nh_report_lines(date: str) -> list:
    import nh_picks
    t = datetime.strptime(date, "%Y%m%d").date()
    recent = [d.isoformat() for d in _tdays(t - timedelta(days=60), t)]
    if not recent or recent[-1] != t.isoformat():
        return []
    prev = recent[-2] if len(recent) > 1 else None
    if prev and prev[:7] == recent[-1][:7]:
        nh_picks.update_closes(recent[-10:])  # 平常日：只補收盤
        return []
    return nh_picks.lines(t.isoformat(), recent)


# ── 在場時爆量收黑加碼（研究 63～64g，2026-11-24 使用者同意加入）──────────────────
# 現行策略在場（持有正2）時，證交所成交金額 ≥ 前 20 個交易日平均 × OVERLAY_K 且加權指數收黑 →
# 當晚 15:00 夜盤起加台指期 0.5～1 倍名目（資金 × 0.5～1），抱 OVERLAY_H 個交易日後收盤平倉；現行策略出場則一起平。
# 回測 2002–2026：加 1x 抱 10 天 23.2%→26.9%（回檔 -36.8%→-39.7%）；真實價格 2015–2026 34.3%→39.7%；
# 勝過「在場日隨機加碼」p 0.005；拔靴 P(回檔<-50%) 66%→69%；鄰近參數 46/50 組通過。3% 停損可選（影響很小）
OVERLAY_K, OVERLAY_H = 1.5, 10
# 獨立短線帳戶（2026-11-24 使用者要求加入日報，研究 63d／63g）：爆量收黑 → 當晚夜盤或隔天開盤買台指期近月，抱 5 天、5% 停損
SHORT_HOLD, SHORT_STOP = 5, 0.05


def turnover_series(date: str, months: int = 3) -> list:
    """[(YYYYMMDD, 成交金額)]，往前 months 個月（FMTQIK 每月一張表；get_json 有快取）"""
    out = {}
    y, m = int(date[:4]), int(date[4:6])
    for _ in range(months):
        d = get_json(f"https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?date={y}{m:02d}01&response=json")
        for t in tables_of(d):
            f = t.get("fields", [])
            if "日期" in f and "成交金額" in f:
                idate, iamt = f.index("日期"), f.index("成交金額")
                for r in t.get("data", []):
                    yy, mm, dd = str(r[idate]).strip().split("/")
                    out[f"{int(yy) + 1911}{int(mm):02d}{int(dd):02d}"] = num(r[iamt])
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return sorted((k, v) for k, v in out.items() if k <= date)


def overlay_lines(date: str, closes: list, heat: dict) -> list:
    lines = _overlay_core(date, closes, heat)
    try:
        lines += foreign_fut_lines(date, closes, heat)
    except Exception as e:  # 觀察段落失敗不影響其他段落
        print(f"外資期貨觀察失敗：{e}", file=sys.stderr)
    return lines


# ── 外資台指期淨未平倉單日大變化（研究 73、75～75d）；雙指標加碼 0.5 倍 2026-11-25 納入規則（研究 128／129／135）──────────
# 外資淨未平倉單日變化相對過去 250 日 z > +1.5（大回補）／< −1.5（大加空）。研究 75（00631L＋台指期真實價，2018-06～2026-11，只有 8 年）：
# 現行在場時「大回補 → 隔天開盤加 1x 抱 5 天、大加空 → 空 1x（降到 1x）5 天」43.0%／-37.2% → 60.4%／-34.6%，隨機對照 p 0.005
FOREIGN_Z = 1.5


def foreign_fut_lines(date: str, closes: list, heat: dict) -> list:
    end = datetime.strptime(date, "%Y%m%d")
    body = urllib.parse.urlencode({"queryStartDate": (end - timedelta(days=430)).strftime("%Y/%m/%d"),
                                   "queryEndDate": end.strftime("%Y/%m/%d"), "commodityId": "TXF"}).encode()
    req = urllib.request.Request("https://www.taifex.com.tw/cht/3/futContractsDateDown", data=body, headers=UA)
    with urlopen_retry(req) as res:
        text = res.read().decode("big5", errors="replace")
    net, flow = [], []
    for ln in text.splitlines()[1:]:
        r = ln.split(",")
        if len(r) >= 14 and "外資" in r[2]:
            lo, sh = num(r[9]), num(r[11])
            if lo or sh:  # 當天未平倉尚未公布時為 0
                net.append((r[0].replace("/", ""), lo - sh))
                flow.append(num(r[3]) - num(r[5]))  # 交易口數淨額（研究 127／128）
    if len(net) < 122 or net[-1][0] != date:
        return []
    deltas = [net[k][1] - net[k - 1][1] for k in range(1, len(net))]
    hist = deltas[-251:-1]
    m_ = sum(hist) / len(hist)
    sd = (sum((x - m_) ** 2 for x in hist) / len(hist)) ** 0.5
    z = (deltas[-1] - m_) / sd if sd > 0 else 0.0
    on_now = strategy_state(closes, heat)[0]
    fh = flow[-251:-1]
    fm = sum(fh) / len(fh)
    fsd = (sum((x - fm) ** 2 for x in fh) / len(fh)) ** 0.5
    zf = (flow[-1] - fm) / fsd if fsd > 0 else 0.0
    lines = [f"📊 外資台指期（研究 73／75／79／128；雙指標加碼 11/25 納入規則）：淨未平倉 {net[-1][1]:+,.0f} 口，今日變化 {deltas[-1]:+,.0f} 口（z {z:+.2f}）、"
             f"交易淨額 {flow[-1]:+,.0f} 口（z {zf:+.2f}），門檻 ±{FOREIGN_Z}"]

    def third_wed(d):
        x = datetime.strptime(d, "%Y%m%d")
        return x.weekday() == 2 and 15 <= x.day <= 21
    prev = net[-2][0]
    if third_wed(date) or third_wed(prev):
        # 研究 79：結算日（第三個星期三）與次日的未平倉變化含到期部位消失，訊號不採用
        return []  # 研究 79：結算日與次日訊號不採用
    if z > FOREIGN_Z:
        skip = short_skip(closes, heat, date)
        if skip:
            lines.append(f"⛔ 外資回補短線（研究 106）建議跳過：{skip.split('（')[0]}（研究 106：空頭時抱 5 天每筆 -1.9%）")
        else:
            lines.append("🎯 獨立短線（研究 106，2019～ 只有 7 年、小額）：明早 8:45 開盤做多台指期近月 0.5 倍名目（樣本少、建議小額），抱 5 個交易日後收盤平倉；停損 5%（研究 175）"
                         "（多頭時歷史 57 筆、勝率 81%、每筆 +1.29%；前後段都正。抱 1 天在 2023 後已無效）")
        lines.append("　外資大回補／加多：歷史上之後 1～10 天偏強")
        if on_now and zf > FOREIGN_Z:
            # 研究 128／129／135（2026-11-25 依使用者「有更好的直接更新」納入）：雙指標都過才加碼，0.5 倍
            lines.append("🔔 外資期貨加碼（雙指標成立）：明早 8:45 開盤加台指期近月 0.5 倍名目（資金 × 0.5），抱 5 個交易日後收盤平倉；現行策略出場則一起平；停損 5%（進場價 −5%，日盤／夜盤碰到就出；研究 175：5% 災難停損不影響期望值、把最差一筆限制在約 -5%，2～3% 太緊反而變差）；"
                         "可和爆量收黑加碼同時持有（研究 135：兩者效果相加、互不干擾）")
            lines.append("　回測（v3、2018-06～）：加 0.5 倍 48.2%→53.5%、回檔 -27.1%→-27.5%；扣掉挑選後家族 p 0.04（研究 129，中等證據，所以只加 0.5 倍）")
            lines.append("　勝率／期望值（每筆，台指期真實價、扣成本）：42 筆 勝率 83%、期望值 +1.43%（平均賺 +1.92%／賠 -1.03%、最差 -3.0%）")
    return lines if any(ln.startswith(("🎯", "🔔", "⛔")) for ln in lines) else []  # 沒有操作建議就不顯示


def _overlay_core(date: str, closes: list, heat: dict) -> list:
    amt = dict(turnover_series(date))
    cdict = dict(closes)
    days = [d for d, _ in closes if d in amt]
    if len(days) < 22 or days[-1] != date:
        return []

    def signal(j):
        base = sum(amt[days[k]] for k in range(j - 20, j)) / 20
        return amt[days[j]] / base, cdict[days[j]] < cdict[days[j - 1]]

    n = len(days)
    vr, down = signal(n - 1)
    on_now = strategy_state(closes, heat)[0]
    lines = ["", f"⚡ 爆量收黑加碼（研究 64b）：今日成交金額 {amt[date] / 1e8:,.0f} 億＝20 日均量 {vr:.2f} 倍"
                 f"（門檻 {OVERLAY_K} 倍且收黑；下一交易日約需 ≥ {sum(amt[days[k]] for k in range(n - 20, n)) / 20 * OVERLAY_K / 1e8:,.0f} 億）"]
    # 近 OVERLAY_H 個交易日內、當時在場的訊號 → 加碼持有中
    active = None
    for j in range(max(21, n - 1 - OVERLAY_H), n - 1):
        r, dn = signal(j)
        if r >= OVERLAY_K and dn and strategy_state([c for c in closes if c[0] <= days[j]], heat)[0]:
            active = j
    if vr >= OVERLAY_K and down:
        if on_now:
            lines.append(f"🔔 加碼訊號成立：明早 8:45 開盤（下午 14:40 提醒時已在夜盤進場就不用再進）加台指期 1 倍名目（資金 × 1；資金 100 萬 ≈ 微台 2～3 口），"
                         f"抱 {OVERLAY_H} 個交易日後收盤平倉；現行策略出場則一起平；停損 5%（進場價 −5%，日盤／夜盤碰到就出；研究 175：5% 災難停損不影響期望值、把最差一筆限制在約 -5%，2～3% 太緊反而變差）")
            lines.append("　勝率／期望值（台指期真實價、1998～、扣成本，研究 172b；11/26 修正用成交金額）：35 筆 勝率 80%、期望值每筆 +2.73%（平均賺 +4.27%／賠 -3.44%、最差 -7.0%）；1998–2007／2008–2016／2017～ 勝率 73%／83%／86%；維持 1 倍不再提高")
            # 觀察（研究 64i／64j，未納入規則）：離出場線 ≥5% 時加碼，真實價格回檔與不加碼相同、報酬幾乎不變
            exit_line = sum(v for _, v in closes[-STRATEGY_EXIT_MA:]) / STRATEGY_EXIT_MA * (1 - STRATEGY_EXIT_BAND)
            gap = cdict[date] / exit_line - 1
            lines.append(f"　觀察：目前離出場線 {exit_line:,.0f} 還有 {gap:+.1%}"
                         + ("（< 5%：研究 64i 顯示這種情況較易遇到隨即出場，保守者可改加 0.5 倍或不加）" if gap < 0.05 else "（≥ 5%：歷史上這類加碼勝率較高）"))
        else:
            lines.append("今日爆量收黑，但現行策略空手：主策略不動作（研究 64）")
        skip = short_skip(closes, heat, date)
        if skip:
            lines.append(f"⛔ 獨立短線（研究 63d／105）建議跳過：{skip}")
        else:
            lines.append(f"🎯 獨立短線（研究 63d／63g／105，與主策略分開、小額）：明早 8:45 開盤買台指期近月 0.5 倍名目（樣本少、建議小額；下午提醒時已在夜盤買就不用再買），抱 {SHORT_HOLD} 個交易日後收盤平倉，"
                         f"停損 {SHORT_STOP:.0%}（多頭且融資正常時歷史 33 筆、勝率 91%、每筆 +1.65%；一年約 1～2 次）")
    elif active is not None and on_now:
        held = n - 1 - active
        lines.append(f"加碼持有中：{int(days[active][4:6])}/{int(days[active][6:])} 的訊號，已過 {held}/{OVERLAY_H} 個交易日"
                     + ("，今天收盤平倉" if held >= OVERLAY_H else ""))
    elif active is not None and not on_now:
        lines.append("現行策略已出場：加碼部位應一起平倉")
    # 獨立短線（不論主策略狀態）：近 SHORT_HOLD 個交易日內的爆量收黑 → 持有中提醒
    if not (vr >= OVERLAY_K and down):
        for j in range(max(21, n - 1 - SHORT_HOLD), n - 1):
            r, dn = signal(j)
            if r >= OVERLAY_K and dn and not short_skip([c for c in closes if c[0] <= days[j]], heat, days[j]):
                held = n - 1 - j
                entry = cdict[days[j]]
                lines.append(f"👀 獨立短線持有中：{int(days[j][4:6])}/{int(days[j][6:])} 的爆量收黑，已過 {held}/{SHORT_HOLD} 個交易日"
                             + ("，今天收盤平倉" if held >= SHORT_HOLD else f"；停損參考：指數跌破約 {entry * (1 - SHORT_STOP):,.0f}"))
                break
    return lines if len(lines) > 2 else []  # 只有標題＝沒觸發、沒持有 → 不顯示


# ── 下午即時提醒（REPORT_PART=alert，14:40 排程）：爆量收黑收盤就知道，21:30 日報時夜盤 15:00 開盤已過 ──────────
# 研究 63d：當晚夜盤 15:00 進每筆 +1.61%、隔天開盤進 +1.08%、隔天收盤才進 +0.44%（不顯著）→ 越早進越好，所以收盤後另外提醒
def short_skip(closes: list, heat: dict, date: str):
    """研究 105：爆量收黑獨立短線只在「多頭（指數 ≥ 出場線）且融資不過熱」有優勢；其他情況回傳跳過的理由"""
    v = heat_on(heat, date)
    if v is not None and is_hot(v):
        return "融資過熱中（研究 105：過熱當天 5 筆、勝率 40%、每筆 -0.5%，含 2026-10-15 -2.2%）"
    exit_line = sum(c for _, c in closes[-STRATEGY_EXIT_MA:]) / STRATEGY_EXIT_MA * (1 - STRATEGY_EXIT_BAND)
    if closes[-1][1] < exit_line:
        return f"指數在出場線 {exit_line:,.0f} 之下（空頭；研究 105：14 筆、勝率 64%、每筆 -0.3%，抱 10 天 -2.1%）"
    return None


def alert_lines(date: str, retry: bool) -> list:
    if wait_for(turnover, date, retry) is None:
        return []
    closes = taiex_daily(date)
    amt = dict(turnover_series(date))
    days = [d for d, _ in closes if d in amt]
    if len(days) < 22 or days[-1] != date:
        return []
    base = sum(amt[d] for d in days[-21:-1]) / 20
    vr = amt[date] / base
    px, prev = closes[-1][1], closes[-2][1]
    if not (vr >= OVERLAY_K and px < prev):
        return []
    heat = heat_series(load_margin_ratio())
    on_now = strategy_state(closes, heat)[0]
    skip = short_skip(closes, heat, date)
    lines = [f"爆量收黑：成交金額 {amt[date] / 1e8:,.0f} 億＝20 日均 {vr:.2f} 倍（門檻 {OVERLAY_K}），指數 {px:,.0f}（{px / prev - 1:+.2%}）",
             "⏰ 操作時間：今天 15:00 夜盤開盤進場最好（研究 63d 每筆約 +1.6%）；來不及就明早 8:45 開盤（約 +1.1%）；"
             "明天收盤才進只剩約 +0.4%，就不要追了",
             (f"⛔ 獨立短線建議跳過：{skip}" if skip else
              f"🎯 獨立短線：買台指期近月 0.5 倍名目（樣本少、建議小額），抱 {SHORT_HOLD} 個交易日後收盤平倉，停損 {SHORT_STOP:.0%}（約指數 {px * (1 - SHORT_STOP):,.0f}）"
              "；多頭且融資正常時歷史 33 筆、勝率 91%、每筆 +1.65%（研究 105）")]
    if on_now:
        # 研究 434：主策略在場時「獨立短線 0.5x」與 V 1x 是同一訊號，合計 1.5x（15% 現金的上限約 1.5x，研究 243）
        lines.append("　⚠️ 主策略在場時，上面的獨立短線和下面的加碼是同一個訊號，合計 1.5 倍；外資期貨加碼也還在持有的話，獨立短線那 0.5 倍就不要加（研究 434：多這 0.5 倍每筆約 +0.8%、最差 -7.9%）")
        lines.append(f"🔔 主策略在場：再加台指期 1 倍名目（資金 100 萬 ≈ 微台 2～3 口），抱 {OVERLAY_H} 個交易日（研究 64b）；主策略出場就一起平；停損 5%（進場價 −5%，日盤／夜盤碰到就出；研究 175：5% 災難停損不影響期望值、把最差一筆限制在約 -5%，2～3% 太緊反而變差）")
        lines.append("　勝率／期望值（1998～、扣成本，研究 172b）：35 筆 勝率 80%、期望值每筆 +2.73%（平均賺 +4.27%／賠 -3.44%、最差 -7.0%）")
    else:
        lines.append("主策略空手：主策略不加碼（研究 64）" + ("，獨立短線也跳過 → 今天不動作" if skip else "，只做獨立短線"))
    lines.append("（融資要 21:00 才公布，這裡用前一天的融資判斷過熱；若 21:30 日報改說「融資過熱、建議跳過」，夜盤已買的可明早開盤平掉）")
    return lines


# ── 早上提醒：恐慌隔天做多（候選 6，研究 139、142～145；2026-11-25 使用者同意加入）────────────
# 夜盤（前一天 15:00→今天 05:00）近月 開→收 跌 ≥2%，或 S&P500 前一個美國交易日跌 ≥2%
# → 今天 08:45 開盤加 1 倍台指期，抱到下一個交易日 08:45 開盤出；5% 災難停損（研究 175，2026-11-26 使用者要求每個進場都有停損）、不分主策略狀態
# 2026-11-26 使用者同意由 0.5 倍提高到 1 倍（研究 170：組合內 1x 回檔不加深、約 1/7 凱利；1.5x 起回檔加深）
PANIC_TH, PANIC_ADD = 0.02, 1.0  # 基準倍數；實際依前一天波動 ×0.5／1／1.5（panic_size，2026-11-27 使用者選研究 444 C 版）
MORNING_SENT_FILE = os.path.join(DATA_DIR, "morning_sent.csv")


def tx_night(date: str):
    """期交所 TX 當天「盤後」列（＝前一天 15:00 開始的夜盤）中成交量最大的月份：(月份, 開, 收)；還沒公布回 None"""
    ymd = f"{date[:4]}/{date[4:6]}/{date[6:]}"
    body = urllib.parse.urlencode({"down_type": "1", "commodity_id": "TX", "commodity_id2": "",
                                   "queryStartDate": ymd, "queryEndDate": ymd}).encode()
    req = urllib.request.Request("https://www.taifex.com.tw/cht/3/futDataDown", data=body, headers=UA)
    with urlopen_retry(req) as res:
        txt = res.read().decode("big5", errors="replace")
    best = None
    for ln in txt.splitlines()[1:]:
        r = [x.strip() for x in ln.split(",")]
        if len(r) < 18 or r[1] != "TX" or "/" in r[2] or "W" in r[2] or r[17] != "盤後":
            continue
        try:
            o, c, v = float(r[3]), float(r[6]), float(r[9])
        except ValueError:
            continue
        if best is None or v > best[3]:
            best = (r[2], o, c, v)
    if best and (best[1] <= 0 or abs(best[2] / best[1] - 1) > 0.105):  # 研究 427：台指期漲跌幅上限 10%，超過＝資料錯誤
        print(f"夜盤 {best} 開收變動超過 10.5%，當作資料錯誤", file=sys.stderr)
        return None
    return best[:3] if best else None


def sp500_last(date: str):
    """S&P500 在台灣日期 date 之前最近一個美國交易日的漲跌：(美國日期 YYYYMMDD, 漲跌)；拿不到回 None"""
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?range=10d&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen_retry(req) as res:
        r = json.loads(res.read().decode("utf-8"))["chart"]["result"][0]
    ny = timezone(timedelta(hours=-5))
    rows = [(datetime.fromtimestamp(t, ny).strftime("%Y%m%d"), c)
            for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c]
    rows = [x for x in rows if x[0] < date]
    if len(rows) < 2:
        return None
    chg = rows[-1][1] / rows[-2][1] - 1
    if abs(chg) > 0.15:  # 研究 425／426：Yahoo 偶有壞值（TWD=X 出現過 1.80），S&P 單日 >15% 視為資料錯誤，不觸發
        print(f"S&P500 單日 {chg:+.1%} 異常（{rows[-2][1]} → {rows[-1][1]}），當作資料錯誤", file=sys.stderr)
        return None
    return rows[-1][0], chg


def vix_level(date: str):
    """前一天台指 VIX（近 3 日中位數：來源偶有單日錯價，2026-11-24 26.18、前後 55～58）；抓不到回 None
    資料來自公開倉庫 salmonmisosoup/leverage-dashboard 的 vixtwn.csv（研究 444）"""
    url = "https://raw.githubusercontent.com/salmonmisosoup/leverage-dashboard/HEAD/data/vixtwn.csv"
    with urlopen_retry(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})) as res:
        rows = [ln.split(",") for ln in res.read().decode("utf-8").splitlines()[1:] if ln.strip()]
    d0 = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    prev = [(d, float(v)) for d, v in rows if d < d0 and v]
    if not prev:
        return None
    last3 = sorted(x for _, x in prev[-3:])
    return prev[-1][0], last3[len(last3) // 2]


def rv20_level(date: str):
    """備援（研究 458）：加權前 20 日實現波動（年化），與 VIX 相關 0.85；23%／36% 對應 VIX 25／35"""
    p = [c for d, c in taiex_daily(date) if d < date][-21:]
    if len(p) < 21:
        return None
    rs = [math.log(b / a) for a, b in zip(p, p[1:])]
    mu = sum(rs) / len(rs)
    return (sum((x - mu) ** 2 for x in rs) / len(rs)) ** 0.5 * 252 ** 0.5


def panic_size(date: str):
    """P 倍數依前一天波動（研究 444～466；2026-11-27 使用者選 C 版，同日改 C2：平靜時在場 1 倍、空手不做）：
    VIX < 25 → 0.5 倍、25～35 → 1 倍、≥ 35 → 1.5 倍；VIX 抓不到改用加權 20 日實現波動 23%／36%；兩者都拿不到 → 1 倍
    回測（研究 465，主策略 1.7x＋P＋D＋V，2002～）：年化 35.2% → 37.2%、回檔 -28.5% 不變；bootstrap 贏現行 99%（研究 466）
    回傳 (倍數, 說明行)"""
    try:
        got = vix_level(date)
    except Exception as e:  # noqa: BLE001
        print(f"VIX 讀取失敗：{e}", file=sys.stderr)
        got = None
    if got:
        d, v = got
        lv = 0 if v < 25 else 2 if v >= 35 else 1
        src = f"台指 VIX（至 {d[5:7]}/{d[8:]}，近 3 日中位）{v:.1f}"
    else:
        try:
            rv = rv20_level(date)
        except Exception as e:  # noqa: BLE001
            print(f"實現波動計算失敗：{e}", file=sys.stderr)
            rv = None
        if rv is None:
            return PANIC_ADD, "📈 波動資料抓不到：照 1 倍"
        lv = 0 if rv < 0.23 else 2 if rv >= 0.36 else 1
        src = f"台指 VIX 抓不到，改看加權 20 日實現波動 {rv:.0%}"
    size = (0.5, 1.0, 1.5)[lv] * PANIC_ADD
    why = ("", "中等波動：照常 1 倍",
           "市場已在恐慌：這區歷史上 P 每筆約 +1.3%（研究 444、459）→ 做 1.5 倍")[lv]
    if lv == 0:  # C2（2026-11-27 使用者選，研究 494～496）：平靜時依主策略狀態，在場 1 倍、空手不做
        try:
            closes = [x for x in taiex_daily(date) if x[0] < date]
            main_on = strategy_state(closes, heat_series(load_margin_ratio()))[0]
        except Exception as e:  # noqa: BLE001
            print(f"主策略狀態判斷失敗：{e}", file=sys.stderr)
            main_on = None
        if main_on is None:
            size, why = 0.5 * PANIC_ADD, "市場原本平靜、主策略狀態判斷失敗 → 照 0.5 倍"
        elif main_on:
            size, why = 1.0 * PANIC_ADD, "市場原本平靜＋主策略在場：這格歷史 65 筆每筆 +0.31%、勝率 69%（研究 494～496）→ 做 1 倍"
        else:
            size, why = 0.0, "市場原本平靜＋主策略空手：這格歷史 53 筆每筆 -0.31%（研究 494～496）→ 這次不做"
    return size, f"📈 {src}｜{why}"


def holiday_panic_lines(date: str) -> list:
    """研究 428（觀察）：長假（台股休市 ≥4 個日曆天）後第一天，假期間 S&P 累積跌 ≥2% 但前一晚單日沒到 2%
    1998～ 13 次：D 開→D+1 開每筆約 +0.6%、勝率 69%（樣本少，未納入規則，只提醒）"""
    closes = taiex_daily(date)
    prev = [d for d, _ in closes if d < date]
    if not prev:
        return []
    p = datetime.strptime(prev[-1], "%Y%m%d")
    if (datetime.strptime(date, "%Y%m%d") - p).days < 4:
        return []
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?range=1mo&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen_retry(req) as res:
        r = json.loads(res.read().decode("utf-8"))["chart"]["result"][0]
    ny = timezone(timedelta(hours=-5))
    us = [(datetime.fromtimestamp(t, ny).strftime("%Y%m%d"), c) for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c]
    a = [c for d, c in us if d < prev[-1]]
    b = [c for d, c in us if d < date]
    if not a or not b:
        return []
    cum = b[-1] / a[-1] - 1
    if cum > -PANIC_TH or abs(cum) > 0.3:
        return []
    return [f"👀 觀察（研究 428，未納入規則）：長假後開紅盤，假期間 S&P500 累積 {cum:+.1%}（單日都沒跌到 {PANIC_TH:.0%}，恐慌做多沒觸發）",
            f"　1998～ 同樣情況 13 次：今天 08:45 進、明天 08:45 出 每筆約 +0.6%、勝率 69%；樣本少，要不要做自行決定（做的話 {PANIC_ADD / 2:g} 倍以內）"]


def morning_lines(date: str, retry: bool) -> list:
    """有觸發才回傳訊息行；排程時夜盤資料還沒出來會等（最多約 30 分鐘）"""
    night = wait_for(tx_night, date, retry)
    try:
        sp = sp500_last(date)
    except Exception as e:  # noqa: BLE001  美股抓不到不影響夜盤判斷
        print(f"S&P500 抓取失敗：{e}", file=sys.stderr)
        sp = None
    nr = night[2] / night[1] - 1 if night else None
    hit_n = nr is not None and nr <= -PANIC_TH
    hit_s = sp is not None and sp[1] <= -PANIC_TH
    print(f"夜盤 {night} {nr}；S&P {sp}")
    if not (hit_n or hit_s):
        try:
            return holiday_panic_lines(date)
        except Exception as e:  # noqa: BLE001
            print(f"長假累積判斷失敗：{e}", file=sys.stderr)
        return []
    lines = []
    if night:
        lines.append(f"{'🔻' if hit_n else '・'}夜盤（{night[0]}）：{night[1]:,.0f} → {night[2]:,.0f}（{nr:+.2%}，門檻 -{PANIC_TH:.0%}）")
    if sp:
        lines.append(f"{'🔻' if hit_s else '・'}S&P500（{sp[0][4:6]}/{sp[0][6:]}）：{sp[1]:+.2%}（門檻 -{PANIC_TH:.0%}）")
    # 研究 158：依觸發類型的歷史（2017-05～，D 開→D+1 開、扣 3 點）
    kind = ("雙觸發（夜盤＋S&P）", 21, "81%", "+1.06%", "+1.93%", "-2.60%") if hit_n and hit_s else \
        ("只有夜盤觸發", 16, "56%", "+0.94%", "+3.00%", "-1.70%") if hit_n else \
        ("只有 S&P 觸發（較弱，研究 158）", 61, "64%", "+0.20%", "+1.13%", "-1.46%")
    size, vline = panic_size(date)
    if size == 0:
        return lines + ["🙅 恐慌做多有觸發，但市場原本平靜＋主策略空手 → 這次不做（C2 版，研究 494～496）", vline]
    lots = f"每 100 萬資金約微台 {size * 1e6 / (night[2] * 10):.1f} 口；" if night else ""
    lines += [
        f"🎯 今天 08:45 開盤買台指期近月 {size:g} 倍名目（{lots}依前一天波動與主策略狀態 0～1.5 倍，研究 444～496），不管主策略在不在場，抱到下一個交易日 08:45 開盤平倉；停損 5%（災難停損：只防極端，研究 175 期望值 +0.52%→+0.51%、302 筆約 9 筆觸發；更緊的 2～3% 會變差）",
        vline,
        f"📊 這次是「{kind[0]}」：2017-05～ {kind[1]} 筆，勝率 {kind[2]}、期望值每筆 {kind[3]}、平均賺 {kind[4]}／平均賠 {kind[5]}",
        "📈 歷史（每筆扣 3 點成本）：",
        "・2017-05～2026（有夜盤，夜盤或 S&P 跌 ≥2%）99 筆：勝率 66%、期望值每筆 +0.49%（約 +104 點／口）、"
        "平均賺 +1.60%／平均賠 -1.64%、最差 -9.3%",
        "・1998～2017（無夜盤，S&P 跌 ≥2% 代理，樣本外）215 筆：勝率 60%、期望值每筆 +0.50%",
        "・疊在現行策略上（2018-06～，加 1 倍）：年化 60.6% → 70.4%、最大回檔 -25.6% → -26.8%；家族檢定 p 0.002（研究 145、170）",
        "⚠️ 好處集中在崩跌期，1 倍時單筆可能賠資金 5～9%、1.5 倍時約 8～14%（歷史最差 -9.3%、連 3 次最差 -12%；照 0.5／1／1.5 倍規則，2008-10 連續 6 次觸發 20 天內累計 -21.5%，研究 470）；照規則開盤進，不要盤中追價或再加碼",
        # 2026-11-26 使用者要求加入：2017-05～ 98 筆，進場後到隔天開盤前最大逆向（日盤低／當晚夜盤低 vs 進場價）
        "💰 保證金：期貨帳戶建議放名目的 20%（例：名目 100 萬 → 放約 20 萬），不要只放原始保證金（11/26 期交所大台 70.1 萬／名目約 763 萬＝約 9%）",
        # 研究 243：使用者選 85% 00631L＋15% 現金（研究 216 (a)），期貨帳戶約撐 1.5 倍名目
        "・主策略在場、且爆量收黑或外資期貨加碼還在持有時：這筆只加到總名目 1.5 倍為止（例：已持有 1 倍 → 這筆只加 0.5 倍；研究 243、468：只發生 2～4 次，年化幾乎不變）；期交所調高保證金時上限跟著降：上限 ≈ 期貨帳戶現金 ÷ 保證金比例（例：15% ÷ 12% ≈ 1.25 倍），恐慌期常見，以當天公告為準",
        "・歷史 98 筆進場後最大逆向：中位 -0.75%；≥3% 12%（只放保證金會被追繳）、≥7% 3%、最差 -10.2%（只放保證金可能在低點被砍倉）",
        "・放 20% 約可撐逆向 7% 不追繳（涵蓋 97%）；崩跌時期交所常調高保證金，以當天公告為準",
        # 研究 146（2026-11-26 使用者同意加入）
        "⏰ 錯過 08:45：可在今天 15:00 夜盤開盤補進（倍數同上，一樣抱到明天 08:45 出）；但若 15:00 價格已比今天 08:45 開盤低 ≥1% 就跳過；市場平靜（0.5 倍）時補進每筆約 +0.04%，可以不補（研究 490：中等 +0.38%、恐慌 +2.30%）",
        "・歷史：15:00 補進 97 筆 勝率 61%、每筆 +0.32%（08:45 進是 +0.51%）；比開盤低 ≥1% 時補進 14 筆 每筆 +0.00%，沒有優勢",
    ]
    return lines


def morning_sent() -> set:
    if not os.path.exists(MORNING_SENT_FILE):
        return set()
    return {ln.strip() for ln in open(MORNING_SENT_FILE, encoding="utf-8") if ln.strip()}


# ── 觀察指標：台指選擇權 Put/Call 未平倉比（研究 31、32，尚未納入策略）────────────
# 空手時，近 10 個交易日內 P/C 未平倉比曾達「過去 250 日的 95 分位以上」，且收盤比近 10 日最低收盤高 3% 以上，
# 回測（2002～2026）提早進場的效果最好：樣本外仍勝現行，安慰劑檢定 p≈0.05～0.10（邊緣顯著）。先放在日報觀察。
PC_PCT, PC_LOOKBACK, PC_REBOUND = 0.95, 10, 0.03


def pc_ratio_history(date: str, months: int = 13) -> list:
    """期交所台指選擇權 Put/Call 未平倉比（%）[(YYYYMMDD, 比率)]。歷史存在 data/pcratio.csv，只重抓當月（期交所一次只能查一個月）"""
    cache = {d: float(v[0]) for d, v in load_csv("pcratio.csv").items()}
    end = datetime.strptime(date, "%Y%m%d")
    for ym in months_to_fetch(date, cache, months):
        y, m = int(ym[:4]), int(ym[4:])
        month_end = datetime(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1)
        body = urllib.parse.urlencode({"queryStartDate": f"{y}/{m:02d}/01",
                                       "queryEndDate": min(end, month_end).strftime("%Y/%m/%d")}).encode()
        req = urllib.request.Request("https://www.taifex.com.tw/cht/3/pcRatioDown", data=body, headers=UA)
        with urlopen_retry(req) as res:
            text = res.read().decode("big5", errors="replace")
        for ln in text.strip().splitlines()[1:]:
            r = ln.split(",")
            if len(r) >= 7 and r[0].count("/") == 2:
                cache[r[0].replace("/", "")] = num(r[6])
        time.sleep(1)
    save_csv("pcratio.csv", "date,oi_ratio", {k: [f"{v:.2f}"] for k, v in cache.items()})
    start = (end - timedelta(days=31 * months)).strftime("%Y%m%d")
    return sorted((k, v) for k, v in cache.items() if start <= k <= date)


def pc_lines(date: str, state: bool, closes: list) -> list:
    hist = pc_ratio_history(date)
    if len(hist) < 160 or hist[-1][0] != date:
        return []
    vals = [v for _, v in hist]

    def pct(k):
        prev = vals[max(0, k - 250):k]
        return sum(1 for x in prev if x < vals[k]) / len(prev) if len(prev) >= 150 else None

    today = pct(len(vals) - 1)
    recent = [pct(k) for k in range(len(vals) - PC_LOOKBACK, len(vals))]
    hot = any(p is not None and p >= PC_PCT for p in recent)
    lines = ["", f"👀 觀察：台指選 P/C 未平倉比 {vals[-1]:.0f}%（過去一年第 {today * 100:.0f} 百分位）"]
    if state:
        return []
    lo = min(px for _, px in closes[-PC_LOOKBACK - 1:])
    px = closes[-1][1]
    if hot and px > lo * (1 + PC_REBOUND):
        lines.append(f"⚡ 提早進場條件成立（近 {PC_LOOKBACK} 日 P/C 曾達前 5%＋從低點 {lo:,.0f} 反彈 {px / lo - 1:.1%}）；"
                     f"僅供觀察，未納入策略（研究 32：停損 {lo:,.0f}）")
        return lines
    return []


def institutional(date: str):
    """回傳 {名稱: 買賣差額(元)}；非交易日或還沒公布回 None"""
    d = get_json(f"https://www.twse.com.tw/rwd/zh/fund/BFI82U?type=day&dayDate={date}&response=json")
    if d.get("stat") != "OK":
        return None
    rows = {}
    for t in tables_of(d):
        for r in t.get("data", []):
            rows[str(r[0]).strip()] = num(r[-1])
    if not rows:
        return None
    foreign = sum(v for k, v in rows.items() if k.startswith("外資"))
    dealer = sum(v for k, v in rows.items() if k.startswith("自營商"))
    trust = rows.get("投信", 0.0)
    total = rows.get("合計", foreign + dealer + trust)
    return {"外資": foreign, "投信": trust, "自營商": dealer, "合計": total}


def close_prices(date: str) -> dict:
    d = get_json(f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date}&type=ALLBUT0999&response=json")
    prices = {}
    for t in tables_of(d):
        f = t.get("fields", [])
        if "證券代號" in f and "收盤價" in f:
            ic, ip = f.index("證券代號"), f.index("收盤價")
            for r in t.get("data", []):
                p = num(r[ip])
                if p > 0:
                    prices[str(r[ic]).strip()] = p
    return prices


def margin_data(date: str):
    """回傳 {ratio 融資維持率%, amount 融資餘額(元), prev_amount 前日融資餘額(元)}；非交易日或資料不齊回 None"""
    d = get_json(f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date}&selectType=ALL&response=json")
    if d.get("stat") != "OK":
        return None
    total_amount = 0.0  # 融資今日餘額（仟元）
    prev_amount = 0.0   # 融資前日餘額（仟元）
    holdings = {}       # 代號 -> 融資今日餘額（張）
    for t in tables_of(d):
        f = [str(x) for x in t.get("fields", [])]
        rows = t.get("data", [])
        if f and f[0] == "項目":
            for r in rows:
                if "融資金額" in str(r[0]):
                    # 欄位：項目, 買進, 賣出, 現金償還, 前日餘額, 今日餘額
                    prev_amount, total_amount = num(r[4]), num(r[5])
        elif f and f[0] in ("代號", "股票代號"):
            # 欄位：代號, 名稱, 融資買進, 融資賣出, 現金償還, 前日餘額, 今日餘額, 限額, 融券…
            for r in rows:
                holdings[str(r[0]).strip()] = num(r[6])
    if total_amount <= 0 or not holdings:
        return None
    prices = close_prices(date)
    if not prices:
        return None
    value = sum(lots * 1000 * prices.get(code, 0.0) for code, lots in holdings.items())
    return {
        "ratio": value / (total_amount * 1000) * 100,
        "amount": total_amount * 1000,
        "prev_amount": prev_amount * 1000,
    }


def margin_ratio(date: str):
    m = margin_data(date)
    return m["ratio"] if m else None


def foreign_futures(date: str):
    """外資台指期（TXF）多空未平倉口數淨額 {net, prev}；資料來源期交所，非交易日回 None"""
    start = (datetime.strptime(date, "%Y%m%d") - timedelta(days=14)).strftime("%Y/%m/%d")
    end = f"{date[:4]}/{date[4:6]}/{date[6:]}"
    body = urllib.parse.urlencode({"queryStartDate": start, "queryEndDate": end, "commodityId": "TXF"}).encode()
    req = urllib.request.Request("https://www.taifex.com.tw/cht/3/futContractsDateDown", data=body, headers=UA)
    with urlopen_retry(req) as res:
        raw = res.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("big5", errors="replace")
    lines = [ln.split(",") for ln in text.strip().splitlines()]
    if not lines or "身份別" not in lines[0]:
        return None
    h = lines[0]
    idate, iwho, inet = h.index("日期"), h.index("身份別"), h.index("多空未平倉口數淨額")
    rows = [(r[idate].strip(), num(r[inet])) for r in lines[1:] if len(r) > inet and r[iwho].strip().startswith("外資")]
    rows.sort()
    if not rows or rows[-1][0] != end:
        return None
    prev = rows[-2][1] if len(rows) >= 2 else None
    return {"net": rows[-1][1], "prev": prev}


def prev_trading_ratio(date: str):
    day = datetime.strptime(date, "%Y%m%d")
    for _ in range(10):
        day -= timedelta(days=1)
        if day.weekday() >= 5:
            continue
        key = day.strftime("%Y%m%d")
        r = cached_maint(key)  # 前一天的維持率日報已經算過並存檔，不用再抓整個市場
        if r is None:
            r = margin_ratio(key)
        if r is not None:
            return r
    return None


def wait_for(fetch, date: str, retry: bool):
    """排程時資料可能晚幾分鐘公布：拿不到就等一下再試；手動指定日期時不等"""
    for i in range(RETRY_TIMES if retry else 1):
        v = fetch(date)
        if v is not None:
            return v
        if retry and i < RETRY_TIMES - 1:
            print(f"{fetch.__name__} 還沒有資料，{RETRY_WAIT_SEC // 60} 分鐘後再試")
            time.sleep(RETRY_WAIT_SEC)
    return None


def yi(v: float) -> str:
    return f"{v / 1e8:+,.1f} 億"


def word(v: float) -> str:
    return "買超" if v > 0 else "賣超" if v < 0 else "持平"


SENT_FILE = os.path.join(DATA_DIR, "sent_dates.csv")


def sent_dates() -> set:
    """已經送過日報的日期（YYYYMMDD）。主排程和備援排程都會跑，靠這份避免重送"""
    try:
        return {ln.strip() for ln in open(SENT_FILE, encoding="utf-8") if ln.strip()}
    except FileNotFoundError:
        return set()


def mark_sent(date: str):
    if date not in sent_dates():
        with open(SENT_FILE, "a", encoding="utf-8") as f:
            f.write(date + "\n")


def close_lines(date: str, retry: bool):
    idx = wait_for(taiex, date, retry)
    if idx is None:
        return None
    inst = wait_for(institutional, date, retry)
    arrow = "🔺" if idx["change"] > 0 else "🔻" if idx["change"] < 0 else "➖"
    trend = "上漲" if idx["change"] > 0 else "下跌" if idx["change"] < 0 else "平盤"
    lines = [f"加權指數：{idx['close']:,.2f}　{arrow}{trend} {abs(idx['change']):,.2f} 點（{idx['pct']:+.2f}%）"]
    try:  # 2026-11-27 使用者：主策略看日線，日報改列日線進出場線（原本的小時 K 均線容易誤會，移除）
        ma = daily_ma_line(date)
    except Exception as e:  # 均線抓不到不影響其他資訊
        print(f"日線均線失敗：{e}", file=sys.stderr)
        ma = None
    if ma:
        lines.append(ma)
    vol = turnover(date)
    if vol is not None:
        diff = f"，比前一交易日 {yi(vol['today'] - vol['prev'])}" if vol["prev"] > 0 else ""
        lines.append(f"成交量：{vol['today'] / 1e8:,.0f} 億{diff}")
    if inst is None:
        lines.append("三大法人：資料還沒公布")
    else:
        lines += [
            f"三大法人：合計{word(inst['合計'])} {yi(inst['合計'])}",
            f"・外資 {yi(inst['外資'])}　・投信 {yi(inst['投信'])}　・自營商 {yi(inst['自營商'])}",
        ]
    return lines


def oi_text(v: float) -> str:
    return f"{'空單' if v < 0 else '多單'} {abs(v):,.0f} 口"


def margin_lines(date: str, retry: bool):
    lines = []
    m = wait_for(margin_data, date, retry)
    if m is not None:
        _TODAY_MARGIN.update(date=date, amount=m["amount"], ratio=m["ratio"])
    if m is None:
        lines.append("大盤融資維持率：資料還沒公布")
    else:
        prev = prev_trading_ratio(date)
        tail = f"（前一交易日 {prev:.1f}%，{m['ratio'] - prev:+.1f}）" if prev is not None else ""
        lines.append(f"大盤融資維持率：{m['ratio']:.1f}%{tail}")
        delta = m["amount"] - m["prev_amount"]
        trend = "增加" if delta > 0 else "減少" if delta < 0 else "持平"
        lines.append(f"融資餘額：{m['amount'] / 1e8:,.0f} 億（{trend} {abs(delta) / 1e8:,.1f} 億）")

    fut = foreign_futures(date)
    if fut is None:
        lines.append("外資台指期淨未平倉：資料還沒公布")
    else:
        line = f"外資台指期淨未平倉：{oi_text(fut['net'])}"
        if fut["prev"] is not None:
            diff = fut["net"] - fut["prev"]
            if diff == 0:
                line += "（與前一交易日相同）"
            elif (fut["net"] < 0) != (fut["prev"] < 0):
                line += f"（前一交易日 {oi_text(fut['prev'])}，多空翻轉）"
            else:
                side = "空單" if fut["net"] < 0 else "多單"
                # 淨空單時數字變小（更負）＝空單增加；淨多單時數字變大＝多單增加
                grew = (diff < 0) if fut["net"] < 0 else (diff > 0)
                line += f"（{side}{'增加' if grew else '減少'} {abs(diff):,.0f} 口）"
        lines.append(line)
    return lines


def run_morning(date, scheduled, retry, now):
    """早上提醒（候選 6）：沒觸發就不送；備援排程重跑不重送"""
    mdate = date or now.strftime("%Y%m%d")
    if datetime.strptime(mdate, "%Y%m%d").weekday() >= 5:
        print(f"{mdate} 是週末，不送")
        return
    if not is_trading_day(datetime.strptime(mdate, "%Y%m%d").date()):  # 研究 271：休市日（如 12/25）不送「今天 08:45 買」
        print(f"{mdate} 證交所休市，不送（S&P 若大跌，下一個交易日早上會再判斷）")
        return
    if scheduled and (mdate in morning_sent() or now.hour >= 13):
        print(f"{mdate} 早上提醒已送過或已過 13:00（排程延遲太久），不送")
        return
    lines = morning_lines(mdate, retry)
    if not lines:
        print(f"{mdate} 夜盤與 S&P 都沒跌 ≥{PANIC_TH:.0%}（或夜盤資料還沒出來／今天沒開盤），不送")
        return
    late = ("（⏰ 排程延遲，已過 08:45 開盤：照下面「錯過 08:45」的方式 15:00 夜盤補進）"
            if scheduled and now.hour * 60 + now.minute > 8 * 60 + 45 else "")
    title = ("早上觀察：長假後美股累積下跌（研究 428，非正式訊號）" if lines and lines[0].startswith("👀")
             else "早上提醒：恐慌隔天做多（候選 6）")
    text = "\n".join([f"🌅 {int(mdate[4:6])}/{int(mdate[6:])} {title}{late}"] + lines)
    print(text)
    send(text)
    if scheduled:
        with open(MORNING_SENT_FILE, "a", encoding="utf-8") as f:
            f.write(mdate + "\n")



def main():
    part = os.environ.get("REPORT_PART") or "all"
    date = os.environ.get("REPORT_DATE") or ""
    scheduled = retry = not date
    late = ""
    now = datetime.now(TW)
    print(f"REPORT_PART={part} EVENT_SCHEDULE={os.environ.get('EVENT_SCHEDULE', '')} 台灣 {now:%m/%d %H:%M}")
    # 早上的排程有時被判成 all（11/26 三次早上排程都是 all）：台灣 07:00～12:59 的排程 all 也順便檢查早上提醒（已送過不重送）
    if part == "morning" or (part == "all" and scheduled and os.environ.get("EVENT_SCHEDULE") and 7 <= now.hour < 13):
        run_morning(date, scheduled, retry, now)
        if part == "morning":
            return

    if scheduled and part != "alert" and now.hour < 14:
        # GitHub 排程曾延遲近 10 小時（11/24 21:30 的排程 11/25 07:11 才跑）：中午前才跑到的改送前一個平日，資料早就有了不用等
        d = now - timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        date, retry, late = d.strftime("%Y%m%d"), False, "（排程延遲補發）"
    date = date or now.strftime("%Y%m%d")
    if scheduled and part != "alert" and date in sent_dates():
        print(f"{date} 已經送過，不重送")
        return
    if datetime.strptime(date, "%Y%m%d").weekday() >= 5:
        print(f"{date} 是週末，不送")
        return
    md = f"{int(date[4:6])}/{int(date[6:])}"

    if part == "alert":  # 收盤後提醒：沒觸發就不送；15:10 備援排程（研究 253），已送過不重送（data/alert_sent.csv）
        sent_file = os.path.join(DATA_DIR, "alert_sent.csv")
        if scheduled and os.path.exists(sent_file) and date in open(sent_file, encoding="utf-8").read().split():
            print(f"{date} 收盤後提醒已送過，不重送")
            return
        lines = alert_lines(date, retry)
        try:  # 研究 247：台美背離加碼（D）14:40 就能判斷（加權收盤＋前一晚 S&P），讓使用者可選 15:00 夜盤進（研究 220：與隔天開盤差不多）
            dl = [x for x in divergence_lines(date, taiex_daily(date)) if x]
            if dl and dl[0].startswith("🎯"):
                dl[0] = dl[0].replace("→ 明早 08:45 開盤加", "→ 今天 15:00 夜盤或明早 08:45 開盤加")
                lines = (lines + [""] if lines else []) + dl
        except Exception as e:  # noqa: BLE001
            print(f"台美背離提醒失敗：{e}", file=sys.stderr)
        if lines:
            text = "\n".join([f"🚨 {md} 收盤後提醒（有訊號觸發）"] + lines)
            print(text)
            send(text)
            if scheduled:
                with open(sent_file, "a", encoding="utf-8") as f:
                    f.write(date + "\n")
        else:
            print(f"{date} 沒有爆量收黑／台美背離觸發，不送")
        return

    # 先確認這天有開盤（國定假日證交所回非 OK）：只等「下午」那段，晚上那段收盤資料一定早就有了
    if part in ("close", "all"):
        body = close_lines(date, retry)
        if body is None:
            print(f"{date} 不是交易日或資料還沒公布，不送")
            return
    else:
        if taiex(date) is None:
            print(f"{date} 不是交易日，不送")
            return
        body = []

    title = {"close": "台股收盤", "margin": "台股融資", "all": "台股日報"}[part]
    if part in ("margin", "all"):
        body += margin_lines(date, retry)
    if part in ("close", "all"):
        try:
            body += strategy_lines(date)
        except Exception as e:  # 策略算不出來不影響其他資訊
            print(f"策略失敗：{e}", file=sys.stderr)
        try:  # 52 週高點選股（研究 301～303，使用者 2026-11-27 要求每月附清單）：每天補抓個股收盤，月初出清單
            body += nh_report_lines(date)
        except Exception as e:  # noqa: BLE001
            print(f"52 週高點選股失敗：{e}", file=sys.stderr)
        try:  # 今天早上若有恐慌隔天做多（候選 6）部位，提醒明早開盤平倉
            if morning_lines(date, False):
                body.append(f"🔔 恐慌隔天做多：今天 08:45 若有進台指期，明早 08:45 開盤平倉（倍數依早上提醒：前一天波動 0.5／1／1.5 倍；研究 143：抱到隔天開盤）")
        except Exception as e:  # noqa: BLE001
            print(f"恐慌部位檢查失敗：{e}", file=sys.stderr)
    # 有要操作的訊號就放到最上面並附期限，免得被長報告淹沒
    acts = [ln.strip() for ln in body if ln.strip().startswith(("🔔", "🎯", "⚠️", "📌"))]
    if part in ("close", "all") and not acts:
        body.append("✅ 今天沒有規則觸發：維持現有部位，不用動作")
    head = [f"📊 {md} {title}{late}"]
    if acts:
        main_ = any(a.startswith("⚠️") for a in acts)
        fut_ = any(a.startswith(("🔔", "🎯")) for a in acts)
        when = "⏰ 期限：" + "；".join(
            ([("主策略（00631L）今天收盤前下單" if late else "主策略（00631L）明天收盤前下單")] if main_ else [])
            + ([("台指期今天 8:45 開盤（補發時已過開盤就用市價）" if late else "台指期明早 8:45 開盤")] if fut_ else [])
            + (["台美背離加碼明天 13:45 收盤前平倉"] if any(a.startswith("📌") for a in acts) else []))
        head += ["", f"🚨 {md} 有訊號觸發："] + [f"・{a}" for a in acts] + [when]
        if fut_ and any(ln.startswith("🧭 主策略應持有：85%") for ln in body):
            # 研究 243／434／435：主策略在場時期貨帳戶只有 15% 現金，所有台指期加碼合計名目上限約 1.5 倍
            head.append("💰 主策略在場：所有台指期加碼（含持有中的）合計不超過 1.5 倍名目（15% 現金的保證金上限）；超過時先不加獨立短線、再縮恐慌做多")
    note = holiday_note(date)  # 研究 272：明天休市時說明「明天／明早」指哪一天
    if note:
        head.insert(1, note)
    text = "\n".join(head + body)
    print(text)
    send(text)
    if part == "all":
        mark_sent(date)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # 失敗也通知，免得默默沒收到
        print(f"失敗：{e}", file=sys.stderr)
        if os.environ.get("TG_BOT_TOKEN") and os.environ.get("TG_CHAT_ID"):
            send(f"⚠️ 台股日報抓資料失敗：{e}")
        sys.exit(1)
