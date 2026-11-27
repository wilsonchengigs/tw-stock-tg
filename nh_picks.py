"""52 週高點選股清單（研究 301～303；2026-11-27 使用者要求每月附在日報）

規則（同研究 302～307 回測）：每月第一個交易日收盤，上市 4 碼普通股（不含 00 開頭 ETF、不含創新板）、
收盤 ≥10 元、當天成交金額 ≥1,000 萬（研究 307）、有 250 個交易日以上歷史、12 個月前的月初有報價、近 12 個月（含本月）沒有還原後單日 >±11% 的跳動；
依「還原除權息收盤 ÷ 過去 250 個交易日最高還原收盤」由大到小，取前 10%（約 80～90 檔）等權，抱到下個月第一個交易日換股。
回測 2014～2026-10（含息、扣成本、無前視、≥1,000 萬，研究 307）：前 30 檔 +23.5%／-25.3%／Sharpe 1.16；前 10% +21.9%／-17.9%／1.22。

資料：
- `backtest/stock_closes/YYYY.csv.gz`：每日收盤（日報每天補抓缺的日子，一天一次證交所 MI_INDEX 請求）
- `backtest/exright.csv`：除權息表（月初選股日更新當年度，一次 TWT49U 請求）
- `data/nh_list.csv`：每月清單（date,rank,code,name,ratio），用來算新增／剔除
"""
import csv
import gzip
import io
import json
import os
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
SC = os.path.join(ROOT, "backtest", "stock_closes")
EXR = os.path.join(ROOT, "backtest", "exright.csv")
LIST = os.path.join(ROOT, "data", "nh_list.csv")
NAMES = os.path.join(SC, "_names.json")
UA = {"User-Agent": "Mozilla/5.0"}
TOP_Q, LOOK, MIN_PX, JUMP, MIN_AMT = 0.10, 250, 10.0, 0.11, 1e7  # 研究 307：選股日成交金額 ≥1,000 萬


def _get(url):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                js = json.loads(r.read().decode("utf-8"))
            time.sleep(2)
            return js
        except Exception as e:  # noqa: BLE001
            print(f"nh_picks 請求失敗（{k + 1}）：{e}", file=sys.stderr)
            time.sleep(10)
    raise RuntimeError(f"抓不到 {url}")


def _read_year(y):
    path = os.path.join(SC, f"{y}.csv.gz")
    if not os.path.exists(path):
        return []
    return list(csv.reader(io.TextIOWrapper(gzip.open(path), encoding="utf-8")))[1:]


def _write_year(y, rows):
    with gzip.open(os.path.join(SC, f"{y}.csv.gz"), "wt", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "code", "close", "sign"])
        w.writerows(sorted(rows))


