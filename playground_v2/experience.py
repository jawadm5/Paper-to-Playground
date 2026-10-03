"""Call 2's declarative contract and bounded, trusted numerical execution.

The model supplies JSON expression trees, never executable source. The same
reviewed interpreter runs here in V8 and in the exported offline page.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path
import re

from jsonschema import Draft202012Validator

from .validation import ValidationError

BASE = Path(__file__).resolve().parents[1]
ENGINE_PATH = Path(__file__).with_name("assets") / "math-engine.js"
SCHEMA_PATH = BASE / "docs/v2/schemas/experience.schema.json"
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
REFERENCE = re.compile(r"^\$(input|output)\.([a-z][a-z0-9_]{0,63})((?:\[\d+\]|\.\d+)*)$")
OP_ARITY = {
    **{name: (2, 2) for name in ("add", "subtract", "multiply", "divide", "power", "dot", "matvec", "matmul", "at", "eq", "lt", "gt")},
    **{name: (1, 1) for name in ("literal", "negate", "abs", "sqrt", "exp", "log", "log2", "sum", "mean", "min", "max", "transpose", "softmax", "normalize", "length")},
    "xlogx": (1, 2), "array": (0, 64), "concat": (1, 64), "slice": (2, 3), "if": (3, 3),
}


def load_experience_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _unique(items, label):
    identifiers = [item["id"] for item in items]
    if len(set(identifiers)) != len(identifiers):
        raise ValidationError(label + ": duplicate ID")
    return set(identifiers)


def _id(identifier):
    if not isinstance(identifier, str) or not IDENTIFIER.fullmatch(identifier) or identifier in {"constructor", "prototype", "__proto__"}:
        raise ValidationError("Unsupported computation identifier")


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValidationError("Numerical values must be finite numbers")


def default_inputs(experiment: dict) -> dict:
    return {variable["id"]: deepcopy(variable["default"]) for variable in experiment["variables"]}


def compile_experiment(experiment: dict) -> dict:
    """Return {plan, engine_js}; createDeclarativeModel(plan) is the JS API."""
    inputs = _unique(experiment["variables"], "variables")
    outputs = _unique(experiment["computation"]["outputs"], "outputs")
    if inputs & outputs:
        raise ValidationError("Input and output IDs must be distinct")
    for identifier in inputs | outputs:
        _id(identifier)
    steps = experiment["computation"]["steps"]
    _unique(steps, "computation steps")
    known, plan_steps, count = set(), [], 0

    def visit(value, depth=0, literal=False):
        nonlocal count
        count += 1
        if depth > 20 or count > 2048:
            raise ValidationError("Computation exceeds its expression budget")
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float)):
            _finite(value)
            return
        if isinstance(value, str) and not literal:
            match = REFERENCE.fullmatch(value)
            if not match:
                raise ValidationError("Expressions accept numerical data and declared references, never code")
            kind, identifier, suffix = match.groups()
            if identifier not in (inputs if kind == "input" else known):
                raise ValidationError("Unknown or forward expression reference: " + value)
            if any(int(index) >= 64 for index in re.findall(r"\d+", suffix)):
                raise ValidationError("Reference index exceeds the array limit")
            return
        if not isinstance(value, list) or len(value) > 64:
            raise ValidationError("Expressions must contain bounded numerical arrays")
        if not literal and value and isinstance(value[0], str):
            operation, arguments = value[0], value[1:]
            if operation not in OP_ARITY:
                raise ValidationError("Unsupported mathematical operation: " + operation)
            lower, upper = OP_ARITY[operation]
            if not lower <= len(arguments) <= upper:
                raise ValidationError(f"Wrong operand count for {operation}: expected {lower} to {upper}, received {len(arguments)}")
            for argument in arguments:
                visit(argument, depth + 1, operation == "literal")
        else:
            for child in value:
                visit(child, depth + 1, literal)

    for step_index, step in enumerate(steps):
        declared, expressions = step["output_ids"], step["expressions"]
        if not expressions or set(declared) != set(expressions) or len(set(declared)) != len(declared):
            raise ValidationError("Each step needs an expression for every declared output")
        if set(expressions) - outputs or set(expressions) & known:
            raise ValidationError("Each declared output must be computed exactly once")
        # Outputs in a step become available only after the entire step.
        for output_id, expression in expressions.items():
            try:
                visit(expression)
            except ValidationError as error:
                raise ValidationError(
                    f"Experiment {experiment.get('id', '(unnamed)')} validation stage=compile "
                    f"/computation/steps/{step_index}/expressions/{output_id}: {error}"
                ) from error
        known.update(expressions)
        plan_steps.append({"id": step["id"], "expressions": deepcopy(expressions)})
    if known != outputs:
        raise ValidationError("Every declared output needs a computation")
    plan = {"variables": [{"id": variable["id"], "type": variable["type"],
                           "domain": deepcopy(variable["domain"])} for variable in experiment["variables"]],
            "steps": plan_steps, "constraints": []}
    return {"plan": plan, "engine_js": ENGINE_PATH.read_text(encoding="utf-8")}


class _Executor:
    def __init__(self, experiment):
        from py_mini_racer import MiniRacer
        compiled = compile_experiment(experiment)
        self.experiment_id = experiment.get("id", "(unnamed)")
        self.context = MiniRacer()
        self.context.set_hard_memory_limit(64 * 1024 * 1024)
        self.context.eval(compiled["engine_js"], timeout=1000)
        self.context.eval("var __model = createDeclarativeModel(" + json.dumps(compiled["plan"], allow_nan=False) + ");", timeout=1000)

    def compute(self, inputs, stage="requested input"):
        encoded = "(not finite JSON)"
        try:
            encoded = json.dumps(inputs, allow_nan=False)
            result = json.loads(self.context.eval(
                "JSON.stringify((function(){try{return {ok:true,result:__model.compute(" + encoded + ")};}"
                "catch(error){return {ok:false,message:String(error.message),step_id:error.step_id||null,"
                "output_id:error.output_id||null,completed_outputs:error.completed_outputs||{}};}})())", timeout=1000))
            if not result["ok"]:
                # Only prior outputs already checked as finite by the trusted
                # interpreter appear here. Bound diagnostic length for repair.
                completed = json.dumps(result["completed_outputs"], allow_nan=False, separators=(",", ":"))
                suffix = "" if len(completed) <= 1600 else " [truncated]"
                raise ValidationError(
                    f"Experiment {self.experiment_id} validation stage={stage}; failing inputs={encoded}; "
                    f"step={result['step_id']!r}; output={result['output_id']!r}; "
                    f"completed outputs={completed[:1600]}{suffix}; calculation failed: {result['message']}"
                )
            return result["result"]
        except ValidationError:
            raise
        except Exception as error:
            raise ValidationError(
                f"Experiment {self.experiment_id} validation stage={stage}; failing inputs={encoded}; "
                "calculation failed: " + str(error).splitlines()[0][:240]
            ) from error

    def close(self):
        self.context.close()


def evaluate_experiment(experiment: dict, inputs: dict | None = None) -> dict:
    executor = _Executor(experiment)
    try:
        return executor.compute(default_inputs(experiment) if inputs is None else inputs)
    finally:
        executor.close()


def _coordinates(value):
    if not isinstance(value, list):
        return [()]
    return [(index,) + rest for index, child in enumerate(value) for rest in _coordinates(child)]


def _replace(value, coordinate, number):
    if not coordinate:
        return number
    result = deepcopy(value)
    target = result
    for index in coordinate[:-1]:
        target = target[index]
    target[coordinate[-1]] = number
    return result


def _different(left, right):
    if isinstance(left, list) or isinstance(right, list):
        return not (isinstance(left, list) and isinstance(right, list) and len(left) == len(right)) or any(_different(a, b) for a, b in zip(left, right))
    return not math.isclose(left, right, abs_tol=1e-12, rel_tol=1e-10)


def _check_views(experiment, result, experiment_path="/experiments/0", inputs=None):
    outputs = result["outputs"]
    inputs = inputs or default_inputs(experiment)
    issues = []
    scalar = lambda value: isinstance(value, (float, int)) and not isinstance(value, bool)
    vector = lambda value: isinstance(value, list) and bool(value) and all(scalar(item) for item in value)
    matrix = lambda value: isinstance(value, list) and bool(value) and all(vector(row) for row in value) and len({len(row) for row in value}) == 1

    def shape(value):
        if scalar(value):
            return "scalar"
        if vector(value):
            return f"vector[{len(value)}]"
        if matrix(value):
            return f"matrix[{len(value)}x{len(value[0])}]"
        return "unsupported numerical shape"

    requirements = {"scalar": "exactly one scalar output", "bars": "exactly one vector output",
                    "line": "exactly one vector output", "scatter": "two equally sized vector outputs (x then y)",
                    "matrix": "exactly one rectangular matrix output", "steps": "existing computed outputs"}
    for view_index, view in enumerate(experiment["views"]):
        location = f"{experiment_path}/views/{view_index} ({view['id']})"
        identifiers = view["output_ids"]
        if set(identifiers) - set(outputs):
            issues.append(location + ": view references an unknown output: " + ", ".join(sorted(set(identifiers) - set(outputs))))
            continue
        values = [outputs[identifier] for identifier in identifiers]
        kind = view["kind"]
        if view.get("color_domain") is not None and (kind != "matrix" or view["color_domain"][0] >= view["color_domain"][1]):
            issues.append(location + ": a matrix color_domain needs increasing minimum and maximum")
        if kind in {"vector_compare", "weight_distribution", "weighted_blend", "contribution_flow"}:
            try:
                b = view.get("bindings", {})
                q, k, v = [inputs[b[name]] for name in ("query_input", "key_input", "value_input")]
                scores, weights, out = [outputs[b[name]] for name in ("scores_output", "weights_output", "result_output")]
                if vector(q): q = [q]
                if vector(scores): scores = [scores]
                if vector(weights): weights = [weights]
                if vector(out): out = [out]
                if not all(matrix(x) for x in (q, k, v, scores, weights, out)):
                    raise ValueError("all scientific bindings must be matrices")
                n, m = len(q), len(k)
                if len(q[0]) != len(k[0]) or len(v) != m or len(scores) != n or len(weights) != n or len(out) != n or any(len(row) != m for row in scores + weights) or len(out[0]) != len(v[0]):
                    raise ValueError("query/key/value and score/weight/result shapes disagree")
                if kind == "vector_compare" and len(q[0]) != 2:
                    raise ValueError("vector geometry requires true 2D queries and keys")
                if kind == "weighted_blend" and len(v[0]) != 2:
                    raise ValueError("weighted geometry requires true 2D values and outputs")
                if view.get("labels") and len(view["labels"]) != m:
                    raise ValueError("labels must match the key count")
                if not {b[name] for name in ("scores_output", "weights_output", "result_output")} <= set(identifiers):
                    raise ValueError("output_ids must include all three bound outputs")
                for i in range(n):
                    if any(w < -1e-10 for w in weights[i]) or not math.isclose(sum(weights[i]), 1, abs_tol=1e-8):
                        raise ValueError("weights must be nonnegative and sum to one")
                    if any(not math.isclose(scores[i][j], sum(x*y for x,y in zip(q[i],k[j])), abs_tol=1e-8, rel_tol=1e-8) for j in range(m)):
                        raise ValueError("raw score binding must equal Q K transpose")
                    if any(not math.isclose(out[i][d], sum(weights[i][j]*v[j][d] for j in range(m)), abs_tol=1e-8, rel_tol=1e-8) for d in range(len(v[0]))):
                        raise ValueError("output binding must equal the weighted values")
            except (KeyError, TypeError, ValueError, IndexError) as error:
                issues.append(location + ": " + str(error))
            continue
        valid = kind in {"steps", "process"} or (
            kind == "scalar" and len(values) == 1 and scalar(values[0]) or
            kind in {"bars", "line"} and len(values) == 1 and vector(values[0]) or
            kind == "matrix" and len(values) == 1 and matrix(values[0]) or
            kind == "scatter" and len(values) == 2 and all(vector(value) for value in values) and len(values[0]) == len(values[1]))
        if not valid:
            actual = ", ".join(identifier + "=" + shape(outputs[identifier]) for identifier in identifiers)
            suggestion = ""
            if kind in {"bars", "line"}:
                suggestion = (' Use separate scalar views, a steps view, or assemble a new vector with ["array", '
                              '"$output.first", "$output.second"] in a later computation step and bind that ONE vector output.')
            issues.append(f"{location}: kind={kind} has incompatible output dimensions; requires {requirements[kind]}; "
                          f"actual bindings: {actual}.{suggestion}")
            continue
        if view.get("labels") and kind in {"bars", "line", "scatter"} and len(view["labels"]) != len(values[0]):
            issues.append(location + f": view labels count={len(view['labels'])} must match plotted values count={len(values[0])}")
        if kind == "matrix":
            if view.get("row_labels") and len(view["row_labels"]) != len(values[0]):
                issues.append(location + ": matrix row labels do not match its shape")
            if view.get("column_labels") and len(view["column_labels"]) != len(values[0][0]):
                issues.append(location + ": matrix column labels do not match its shape")
    if issues:
        raise ValidationError(" | ".join(issues))


def _check_experiment(experiment, experiment_path="/experiments/0"):
    _unique(experiment["views"], "views")
    _unique(experiment["challenges"], "challenges")
    defaults = default_inputs(experiment)
    coordinates = 0
    for variable in experiment["variables"]:
        domain = variable["domain"]
        if domain["min"] >= domain["max"]:
            raise ValidationError("Editable input bounds must increase")
        if variable["type"] == "integer" and any(not float(domain[name]).is_integer() for name in ("min", "max", "step")):
            raise ValidationError("Integer controls require whole-number bounds and step")
        required = {"vector": {"length"}, "matrix": {"rows", "columns"}}.get(variable["type"], set())
        present = {key for key in ("length", "rows", "columns") if key in domain}
        if present != required:
            raise ValidationError("Input domain dimensions must match its type")
        coordinates += len(_coordinates(variable["default"]))
    if coordinates > 64:
        raise ValidationError("At most 64 editable numerical elements per experiment")
    executor = _Executor(experiment)
    try:
        initial = executor.compute(defaults, "defaults")
        _check_views(experiment, initial, experiment_path, defaults)
        shown = {identifier for view in experiment["views"] for identifier in view["output_ids"]}
        for variable in experiment["variables"]:
            domain, changed = variable["domain"], False
            midpoint = (domain["min"] + domain["max"]) / 2
            if variable["type"] == "integer":
                midpoint = round(midpoint)
            for coordinate in _coordinates(variable["default"]):
                for endpoint in dict.fromkeys((domain["min"], midpoint, domain["max"])):
                    inputs = deepcopy(defaults)
                    inputs[variable["id"]] = _replace(inputs[variable["id"]], coordinate, endpoint)
                    result = executor.compute(inputs, f"coordinate probe {variable['id']}{list(coordinate)}={endpoint!r}")
                    _check_views(experiment, result, experiment_path, inputs)
                    changed |= any(_different(initial["outputs"][key], result["outputs"][key]) for key in shown)
            if not changed:
                raise ValidationError("Editable input " + variable["id"] + " does not change a visible output in bounded probes")
        # Also cover simultaneous all-minimum and all-maximum inputs.
        for bound in ("min", "max"):
            inputs = deepcopy(defaults)
            for variable in experiment["variables"]:
                for coordinate in _coordinates(variable["default"]):
                    inputs[variable["id"]] = _replace(inputs[variable["id"]], coordinate, variable["domain"][bound])
            _check_views(experiment, executor.compute(inputs, f"simultaneous {bound} endpoints"), experiment_path, inputs)
    finally:
        executor.close()


def validate_experience(spec: dict, handoff: dict) -> dict:
    """Validate shape, joins, assessment coverage and executable numerical probes.

    This establishes structural and bounded behavioral validity, not scientific
    correctness of arbitrary generated explanations or a proof over the domain.
    """
    errors = list(Draft202012Validator(load_experience_schema()).iter_errors(spec))
    if errors:
        error = errors[0]
        raise ValidationError("experience /" + "/".join(map(str, error.absolute_path)) + ": " + error.message[:350])
    try:
        json.dumps(spec, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValidationError("Experience must contain finite JSON data") from error
    content = handoff["content"]
    sections = {section["id"]: section for section in content["sections"]}
    outcomes = {outcome["id"] for outcome in content["learning_outcomes"]}
    visuals = {visual["id"]: visual for visual in handoff["source"]["visuals"]}
    experiment_ids = _unique(spec["experiments"], "experiments")
    experiment_by_id = {experiment["id"]: experiment for experiment in spec["experiments"]}
    experiment_paths = {experiment["id"]: f"/experiments/{index}" for index, experiment in enumerate(spec["experiments"])}
    assigned = [section["section_id"] for section in spec["sections"]]
    if len(set(assigned)) != len(assigned) or set(assigned) != set(sections):
        raise ValidationError("Experience sections must cover each content section exactly once")
    placements = []
    for section in spec["sections"]:
        for identifier in section["experiment_ids"]:
            if identifier not in experiment_ids or experiment_by_id[identifier]["section_id"] != section["section_id"]:
                raise ValidationError("Experiment placement must match its existing section")
            placements.append(identifier)
        for figure in section["figures"]:
            visual = visuals.get(figure["visual_id"])
            if not visual or not visual.get("asset_path") or visual.get("provided_as") == "not_provided":
                raise ValidationError("Figure must reference an available original image")
    if len(set(placements)) != len(placements) or set(placements) != experiment_ids:
        raise ValidationError("Every experiment must be placed exactly once")
    if spec["experiments"]:
        if spec["no_experiments_reason"] is not None:
            raise ValidationError("An experience with experiments must use a null no_experiments_reason")
    elif not spec["no_experiments_reason"]:
        raise ValidationError("A narrative-only experience needs an explicit rationale")
    if not spec["experiments"] and any(section.get("mathematical_model", {}).get("steps") for section in sections.values()):
        raise ValidationError("Content with a computable mathematical model needs at least one meaningful experiment")
    validation_issues = []
    for experiment_index, experiment in enumerate(spec["experiments"]):
        if experiment["section_id"] not in sections:
            raise ValidationError("Experiment references an unknown section")
        try:
            _check_experiment(experiment, f"/experiments/{experiment_index}")
        except ValidationError as error:
            validation_issues.append(str(error))
    _unique(spec["questions"], "questions")
    covered = set()
    prediction_mismatches = []
    for question_index, question in enumerate(spec["questions"]):
        if question["section_id"] not in sections or question["outcome_id"] not in outcomes:
            raise ValidationError("Question must reference an existing section and outcome")
        covered.add(question["outcome_id"])
        if question["outcome_id"] not in sections[question["section_id"]]["learning_outcome_ids"]:
            raise ValidationError("Question outcome must be taught in its referenced section")
        if question["kind"] == "choice":
            if len(question["options"]) < 2:
                raise ValidationError("Choice questions need at least two answer options")
            option_ids = _unique(question["options"], "question options")
            if question["correct_option_id"] not in option_ids:
                raise ValidationError("Question correct_option_id must identify a declared option")
            if question["expected"] is not None or question["tolerance"] is not None:
                raise ValidationError("Choice questions do not have numerical answers")
        else:
            if question["options"] or question["correct_option_id"] is not None or question["expected"] is None or question["tolerance"] is None:
                raise ValidationError("Numeric questions require expected/tolerance and no choice options")
        experiment_id = question.get("experiment_id")
        if experiment_id:
            if experiment_id not in experiment_ids or not question.get("scenario_inputs"):
                raise ValidationError("Prediction questions require an existing experiment and complete scenario_inputs")
            try:
                result = evaluate_experiment(experiment_by_id[experiment_id], question["scenario_inputs"])
            except ValidationError as error:
                validation_issues.append(f"/questions/{question_index}/scenario_inputs: {error}")
                continue
            output_id = question.get("output_id")
            if output_id:
                value = result["outputs"].get(output_id)
                if question["kind"] != "numeric" or not isinstance(value, (int, float)):
                    validation_issues.append(f"/questions/{question_index}/output_id: {output_id} is not scalar. Bind an existing scalar diagnostic or add a later scalar extraction output with at; update both output_id and expected. Do not bind an entire vector/matrix.")
                    continue
                if not math.isclose(value, question["expected"], rel_tol=0, abs_tol=question["tolerance"]):
                    prediction_mismatches.append(
                        f"/questions/{question_index}/expected ({question['id']}): declared AST scenario calculation "
                        f"for {experiment_id}.{output_id} = {value!r}; declared expected = {question['expected']!r}; "
                        f"absolute tolerance = {question['tolerance']!r}. This reports what the supplied expressions "
                        "compute, not an independently verified scientific answer. FIRST compare "
                        f"{experiment_paths[experiment_id]}/computation with the Call 1 mathematical_model equations. "
                        "If the AST mistranslates the source equation, correct the AST and retain any scientifically "
                        "correct expected answer. Otherwise correct the expected answer. In either case update "
                        f"/questions/{question_index}/explanation to match the source-grounded calculation. "
                        "Do not blindly copy the computed value into expected. Do not loosen tolerance to hide "
                        "a mismatch or alter the scientific model merely to fit a guessed answer."
                    )
            elif question["kind"] == "numeric":
                raise ValidationError("Numeric prediction needs a scalar output_id for verified grading")
        elif question.get("scenario_inputs") or question.get("output_id"):
            raise ValidationError("Scenario inputs and output binding require an experiment")
    if prediction_mismatches:
        validation_issues.append("Prediction answers do not match the scenario calculation: " + " | ".join(prediction_mismatches))
    if validation_issues:
        raise ValidationError(" | ".join(validation_issues))
    if covered != outcomes:
        raise ValidationError("Assessment must cover every learning outcome")
    if not any(question["level"] in {"analyze", "evaluate", "create"} for question in spec["questions"]):
        raise ValidationError("Assessment needs at least one higher-order question")
    return spec
