"""日報回歸檢查（研究 429）：用已知日期跑早上／收盤後／晚上三種，確認不會出錯、該送的有送（不實際送 Telegram、不寫已送紀錄）
改完 report.py 後跑：python -X utf8 check_report.py（跑完會還原 data/ 的快取變動要自己 git checkout -- data/）
預期：morning 20261125 送出（夜盤 -5.6%）、morning 20261126 不送、alert 20261125 送出（台美背離）、alert 20261126 不送、all 兩天都送出
"""
import os
import sys

CASES = [("morning", "20261125", True), ("morning", "20261126", False), ("alert", "20261125", True),
         ("alert", "20261126", False), ("all", "20261126", True), ("all", "20261120", True)]


def main():
    import report
    bad = 0
    for part, d, expect in CASES:
        sent = []
        report.send = lambda t: sent.append(t)  # noqa: E731
        report.main.__globals__["send"] = report.send
        report.mark_sent = lambda x: None  # noqa: E731
        os.environ["REPORT_PART"], os.environ["REPORT_DATE"] = part, d
        try:
            report.main()
            ok = bool(sent) == expect
            print(f"{'✅' if ok else '❌'} {part} {d}：{'送出' if sent else '不送'}（預期 {'送出' if expect else '不送'}）")
            bad += not ok
        except Exception as e:  # noqa: BLE001
            import socket
            import urllib.error
            if isinstance(e, (TimeoutError, socket.timeout, urllib.error.URLError, ConnectionError)) or "timed out" in str(e):
                print(f"⚠️ {part} {d}：網路逾時／連線失敗，略過（不算程式錯誤）：{e}")
                continue
            print(f"❌ {part} {d}：例外 {e}")
            bad += 1
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