def update_closes(trading_days):
    """trading_days：要確保有資料的交易日（YYYY-MM-DD，由日報依證交所休市日曆給）；缺的才抓"""
    done_path = os.path.join(SC, "_done.txt")
    done = set(open(done_path, encoding="utf-8").read().split()) if os.path.exists(done_path) else set()
    miss = [d for d in trading_days if d not in done]
    names = json.load(open(NAMES, encoding="utf-8")) if os.path.exists(NAMES) else {}
    if not names and trading_days and trading_days[-1] not in miss:
        miss.append(trading_days[-1])  # 第一次沒有股名檔：重抓最近一天取股名
    by_year = defaultdict(list)
    for d in miss:
        js = _get(f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={d.replace('-', '')}&type=ALLBUT0999&response=json")
        if js.get("stat") != "OK":
            continue
        got = 0
        for t in js.get("tables", []):
            fl = t.get("fields") or []
            if "證券代號" in fl and "收盤價" in fl:
                ic, inm, ip, isg = fl.index("證券代號"), fl.index("證券名稱"), fl.index("收盤價"), fl.index("漲跌(+/-)")
                for r in t.get("data", []):
                    code = str(r[ic]).strip()
                    if not code.isdigit() or not 4 <= len(code) <= 6:
                        continue
                    try:
                        px = float(str(r[ip]).replace(",", ""))
                    except ValueError:
                        continue
                    sg = "+" if "+" in str(r[isg]) else "-" if "-" in str(r[isg]) else ""
                    by_year[d[:4]].append([d, code, f"{px:g}", sg])
                    names[code] = str(r[inm]).strip()
                    got += 1
        if got:
            done.add(d)
    for y, rows in by_year.items():
        allr = {(r[0], r[1]): r for r in _read_year(y)}
        for r in rows:
            allr[(r[0], r[1])] = r
        _write_year(y, list(allr.values()))
    if miss:
        with open(done_path, "w", encoding="utf-8") as f:
            f.write("".join(x + "\n" for x in sorted(done, reverse=True)))
        json.dump(names, open(NAMES, "w", encoding="utf-8"), ensure_ascii=False)
    return len(miss)


def roc_to_iso(s):
    y, rest = s.split("年")
    m, rest = rest.split("月")
    return f"{int(y) + 1911}-{int(m):02d}-{int(rest.replace('日', '')):02d}"


def update_exright(year):
    js = _get(f"https://www.twse.com.tw/rwd/zh/exRight/TWT49U?startDate={year}0101&endDate={year}1231&response=json")
    new = []
    for r in js.get("data", []):
        try:
            new.append([roc_to_iso(r[0]), r[1].strip(), float(r[3].replace(",", "")), float(r[4].replace(",", "")), r[6]])
        except (ValueError, IndexError):
            continue
    old = list(csv.reader(open(EXR, encoding="utf-8")))[1:] if os.path.exists(EXR) else []
    allr = {(r[0], r[1]): r for r in old}
    for r in new:
        allr[(r[0], r[1])] = [r[0], r[1], f"{r[2]:g}", f"{r[3]:g}", r[4]]
    with open(EXR, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "code", "pre_close", "ref", "kind"])
        w.writerows(sorted(allr.values()))


def amounts(date_iso):
    """選股日的成交金額（元）與股名；一次 MI_INDEX 請求"""
    js = _get(f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date_iso.replace('-', '')}&type=ALLBUT0999&response=json")
    amt, nm = {}, {}
    for t in js.get("tables", []):
        fl = t.get("fields") or []
        if "證券代號" in fl and "成交金額" in fl:
            ic, ia, inm = fl.index("證券代號"), fl.index("成交金額"), fl.index("證券名稱")
            for r in t.get("data", []):
                c = str(r[ic]).strip()
                nm[c] = str(r[inm]).strip()
                try:
                    amt[c] = float(str(r[ia]).replace(",", ""))
                except ValueError:
                    pass
    return amt, nm


def pick(date_iso, amt=None, nm=None):
    """date_iso＝當月第一個交易日；回傳 [(code, ratio)] 由大到小（前 TOP_Q）與候選數"""
    y = int(date_iso[:4])
    rows = _read_year(y - 2) + _read_year(y - 1) + _read_year(y)
    px = defaultdict(dict)
    for d, c, p, _ in rows:
        if d <= date_iso and len(c) == 4 and not c.startswith("00"):
            px[c][d] = float(p)
    ex = {}
    for r in csv.DictReader(open(EXR, encoding="utf-8")):
        ex[(r["code"], r["date"])] = float(r["ref"])
    dates = sorted({d for m in px.values() for d in m})
    firsts = [d for a, d in zip([""] + dates, dates) if d[:7] != a[:7]]  # 每月第一個交易日
    if date_iso not in firsts:
        raise ValueError(f"{date_iso} 不是資料裡的月初交易日")
    k = firsts.index(date_iso)
    if k < 12:
        raise ValueError("歷史不足 12 個月")
    m12, months = firsts[k - 12], {f[:7] for f in firsts[k - 11:k + 1]}
    cand = []
    for c, m in px.items():
        if date_iso not in m or m12 not in m or m[date_iso] < MIN_PX:
            continue
        if amt is not None and amt.get(c, 0.0) < MIN_AMT:
            continue  # 研究 307：流動性門檻
        if nm is not None and "-創" in nm.get(c, ""):
            continue  # 創新板：一般投資人須具資格
        ds = sorted(m)
        if len(ds) <= LOOK:
            continue
        lv, adj, bad = m[ds[0]], [m[ds[0]]], False
        for a, b in zip(ds, ds[1:]):
            base = ex.get((c, b)) or m[a]
            r = m[b] / base - 1
            if b[:7] in months and abs(r) > JUMP:
                bad = True
                break
            lv *= 1 + r
            adj.append(lv)
        if bad:
            continue
        ratio = adj[-1] / max(adj[-LOOK - 1:])
        cand.append((c, ratio))
    cand.sort(key=lambda x: -x[1])
    return cand[:int(len(cand) * TOP_Q)], len(cand)


