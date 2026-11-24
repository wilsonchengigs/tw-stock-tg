"""
每個交易日 21:30 傳台股日報到 Telegram（資料來源：臺灣證券交易所公開資料）

- 下午（REPORT_PART=close）：加權指數漲跌、小時K MA20／60／240（資料存在 data/taiex_hourly.csv）、成交量（成交金額）、三大法人買賣超（證交所約 15:00 公布）
- 晚上（REPORT_PART=margin）：大盤（上市）融資維持率、融資餘額增減（約 21:00 公布）、外資台指期淨未平倉（期交所）
- REPORT_PART=all（預設，排程用這個）：兩段一起
- 策略段落後附「觀察」：台指選擇權 Put/Call 未平倉比與研究 32 的提早進場條件（期交所，僅供觀察、未納入策略）
- 加快速度：過去的資料存在 data/（taiex_daily、pcratio、margin_ratio、taiex_hourly），每次只抓當天／當月，
  GitHub Actions 跑完把 data/*.csv commit 回來

融資維持率 = Σ(個股融資餘額張數 × 1000 × 收盤價) ÷ 融資餘額總金額（證交所不直接公布，一般網站也是這樣估算）

環境變數：TG_BOT_TOKEN、TG_CHAT_ID；REPORT_PART；REPORT_DATE（選填，YYYYMMDD，測試用）
只用 Python 標準函式庫。
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

TW = timezone(timedelta(hours=8))
UA = {"User-Agent": "Mozilla/5.0 (tw-stock-tg report)"}
# 資料還沒公布時每 5 分鐘再試一次，最多等 30 分鐘
RETRY_TIMES = 6
RETRY_WAIT_SEC = 300


_JSON_MEMO = {}  # 同一次執行裡同一個網址只抓一次（例如當月 FMTQIK 成交量與指數都要用）
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def get_json(url: str) -> dict:
    if url in _JSON_MEMO:
        return _JSON_MEMO[url]
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode("utf-8"))
    time.sleep(2)  # 證交所對短時間大量請求會擋，間隔一下
    if data.get("stat") == "OK":
        _JSON_MEMO[url] = data
    return data


def load_csv(name: str) -> dict:
    """data/{name}：第一欄日期 YYYYMMDD → 其餘欄位（字串）"""
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        lines = [ln.strip().split(",") for ln in f.readlines()[1:] if ln.strip()]
    return {r[0]: r[1:] for r in lines}


def save_csv(name: str, header: str, rows: dict):
    with open(os.path.join(DATA_DIR, name), "w", encoding="utf-8", newline="") as f:
        f.write(header + "\n")
        for d in sorted(rows):
            f.write(",".join([d] + [str(x) for x in rows[d]]) + "\n")


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


def num(s) -> float:
    s = str(s).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def tables_of(data: dict) -> list:
    """新版回傳 tables:[{fields,data}]；舊版是 fields/data 或 fields1/data1…，統一成 list"""
    if isinstance(data.get("tables"), list):
        return data["tables"]
    out = []
    if "fields" in data:
        out.append({"fields": data["fields"], "data": data.get("data", [])})
    for i in range(1, 20):
        if f"fields{i}" in data:
            out.append({"fields": data[f"fields{i}"], "data": data.get(f"data{i}", [])})
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
STRATEGY_ON = "100% 00631L（台灣50正2）"
STRATEGY_OFF = "100% 現金（或定存）"
# 融資過熱濾網（2026-11-24 加入，研究 38／38b／40）：上市融資金額 ÷ 加權指數 高於近 250 個交易日平均 17.5% 以上
# → 週五判斷時出場且不進場。回測 2002～2026：全期 23.2%／-36.8%（無濾網 20.2%／-43.6%），前段、後段、真實價格都較好；
# 鄰近參數 14／18 組顯著、安慰劑 p≈0.01。歷史資料存在 data/margin_ratio.csv（每天抓到融資餘額就追加一列）
HEAT_N, HEAT_TH = 250, 0.175
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
    """{YYYYMMDD: 融資/指數 比值 相對近 HEAT_N 日平均的偏離}"""
    ratio = [a / t for _, a, t in rows]
    out = {}
    for i in range(HEAT_N - 1, len(rows)):
        avg = sum(ratio[i + 1 - HEAT_N:i + 1]) / HEAT_N
        out[rows[i][0]] = ratio[i] / avg - 1
    return out


def heat_on(heat: dict, d: str):
    """d 當天（沒有就用之前最近一天）的偏離；完全沒資料回 None"""
    keys = [k for k in heat if k <= d]
    return heat[max(keys)] if keys else None


def strategy_state(closes: list, heat: dict = None):
    """依每週最後一個交易日的收盤跑一遍，回傳 (目前狀態, 上次切換日, 今天的出場均線, 今天的進場均線)
    heat：融資過熱偏離（heat_series）；過熱時出場且不進場"""
    state, switched = False, None
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
        if not last_of_week:
            continue
        if i == len(closes) - 1 and datetime.strptime(d, "%Y%m%d").weekday() != 4:
            continue  # 今天不是週五：這週還沒結束，不判斷
        dev = heat_on(heat, d) if heat else None
        hot = dev is not None and dev > HEAT_TH
        if not state and px > ma_n * (1 + STRATEGY_ENTRY_BAND) and not hot:
            state, switched = True, d
        elif state and (px < ma_x * (1 - STRATEGY_EXIT_BAND) or hot):
            state, switched = False, d
    return state, switched, ma_x, ma_n


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
    is_friday = datetime.strptime(date, "%Y%m%d").weekday() == 4
    lines = ["", f"🧭 策略（進場 MA{STRATEGY_ENTRY_MA}+{STRATEGY_ENTRY_BAND * 100:g}%、出場 MA{STRATEGY_EXIT_MA}-{STRATEGY_EXIT_BAND * 100:g}%，每週五收盤判斷）"]
    lines.append(f"指數 {px:,.0f}｜進場線 {up:,.0f}（MA{STRATEGY_ENTRY_MA} {ma_n:,.0f}）｜出場線 {dn:,.0f}（MA{STRATEGY_EXIT_MA} {ma_x:,.0f}）")
    hold = STRATEGY_ON if state else STRATEGY_OFF
    since = f"（{int(switched[4:6])}/{int(switched[6:])} 起）" if switched else ""
    dev = heat_on(heat, date)
    if dev is not None:
        last = max(k for k in heat if k <= date)
        stale = "" if last == date else f"（用 {int(last[4:6])}/{int(last[6:])} 的融資資料）"
        status = "🔥 過熱：出場、不進場" if dev > HEAT_TH else "正常"
        lines.append(f"融資過熱濾網：融資÷指數 比 {HEAT_N} 日平均 {dev:+.1%}（門檻 +{HEAT_TH:.1%}）→ {status}{stale}")
    lines.append(f"應持有：{hold}{since}")
    if is_friday and switched == date:
        action = f"買進 → {STRATEGY_ON}" if state else f"全部賣出 → {STRATEGY_OFF}"
        lines.append(f"⚠️ 本週訊號切換：下一個交易日收盤 {action}")
    elif is_friday:
        lines.append("本週判斷：不用動作")
    else:
        need = up if not state else dn
        word_ = "站上" if not state else "跌破"
        lines.append(f"週五收盤{word_} {need:,.0f} 才切換（目前距離 {(need / px - 1):+.1%}）")
    try:
        lines += pc_lines(date, state, closes)
    except Exception as e:  # 觀察指標抓不到不影響策略段落
        print(f"P/C 失敗：{e}", file=sys.stderr)
    return lines


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
        with urllib.request.urlopen(req, timeout=30) as res:
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
        return lines
    lo = min(px for _, px in closes[-PC_LOOKBACK - 1:])
    px = closes[-1][1]
    if hot and px > lo * (1 + PC_REBOUND):
        lines.append(f"⚡ 提早進場條件成立（近 {PC_LOOKBACK} 日 P/C 曾達前 5%＋從低點 {lo:,.0f} 反彈 {px / lo - 1:.1%}）；"
                     f"僅供觀察，未納入策略（研究 32：停損 {lo:,.0f}）")
    elif hot:
        lines.append(f"P/C 近 {PC_LOOKBACK} 日曾達前 5%，等指數從低點 {lo:,.0f} 反彈 {PC_REBOUND:.0%}（{lo * (1 + PC_REBOUND):,.0f}）才算成立")
    else:
        lines.append(f"提早進場條件：P/C 達過去一年前 5%（目前未達）＋指數從近 {PC_LOOKBACK} 日低點反彈 {PC_REBOUND:.0%}")
    return lines


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
    with urllib.request.urlopen(req, timeout=30) as res:
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


def send(text: str):
    token, chat = os.environ["TG_BOT_TOKEN"], os.environ["TG_CHAT_ID"]
    body = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body)
    with urllib.request.urlopen(req, timeout=30) as res:
        res.read()


def close_lines(date: str, retry: bool):
    idx = wait_for(taiex, date, retry)
    if idx is None:
        return None
    inst = wait_for(institutional, date, retry)
    arrow = "🔺" if idx["change"] > 0 else "🔻" if idx["change"] < 0 else "➖"
    trend = "上漲" if idx["change"] > 0 else "下跌" if idx["change"] < 0 else "平盤"
    lines = [f"加權指數：{idx['close']:,.2f}　{arrow}{trend} {abs(idx['change']):,.2f} 點（{idx['pct']:+.2f}%）"]
    try:
        ma = hourly_ma_line(date)
    except Exception as e:  # 均線抓不到不影響其他資訊
        print(f"小時K 均線失敗：{e}", file=sys.stderr)
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


def main():
    part = os.environ.get("REPORT_PART") or "all"
    date = os.environ.get("REPORT_DATE") or ""
    retry = not date
    date = date or datetime.now(TW).strftime("%Y%m%d")
    if datetime.strptime(date, "%Y%m%d").weekday() >= 5:
        print(f"{date} 是週末，不送")
        return
    md = f"{int(date[4:6])}/{int(date[6:])}"

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
    text = "\n".join([f"📊 {md} {title}"] + body)
    print(text)
    send(text)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # 失敗也通知，免得默默沒收到
        print(f"失敗：{e}", file=sys.stderr)
        if os.environ.get("TG_BOT_TOKEN") and os.environ.get("TG_CHAT_ID"):
            send(f"⚠️ 台股日報抓資料失敗：{e}")
        sys.exit(1)
