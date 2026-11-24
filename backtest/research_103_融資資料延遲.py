"""研究 103：融資資料延遲的影響——過熱判斷改用前 1／2／5 個交易日的融資資料（模擬晚公布、抓不到）
用法：python -X utf8 backtest/research_103_融資資料延遲.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("v3", os.path.join(HERE, "strategy_v3.py"))
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)


def main():
    L = ["研究 103：融資資料延遲（全期 2002- | 前段 | 後段 | 真實）"]
    dev0, z0 = V.DEV, V.Z
    for lag in (0, 1, 2, 5):
        V.DEV = [None] * lag + dev0[:len(dev0) - lag] if lag else dev0
        V.Z = [None] * lag + z0[:len(z0) - lag] if lag else z0
        L.append(f"延遲 {lag} 天  {V.fmt()}")
        print(L[-1], flush=True)
    V.DEV, V.Z = dev0, z0
    open(os.path.join(HERE, "結果_研究103_融資資料延遲.txt"), "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
