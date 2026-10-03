"""Whole-application budget and saved-artifact regressions without paid calls."""
from copy import deepcopy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from PIL import Image

from playground_v2.application import RunBudget, build, copy_handoff, main
from playground_v2.pipeline import write_json
from playground_v2.provider import ProviderError


ROOT = Path(__file__).resolve().parents[1]
MODULE = "playground_v2.application"


def fixture():
    handoff = json.loads((ROOT / "docs/v2/examples/paper_content.json").read_text(encoding="utf-8"))
    sections = handoff["content"]["sections"]
    owner = next(section["id"] for section in sections if section.get("mathematical_model"))
    experiment = {
        "id": "equal_weights", "title": "Equal-weight toy case", "section_id": owner,
        "goal": "Explore the equal-weight special case.", "explanation": "Two values contribute equally.",
        "assumptions": ["Synthetic developer fixture with fixed equal weights, not experimental evidence."],
        "variables": [{"id": name, "label": name, "type": "number", "default": default,
                       "domain": {"min": 0, "max": 10, "step": 1}, "unit": "", "explanation": "One stored value."}
                      for name, default in (("first", 2), ("second", 8))],
        "computation": {
            "outputs": [{"id": "mean", "label": "Mean", "unit": ""}],
            "steps": [{"id": "average", "label": "Average", "explanation": "Sum and divide by two.",
                       "output_ids": ["mean"], "expressions": {"mean": ["divide", ["add", "$input.first", "$input.second"], 2]}}],
        },
        "views": [{"id": "result", "kind": "scalar", "title": "Mean", "output_ids": ["mean"], "labels": []}],
        "challenges": [{"id": "increase", "instructions": "Increase the first value and observe the mean."},
                       {"id": "equal", "instructions": "Set the values equal and explain the resulting mean."}],
    }
    questions = []
    for index, outcome in enumerate(handoff["content"]["learning_outcomes"]):
        section = next(section for section in sections if outcome["id"] in section["learning_outcome_ids"])
        questions.append({
            "id": "question_" + str(index), "kind": "choice", "outcome_id": outcome["id"], "section_id": section["id"],
            "level": "evaluate" if index == 0 else "understand", "prompt": "Does this synthetic example prove benchmark superiority?",
            "options": [{"id": "no", "text": "No."}, {"id": "yes", "text": "Yes."}], "correct_option_id": "no",
            "expected": None, "tolerance": None, "explanation": "A toy calculation does not supply empirical evidence.",
        })
    experience = {
        "schema_version": "1.0", "introduction": "Synthetic developer fixture for application integration.",
        "no_experiments_reason": None,
        "sections": [{"section_id": section["id"], "experiment_ids": ["equal_weights"] if section["id"] == owner else [], "figures": []}
                     for section in sections],
        "experiments": [experiment], "questions": questions,
    }
    return handoff, experience


class ApplicationBudgetTests(unittest.TestCase):
    def test_unknown_usage_reserves_full_cap_without_inventing_usage(self):
        budget = RunBudget(time.monotonic())
        budget.record({"attempts": 1, "usage": None}, 18000)
        budget.record({"attempts": 1, "usage": {"prompt_tokens": 100, "completion_tokens": 2000, "total_tokens": 2100}}, 2000)
        self.assertEqual(budget.charged_tokens, 20000)
        self.assertEqual(budget.allowance(14000, 150)[0], 10000)
        self.assertIsNone(budget.usage())
        before = budget.charged_tokens
        budget.record({"attempts": 0, "usage": None}, 6000)
        self.assertEqual(budget.charged_tokens, before)

    def test_request_token_and_time_limits_block_further_calls(self):
        budget = RunBudget(time.monotonic())
        for _ in range(10):
            budget.record({"attempts": 1, "usage": {"completion_tokens": 1}}, 6000)
        with self.assertRaisesRegex(ValueError, "request limit"):
            budget.allowance(6000, 150)
        budget = RunBudget(time.monotonic())
        budget.record({"attempts": 1, "usage": None}, 29900)
        with self.assertRaisesRegex(ValueError, "remaining run budget"):
            budget.allowance(6000, 150)
        with self.assertRaisesRegex(ValueError, "remaining run budget"):
            RunBudget(time.monotonic() - 589).allowance(6000, 150)
        with self.assertRaisesRegex(ValueError, "exceeded"):
            RunBudget(time.monotonic()).record({"attempts": 1, "usage": {"completion_tokens": 30001}}, 6000)


class ApplicationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.handoff, self.experience = fixture()
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.saved = self.base / "saved"
        self.output = self.base / "output"
        self.saved.mkdir()
        self.output.mkdir()
        self.handoff_path = self.saved / "paper_content.json"
        self.experience_path = self.saved / "experience.json"
        write_json(self.handoff_path, self.handoff)
        write_json(self.experience_path, self.experience)

    def test_handoff_reuse_checks_input_before_copy_and_copies_verified_images(self):
        different = {**self.handoff["input"], "focus": "Another question"}
        with self.assertRaisesRegex(ValueError, "differs"):
            copy_handoff(self.handoff_path, different, self.output)
        self.assertEqual(list(self.output.iterdir()), [])
        (self.saved / "assets").mkdir()
        Image.new("RGB", (2, 2), "white").save(self.saved / "assets" / "fixture.png")
        self.handoff["source"]["visuals"][0].update(asset_path="assets/fixture.png", mime_type="image/png")
        write_json(self.handoff_path, self.handoff)
        copied = copy_handoff(self.handoff_path, self.handoff["input"], self.output)
        self.assertEqual(copied, self.handoff)
        self.assertEqual((self.output / "assets/fixture.png").read_bytes(), (self.saved / "assets/fixture.png").read_bytes())
        self.assertEqual(json.loads((self.output / "paper_content.json").read_text(encoding="utf-8")), self.handoff)

    def test_saved_render_cli_needs_no_model_key_or_provider_and_builds_real_html(self):
        input_path = self.saved / "input.json"
        write_json(input_path, self.handoff["input"])
        with patch(MODULE + "._load_api_key", side_effect=AssertionError("Offline render loaded credentials")), \
                patch(MODULE + "._generate", side_effect=AssertionError("Offline render made a model call")), redirect_stdout(io.StringIO()):
            code = main(["--input", str(input_path), "--output", str(self.output),
                         "--from-content", str(self.handoff_path), "--experience", str(self.experience_path)])
        self.assertEqual(code, 0)
        summary = json.loads((self.output / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual((summary["status"], summary["attempts"], summary["run_kind"]), ("complete", 0, "render_saved"))
        self.assertEqual(summary["charged_completion_tokens"], 0)
        self.assertEqual(summary["render"]["runtime_network_dependencies"], 0)
        page = (self.output / "index.html").read_text(encoding="utf-8")
        self.assertIn("Synthetic developer fixture", page)
        self.assertIn("id=\"assessment\"", page)

    def test_mocked_generation_accounts_usage_and_uses_supplied_model(self):
        report = {"attempts": 1, "stage": "call2", "usage": {"prompt_tokens": 120, "completion_tokens": 300, "total_tokens": 420}}
        with patch(MODULE + "._generate", return_value=(self.experience, report)) as provider:
            code = build(self.handoff["input"], self.output, model="test/model", key="fake-key", from_content=self.handoff_path)
        self.assertEqual(code, 0)
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(provider.call_args.kwargs["model"], "test/model")
        summary = json.loads((self.output / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual((summary["attempts"], summary["charged_completion_tokens"]), (1, 300))
        self.assertEqual(summary["usage"]["total_tokens"], 420)
        events = [json.loads(line) for line in (self.output / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
        call_events = [event for event in events if event["action"] == "api_finished"]
        self.assertEqual(len(call_events), 1)
        self.assertEqual(call_events[0]["usage"], report["usage"])
        self.assertEqual(call_events[0]["stage"], "call2")

    def test_explicit_review_notes_revise_saved_candidate_in_one_bounded_call(self):
        input_path = self.saved / "input.json"
        notes_path = self.saved / "review.txt"
        write_json(input_path, self.handoff["input"])
        notes_path.write_text("Clarify the introduction as an equal-weight special case.", encoding="utf-8")
        revised = "Synthetic fixture: explore the equal-weight special case."
        report = {"attempts": 1, "stage": "call2-repair",
                  "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}
        with patch(MODULE + "._load_api_key", return_value="fake-key"), \
                patch(MODULE + "._generate", return_value=({"patches": [{"path": "/introduction", "value": revised}]}, report)) as provider, \
                redirect_stdout(io.StringIO()):
            code = main(["--input", str(input_path), "--output", str(self.output), "--model", "test/model",
                         "--from-content", str(self.handoff_path), "--experience", str(self.experience_path),
                         "--review-notes", str(notes_path)])
        self.assertEqual(code, 0)
        provider.assert_called_once()
        self.assertEqual(provider.call_args.kwargs["stage"], "call2-repair")
        self.assertEqual(provider.call_args.kwargs["max_tokens"], 2000)
        self.assertIn(notes_path.read_text(encoding="utf-8"), provider.call_args.kwargs["extra_text"])
        self.assertEqual(json.loads((self.output / "experience.json").read_text(encoding="utf-8"))["introduction"], revised)
        self.assertEqual(json.loads(self.experience_path.read_text(encoding="utf-8")), self.experience)
        summary = json.loads((self.output / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual((summary["run_kind"], summary["attempts"]), ("review_experience", 1))

    def test_unresolved_repair_never_publishes_a_page_or_retries_again(self):
        invalid = deepcopy(self.experience)
        invalid["sections"][0]["section_id"] = "not_a_section"
        report = {"attempts": 1, "usage": {"completion_tokens": 100}}
        with patch(MODULE + "._generate", side_effect=[(invalid, report), ({"patches": []}, report)]) as provider:
            code = build(self.handoff["input"], self.output, model="test/model", key="fake-key", from_content=self.handoff_path)
        self.assertEqual(code, 4)
        self.assertEqual(provider.call_count, 2)
        self.assertEqual(provider.call_args.kwargs["stage"], "call2-repair")
        self.assertFalse((self.output / "index.html").exists())
        self.assertTrue((self.output / "call2-candidate.json").is_file())
        self.assertTrue((self.output / "call2-repair.json").is_file())
        self.assertEqual(json.loads((self.output / "summary.json").read_text(encoding="utf-8"))["status"], "failed")

    def test_failed_attempt_without_usage_remains_charged_and_reviewable(self):
        error = ProviderError("Provider timed out", report={"attempts": 1, "stage": "call2", "usage": None})
        with patch(MODULE + "._generate", side_effect=error) as provider:
            code = build(self.handoff["input"], self.output, model="test/model", key="fake-key", from_content=self.handoff_path)
        self.assertEqual(code, 4)
        self.assertEqual(provider.call_count, 1)
        summary = json.loads((self.output / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual((summary["attempts"], summary["charged_completion_tokens"]), (1, 7000))
        self.assertIsNone(summary["usage"])
        self.assertFalse((self.output / "index.html").exists())
        events = [json.loads(line) for line in (self.output / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
        call_events = [event for event in events if event["action"] == "api_finished"]
        self.assertEqual(len(call_events), 1)
        self.assertIsNone(call_events[0]["usage"])
        self.assertEqual(call_events[0]["attempts"], 1)


if __name__ == "__main__":
    unittest.main()
