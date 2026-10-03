"""Focused Call 1 transport checks; no real network calls or credentials."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from playground_v2.provider import PATCH_SCHEMA, ProviderError, generate_content, generate_patch

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=")
TEST_KEY = "sk-test-private-key-never-a-real-credential"


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name) / "out"
        (self.output / "assets").mkdir(parents=True)
        (self.output / "assets/v0001.png").write_bytes(PNG)
        self.prompt = Path(self.tmp.name) / "prompt.md"
        self.prompt.write_text("Write faithful learning content. Return bare JSON.", encoding="utf-8")
        locator = {"section": "Synthetic section", "page": 1, "equation": None, "figure": None}
        visual = {"id": "v0001", "kind": "page_image", "caption": "Synthetic image fixture",
                  "locator": locator, "provided_as": "image_and_caption"}
        self.context = {"focus": "Explain a synthetic mechanism", "audience": "Undergraduate",
                        "source_blocks": [{"id": "s1", "kind": "paragraph", "locator": locator,
                                           "text": "Synthetic evidence for a transport test."}],
                        "visuals": [visual], "extraction_warnings": []}
        self.source = {"visuals": [dict(visual, asset_path="assets/v0001.png", mime_type="image/png")]}
        self.schema = {"type": "object", "properties": {"title": {"type": "string"}}}
        self.schema_patch = patch("playground_v2.provider.load_schema", return_value=self.schema)
        self.schema_patch.start()
        self.addCleanup(self.schema_patch.stop)

    def call(self, **kwargs):
        arguments = {"model": "test/vision-model", "key": TEST_KEY,
                     "prompt_path": self.prompt, "max_tokens": 14000, "timeout": 10.0}
        arguments.update(kwargs)
        return generate_content(self.context, self.source, self.output, **arguments)

    @staticmethod
    def response(content='{"title":"A learning narrative"}', **changes):
        result = {"status": 200, "id": "request_fixture", "content": content,
                  "finish_reason": "stop", "usage": {"prompt_tokens": 120, "completion_tokens": 80,
                  "total_tokens": 200, "completion_tokens_details": {"reasoning_tokens": 0,
                  "reasoning": "PRIVATE-HIDDEN-REASONING"}, "reasoning": "PRIVATE-HIDDEN-REASONING"},
                  "reasoning": "PRIVATE-HIDDEN-REASONING"}
        result.update(changes)
        return result

    def read(self, path):
        return json.loads((self.output / path).read_text(encoding="utf-8"))

    def repair(self, content=None, diagnostic="Invalid basis metadata", **kwargs):
        arguments = {"model": "test/vision-model", "key": TEST_KEY, "prompt_path": self.prompt}
        arguments.update(kwargs)
        return generate_patch(content or {"sections": [{"boundaries": [{"basis": "incorrect"}]}]},
                              diagnostic, self.context, self.source, self.output, **arguments)

    def test_exact_reviewable_request_attaches_actual_image_and_preserves_accounting(self):
        with patch("playground_v2.provider.run_worker", return_value=self.response()) as worker:
            content, report = self.call()
        worker.assert_called_once()
        kind, transport, timeout = worker.call_args.args
        request = self.read("requests/call1.json")
        self.assertEqual(kind, "http")
        self.assertEqual(transport["key"], TEST_KEY)
        self.assertEqual(request, transport["payload"])
        self.assertGreater(timeout, 0)
        self.assertLessEqual(timeout, 10)
        self.assertEqual(request["model"], "test/vision-model")
        self.assertEqual(request["provider"], {"require_parameters": True})
        self.assertEqual(request["temperature"], 0.2)
        self.assertEqual(request["max_completion_tokens"], 14000)
        self.assertEqual(request["reasoning"], {"enabled": False, "exclude": True})
        self.assertEqual(request["response_format"], {"type": "json_object"})
        parts = request["messages"][1]["content"]
        self.assertIn('"source_blocks"', parts[0]["text"])
        self.assertIn(json.dumps(self.schema, indent=2), parts[1]["text"])
        self.assertIn("finished, paper-specific", parts[1]["text"])
        self.assertIn("v0001", parts[2]["text"])
        data_url = parts[3]["image_url"]["url"]
        self.assertTrue(data_url.startswith("data:image/png;base64,"))
        self.assertEqual(base64.b64decode(data_url.split(",", 1)[1]), PNG)
        self.assertEqual(content["title"], "A learning narrative")
        self.assertEqual(report["attempts"], 1)
        self.assertEqual(report["status"], "success")
        self.assertEqual(report["response_format"], "json_object")
        self.assertEqual(report["attached_image_ids"], ["v0001"])
        self.assertEqual(report["usage"]["total_tokens"], 200)
        self.assertEqual(report, self.read("reports/call1.json"))
        persisted = "\n".join(path.read_text(encoding="utf-8") for folder in ("requests", "responses", "reports") for path in (self.output / folder).glob("*.json"))
        self.assertNotIn(TEST_KEY, persisted)
        self.assertNotIn("PRIVATE-HIDDEN-REASONING", persisted)

    def test_repair_provenance_annotations_are_preserved_but_not_operations(self):
        returned = {"patches": [{"path": "/title", "value": "Corrected title",
                                 "basis": "source_supported", "source_refs": ["s1"]}]}
        with patch("playground_v2.provider.run_worker", return_value=self.response(json.dumps(returned))):
            canonical, report = self.repair()
        self.assertEqual(canonical, {"patches": [{"path": "/title", "value": "Corrected title"}]})
        self.assertEqual(report["patch_annotations"][0]["source_refs"], ["s1"])
        self.assertEqual(json.loads(self.read("responses/call1-repair.json")["content"]), returned)
        returned["patches"][0]["op"] = "remove"
        with patch("playground_v2.provider.run_worker", return_value=self.response(json.dumps(returned))):
            with self.assertRaises(ProviderError):
                self.repair()

    def test_editable_prompt_is_loaded_on_every_invocation(self):
        with patch("playground_v2.provider.run_worker", return_value=self.response()) as worker:
            self.call()
            self.prompt.write_text("A refined, explicit prompt.", encoding="utf-8")
            self.call()
        self.assertEqual(worker.call_count, 2)
        self.assertEqual(self.read("requests/call1.json")["messages"][0]["content"], "A refined, explicit prompt.")

    def test_caption_only_visual_does_not_imply_an_image_attachment(self):
        self.context["visuals"][0]["provided_as"] = "caption_only"
        self.source["visuals"][0].update(provided_as="caption_only", asset_path=None, mime_type=None)
        with patch("playground_v2.provider.run_worker", return_value=self.response()):
            _, report = self.call()
        self.assertEqual(report["attached_image_ids"], [])
        self.assertEqual(len(self.read("requests/call1.json")["messages"][1]["content"]), 2)

    def test_json_schema_is_explicit_opt_in_and_schema_text_is_still_visible(self):
        with patch("playground_v2.provider.run_worker", return_value=self.response()) as worker:
            _, report = self.call(response_format="json_schema")
        worker.assert_called_once()
        request = self.read("requests/call1.json")
        self.assertEqual(request["response_format"]["type"], "json_schema")
        self.assertEqual(request["response_format"]["json_schema"]["schema"], self.schema)
        self.assertFalse(request["response_format"]["json_schema"]["strict"])
        self.assertIn(json.dumps(self.schema, indent=2), request["messages"][1]["content"][1]["text"])
        self.assertEqual(report["response_format"], "json_schema")

    def test_unknown_response_format_fails_before_provider_attempt(self):
        with patch("playground_v2.provider.run_worker") as worker:
            with self.assertRaises(ProviderError) as caught:
                self.call(response_format="automatic")
        worker.assert_not_called()
        self.assertEqual(caught.exception.report["attempts"], 0)
        self.assertEqual(caught.exception.report["error_code"], "request_preparation")

    def test_literal_credential_in_text_is_redacted_before_transport_and_persistence(self):
        self.context["source_blocks"][0]["text"] += " Accidental literal: " + TEST_KEY
        with patch("playground_v2.provider.run_worker", return_value=self.response(json.dumps({"title": TEST_KEY}))) as worker:
            content, report = self.call()
        self.assertNotIn(TEST_KEY, json.dumps(worker.call_args.args[1]["payload"]))
        self.assertEqual(content["title"], "[REDACTED]")
        self.assertNotIn(TEST_KEY, json.dumps(self.read("responses/call1.json")))

    def test_invalid_json_fences_duplicates_nonfinite_and_nonobject_are_rejected(self):
        for text in ('not JSON', '```json\n{"title":"x"}\n```', '{"x":1,"x":2}',
                     '{"x":NaN}', '{"x":1e999}', '["not an object"]'):
            with self.subTest(text=text), patch("playground_v2.provider.run_worker", return_value=self.response(text)) as worker:
                with self.assertRaises(ProviderError) as caught:
                    self.call()
                worker.assert_called_once()
                self.assertEqual(caught.exception.report["error_code"], "invalid_json")
                self.assertEqual(caught.exception.report["status"], "failed")
                self.assertEqual(self.read("responses/call1.json")["content"], text)
                self.assertEqual(self.read("reports/call1.json")["attempts"], 1)

    def test_truncation_rejects_even_a_parseable_json_object(self):
        with patch("playground_v2.provider.run_worker", return_value=self.response(finish_reason="length")) as worker:
            with self.assertRaises(ProviderError) as caught:
                self.call()
        worker.assert_called_once()
        self.assertEqual(caught.exception.report["error_code"], "truncated")
        self.assertEqual(caught.exception.report["usage"]["completion_tokens"], 80)
        self.assertEqual(self.read("responses/call1.json")["finish_reason"], "length")

    def test_unsupported_structured_parameters_fail_without_fallback(self):
        with patch("playground_v2.provider.run_worker", return_value=self.response(status=400, content=None, format_unsupported=True)) as worker:
            with self.assertRaises(ProviderError) as caught:
                self.call(response_format="json_schema")
        worker.assert_called_once()
        self.assertEqual(caught.exception.report["error_code"], "structured_parameters_unsupported")
        self.assertIn("No fallback", str(caught.exception))
        self.assertEqual(self.read("requests/call1.json")["response_format"]["type"], "json_schema")

    def test_timeout_preserves_failed_attempt_and_response_snapshot(self):
        with patch("playground_v2.provider.run_worker", side_effect=TimeoutError) as worker:
            with self.assertRaises(ProviderError) as caught:
                self.call()
        worker.assert_called_once()
        self.assertEqual(caught.exception.report["error_code"], "total_timeout")
        self.assertEqual(caught.exception.report["attempts"], 1)
        self.assertIsNone(caught.exception.report["usage"])
        self.assertEqual(self.read("responses/call1.json")["status"], 0)

    def test_unreadable_or_escaping_image_is_not_silently_skipped(self):
        for asset in ("assets/missing.png", "../outside.png"):
            with self.subTest(asset=asset):
                (Path(self.tmp.name) / "outside.png").write_bytes(PNG)
                self.source["visuals"][0]["asset_path"] = asset
                with patch("playground_v2.provider.run_worker") as worker:
                    with self.assertRaises(ProviderError) as caught:
                        self.call()
                worker.assert_not_called()
                self.assertEqual(caught.exception.report["attempts"], 0)
                self.assertEqual(caught.exception.report["error_code"], "request_preparation")
                self.assertEqual(self.read("reports/call1.json")["status"], "failed")

    def test_image_content_must_match_declared_media_type(self):
        self.source["visuals"][0]["mime_type"] = "image/jpeg"
        with patch("playground_v2.provider.run_worker") as worker:
            with self.assertRaises(ProviderError) as caught:
                self.call()
        worker.assert_not_called()
        self.assertIn("mismatched image bytes", str(caught.exception))

    def test_patch_uses_separate_stage_snapshots_full_evidence_and_bounded_transport(self):
        candidate = {"sections": [{"boundaries": [{"basis": "incorrect"}]}]}
        original_candidate = deepcopy(candidate)
        patch_object = {"patches": [{"path": "/sections/0/boundaries/0/basis", "value": "derived"}]}
        with patch("playground_v2.provider.run_worker", return_value=self.response()):
            self.call()
        original_files = {folder: (self.output / folder / "call1.json").read_bytes()
                          for folder in ("requests", "responses", "reports")}
        with patch("playground_v2.provider.run_worker", return_value=self.response(json.dumps(patch_object))) as worker:
            result, report = self.repair(candidate, diagnostic={"path": "/sections/0/boundaries/0/basis", "message": "Invalid metadata"})
        worker.assert_called_once()
        self.assertEqual(result, patch_object)
        self.assertEqual(candidate, original_candidate)
        self.assertEqual(report["stage"], "call1-repair")
        self.assertEqual(report["attempts"], 1)
        self.assertEqual(report["attached_image_ids"], ["v0001"])
        transport = worker.call_args.args[1]
        request = self.read("requests/call1-repair.json")
        self.assertEqual(request, transport["payload"])
        self.assertEqual(request["max_completion_tokens"], 2000)
        self.assertLessEqual(worker.call_args.args[2], 60)
        parts = request["messages"][1]["content"]
        self.assertIn('"source_blocks"', parts[0]["text"])
        self.assertIn(json.dumps(PATCH_SCHEMA, indent=2), parts[1]["text"])
        self.assertIn('"candidate"', parts[2]["text"])
        self.assertIn('"diagnostic"', parts[2]["text"])
        self.assertIn("v0001", parts[3]["text"])
        self.assertEqual(base64.b64decode(parts[4]["image_url"]["url"].split(",", 1)[1]), PNG)
        for folder, before in original_files.items():
            self.assertEqual((self.output / folder / "call1.json").read_bytes(), before)
            self.assertTrue((self.output / folder / "call1-repair.json").exists())

    def test_patch_shape_rejects_wrong_operations_and_accepts_no_justified_changes(self):
        bad_values = [
            {"title": "A rewritten candidate"},
            {"patches": [{"path": "/title", "value": "x", "op": "replace"}]},
            {"patches": [{"path": "/title"}]},
            {"patches": [{"path": "", "value": {}}]},
            {"patches": [{"path": "/", "value": {}}]},
            {"patches": [{"path": "/bad~escape", "value": 1}]},
            {"patches": [{"path": "/title", "value": str(i)} for i in range(9)]},
        ]
        for value in bad_values:
            with self.subTest(value=value), patch("playground_v2.provider.run_worker", return_value=self.response(json.dumps(value))) as worker:
                with self.assertRaises(ProviderError) as caught:
                    self.repair()
                worker.assert_called_once()
                self.assertEqual(caught.exception.report["error_code"], "invalid_patch")
                self.assertEqual(caught.exception.report["response_path"], "responses/call1-repair.json")
        with patch("playground_v2.provider.run_worker", return_value=self.response('{"patches":[]}')) as worker:
            value, report = self.repair(response_format="json_schema")
        worker.assert_called_once()
        self.assertEqual(value, {"patches": []})
        self.assertEqual(report["status"], "success")
        schema_request = self.read("requests/call1-repair.json")["response_format"]["json_schema"]
        self.assertEqual(schema_request["name"], "call1_repair")
        self.assertEqual(schema_request["schema"], PATCH_SCHEMA)

    def test_patch_transport_failure_records_its_own_attempt_without_retry(self):
        with patch("playground_v2.provider.run_worker", side_effect=TimeoutError) as worker:
            with self.assertRaises(ProviderError) as caught:
                self.repair()
        worker.assert_called_once()
        self.assertEqual(caught.exception.report["error_code"], "total_timeout")
        self.assertEqual(caught.exception.report["stage"], "call1-repair")
        self.assertEqual(caught.exception.report["attempts"], 1)
        self.assertEqual(self.read("reports/call1-repair.json")["status"], "failed")
        self.assertEqual(self.read("responses/call1-repair.json")["status"], 0)
        self.assertFalse((self.output / "responses/call1.json").exists())


if __name__ == "__main__":
    unittest.main()
