from copy import deepcopy
import unittest

from playground_v2.repair import apply_replacements
from playground_v2.validation import ValidationError


class V2RepairTests(unittest.TestCase):
    def setUp(self):
        self.content = {
            "title": "Original",
            "sections": [{"id": "s1", "boundaries": [{"kind": "missing_information"}]},
                         {"id": "s2", "text": "Original text"}],
            "a/b": {"~field": 1, "~1": "escaped once"},
        }

    def test_replaces_existing_branches_without_mutating_either_input(self):
        before = deepcopy(self.content)
        patch = {"patches": [
            {"path": "/sections/0/boundaries", "value": []},
            {"path": "/sections/1", "value": {"id": "s2", "text": "Repaired"}},
        ]}
        result = apply_replacements(self.content, patch)
        self.assertEqual(result["sections"][0]["boundaries"], [])
        self.assertEqual(result["sections"][1]["text"], "Repaired")
        self.assertEqual(self.content, before)
        result["sections"][1]["text"] = "Later edit"
        self.assertEqual(patch["patches"][1]["value"]["text"], "Repaired")
        result["a/b"]["~field"] = 8
        self.assertEqual(self.content["a/b"]["~field"], 1)

    def test_rfc6901_escapes_and_empty_patch(self):
        result = apply_replacements(self.content, {"patches": [
            {"path": "/a~1b/~0field", "value": 2},
            {"path": "/a~1b/~01", "value": "still escaped once"},
        ]})
        self.assertEqual(result["a/b"], {"~field": 2, "~1": "still escaped once"})
        result = apply_replacements(self.content, {"patches": []})
        self.assertEqual(result, self.content)
        self.assertIsNot(result["sections"], self.content["sections"])

    def test_rejects_invalid_patch_envelopes_and_non_json_values(self):
        invalid = [
            None, [], {}, {"patches": [], "extra": True}, {"patches": {}},
            {"patches": [{"path": "/title", "value": "x", "op": "set"}]},
            {"patches": [{"path": "/title"}]},
            {"patches": [{"path": "/title", "value": float("nan")}]},
            {"patches": [{"path": "/title", "value": {"bad": {1, 2}}}]},
            {"patches": [{"path": "/title", "value": "x"}] * 9},
        ]
        for patch in invalid:
            with self.subTest(patch=patch), self.assertRaises(ValidationError):
                apply_replacements(self.content, patch)

    def test_rejects_root_bad_escapes_new_keys_and_invalid_array_indices(self):
        paths = ["", "title", "/a~2b", "/a~", "/missing", "/missing/title",
                 "/sections/-", "/sections/01", "/sections/+1", "/sections/-1",
                 "/sections/2", "/sections/" + "9" * 5000, "/title/child"]
        before = deepcopy(self.content)
        for path in paths:
            with self.subTest(path=path[:70]), self.assertRaises(ValidationError):
                apply_replacements(self.content, {"patches": [{"path": path, "value": None}]})
        self.assertEqual(self.content, before)

    def test_duplicate_and_overlapping_paths_are_rejected_in_either_order(self):
        pairs = [
            ("/title", "/title"),
            ("/sections", "/sections/0/id"),
            ("/sections/0/id", "/sections"),
            ("/a~1b", "/a~1b/~0field"),
        ]
        for first, second in pairs:
            with self.subTest(first=first, second=second), self.assertRaisesRegex(ValidationError, "duplicate or overlap"):
                apply_replacements(self.content, {"patches": [
                    {"path": first, "value": {}}, {"path": second, "value": "changed"},
                ]})

    def test_failed_later_replacement_does_not_partially_modify_original(self):
        before = deepcopy(self.content)
        with self.assertRaises(ValidationError):
            apply_replacements(self.content, {"patches": [
                {"path": "/title", "value": "Changed"},
                {"path": "/sections/0/unknown", "value": "Invalid"},
            ]})
        self.assertEqual(self.content, before)


if __name__ == "__main__":
    unittest.main()
