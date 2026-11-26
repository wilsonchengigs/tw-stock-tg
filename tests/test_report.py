"""report.py 的單元測試（不連網）：python -m unittest discover -s tests -v"""
import os
import sys
import tempfile
import unittest
import urllib.error
from datetime import date, timedelta
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import report  # noqa: E402


def weekdays(start: date, n: int) -> list:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
    return out


def closes_from(prices: list) -> list:
    # 最後一天要是週五，週頻規則才會在「今天」判斷：從週一起排滿整週
    days = weekdays(date(2024, 1, 1), len(prices))
    return list(zip(days, prices))


class SplitMessage(unittest.TestCase):
    def test_short_unchanged(self):
        self.assertEqual(report.split_message("a\nb"), ["a\nb"])

    def test_splits_on_lines_within_limit(self):
        text = "\n".join(["x" * 30] * 10)
        parts = report.split_message(text, limit=100)
        self.assertTrue(all(len(p) <= 100 for p in parts))
        self.assertEqual("\n".join(parts), text)

    def test_long_single_line_hard_cut(self):
        parts = report.split_message("y" * 250, limit=100)
        self.assertEqual([len(p) for p in parts], [100, 100, 50])


class LoadCsv(unittest.TestCase):
    def test_roundtrip_and_quoted_comma(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(report, "DATA_DIR", tmp):
            report.save_csv("t.csv", "date,a,b", {"20240102": [1, 2], "20240101": [3, 4]})
            self.assertEqual(report.load_csv("t.csv"), {"20240101": ["3", "4"], "20240102": ["1", "2"]})
            with open(os.path.join(tmp, "q.csv"), "w", encoding="utf-8") as f:
                f.write('date,note\n20240103,"a,b"\n')
            self.assertEqual(report.load_csv("q.csv"), {"20240103": ["a,b"]})

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(report, "DATA_DIR", tmp):
            self.assertEqual(report.load_csv("none.csv"), {})


class UrlopenRetry(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(report.time, "sleep")
        p.start()
        self.addCleanup(p.stop)

    def err(self, code):
        return urllib.error.HTTPError("http://x", code, "e", {}, None)

    def test_retries_5xx_then_succeeds(self):
        req = mock.Mock(data=None)
        with mock.patch("urllib.request.urlopen", side_effect=[self.err(503), self.err(429), "ok"]) as m:
            self.assertEqual(report.urlopen_retry(req), "ok")
            self.assertEqual(m.call_count, 3)

    def test_404_not_retried(self):
        req = mock.Mock(data=None)
        with mock.patch("urllib.request.urlopen", side_effect=self.err(404)) as m:
            with self.assertRaises(urllib.error.HTTPError):
                report.urlopen_retry(req)
            self.assertEqual(m.call_count, 1)

    def test_post_timeout_not_retried(self):
        req = mock.Mock(data=b"x")
        with mock.patch("urllib.request.urlopen", side_effect=TimeoutError()) as m:
            with self.assertRaises(TimeoutError):
                report.urlopen_retry(req)
            self.assertEqual(m.call_count, 1)

    def test_get_timeout_retried(self):
        req = mock.Mock(data=None)
        with mock.patch("urllib.request.urlopen", side_effect=[TimeoutError(), "ok"]) as m:
            self.assertEqual(report.urlopen_retry(req), "ok")
            self.assertEqual(m.call_count, 2)


class StrategyState(unittest.TestCase):
    """合成價格：持續上漲 → 在場；持續下跌 → 空手；結果鎖住現行規則，改規則時測試會變紅"""

    def friday_series(self, prices):
        c = closes_from(prices)
        while datetime_weekday(c[-1][0]) != 4:  # 補到週五
            c.append((next_weekday(c[-1][0]), c[-1][1]))
        return c

    def test_uptrend_in_market(self):
        c = self.friday_series([100 + i * 0.5 for i in range(200)])
        state, switched, ma_x, ma_n = report.strategy_state(c)
        self.assertTrue(state)
        self.assertIsNotNone(switched)

    def test_downtrend_out_of_market(self):
        c = self.friday_series([200 - i * 0.5 for i in range(200)])
        state, *_ = report.strategy_state(c)
        self.assertFalse(state)

    def test_exit_below_ma_band(self):
        up = [100 + i * 0.5 for i in range(150)]
        c = self.friday_series(up + [up[-1] * 0.8] * 10)
        state, *_ = report.strategy_state(c)
        self.assertFalse(state)

    def test_hot_heat_forces_exit_and_blocks_entry(self):
        c = self.friday_series([100 + i * 0.5 for i in range(200)])
        heat = {d: (0.5, 5.0) for d, _ in c}
        state, *_ = report.strategy_state(c, heat)
        self.assertFalse(state)


def datetime_weekday(ymd: str) -> int:
    return date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:])).weekday()


def next_weekday(ymd: str) -> str:
    d = date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:])) + timedelta(days=1)
    while d.weekday() > 4:
        d += timedelta(days=1)
    return d.strftime("%Y%m%d")


if __name__ == "__main__":
    unittest.main()
