"""Synthetic check of the usage de-duplication in build_metrics.session_metrics.

A response is written once per content block, each line carrying the same usage block. The test builds a small
session file (no real content) and checks that a response counts once, with and without message ids.
"""
import importlib.util
import json
import pathlib
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "build_metrics.py"


def load():
    spec = importlib.util.spec_from_file_location("build_metrics_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def line(ts, usage, mid=None, tool=None):
    block = {"type": "tool_use", "name": "Bash", "input": {"command": tool}} if tool else {"type": "text", "text": "x"}
    msg = {"usage": usage, "content": [block]}
    if mid:
        msg["id"] = mid
    return json.dumps({"type": "assistant", "timestamp": ts, "message": msg})


def usage(out, inp=10):
    return {"input_tokens": inp, "output_tokens": out, "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0}


class DedupTest(unittest.TestCase):
    def run_session(self, lines):
        bm = load()
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "doc").mkdir()
            src = root / "sess.jsonl"
            src.write_text("\n".join(lines) + "\n")
            bm.ROOT = root
            bm.find_session_file = lambda: src
            m = {}
            bm.session_metrics(m)
            skeleton = (root / "doc" / "telemetry" / "usage-sess.jsonl").read_text().splitlines()
        return m, skeleton

    def test_same_id_counts_once(self):
        m, sk = self.run_session([
            line("2026-10-01T10:00:00Z", usage(100), mid="msg_1"),
            line("2026-10-01T10:00:01Z", usage(100), mid="msg_1", tool="ls"),
            line("2026-10-01T10:00:05Z", usage(50), mid="msg_2"),
        ])
        self.assertEqual(m["requests"], 2)
        self.assertEqual(m["requests_repeated"], 1)
        self.assertEqual(m["tok_output"], 150)
        self.assertEqual(json.loads(sk[0])["id"], "msg_1")  # skeleton keeps the id for later checks

    def test_without_id_identical_neighbour_is_repeat(self):
        m, _ = self.run_session([
            line("2026-10-01T10:00:00Z", usage(100)),
            line("2026-10-01T10:00:01Z", usage(100), tool="ls"),
            line("2026-10-01T10:00:05Z", usage(50)),
        ])
        self.assertEqual(m["requests"], 2)
        self.assertEqual(m["requests_repeated"], 1)
        self.assertEqual(m["tok_output"], 150)

    def test_distinct_usage_without_id_is_not_merged(self):
        m, _ = self.run_session([
            line("2026-10-01T10:00:00Z", usage(100)),
            line("2026-10-01T10:00:05Z", usage(101)),
        ])
        self.assertEqual(m["requests"], 2)
        self.assertEqual(m["requests_repeated"], 0)

    def test_cost_counts_response_once(self):
        m, _ = self.run_session([
            line("2026-10-01T10:00:00Z", usage(1_000_000, inp=0), mid="a"),
            line("2026-10-01T10:00:01Z", usage(1_000_000, inp=0), mid="a"),
        ])
        self.assertEqual(m["cost_usd"], 50.0)  # one response at 50 USD per 1M output tokens, not two


if __name__ == "__main__":
    unittest.main()
