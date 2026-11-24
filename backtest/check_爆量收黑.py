"""每日檢查「爆量收黑」訊號（研究 63～63i 的規則；只讀資料、印出結果，不改 report.py、不下單）

規則（研究 63d／63i）：
- 證交所成交金額 ≥ 前 20 個交易日平均 × 1.5，且加權指數收黑（收盤 < 前一日收盤）
- 研究結果：台指期當晚夜盤或隔天開盤買近月、抱 5～10 個交易日；5% 停損
- 多頭（加權指數 > 60 日均線）時效果較好（抱 10 天每筆 +2.88%、勝率 76%）；空頭時效果弱
- 只在「突然」爆量時有效：連續崩跌中 20 日均量已被墊高，不會觸發，這是對的（研究 63h）
資料：證交所 FMTQIK（每日成交金額、加權指數），抓最近 6 個月；現行策略狀態用 report.strategy_state（含融資過熱，只讀 data/margin_ratio.csv）
研究 64b～64g：現行策略「在場」時遇訊號 → 當晚夜盤加台指期 0.5～1 倍名目、抱 5～10 天，是目前驗證最完整的用法
用法：python -X utf8 backtest/check_爆量收黑.py [顯示天數，預設 15]
"""
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import report  # noqa: E402

TW = timezone(timedelta(hours=8))


def fetch(months=6):
    rows = {}
    today = datetime.now(TW)
    y, m = today.year, today.month
    for _ in range(months):
        d = report.get_json(f"https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK?date={y}{m:02d}01&response=json")
        for t in report.tables_of(d):
            fl = t.get("fields", [])
            if "日期" in fl and "成交金額" in fl and "發行量加權股價指數" in fl:
                idt, iam, ix = fl.index("日期"), fl.index("成交金額"), fl.index("發行量加權股價指數")
                for r in t.get("data", []):
                    yy, mm, dd = str(r[idt]).strip().split("/")
                    rows[f"{int(yy) + 1911}-{int(mm):02d}-{int(dd):02d}"] = (report.num(r[iam]), report.num(r[ix]))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return sorted(rows.items())


def main():
    show = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    rows = fetch()
    days = [d for d, _ in rows]
    amt = [a for _, (a, _c) in rows]
    px = [c for _, (_a, c) in rows]
    print("日期         加權指數    漲跌     成交金額(億)  量比   60日線     狀態")
    last_sig = None
    for i in range(max(21, len(rows) - show), len(rows)):
        base = sum(amt[i - 20:i]) / 20
        vr = amt[i] / base
        ch = px[i] / px[i - 1] - 1
        ma60 = sum(px[i - 59:i + 1]) / 60 if i >= 59 else None
        bull = ma60 is not None and px[i] > ma60
        sig = vr >= 1.5 and ch < 0
        if sig:
            last_sig = (days[i], bull)
        tag = ("★ 爆量收黑" + ("（多頭，研究較強）" if bull else "（空頭，研究較弱）")) if sig else ("  爆量收紅" if vr >= 1.5 else "")
        print(f"{days[i]}  {px[i]:10.2f}  {ch:+6.2%}  {amt[i] / 1e8:10.0f}  {vr:5.2f}  "
              + (f"{ma60:10.2f}{'↑' if bull else '↓'}" if ma60 else f"{'—':>10s} ") + f"  {tag}")
    closes = [(d.replace("-", ""), c) for d, c in zip(days, px)]
    try:
        heat = report.heat_series(report.load_margin_ratio())
    except Exception:  # noqa: BLE001
        heat = None
    on, switched, ma_x, ma_n = report.strategy_state(closes, heat)
    print(f"\n現行策略（週五判斷）：{'在場（2x）' if on else '空手'}，上次切換 {switched}")
    if last_sig:
        if on:
            print("  → 若今天有爆量收黑：研究 64b 的用法是當晚夜盤加台指期 0.5～1 倍名目、抱 5～10 天（3% 停損可選）")
        else:
            print("  → 現行策略空手：研究 64 顯示空手時加碼無幫助；單獨短線見研究 63d／63g")
    i = len(rows) - 1
    need = sum(amt[i - 19:i + 1]) / 20 * 1.5
    print(f"\n下一個交易日要觸發，成交金額需 ≥ 約 {need / 1e8:,.0f} 億且收黑（以今天為止的 20 日均量估）")
    if last_sig:
        print(f"最近一次訊號：{last_sig[0]}（{'多頭' if last_sig[1] else '空頭'}）")
    print("提醒：這是研究用的統計規則，一年約 2～3 次，單筆最差曾 -11%；不是投資建議")


if __name__ == "__main__":
    main()
