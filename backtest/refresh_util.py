"""資料下載程式共用：每月健康檢查前，刪掉最近 N 個月（含本月）的資料讓它重抓（本月可能只抓到一半）"""
import os
from datetime import date


def recent_months(months=2):
    t = date.today()
    y, m = t.year, t.month
    keys = []
    for _ in range(months):
        keys.append(f"{y}-{m:02d}")
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return keys


def drop_recent(path, months=2):
    """path 是 csv、第一欄是 YYYY-MM-DD；刪掉最近 months 個月的列"""
    if not os.path.exists(path):
        return
    keys = set(recent_months(months))
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    keep = lines[:1] + [ln for ln in lines[1:] if ln[:7] not in keys]
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(keep) + "\n")


def this_month():
    t = date.today()
    return t.year, t.month
