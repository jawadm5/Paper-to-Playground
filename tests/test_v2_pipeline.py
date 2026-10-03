"""End-to-end orchestration boundaries with a mocked single provider response."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from playground_v2.cli import main
from playground_v2.pipeline import run, write_json

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "docs" / "v2"


class V2PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = json.loads((FIXTURES / "examples" / "input.json").read_text(encoding="utf-8"))
        self.context = json.loads((FIXTURES / "examples" / "call1-input.json").read_text(encoding="utf-8"))
        self.handoff = json.loads((FIXTURES / "examples" / "paper_content.json").read_text(encoding="utf-8"))
        self.source = self.handoff["source"]
        self.content = self.handoff["content"]

    def output(self, name):
        path = self.root / name
        path.mkdir()
        return path

    def test_identifier_casing_is_recorded_without_a_model_repair(self):
        candidate = deepcopy(self.content)
        identifier = candidate["concepts"][0]["id"]
        candidate["concepts"][0]["id"] = identifier.upper()
        for relationship in candidate["relationships"]:
            for key in ("from", "to"):
                if relationship[key] == identifier:
                    relationship[key] = identifier.upper()
        out = self.output("normalized")
        with patch("playground_v2.pipeline.prepare_in_worker", return_value=(self.context, self.source)), \
                patch("playground_v2.pipeline.generate_content", return_value=(candidate, {"attempts": 1})), \
                patch("playground_v2.pipeline.generate_patch") as repair_call:
            self.assertEqual(run(self.case, out, model="chosen/model", key="secret"), 0)
        repair_call.assert_not_called()
        self.assertEqual(json.loads((out / "paper_content.json").read_text(encoding="utf-8")), self.handoff)
        self.assertEqual(json.loads((out / "call1-content.json").read_text(encoding="utf-8")), candidate)
        self.assertTrue((out / "call1-id-normalization.json").is_file())

    def test_single_call_produces_exact_validated_handoff(self):
        out = self.output("success")
        report = {"attempts": 1, "usage": {"completion_tokens": 200}}
        with patch("playground_v2.pipeline.prepare_in_worker", return_value=(self.context, self.source)), \
                patch("playground_v2.pipeline.generate_content", return_value=(self.content, report)) as provider:
            self.assertEqual(run(self.case, out, model="chosen/model", key="secret"), 0)
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(provider.call_args.kwargs["model"], "chosen/model")
        self.assertEqual(json.loads((out / "paper_content.json").read_text(encoding="utf-8")), self.handoff)
        summary = json.loads((out / "summary.json").read_text())
        self.assertEqual(summary["status"], "complete")
        self.assertEqual(summary["scientific_review"], "not_run")

    def test_invalid_content_preserved_without_final_handoff(self):
        out = self.output("invalid")
        candidate = deepcopy(self.content)
        candidate["concepts"][0]["section_id"] = "invented_section"
        with patch("playground_v2.pipeline.prepare_in_worker", return_value=(self.context, self.source)), \
                patch("playground_v2.pipeline.generate_content", return_value=(candidate, {"attempts": 1})):
            self.assertEqual(run(self.case, out, model="chosen/model", key="secret", repair=False), 4)
        self.assertTrue((out / "call1-content.json").exists())
        self.assertFalse((out / "paper_content.json").exists())
        self.assertEqual(json.loads((out / "summary.json").read_text())["attempts"], 1)

    def test_prepare_only_cli_needs_no_key_and_does_not_call_model(self):
        input_path = self.root / "case.json"
        # Extra values are discarded, not stored in the trace.
        write_json(input_path, {**self.case, "ignored_secret": "never-log-this"})
        out = self.root / "prepared"
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}), \
                patch("playground_v2.pipeline.prepare_in_worker", return_value=(self.context, self.source)), \
                patch("playground_v2.pipeline.generate_content") as provider:
            self.assertEqual(main(["--input", str(input_path), "--output", str(out), "--prepare-only"]), 0)
        provider.assert_not_called()
        summary = json.loads((out / "summary.json").read_text())
        self.assertEqual(summary["status"], "prepared")
        self.assertNotIn("never-log-this", (out / "trace.jsonl").read_text())
        self.assertEqual(json.loads((out / "input.json").read_text()), self.case)

    def test_prepared_reuse_skips_retrieval_and_checks_case(self):
        prepared = self.output("prepared")
        for name, value in (("input.json", self.case), ("call1-input.json", self.context), ("source.json", self.source)):
            write_json(prepared / name, value)
        out = self.output("reuse")
        with patch("playground_v2.pipeline.prepare_in_worker") as retrieval, \
                patch("playground_v2.pipeline.generate_content", return_value=(self.content, {"attempts": 1})):
            self.assertEqual(run(self.case, out, model="chosen/model", key="secret", prepared_dir=prepared), 0)
        retrieval.assert_not_called()
        changed = {**self.case, "audience": "A different audience"}
        with patch("playground_v2.pipeline.generate_content") as provider:
            self.assertEqual(run(changed, self.output("mismatch"), model="chosen/model", key="secret", prepared_dir=prepared), 4)
        provider.assert_not_called()

    def test_existing_output_and_invalid_limits_do_not_start_work(self):
        input_path = self.root / "case.json"
        write_json(input_path, self.case)
        out = self.output("existing")
        (out / "keep.txt").write_text("keep")
        with patch("playground_v2.cli.run") as runner:
            self.assertEqual(main(["--input", str(input_path), "--output", str(out), "--prepare-only"]), 2)
            self.assertEqual(main(["--input", str(input_path), "--output", str(self.root / "bad"),
                                   "--prepare-only", "--call-timeout", "nan"]), 2)
        runner.assert_not_called()
        self.assertEqual((out / "keep.txt").read_text(), "keep")

    def test_corrupt_prepared_metadata_reports_failed_before_provider(self):
        prepared = self.output("corrupt")
        for name, value in (("input.json", self.case), ("call1-input.json", self.context), ("source.json", [])):
            write_json(prepared / name, value)
        out = self.output("corrupt-result")
        with patch("playground_v2.pipeline.generate_content") as provider:
            self.assertEqual(run(self.case, out, model="chosen/model", key="secret", prepared_dir=prepared), 4)
        provider.assert_not_called()
        self.assertEqual(json.loads((out / "summary.json").read_text())["status"], "failed")

    def test_prepared_reuse_cannot_ignore_lower_image_limits(self):
        from PIL import Image
        prepared = self.output("image-prepared")
        (prepared / "assets").mkdir()
        Image.new("RGB", (8, 8), "white").save(prepared / "assets" / "v1.png")
        source, context = deepcopy(self.source), deepcopy(self.context)
        source["visuals"][0].update(provided_as="image_and_caption", asset_path="assets/v1.png", mime_type="image/png")
        context["visuals"][0]["provided_as"] = "image_and_caption"
        for name, value in (("input.json", self.case), ("call1-input.json", context), ("source.json", source)):
            write_json(prepared / name, value)
        out = self.output("image-limit")
        with patch("playground_v2.pipeline.generate_content") as provider:
            self.assertEqual(run(self.case, out, model="chosen/model", key="secret",
                                 prepared_dir=prepared, max_images=0), 4)
        provider.assert_not_called()
        self.assertIn("exceeds", json.loads((out / "summary.json").read_text())["error"])

    def test_one_targeted_repair_is_revalidated_and_accounted(self):
        out = self.output("repair")
        candidate = deepcopy(self.content)
        correct = candidate["concepts"][0]["section_id"]
        candidate["concepts"][0]["section_id"] = "missing_section"
        patch_data = {"patches": [{"path": "/concepts/0/section_id", "value": correct}]}
        with patch("playground_v2.pipeline.prepare_in_worker", return_value=(self.context, self.source)), \
                patch("playground_v2.pipeline.generate_content", return_value=(candidate, {"attempts": 1, "usage": {"completion_tokens": 200}})), \
                patch("playground_v2.pipeline.generate_patch", return_value=(patch_data, {"attempts": 1, "usage": {"completion_tokens": 20}})) as repair_call:
            self.assertEqual(run(self.case, out, model="chosen/model", key="secret"), 0)
        repair_call.assert_called_once()
        self.assertEqual(repair_call.call_args.kwargs["model"], "chosen/model")
        self.assertEqual(json.loads((out / "paper_content.json").read_text(encoding="utf-8")), self.handoff)
        self.assertEqual(json.loads((out / "call1-content.json").read_text(encoding="utf-8")), candidate)
        summary = json.loads((out / "summary.json").read_text())
        self.assertEqual(summary["attempts"], 2)
        self.assertEqual(summary["usage"]["completion_tokens"], 220)

    def test_unresolved_repair_does_not_publish_or_repeat(self):
        out = self.output("unresolved")
        candidate = deepcopy(self.content)
        candidate["concepts"][0]["section_id"] = "missing_section"
        with patch("playground_v2.pipeline.prepare_in_worker", return_value=(self.context, self.source)), \
                patch("playground_v2.pipeline.generate_content", return_value=(candidate, {"attempts": 1})), \
                patch("playground_v2.pipeline.generate_patch", return_value=({"patches": []}, {"attempts": 1})) as repair_call:
            self.assertEqual(run(self.case, out, model="chosen/model", key="secret"), 4)
        repair_call.assert_called_once()
        self.assertFalse((out / "paper_content.json").exists())

    def test_saved_candidate_review_skips_full_generation_and_targets_exact_boundary(self):
        out = self.output("candidate-review")
        candidate = deepcopy(self.content)
        candidate["sections"][3]["boundaries"][2]["kind"] = "missing_information"
        path = self.root / "candidate.json"
        write_json(path, candidate)
        replacements = {"patches": [{"path": "/sections/3/boundaries/2/kind", "value": "limitation"}]}
        with patch("playground_v2.pipeline.prepare_in_worker", return_value=(self.context, self.source)), \
                patch("playground_v2.pipeline.generate_content") as initial_call, \
                patch("playground_v2.pipeline.generate_patch", return_value=(replacements, {"attempts": 1})) as repair_call:
            self.assertEqual(run(self.case, out, model="chosen/model", key="secret", candidate_path=path), 0)
        initial_call.assert_not_called()
        self.assertIn("/sections/3/boundaries/2", repair_call.call_args.args[1])
        summary = json.loads((out / "summary.json").read_text())
        self.assertEqual(summary["run_kind"], "candidate_review")
        self.assertEqual(summary["attempts"], 1)

    def test_source_review_feedback_revises_valid_candidate_without_regeneration(self):
        out = self.output("source-review")
        candidate_path = self.root / "valid-candidate.json"
        write_json(candidate_path, self.content)
        notes = self.root / "review.txt"
        notes.write_text("Clarify the title without changing claims.")
        replacements = {"patches": [{"path": "/title", "value": "A clarified teaching title"}]}
        with patch("playground_v2.pipeline.prepare_in_worker", return_value=(self.context, self.source)), \
                patch("playground_v2.pipeline.generate_content") as initial_call, \
                patch("playground_v2.pipeline.generate_patch", return_value=(replacements, {"attempts": 1})) as repair_call:
            self.assertEqual(run(self.case, out, model="chosen/model", key="secret",
                                 candidate_path=candidate_path, review_notes=notes), 0)
        initial_call.assert_not_called()
        self.assertIn("Clarify the title", repair_call.call_args.args[1])
        self.assertEqual(json.loads((out / "paper_content.json").read_text(encoding="utf-8"))["content"]["title"],
                         "A clarified teaching title")


if __name__ == "__main__":
    unittest.main()
