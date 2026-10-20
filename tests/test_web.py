"""Browser JSON boundary: real engine results, replayable exports and limits."""

import json
import unittest
from unittest.mock import patch

from muql.backends import BackendUnavailable
from muql.checker import check, replay
from muql.theory import loads
from muql.web import MAX_SOURCE_CHARS, handle_json
from muql.web import _downloads


SCOPED = """# Tiny choices

```muql
theory "Tiny choices"
points alice
values red blue
stages 1
quorums {alice}
predicate chosen/1
axiom Correct: ∀v. TF(chosen(v))
axiom Unique: ∃⁰¹v. chosen(v)
property AtMostOne: ∃⁰¹v. chosen(v)
property Reflexive: ∀v. chosen(v) ⇀ chosen(v)
```
"""

TEMPLATE = """```muql
theory "Choices"
predicate chosen/1
axiom Correct: ∀v. TF(chosen(v))
property AtMostOne: ∃⁰¹v. chosen(v)
```
"""


def request(**changes):
    data = {"action": "run", "source": SCOPED, "solver": "builtin"}
    data.update(changes)
    return json.loads(handle_json(json.dumps(data)))


def download(result, name):
    return next(item["content"] for item in result["downloads"] if item["name"] == name)


class WebBridgeTests(unittest.TestCase):
    def test_inspect_expands_to_readable_unicode_and_marks_templates(self):
        result = request(action="inspect", source=TEMPLATE.replace("∀", "forall "))
        self.assertTrue(result["ok"])
        metadata = result["metadata"]
        self.assertEqual(metadata["name"], "Choices")
        self.assertEqual(metadata["predicates"], [{"name": "chosen", "arity": 1}])
        self.assertFalse(metadata["scope_declared"])
        self.assertEqual(metadata["axioms"][0]["formula"], "∀ v. TF(chosen(v))")
        self.assertEqual(metadata["properties"][0]["name"], "AtMostOne")
        self.assertTrue(request(action="inspect")["metadata"]["scope_declared"])

    def test_check_matches_core_and_report_download_is_exact(self):
        result = request(properties=["AtMostOne"])
        expected = check(loads(SCOPED), ["AtMostOne"], total_timeout=10)
        self.assertTrue(result["ok"])
        self.assertEqual(result["report"]["status"], expected.status)
        self.assertEqual(result["report"]["properties"], [p.to_dict() for p in expected.properties])
        self.assertEqual(json.loads(download(result, "report")), result["report"])
        retained = loads(download(result, "theory"))
        self.assertEqual(retained.axioms, loads(SCOPED).axioms)
        self.assertIn("⇀", download(result, "theory"))

    def test_search_template_exports_witness_that_replays(self):
        result = request(source=TEMPLATE, mode="search", limits={
            "max_points": 1, "max_values": 2, "max_stages": 1, "max_quorums": 1,
        })
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["report"]["properties"][0]["status"], "counterexample")
        scoped = loads(download(result, "witness-AtMostOne-theory"))
        witness = json.loads(download(result, "witness-AtMostOne-countermodel"))
        self.assertTrue(replay(scoped, witness))
        retained = loads(download(result, "theory"), for_search=True)
        self.assertFalse(retained.scope_declared)
        self.assertEqual(retained.axioms, loads(TEMPLATE, for_search=True).axioms)
        self.assertEqual(witness["scope"]["values"], ["v0", "value0"])

    def test_dropped_axiom_is_absent_from_all_theory_exports(self):
        result = request(drop=["Unique"], properties=["AtMostOne"])
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["report"]["properties"][0]["status"], "counterexample")
        self.assertEqual([a["name"] for a in result["metadata"]["axioms"]], ["Correct"])
        witness = json.loads(download(result, "witness-AtMostOne-countermodel"))
        for name in ("theory", "witness-AtMostOne-theory"):
            retained = loads(download(result, name))
            self.assertNotIn("Unique", retained.axioms)
            self.assertTrue(replay(retained, witness))
            self.assertEqual(set(retained.properties), {"AtMostOne", "Reflexive"})
        with self.assertRaises(ValueError):
            replay(loads(SCOPED), witness)

    def test_empty_property_list_only_finds_axiom_model(self):
        for mode in ("check", "search"):
            with self.subTest(mode=mode):
                result = request(mode=mode, properties=[], limits={
                    "max_points": 1, "max_values": 2, "max_stages": 1,
                })
                self.assertTrue(result["ok"], result)
                self.assertEqual(result["report"]["properties"], [])
                self.assertIsNotNone(result["report"]["consistency_model"])
                self.assertEqual(len(result["downloads"]), 2)

    def test_exhausted_time_and_node_limits_are_unknown_never_holds(self):
        for mode in ("check", "search"):
            for limits in ({"timeout": 0}, {"max_nodes": 1}):
                with self.subTest(mode=mode, limits=limits):
                    result = request(mode=mode, limits=limits)
                    self.assertTrue(result["ok"], result)
                    self.assertEqual(result["report"]["status"], "unknown")
                    self.assertTrue(all(p["status"] == "unknown" for p in result["report"]["properties"]))

    def test_check_uses_one_total_deadline(self):
        with patch("muql.web.check", wraps=check) as checked:
            result = request(limits={"timeout": 0.5})
        self.assertTrue(result["ok"])
        self.assertEqual(checked.call_args.kwargs["timeout"], 0.5)
        self.assertEqual(checked.call_args.kwargs["total_timeout"], 0.5)

    def test_invalid_bounds_and_booleans_are_rejected_before_engine(self):
        limits = [{"max_points": 7}, {"max_values": 9}, {"max_stages": 13},
                  {"max_quorums": 65}, {"max_frames": 5001}, {"max_nodes": 500001},
                  {"max_decisions": 1000001}, {"max_mu_contexts": 13},
                  {"timeout": -1}, {"timeout": True}, {"timeout": 10**400},
                  {"max_points": True}, {"max_points": 2.0}, {"max_nodes": 0},
                  {"timeout": "10"}, {"max_frames": None}, {"typo": 1}]
        with patch("muql.web.check") as checked, patch("muql.web.search") as searched:
            for value in limits:
                with self.subTest(limits=value):
                    self.assertFalse(request(limits=value)["ok"])
            checked.assert_not_called()
            searched.assert_not_called()

    def test_invalid_request_shapes_and_names_are_readable_errors(self):
        invalid = [{"action": "execute"}, {"mode": "guess"}, {"solver": "auto"},
                   {"source": []}, {"limits": []}, {"properties": "AtMostOne"},
                   {"properties": [True]}, {"properties": ["Reflexive", "Reflexive"]},
                   {"drop": None}, {"drop": ["Missing"]}, {"properties": ["Missing"]},
                   {"python": "print('never executed')"}]
        for change in invalid:
            with self.subTest(change=change):
                result = request(**change)
                self.assertFalse(result["ok"])
                self.assertTrue(result["error"]["message"])

    def test_json_malformed_nonfinite_duplicate_and_wrong_root_are_errors(self):
        for text in ("{", "[]", "null", '{"action":"inspect","action":"run"}',
                     '{"action":"inspect","limits":{"timeout":NaN}}',
                     '{"action":"inspect","limits":{"timeout":Infinity}}'):
            with self.subTest(text=text):
                result = json.loads(handle_json(text))
                self.assertFalse(result["ok"])
        self.assertFalse(json.loads(handle_json(None))["ok"])

    def test_bad_formula_reports_original_markdown_location(self):
        result = request(action="inspect", source=SCOPED.replace("⇀", "=>"))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["line"], 13)
        self.assertGreater(result["error"]["column"], 1)
        self.assertIn("not supported", result["error"]["message"])
        self.assertIn("-\\", result["error"]["message"])

    def test_error_locations_count_unicode_characters_and_loader_line_endings(self):
        lines = ['```muql', 'values "😀"', 'predicate P/1',
                 'property Invalid: P("😀") => P("😀")', '```']
        for separator in ("\n", "\r\n", "\u2028", "\u2029", "\v", "\x85"):
            with self.subTest(separator=repr(separator)):
                result = request(action="inspect", source=separator.join(lines))
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"]["line"], 4)
                self.assertEqual(result["error"]["column"], lines[3].index("=>") + 1)

    def test_oversized_sources_and_declared_scopes_are_rejected(self):
        self.assertFalse(request(source=" " * (MAX_SOURCE_CHARS + 1))["ok"])
        self.assertFalse(request(source=SCOPED.replace("stages 1", "stages 13"))["ok"])
        values = SCOPED.replace("values red blue", "values a b c d e f g h i")
        self.assertFalse(request(source=values, mode="search")["ok"])
        self.assertFalse(request(source=TEMPLATE)["ok"])

    def test_missing_acceleration_offers_browser_fallback(self):
        with patch("muql.web.check", side_effect=BackendUnavailable("desktop install command")):
            result = request(solver="pysat")
        self.assertFalse(result["ok"])
        self.assertIn("built-in", result["error"]["message"])
        self.assertNotIn("install command", result["error"]["message"])

    def test_large_finite_time_budgets_reach_the_checker_without_a_browser_cap(self):
        for seconds in (121, 3600, 1e100):
            with self.subTest(seconds=seconds), patch("muql.web.check", wraps=check) as checked:
                result = request(limits={"timeout": seconds})
                self.assertTrue(result["ok"], result)
                self.assertEqual(checked.call_args.kwargs["timeout"], seconds)
                self.assertEqual(checked.call_args.kwargs["total_timeout"], seconds)

    def test_run_progress_uses_json_strings_and_inspection_never_calls_observer(self):
        events = []
        text = handle_json(json.dumps({"action": "run", "source": SCOPED}), events.append)
        self.assertTrue(json.loads(text)["ok"])
        self.assertTrue(events)
        self.assertTrue(all(isinstance(event, str) for event in events))
        snapshots = [json.loads(event) for event in events]
        self.assertEqual(snapshots[0]["phase"], "validating")
        self.assertEqual(snapshots[-1]["phase"], "preparing_results")
        events.clear()
        self.assertTrue(json.loads(handle_json(json.dumps({"action": "inspect", "source": SCOPED}), events.append))["ok"])
        self.assertEqual(events, [])

    def test_progress_callback_failure_does_not_replace_a_valid_response(self):
        def failed(_snapshot):
            raise RuntimeError("observer failed")
        data = json.loads(handle_json(json.dumps({"action": "run", "source": SCOPED}), failed))
        self.assertTrue(data["ok"], data)
        self.assertEqual(data["report"]["status"], "checked")

    def test_export_preparation_retains_search_counts_before_witness_download_replay(self):
        snapshots = []

        def downloads(theory, report, max_mu_contexts):
            self.assertEqual(snapshots[-1]["phase"], "preparing_results")
            self.assertEqual(snapshots[-1]["frames_completed"], report.stats["frames"])
            self.assertEqual(snapshots[-1]["counterexamples_found"], 1)
            return _downloads(theory, report, max_mu_contexts)

        with patch("muql.web._downloads", side_effect=downloads):
            result = json.loads(handle_json(json.dumps({"action": "run", "mode": "search", "source": TEMPLATE}),
                                            lambda text: snapshots.append(json.loads(text))))
        self.assertTrue(result["ok"], result)

    def test_declared_values_raise_implicit_search_default(self):
        source = "```muql\nvalues red blue green\nproperty Reflexive: t\n```"
        result = request(source=source, mode="search", limits={"max_points": 1, "max_stages": 1})
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["report"]["bounds"]["values"], [3, 3])
        self.assertFalse(request(source=source, mode="search", limits={"max_values": 2})["ok"])


if __name__ == "__main__":
    unittest.main()
