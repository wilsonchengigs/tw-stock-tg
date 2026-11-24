# CLAUDE.md

## 語言

一律用繁體中文回覆、寫文件與 commit 訊息。

## 先讀

- `research/研究紀錄.md`：目標、驗收標準、現行策略、已研究結論（表格）、待研究清單、研究日誌、兩個 AI 的分工。接續任何研究前先讀
- `README.md`：日報內容、現行策略、檔案架構

## 硬規則

- **改 `report.py` 的策略規則（進出場、濾網、加碼）一定要使用者同意**；研究結果只能「列候選」，在報告或對話中提出
- **Telegram token、chat id 不能寫進任何檔案或 commit**（公開倉庫）；只用環境變數或 GitHub Secrets
- 不要 force push；push 被拒就 `git pull --rebase --autostash` 再 push（Actions 每天會 commit `data/*.csv`，另一個 AI 也在同一個倉庫工作）
- 只 `git add` 自己改的檔案；`*.txt` 被 .gitignore 忽略，研究結果檔要 `git add -f`

## 研究流程

1. 從待研究清單挑題目，先標「【AI-x 進行中，研究 NN】」並 push，避免兩個 AI 重複
2. 程式放 `backtest/research_NN_主題.py`、結果 `backtest/結果_研究NN_主題.txt`；現行規則的基準用 `backtest/strategy_v3.py`
3. 驗收標準：全期 2002–2026、前段 2002–2012、後段 2013–2026 都要勝現行；最大回檔 < 50%；鄰近參數穩定；2015-09 後用 00631L 真實價格驗證；有序列可平移的指標要做安慰劑檢定（循環平移 100～200 次），一次測很多組要考慮多重比較
4. 寫回研究紀錄：「已研究」表格一列（方法、主要數字、結論、結果檔）＋研究日誌一段（時間、做了什麼、結論）
5. commit 訊息：「研究 NN：主題（一句結論）」，結尾加 Co-Authored-By

## 資料注意

- Yahoo 的 0050 在 2014 前、00631L 在 2015-08 前有錯價；TWD=X 有錯價要清洗（研究 09）；00662、00663L 有未調整分割
- 證交所請求要間隔（`report.get_json` 已 sleep 2 秒）；兩個 AI 同時大量請求可能被擋，下載先確認對方沒在跑
- 美國資料對台股要用「前一晚」的值（台股收盤時美股還沒開）；國發會月資料延後 2 個月使用
- 證交所 MI_INDEX 收盤價最早只到 2004-02-11；期交所三大法人期貨只能查近幾年

## 環境

- Windows：python 要加 `-X utf8`；bash heredoc 遇到含 `'—'` 等字元的長 Python 有時會失敗，改用檔案工具寫檔
- 日報本機測試：`REPORT_DATE=YYYYMMDD python -X utf8 report.py`（沒有 token 時 send 會失敗，可在 `-c` 裡把 `report.send` 換成空函式）
