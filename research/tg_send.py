"""傳一則 Telegram 訊息：python research/tg_send.py "內容"（或從 stdin 讀）。需要環境變數 TG_BOT_TOKEN、TG_CHAT_ID"""
import os
import sys
import urllib.parse
import urllib.request

text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()
token, chat = os.environ["TG_BOT_TOKEN"], os.environ["TG_CHAT_ID"]
# Telegram 單則上限 4096 字
for i in range(0, len(text), 4000):
    body = urllib.parse.urlencode({"chat_id": chat, "text": text[i:i + 4000]}).encode()
    urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body), timeout=30).read()
print("sent")
