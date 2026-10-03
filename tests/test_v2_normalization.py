from copy import deepcopy
import unittest

from playground_v2.normalization import normalize_content_ids
from playground_v2.validation import ValidationError


class ContentIdNormalizationTests(unittest.TestCase):
    def fixture(self):
        return {
            "title": "Keep Q, OUT and Eq unchanged in prose.",
            "learning_outcomes": [{"id": "Learn_1", "description": "Calculate Q."}],
            "sections": [
                {"id": "Intro", "parent_id": None, "learning_outcome_ids": ["Learn_1"],
                 "source_refs": ["Intro", "Q"], "visual_ids": ["Intro"],
                 "connections": [{"section_id": "Method", "explanation": "See Method."}]},
                {"id": "Method", "parent_id": "Intro", "learning_outcome_ids": ["Learn_1"],
                 "mathematical_model": {
                     "variables": [{"id": "Q", "notation": "Q"}, {"id": "OUT", "notation": "OUT"}],
                     "equations": [{"id": "Eq", "latex": "OUT = Q", "variable_ids": ["Q", "OUT"], "source_refs": ["Q"]}],
                     "steps": [{"input_ids": ["Q"], "output_ids": ["OUT"], "equation_ids": ["Eq"]}],
                 }},
            ],
            "concepts": [{"id": "Query", "section_id": "Intro"}, {"id": "Result", "section_id": "Method"}],
            "relationships": [{"from": "Query", "to": "Result", "label": "Q becomes OUT", "source_refs": ["Eq"]}],
        }

    def test_safe_definition_casing_updates_typed_references_and_audits_without_mutation(self):
        original = self.fixture()
        before = deepcopy(original)
        result, changes = normalize_content_ids(original)
        self.assertEqual(original, before)
        self.assertEqual(result["learning_outcomes"][0]["id"], "learn_1")
        self.assertEqual(result["sections"][1]["parent_id"], "intro")
        self.assertEqual(result["sections"][0]["connections"][0]["section_id"], "method")
        self.assertEqual(result["concepts"][0]["section_id"], "intro")
        self.assertEqual(result["relationships"][0]["from"], "query")
        model = result["sections"][1]["mathematical_model"]
        self.assertEqual(model["steps"][0], {"input_ids": ["q"], "output_ids": ["out"], "equation_ids": ["eq"]})
        self.assertEqual(model["equations"][0]["variable_ids"], ["q", "out"])
        self.assertIn({"path": "/sections/1/mathematical_model/steps/0/input_ids/0", "before": "Q", "after": "q"}, changes)
        self.assertTrue(all(set(change) == {"path", "before", "after"} for change in changes))
        again, second_changes = normalize_content_ids(result)
        self.assertEqual(again, result)
        self.assertEqual(second_changes, [])

    def test_case_distinct_ids_are_disambiguated_with_their_typed_references(self):
        content = self.fixture()
        model = content["sections"][1]["mathematical_model"]
        model["variables"].extend([{"id": "q", "notation": "q"}, {"id": "q_2", "notation": "q_2"}])
        model["equations"][0].update(latex="Q = q + q_2", variable_ids=["Q", "q", "q_2"])
        model["steps"][0].update(input_ids=["Q", "q", "q_2"])
        before = deepcopy(content)
        result, changes = normalize_content_ids(content)
        self.assertEqual(content, before)
        normalized = result["sections"][1]["mathematical_model"]
        self.assertEqual([v["id"] for v in normalized["variables"]], ["q_3", "out", "q", "q_2"])
        self.assertEqual(normalized["equations"][0]["variable_ids"], ["q_3", "q", "q_2"])
        self.assertEqual(normalized["steps"][0]["input_ids"], ["q_3", "q", "q_2"])
        self.assertEqual(normalized["equations"][0]["latex"], "Q = q + q_2")
        self.assertEqual([v["notation"] for v in normalized["variables"]], ["Q", "OUT", "q", "q_2"])
        self.assertEqual(result["sections"][0]["source_refs"], ["Intro", "Q"])
        self.assertEqual(normalize_content_ids(result), (result, []))
        self.assertTrue(changes)

    def test_suffixes_respect_length_and_reserve_later_canonical_names(self):
        base = "a" * 64
        reserved = "a" * 62 + "_2"
        content = {"concepts": [{"id": base.upper()}, {"id": base}, {"id": reserved}]}
        result, _ = normalize_content_ids(content)
        ids = [c["id"] for c in result["concepts"]]
        self.assertEqual(ids, ["a" * 62 + "_3", base, reserved])
        self.assertTrue(all(len(identifier) <= 64 for identifier in ids))
        self.assertEqual(normalize_content_ids(result), (result, []))

    def test_identical_duplicates_remain_ambiguous_for_validation(self):
        content = {"concepts": [{"id": "Q"}, {"id": "Q"}, {"id": "q"}]}
        result, _ = normalize_content_ids(content)
        self.assertEqual([c["id"] for c in result["concepts"]], ["q_2", "q_2", "q"])

    def test_prose_external_refs_and_syntactically_unsafe_ids_remain_exact(self):
        content = self.fixture()
        content["sections"][0]["paper_explanation"] = "Q → OUT; https://example.org/Intro?Q=Eq"
        content["concepts"].append({"id": "Bad-ID", "section_id": "MissingSection"})
        content["concepts"].append({"id": "Éclair", "section_id": "Method"})
        result, changes = normalize_content_ids(content)
        self.assertEqual(result["title"], content["title"])
        self.assertEqual(result["sections"][0]["paper_explanation"], content["sections"][0]["paper_explanation"])
        self.assertEqual(result["sections"][0]["source_refs"], ["Intro", "Q"])
        self.assertEqual(result["sections"][0]["visual_ids"], ["Intro"])
        self.assertEqual(result["relationships"][0]["source_refs"], ["Eq"])
        self.assertEqual(result["relationships"][0]["label"], "Q becomes OUT")
        model = result["sections"][1]["mathematical_model"]
        self.assertEqual(model["variables"][0]["notation"], "Q")
        self.assertEqual(model["equations"][0]["latex"], "OUT = Q")
        self.assertEqual(model["equations"][0]["source_refs"], ["Q"])
        self.assertEqual(result["concepts"][-2], {"id": "Bad-ID", "section_id": "MissingSection"})
        self.assertEqual(result["concepts"][-1]["id"], "Éclair")
        self.assertFalse(any("source_refs" in item["path"] or "visual_ids" in item["path"] for item in changes))


if __name__ == "__main__":
    unittest.main()