def save_list(date_iso, top, names):
    old = list(csv.reader(open(LIST, encoding="utf-8")))[1:] if os.path.exists(LIST) else []
    old = [r for r in old if r[0] != date_iso]
    new = [[date_iso, str(i + 1), c, names.get(c, ""), f"{r:.4f}"] for i, (c, r) in enumerate(top)]
    with open(LIST, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "rank", "code", "name", "ratio"])
        w.writerows(old + new)
    prev_dates = sorted({r[0] for r in old if r[0] < date_iso})
    prev = {r[2] for r in old if prev_dates and r[0] == prev_dates[-1]}
    return prev_dates[-1] if prev_dates else None, prev


def lines(date_iso, trading_days):
    """日報段落（每月第一個交易日）；trading_days＝近 ~40 個交易日，用來補抓缺的收盤"""
    update_closes(trading_days)
    update_exright(int(date_iso[:4]))
    amt, nm = amounts(date_iso)
    top, n = pick(date_iso, amt, nm)
    names = json.load(open(NAMES, encoding="utf-8")) if os.path.exists(NAMES) else {}
    names.update(nm)
    pdate, prev = save_list(date_iso, top, names)
    cur = {c for c, _ in top}
    nm = lambda c: f"{names.get(c, '')}{c}"  # noqa: E731
    out = ["", f"🗂️ 52 週高點選股（每月第一個交易日換股，研究 301～307；參考清單、不在主策略內）：候選 {n} 檔取前 10% 共 {len(top)} 檔，等權持有到下個月第一個交易日",
           "　篩選：收盤 ≥10 元、選股日成交金額 ≥1,000 萬、不含創新板（研究 307）",
           "　回測 2014～2026-10 含息扣成本（研究 307，同樣篩選）：前 30 檔年化 +23.5%、最大回檔 -25.3%；前 10% +21.9%／-17.9%（0050 +20.7%／-29.2%）｜每月換（研究 304）｜勝過隨機選股（研究 306）｜單一時期、回測可能偏樂觀",
           "　精簡版前 30 檔：" + "、".join(f"{names.get(c, '')}{c}" for c, _ in top[:30])]
    if prev:
        add = [c for c, _ in top if c not in prev]
        drop = sorted(prev - cur)
        out.append(f"　vs {int(pdate[5:7])}/{int(pdate[8:])}：新增 {len(add)} 檔、剔除 {len(drop)} 檔")
        if add:
            out.append("　＋ " + "、".join(nm(c) for c in add))
        if drop:
            out.append("　－ " + "、".join(nm(c) for c in drop))
        out.append("　續抱 " + "、".join(nm(c) for c, _ in top if c in prev))
    else:
        out.append("　清單（依接近高點排序）：" + "、".join(nm(c) for c, _ in top))
    return out


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    top, n = pick(d)
    names = json.load(open(NAMES, encoding="utf-8")) if os.path.exists(NAMES) else {}
    print(d, "候選", n, "取", len(top))
    print("、".join(f"{names.get(c, '')}{c}({r:.3f})" for c, r in top))
