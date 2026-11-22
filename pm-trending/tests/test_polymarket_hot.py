"""离线单测：python3 -m unittest discover -s tests（在 pm-trending/ 下运行）。"""
import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import polymarket_hot as ph  # noqa: E402


def ev(i, **kw):
    return {"id": str(i), "title": f"E{i}", "slug": f"e{i}", "volume24hr": 100 - i, "markets": [], **kw}


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def resp(obj):
    return FakeResp(json.dumps(obj).encode())


class FetchEventsTest(unittest.TestCase):
    def setUp(self):
        mock.patch.object(ph.time, "sleep").start()
        self.addCleanup(mock.patch.stopall)

    def test_dedupes_events_shifted_between_pages(self):
        pages = [[ev(1), ev(2)], [ev(2), ev(3)], [ev(4)]]   # 翻页时 ev(2) 漂移到第二页
        with mock.patch.object(ph, "get_json", side_effect=pages):
            events, complete = ph.fetch_events(limit=4, page_size=2)
        self.assertEqual([e["id"] for e in events], ["1", "2", "3", "4"])
        self.assertTrue(complete)

    def test_later_page_failure_keeps_partial(self):
        with mock.patch.object(ph, "get_json", side_effect=[[ev(1), ev(2)], TimeoutError("read timed out")]):
            events, complete = ph.fetch_events(limit=4, page_size=2)
        self.assertEqual(len(events), 2)
        self.assertFalse(complete)

    def test_first_page_failure_raises(self):
        with mock.patch.object(ph, "get_json", side_effect=TimeoutError("x")):
            with self.assertRaises(TimeoutError):
                ph.fetch_events(limit=4, page_size=2)

    def test_get_json_retries_timeout_then_succeeds(self):
        with mock.patch.object(ph.urllib.request, "urlopen",
                               side_effect=[TimeoutError("t"), resp([ev(1)])]) as m:
            self.assertEqual(ph.get_json("http://x")[0]["id"], "1")
        self.assertEqual(m.call_count, 2)

    def test_get_json_does_not_retry_4xx(self):
        err = urllib.error.HTTPError("http://x", 406, "Not Acceptable", {}, None)
        with mock.patch.object(ph.urllib.request, "urlopen", side_effect=err) as m:
            with self.assertRaises(urllib.error.HTTPError):
                ph.get_json("http://x")
        self.assertEqual(m.call_count, 1)

    def test_get_json_gives_up_after_all_retries(self):
        with mock.patch.object(ph.urllib.request, "urlopen", side_effect=TimeoutError("t")) as m:
            with self.assertRaises(TimeoutError):
                ph.get_json("http://x")
        self.assertEqual(m.call_count, len(ph.RETRY_BACKOFF) + 1)


class ProbabilityTest(unittest.TestCase):
    def test_zero_spread_uses_midpoint(self):
        self.assertEqual(ph.yes_probability({"bestBid": 0.42, "bestAsk": 0.42}), 0.42)

    def test_wide_spread_falls_back_to_outcome_prices(self):
        m = {"bestBid": 0.1, "bestAsk": 0.6, "outcomes": '["Yes","No"]', "outcomePrices": '["0.3","0.7"]'}
        self.assertEqual(ph.yes_probability(m), 0.3)

    def test_summary_carries_market_ids(self):
        e = ev(1, markets=[{"id": "m1", "conditionId": "0xabc", "slug": "s", "question": "Q?",
                            "bestBid": 0.5, "bestAsk": 0.52, "lastTradePrice": 0.51, "negRisk": True}])
        o = ph.summarize_event(e)["outcomes"][0]
        self.assertEqual((o["market_id"], o["condition_id"], o["last_trade"], o["neg_risk"]),
                         ("m1", "0xabc", 0.51, True))


class RawStorageTest(unittest.TestCase):
    def test_compact_raw_drops_closed_markets_and_static_text(self):
        e = ev(1, description="rules", image="u", markets=[
            {"id": "a", "description": "r", "icon": "u", "bestBid": 0.1},
            {"id": "b", "closed": True}])
        out = ph.compact_raw([e])[0]
        self.assertNotIn("description", out)
        self.assertEqual([m["id"] for m in out["markets"]], ["a"])
        self.assertEqual(out["markets"][0], {"id": "a", "bestBid": 0.1})

    def test_catalog_appends_each_description_once(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d, mock.patch.object(ph, "ROOT", Path(d)):
            raw = [ev(1, description="E rules", markets=[{"id": "a", "description": "A rules"}])]
            self.assertEqual(ph.update_catalog(raw, "t1"), 2)
            self.assertEqual(ph.update_catalog(raw, "t2"), 0)
            raw[0]["markets"].append({"id": "b", "description": "B rules"})
            self.assertEqual(ph.update_catalog(raw, "t3"), 1)


if __name__ == "__main__":
    unittest.main()
