"""研究 76：AI-1 的兩個加碼候選在 AI-2 的 v3 現行策略上重驗（真實價：00631L＋台指期）

v3＝MA60×1.01 進／MA80×0.975 出＋融資過熱（偏離 >17.5% 或 z>2）每天檢查＋過熱出場後回補（偏離 <12.5% 且 z≤2 且在出場線上）
     （照 backtest/research_90_過熱每日檢查.py 的 run(daily_heat=True) 邏輯算每天的在場狀態）
候選：研究 64c（爆量收黑加碼，夜盤開盤進）、研究 75b（外資台指期大變化加減碼，隔天開盤進）
做法：把兩個研究引擎裡的 state_series() 換成 v3 狀態，其餘不變
用法：python -X utf8 backtest/research_76_加碼候選在v3重驗.py
"""
import contextlib
import importlib.util
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


V = load("v3", "strategy_v3.py")


def v3_states():
    """回傳每天「週判斷／過熱檢查後」的狀態（同 r64.state_series 的語意：實際持有＝前一天的值）"""
    out = [False] * V.N
    st, heat_out = 0, False
    for i in range(V.N):
        if i >= 260:
            hot = V.hot_at(i)
            if st == 1 and hot and not V.WE[i]:
                st, heat_out = 0, True
            if V.WE[i]:
                p = V.PX[i]
                above = p >= V.M80[i] * 0.975
                if st == 0:
                    if heat_out and not above:
                        heat_out = False
                    cooled = V.DEV[i] is None or (V.DEV[i] < 0.125 and V.Z[i] <= 2.0)
                    if (p > V.M60[i] * 1.01 and not hot) or (heat_out and cooled and above):
                        st, heat_out = 1, False
                elif hot:
                    st, heat_out = 0, True
                elif not above:
                    st, heat_out = 0, False
        out[i] = st == 1
    return out


def main():
    S = v3_states()
    L = ["研究 76：加碼候選在 v3 現行策略上重驗（00631L＋台指期真實價）"]
    c64 = load("r64c", "research_64c_在場加碼真實價.py")
    assert c64.r64.DAYS == list(V.DAYS), "日期序列不一致"
    old = c64.r64.state_series
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        c64.main()
    L.append("\n== 研究 64c 爆量收黑加碼（舊版現行，2015-10～）==")
    L += [x for x in buf.getvalue().splitlines() if "年化" in x]
    c64.r64.state_series = lambda: S
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        c64.main()
    L.append("== 研究 64c 爆量收黑加碼（v3 現行，2015-10～）==")
    L += [x for x in buf.getvalue().splitlines() if "年化" in x]
    c64.r64.state_series = old
    with contextlib.redirect_stdout(io.StringIO()):
        c64.main()  # 還原 64c 結果檔

    b75 = load("r75b", "research_75b_外資期貨加減碼_真實價.py")
    b75.ENTRY = "day_open"
    L.append("\n== 研究 75b 外資期貨加減碼（舊版現行，2018-06～，隔天開盤進）==")
    L += b75.main()[1:]
    b75.r64.state_series = lambda: S
    L.append("== 研究 75b 外資期貨加減碼（v3 現行，2018-06～，隔天開盤進）==")
    L += b75.main()[1:]
    out = "\n".join(L) + "\n"
    print(out)
    open(os.path.join(HERE, "結果_研究76_加碼候選v3重驗.txt"), "w", encoding="utf-8").write(out)


if __name__ == "__main__":
    main()
