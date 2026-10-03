from copy import deepcopy
import math
import unittest

from playground_v2.experience import (
    compile_experiment, default_inputs, evaluate_experiment, validate_experience,
)
from playground_v2.validation import ValidationError


def fixture():
    handoff = {"content": {
        "sections": [{"id": "attention", "learning_outcome_ids": ["mechanism", "calculate", "limits"],
                      "mathematical_model": {"steps": [{"description": "Scaled attention"}]}}],
        "learning_outcomes": [{"id": value} for value in ("mechanism", "calculate", "limits")],
    }, "source": {"visuals": [{"id": "v0001", "asset_path": "assets/v0001.png", "provided_as": "image"},
                               {"id": "v0002", "asset_path": None, "provided_as": "caption_only"}]}}
    experiment = {
        "id": "attention_lab", "title": "One-query attention", "section_id": "attention",
        "goal": "Distinguish selecting information from the information selected.",
        "explanation": "Two fixed orthogonal keys compare to an editable query; softmax determines how two values are mixed.",
        "assumptions": ["Synthetic two-token teaching example, not a trained Transformer.", "Fixed keys are the two unit vectors; key dimension is two."],
        "variables": [
            {"id": "query", "label": "Query", "type": "vector", "default": [1, 0], "domain": {"min": -4, "max": 4, "step": 0.1, "length": 2}, "unit": "", "explanation": "Changes relative compatibility with fixed keys."},
            {"id": "values", "label": "Values", "type": "vector", "default": [2, 8], "domain": {"min": -10, "max": 10, "step": 0.5, "length": 2}, "unit": "", "explanation": "Changes the mixed information while leaving selection weights unchanged."}
        ],
        "computation": {
            "outputs": [{"id": name, "label": name.capitalize(), "unit": ""} for name in ("scores", "weights", "result")],
            "steps": [
                {"id": "scale", "label": "Scale compatibility", "explanation": "Dot products with identity keys equal query coordinates; divide once by sqrt(2).", "output_ids": ["scores"], "expressions": {"scores": ["divide", "$input.query", ["sqrt", 2]]}},
                {"id": "normalize", "label": "Normalize", "explanation": "Softmax over the two keys.", "output_ids": ["weights"], "expressions": {"weights": ["softmax", "$output.scores"]}},
                {"id": "mix", "label": "Mix values", "explanation": "Weighted sum of the two values.", "output_ids": ["result"], "expressions": {"result": ["dot", "$output.weights", "$input.values"]}}
            ]
        },
        "views": [{"id": "weights_view", "kind": "bars", "title": "Selection weights", "output_ids": ["weights"], "labels": ["Token A", "Token B"]},
                  {"id": "result_view", "kind": "scalar", "title": "Mixed value", "output_ids": ["result"], "labels": []}],
        "challenges": [{"id": "select", "instructions": "Predict which token dominates when the first query coordinate increases; change it and explain the weight change."},
                       {"id": "change_value", "instructions": "Keep the query fixed, predict the effect of doubling the first value, then compare the weights and mixed result."}]
    }
    def question(identifier, outcome, level):
        return {"id": identifier, "kind": "choice", "outcome_id": outcome, "section_id": "attention", "level": level,
                "prompt": "Which statement is supported?", "options": [{"id": "a", "text": "The bounded teaching example illustrates a mechanism."}, {"id": "b", "text": "This example proves benchmark superiority."}],
                "correct_option_id": "a", "expected": None, "tolerance": None, "explanation": "A toy example is not benchmark evidence."}
    numeric = {"id": "q_calculate", "kind": "numeric", "outcome_id": "calculate", "section_id": "attention", "level": "apply",
               "prompt": "Query [0,0], values [2,8]: predict the mixed value.", "options": [], "correct_option_id": None,
               "expected": 5, "tolerance": 1e-6, "explanation": "Equal scores give equal weights, so (2+8)/2=5.",
               "experiment_id": "attention_lab", "scenario_inputs": {"query": [0, 0], "values": [2, 8]}, "output_id": "result"}
    spec = {"schema_version": "1.0", "introduction": "Read the idea, then test it with a small calculation.", "no_experiments_reason": None,
            "sections": [{"section_id": "attention", "experiment_ids": ["attention_lab"], "figures": [{"visual_id": "v0001", "alt": "Original attention diagram.", "explanation": "The original paper illustrates the sequence of operations."}]}],
            "experiments": [experiment], "questions": [question("q_mechanism", "mechanism", "understand"), numeric, question("q_limits", "limits", "evaluate")]}
    return spec, handoff


