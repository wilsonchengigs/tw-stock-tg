"""研究 69b：投信、自營商週買賣超（同研究 69 的方法：z-score、事件研究、濾網／反向提早進場、平移安慰劑）
「跟著投信買」：投信近 n 週大買（z > x）才進場／大賣就出場；另測反向（大賣後提早進）
用法：python -X utf8 backtest/research_69b_投信自營商週買賣超.py
"""
import contextlib
import csv
import importlib.util
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("r69", os.path.join(HERE, "research_69_外資週買賣超.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def main():
    rows = sorted(csv.DictReader(open(os.path.join(HERE, "inst_weekly.csv"), encoding="utf-8")), key=lambda r: r["week_end"])
    out_all = ["研究 69b：投信、自營商週買賣超（方法同研究 69；欄位意義：z < -x 為大賣）"]
    for col, nm in (("trust", "投信"), ("dealer", "自營商")):
        m.rows = [(r["week_end"], float(r[col])) for r in rows]
        m.WD = [d for d, _ in m.rows]
        m.FV = [v for _, v in m.rows]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            m.main()
        txt = buf.getvalue().replace("外資", nm)
        out_all.append(f"\n==================== {nm} ====================\n" + txt)
    # 跟著投信買：投信 z > x 時「提早進場」＝把 z 取負號後用研究 69 的 C 模式
    m.rows = [(r["week_end"], -float(r["trust"])) for r in rows]
    m.WD = [d for d, _ in m.rows]
    m.FV = [v for _, v in m.rows]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        m.main()
    txt = buf.getvalue().replace("外資大賣後提早進", "投信大買後提早進").replace("外資", "投信(反號)")
    out_all.append("\n==================== 跟著投信買（投信大買＝反號後的「大賣」） ====================\n" + txt)
    out = "\n".join(out_all)
    print(out)
    open(os.path.join(HERE, "結果_研究69b_投信自營商.txt"), "w", encoding="utf-8").write(out)
    open(os.path.join(HERE, "結果_研究69_外資週買賣超.txt"), "w", encoding="utf-8")  # m.main() 覆寫了 69 的結果檔，下面還原
    m.rows = [(r["week_end"], float(r["foreign"])) for r in rows]
    m.WD = [d for d, _ in m.rows]
    m.FV = [v for _, v in m.rows]
    with contextlib.redirect_stdout(io.StringIO()):
        m.main()


if __name__ == "__main__":
    main()
