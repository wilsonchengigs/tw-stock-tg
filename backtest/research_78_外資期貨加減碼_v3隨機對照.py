"""研究 78：研究 75（外資台指期大變化加減碼）在 v3 現行策略上的隨機對照（同研究 75c 的方法，狀態換成研究 76 的 v3）
用法：python -X utf8 backtest/research_78_外資期貨加減碼_v3隨機對照.py
"""
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    S = load("r76", "research_76_加碼候選在v3重驗.py").v3_states()
    c = load("r75c", "research_75c_外資期貨加減碼_隨機對照.py")
    c.m.r64.state_series = lambda: S
    c.main()
    src = os.path.join(HERE, "結果_研究75c_隨機對照.txt")
    txt = "研究 78：外資期貨加減碼 × v3 現行的隨機對照\n" + open(src, encoding="utf-8").read()
    open(os.path.join(HERE, "結果_研究78_v3隨機對照.txt"), "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