class ExperienceTests(unittest.TestCase):
    def setUp(self):
        self.spec, self.handoff = fixture()
        self.experiment = self.spec["experiments"][0]

    def test_full_contract_and_same_trusted_plan(self):
        self.assertIs(validate_experience(self.spec, self.handoff), self.spec)
        compiled = compile_experiment(self.experiment)
        self.assertIn("createDeclarativeModel", compiled["engine_js"])
        self.assertEqual(compiled["plan"]["variables"][0]["domain"]["length"], 2)

    def test_attention_known_result_and_invariants(self):
        inputs = default_inputs(self.experiment)
        result = evaluate_experiment(self.experiment, inputs)["outputs"]
        expected_first = 1 / (1 + math.exp(-1 / math.sqrt(2)))
        self.assertAlmostEqual(result["weights"][0], expected_first)
        self.assertAlmostEqual(sum(result["weights"]), 1)
        self.assertAlmostEqual(result["result"], expected_first * 2 + (1 - expected_first) * 8)
        changed = evaluate_experiment(self.experiment, {"query": inputs["query"], "values": [7, -3]})["outputs"]
        self.assertEqual(changed["weights"], result["weights"])
        # A common score offset leaves row softmax invariant.
        offset = evaluate_experiment(self.experiment, {"query": [3, 2], "values": inputs["values"]})["outputs"]
        for a, b in zip(result["weights"], offset["weights"]):
            self.assertAlmostEqual(a, b)
        swapped = evaluate_experiment(self.experiment, {"query": [0, 1], "values": [8, 2]})["outputs"]
        self.assertAlmostEqual(swapped["result"], result["result"])

    def test_input_rejection_preserves_type_shape_and_bounds(self):
        for bad in ({"query": [1], "values": [2, 8]}, {"query": [9, 0], "values": [2, 8]},
                    {"query": ["1", 0], "values": [2, 8]}, {"query": [1, 0], "values": [2, 8], "unknown": 0}):
            with self.subTest(inputs=bad), self.assertRaises(ValidationError):
                evaluate_experiment(self.experiment, bad)

    def test_no_executable_strings_or_unknown_operations(self):
        for expression in ("alert(1)", ["eval", "1+1"], {"code": "fetch('url')"}, "$input.constructor", "$output.weights"):
            experiment = deepcopy(self.experiment)
            experiment["computation"]["steps"][0]["expressions"]["scores"] = expression
            with self.subTest(expression=expression), self.assertRaises(ValidationError):
                compile_experiment(experiment)

    def test_ast_budget_and_same_step_forward_reference(self):
        expression = 1
        for _ in range(24):
            expression = ["add", expression, 1]
        self.experiment["computation"]["steps"][0]["expressions"]["scores"] = expression
        with self.assertRaisesRegex(ValidationError, "budget"):
            compile_experiment(self.experiment)
        self.spec, self.handoff = fixture()
        experiment = self.spec["experiments"][0]
        experiment["computation"]["steps"][0]["expressions"]["scores"] = "$output.weights"
        with self.assertRaisesRegex(ValidationError, "forward"):
            compile_experiment(experiment)

    def test_unresponsive_control_and_unsafe_endpoint_fail(self):
        self.experiment["computation"]["steps"][0]["expressions"]["scores"] = [1, 0]
        with self.assertRaisesRegex(ValidationError, "does not change"):
            validate_experience(self.spec, self.handoff)
        self.spec, self.handoff = fixture()
        self.spec["experiments"][0]["computation"]["steps"][0]["expressions"]["scores"] = ["divide", [1, 2], "$input.query"]
        with self.assertRaisesRegex(ValidationError, "divide by zero"):
            validate_experience(self.spec, self.handoff)

    def test_view_dimensions_and_unavailable_figures_fail(self):
        self.experiment["views"][0]["kind"] = "matrix"
        with self.assertRaisesRegex(ValidationError, "dimensions"):
            validate_experience(self.spec, self.handoff)

    def test_matrix_labels_and_fixed_color_domain(self):
        self.experiment["computation"]["outputs"].append({"id": "weight_matrix", "label": "Row attention", "unit": ""})
        self.experiment["computation"]["steps"].append({"id": "matrix", "label": "Row view", "explanation": "One query row.",
            "output_ids": ["weight_matrix"], "expressions": {"weight_matrix": ["array", "$output.weights"]}})
        self.experiment["views"].append({"id": "matrix_view", "kind": "matrix", "title": "Attention row", "output_ids": ["weight_matrix"],
            "labels": [], "row_labels": ["Query"], "column_labels": ["Key A", "Key B"], "color_domain": [0, 1]})
        validate_experience(self.spec, self.handoff)
        self.experiment["views"][-1]["color_domain"] = [1, 0]
        with self.assertRaisesRegex(ValidationError, "color_domain"):
            validate_experience(self.spec, self.handoff)
        self.spec, self.handoff = fixture()
        self.spec["sections"][0]["figures"][0]["visual_id"] = "v0002"
        with self.assertRaisesRegex(ValidationError, "original image"):
            validate_experience(self.spec, self.handoff)

    def test_outcome_coverage_and_higher_order_required(self):
        self.spec["questions"][2]["outcome_id"] = "mechanism"
        with self.assertRaisesRegex(ValidationError, "every learning outcome"):
            validate_experience(self.spec, self.handoff)
        self.spec, self.handoff = fixture()
        self.spec["questions"][2]["level"] = "remember"
        with self.assertRaisesRegex(ValidationError, "higher-order"):
            validate_experience(self.spec, self.handoff)

    def test_prediction_answers_recomputed_and_join_checked(self):
        self.spec["questions"][1]["expected"] = 6
        with self.assertRaisesRegex(ValidationError, "scenario calculation"):
            validate_experience(self.spec, self.handoff)

    def test_all_prediction_mismatches_report_exact_paths_and_computed_values(self):
        first = self.spec["questions"][1]
        first["expected"] = 6
        second = deepcopy(first)
        second.update(id="second_wrong_prediction", expected=8,
                      scenario_inputs={"query": [0, 0], "values": [4, 8]})
        self.spec["questions"].append(second)
        with self.assertRaises(ValidationError) as caught:
            validate_experience(self.spec, self.handoff)
        diagnostic = str(caught.exception)
        self.assertIn("/questions/1/expected", diagnostic)
        self.assertIn("/questions/3/expected", diagnostic)
        self.assertIn("result = 5", diagnostic)
        self.assertIn("result = 6", diagnostic)
        self.assertIn("declared expected = 8", diagnostic)
        self.assertIn("absolute tolerance = 1e-06", diagnostic)
        self.assertIn("/questions/1/explanation", diagnostic)
        self.assertIn("Do not loosen tolerance", diagnostic)
        self.spec, self.handoff = fixture()
        self.spec["sections"][0]["experiment_ids"] = []
        with self.assertRaisesRegex(ValidationError, "placed exactly once"):
            validate_experience(self.spec, self.handoff)

    def test_choice_option_integrity_and_no_nan(self):
        self.spec["questions"][0]["options"][1]["id"] = "a"
        with self.assertRaisesRegex(ValidationError, "duplicate ID"):
            validate_experience(self.spec, self.handoff)
        self.spec, self.handoff = fixture()
        self.spec["questions"][1]["expected"] = float("nan")
        with self.assertRaisesRegex(ValidationError, "finite"):
            validate_experience(self.spec, self.handoff)

    def test_narrative_case_requires_rationale_and_real_math_requires_lab(self):
        self.spec["experiments"] = []
        self.spec["sections"][0]["experiment_ids"] = []
        self.spec["no_experiments_reason"] = "This source evaluates qualitative arguments, with no computable mechanism."
        for key in ("experiment_id", "scenario_inputs", "output_id"):
            self.spec["questions"][1].pop(key)
        with self.assertRaisesRegex(ValidationError, "computable mathematical model"):
            validate_experience(self.spec, self.handoff)
        self.handoff["content"]["sections"][0].pop("mathematical_model")
        validate_experience(self.spec, self.handoff)
        self.spec["no_experiments_reason"] = None
        with self.assertRaisesRegex(ValidationError, "rationale"):
            validate_experience(self.spec, self.handoff)

    def test_entropy_zero_terms_and_known_cases(self):
        experiment = {"variables": [{"id": "probabilities", "type": "vector", "default": [1, 0, 0, 0], "domain": {"min": 0, "max": 1, "length": 4}}],
                      "computation": {"outputs": [{"id": "entropy"}], "steps": [{"id": "compute", "output_ids": ["entropy"],
                        "expressions": {"entropy": ["negate", ["sum", ["xlogx", "$input.probabilities", 2]]]}}]}}
        for probabilities, expected in (([1, 0, 0, 0], 0), ([.25]*4, 2), ([.5, .5, 0, 0], 1), ([.75, .25, 0, 0], .8112781244591328)):
            with self.subTest(probabilities=probabilities):
                result = evaluate_experiment(experiment, {"probabilities": probabilities})["outputs"]["entropy"]
                self.assertAlmostEqual(result, expected)

    def test_failed_endpoint_diagnostic_contains_state_stage_and_prior_outputs(self):
        experiment = self.experiment
        experiment["variables"] = [
            {"id": "p_a", "label": "A", "type": "number", "default": .5,
             "domain": {"min": .05, "max": .9, "step": .05}, "unit": "", "explanation": "First probability."},
            {"id": "p_b", "label": "B", "type": "number", "default": .3,
             "domain": {"min": .05, "max": .9, "step": .05}, "unit": "", "explanation": "Second probability."}]
        experiment["computation"] = {
            "outputs": [{"id": identifier, "label": identifier, "unit": ""} for identifier in ("remainder", "entropy")],
            "steps": [
                {"id": "remainder_step", "label": "Remainder", "explanation": "An intentionally invalid independent-control remainder.", "output_ids": ["remainder"],
                 "expressions": {"remainder": ["subtract", 1, ["add", "$input.p_a", "$input.p_b"]]}},
                {"id": "entropy_step", "label": "Entropy", "explanation": "Sum the contributions.", "output_ids": ["entropy"],
                 "expressions": {"entropy": ["negate", ["sum", ["xlogx", ["array", "$input.p_a", "$input.p_b", "$output.remainder"], 2]]]}}
            ]}
        experiment["views"] = [{"id": "entropy_view", "kind": "scalar", "title": "Entropy", "output_ids": ["entropy"], "labels": []}]
        with self.assertRaises(ValidationError) as caught:
            validate_experience(self.spec, self.handoff)
        diagnostic = str(caught.exception)
        self.assertIn("Experiment attention_lab", diagnostic)
        self.assertIn("validation stage=coordinate probe p_a[]=0.9", diagnostic)
        self.assertIn('"p_a": 0.9', diagnostic)
        self.assertIn('"p_b": 0.3', diagnostic)
        self.assertIn("step='entropy_step'", diagnostic)
        self.assertIn("output='entropy'", diagnostic)
        self.assertIn('completed outputs={"remainder":-', diagnostic)
        self.assertIn("x log x needs nonnegative", diagnostic)

    def test_compile_diagnostic_identifies_experiment_and_expression(self):
        self.experiment["computation"]["steps"][0]["expressions"]["scores"] = ["max", "$input.query", 0]
        with self.assertRaises(ValidationError) as caught:
            compile_experiment(self.experiment)
        diagnostic = str(caught.exception)
        self.assertIn("Experiment attention_lab validation stage=compile", diagnostic)
        self.assertIn("/computation/steps/0/expressions/scores", diagnostic)
        self.assertIn("max: expected 1 to 1, received 2", diagnostic)

    def test_all_view_shapes_and_prediction_answers_share_one_diagnostic(self):
        self.experiment["views"][0]["output_ids"] = ["result", "result"]
        # Distinct scalar diagnostics reproduce a generated bars-binding mistake.
        self.experiment["computation"]["outputs"].append({"id": "weight_sum", "label": "Weight sum", "unit": ""})
        self.experiment["computation"]["steps"].append({"id": "sum_weights", "label": "Sum", "explanation": "The row sums to one.",
            "output_ids": ["weight_sum"], "expressions": {"weight_sum": ["sum", "$output.weights"]}})
        self.experiment["views"][0]["output_ids"] = ["result", "weight_sum"]
        self.experiment["views"][1]["output_ids"] = ["scores"]
        self.spec["questions"][1]["expected"] = 6
        with self.assertRaises(ValidationError) as caught:
            validate_experience(self.spec, self.handoff)
        diagnostic = str(caught.exception)
        self.assertIn("/experiments/0/views/0", diagnostic)
        self.assertIn("kind=bars", diagnostic)
        self.assertIn("requires exactly one vector output", diagnostic)
        self.assertIn("result=scalar, weight_sum=scalar", diagnostic)
        self.assertIn("separate scalar views", diagnostic)
        self.assertIn("/experiments/0/views/1", diagnostic)
        self.assertIn("scores=vector[2]", diagnostic)
        self.assertIn("/questions/1/expected", diagnostic)
        self.assertIn("result = 5", diagnostic)

    def test_prediction_diagnostic_does_not_treat_incorrect_ast_as_answer_authority(self):
        # The expected answer +5 is mathematically correct; the extra negation
        # represents a model translation mistake like dropping entropy's minus.
        expression = self.experiment["computation"]["steps"][-1]["expressions"]["result"]
        self.experiment["computation"]["steps"][-1]["expressions"]["result"] = ["negate", expression]
        with self.assertRaises(ValidationError) as caught:
            validate_experience(self.spec, self.handoff)
        diagnostic = str(caught.exception)
        self.assertIn("declared AST scenario calculation", diagnostic)
        self.assertIn("result = -5", diagnostic)
        self.assertIn("declared expected = 5", diagnostic)
        self.assertIn("FIRST compare /experiments/0/computation with the Call 1 mathematical_model equations", diagnostic)
        self.assertIn("correct the AST and retain any scientifically correct expected answer", diagnostic)
        self.assertIn("Do not blindly copy the computed value into expected", diagnostic)
        self.assertNotIn("trusted scenario calculation", diagnostic)


if __name__ == "__main__":
    unittest.main()
