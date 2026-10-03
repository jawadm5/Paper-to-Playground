from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from playground_v2.validation import (
    ValidationError, load_schema, validate_content, validate_context,
    validate_handoff, validate_input, validate_source,
)


BASE = Path(__file__).resolve().parents[1] / "docs" / "v2"


def read(relative):
    return json.loads((BASE / relative).read_text(encoding="utf-8"))


class V2ValidationTests(unittest.TestCase):
    def setUp(self):
        self.case = read("examples/input.json")
        self.context = read("examples/call1-input.json")
        self.content = read("call1-output.example.json")
        self.handoff = read("examples/paper_content.json")

    def model(self, content=None):
        return next(section["mathematical_model"] for section in (content or self.content)["sections"] if "mathematical_model" in section)

    def test_authoritative_fixture_and_normalized_external_input(self):
        expanded = {**self.case, "focus": "  " + self.case["focus"] + "\n", "ignored_private_field": "not copied"}
        self.assertEqual(validate_input(expanded), self.case)
        self.assertIsNone(validate_context(self.context))
        self.assertIsNone(validate_content(self.content, self.context))
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(validate_handoff(self.handoff, Path(folder)))
        for name in ("input", "call1-input", "call1-content", "paper-content"):
            self.assertEqual(load_schema(name)["$schema"], "https://json-schema.org/draft/2020-12/schema")
        with self.assertRaises(ValidationError):
            load_schema("../input")

    def test_invalid_inputs_and_duplicate_evidence(self):
        for changes in ({"focus": " \t"}, {"audience": 7}, {"source_url": "https://user:password@example.org/paper"}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                validate_input({**self.case, **changes})
        self.context["source_blocks"].append(deepcopy(self.context["source_blocks"][0]))
        with self.assertRaisesRegex(ValidationError, "duplicate ID"):
            validate_context(self.context)

    def test_unknown_references_are_rejected_at_their_destination(self):
        mutations = [
            lambda c: c["sections"][1]["source_refs"].append("unknown_evidence"),
            lambda c: c["sections"][1]["learning_outcome_ids"].append("unknown_goal"),
            lambda c: c["sections"][1]["visual_ids"].append("unknown_image"),
            lambda c: c["concepts"][0].update(section_id="unknown_section"),
            lambda c: c["relationships"][0].update(to="unknown_concept"),
            lambda c: self.model(c)["equations"][0]["variable_ids"].append("unknown_variable"),
        ]
        for mutate in mutations:
            content = deepcopy(self.content)
            mutate(content)
            with self.subTest(mutation=mutate), self.assertRaisesRegex(ValidationError, "unknown or unavailable"):
                validate_content(content, self.context)

    def test_parent_order_and_step_dependency_order(self):
        for parent in (self.content["sections"][1]["id"], self.content["sections"][-1]["id"], "unknown_parent"):
            content = deepcopy(self.content)
            content["sections"][1]["parent_id"] = parent
            with self.subTest(parent=parent), self.assertRaisesRegex(ValidationError, "earlier section"):
                validate_content(content, self.context)
        self.content["sections"][1]["parent_id"] = self.content["sections"][0]["id"]
        validate_content(self.content, self.context)
        steps = self.model()["steps"]
        steps[0], steps[1] = steps[1], steps[0]
        with self.assertRaisesRegex(ValidationError, "defined before this step"):
            validate_content(self.content, self.context)

    def test_global_math_ids_and_shared_earlier_definitions(self):
        model = self.model()
        output_id = next(v["id"] for v in model["variables"] if v["role"] == "output")
        self.content["sections"][-1]["mathematical_model"] = {
            "variables": [{"id": "revisited_output", "notation": "y'",
                           "meaning": "An output revisited in the later section.",
                           "role": "output", "domain": "Real vector."}],
            "equations": [], "constraints": [],
            "steps": [{"description": "Revisit an output defined by the preceding method.",
                       "input_ids": [output_id], "output_ids": ["revisited_output"],
                       "equation_ids": [model["equations"][-1]["id"]]}],
        }
        validate_content(self.content, self.context)
        self.content["sections"][-1]["mathematical_model"]["variables"].append(deepcopy(model["variables"][0]))
        with self.assertRaisesRegex(ValidationError, "variables across sections: duplicate ID"):
            validate_content(self.content, self.context)

    def test_outcome_and_map_coverage_and_empty_content(self):
        content = deepcopy(self.content)
        content["learning_outcomes"].append({"id": "untaught", "level": "understand", "description": "An untaught objective."})
        with self.assertRaisesRegex(ValidationError, "not covered"):
            validate_content(content, self.context)
        content = deepcopy(self.content)
        content["concepts"].append({"id": "unlinked", "name": "Unlinked", "summary": "An isolated map anchor.", "section_id": content["sections"][0]["id"]})
        with self.assertRaisesRegex(ValidationError, "without a map relationship"):
            validate_content(content, self.context)
        self.content["sections"] = []
        with self.assertRaises(ValidationError):
            validate_content(self.content, self.context)

    def test_paper_sections_need_evidence_and_essential_gaps_block_completion(self):
        content = deepcopy(self.content)
        content["sections"][1]["source_refs"] = []
        with self.assertRaisesRegex(ValidationError, "supporting source_refs"):
            validate_content(content, self.context)
        self.content["sections"][1]["boundaries"].append({
            "kind": "missing_information", "description": "The defining equation is unreadable.",
            "basis": "derived", "source_refs": [],
        })
        with self.assertRaisesRegex(ValidationError, "essential missing information"):
            validate_content(self.content, self.context)

    def test_not_provided_visuals_are_retained_but_cannot_be_cited(self):
        unused = deepcopy(self.handoff["source"]["visuals"][0])
        unused.update(id="unused_visual", provided_as="not_provided")
        self.handoff["source"]["visuals"].append(unused)
        with tempfile.TemporaryDirectory() as folder:
            validate_handoff(self.handoff, Path(folder))
            self.handoff["content"]["sections"][1]["source_refs"].append("unused_visual")
            with self.assertRaisesRegex(ValidationError, "unknown or unavailable"):
                validate_handoff(self.handoff, Path(folder))

    def test_asset_paths_existence_and_actual_mime_are_checked(self):
        visual = self.handoff["source"]["visuals"][0]
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            visual.update(asset_path="assets/../../escape.png", mime_type="image/png")
            with self.assertRaises(ValidationError):
                validate_handoff(self.handoff, output)
            visual["asset_path"] = "assets/figure.png"
            with self.assertRaisesRegex(ValidationError, "must exist inside"):
                validate_handoff(self.handoff, output)
            (output / "assets").mkdir()
            image_path = output / visual["asset_path"]
            image_path.write_bytes(b"This is not an image.")
            with self.assertRaisesRegex(ValidationError, "not a valid supported image"):
                validate_handoff(self.handoff, output)
            Image.new("RGB", (2, 2), (10, 20, 30)).save(image_path)
            visual["mime_type"] = "image/jpeg"
            with self.assertRaisesRegex(ValidationError, "actual image format"):
                validate_handoff(self.handoff, output)
            visual["mime_type"] = "image/png"
            # A saved image can legitimately be retained for rendering even if
            # only its caption was supplied to call 1.
            validate_handoff(self.handoff, output)
            visual["provided_as"] = "image_and_caption"
            validate_handoff(self.handoff, output)
            visual["provided_as"] = "image_only"
            with self.assertRaises(ValidationError):
                validate_handoff(self.handoff, output)

    def test_source_preflight_rejects_bad_metadata_and_assets_without_content(self):
        source = self.handoff["source"]
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            validate_source(source, output)
            malformed = deepcopy(source)
            del malformed["references"]
            with self.assertRaisesRegex(ValidationError, "HandoffSource contract"):
                validate_source(malformed, output)
            duplicate = deepcopy(source)
            duplicate["references"].append(deepcopy(source["references"][0]))
            with self.assertRaisesRegex(ValidationError, "duplicate ID"):
                validate_source(duplicate, output)
            source["visuals"][0].update(asset_path="assets/corrupt.png", mime_type="image/png")
            (output / "assets").mkdir()
            (output / "assets" / "corrupt.png").write_bytes(b"Not a PNG image")
            with self.assertRaisesRegex(ValidationError, "not a valid supported image"):
                validate_source(source, output)


if __name__ == "__main__":
    unittest.main()
