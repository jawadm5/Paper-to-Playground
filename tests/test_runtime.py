import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from src.renderer import render_to_html
from src.schema import LegacyLessonRenderSpec, LessonRenderSpec


PROJECT_ROOT = Path(__file__).parents[1]
RUNTIME_PATH = PROJECT_ROOT / "src" / "runtime" / "runtime.js"
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "attention_render_spec.json"
CALL1_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "call1_render_spec.json"
NUMERIC_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "numeric_render_spec.json"


def full_page_runtime_payload(fixture_path: Path):
    spec = LessonRenderSpec.model_validate_json(fixture_path.read_text(encoding="utf-8"))
    html = render_to_html(spec)

    def embedded_json(element_id: str):
        match = re.search(
            rf'<script type="application/json" id="{element_id}">(.*?)</script>',
            html,
            re.DOTALL,
        )
        assert match is not None
        return json.loads(match.group(1))

    return (
        html,
        embedded_json("lesson-initial-state"),
        embedded_json("lesson-computations"),
        embedded_json("lesson-outputs"),
    )


def run_runtime(
    expression: str,
    state: Optional[Dict[str, Any]] = None,
    computations: Optional[List[Dict[str, Any]]] = None,
    outputs: Optional[Dict[str, Any]] = None,
) -> Any:
    state = state or {}
    computations = computations or []
    outputs = outputs or {"intermediate_values": [], "visualizations": []}
    harness = f"""
const fs = require("fs");
const vm = require("vm");
class FakeElement {{
  constructor(tagName) {{
    this.tagName = tagName;
    this.children = [];
    this.attributes = {{}};
    this.style = {{}};
    this.className = "";
    this.textContent = "";
    this.hidden = false;
  }}
  appendChild(child) {{ this.children.push(child); return child; }}
  removeChild(child) {{
    const index = this.children.indexOf(child);
    if (index >= 0) this.children.splice(index, 1);
    return child;
  }}
  get firstChild() {{ return this.children.length ? this.children[0] : null; }}
  setAttribute(name, value) {{ this.attributes[name] = String(value); }}
}}
function collectText(element) {{
  return element.textContent + element.children.map(collectText).join("|");
}}
const elements = {{
  "lesson-initial-state": new FakeElement("script"),
  "lesson-computations": new FakeElement("script"),
  "lesson-outputs": new FakeElement("script"),
  "runtime-error": new FakeElement("p")
}};
elements["lesson-initial-state"].textContent = {json.dumps(json.dumps(state))};
elements["lesson-computations"].textContent = {json.dumps(json.dumps(computations))};
elements["lesson-outputs"].textContent = {json.dumps(json.dumps(outputs))};
JSON.parse(elements["lesson-outputs"].textContent).intermediate_values
  .concat(JSON.parse(elements["lesson-outputs"].textContent).visualizations)
  .forEach(function (definition) {{
    elements[definition.element_id] = new FakeElement("div");
  }});
global.document = {{
  activeElement: null,
  getElementById: function (id) {{ return elements[id] || null; }},
  querySelectorAll: function () {{ return []; }},
  createElement: function (tagName) {{ return new FakeElement(tagName); }},
  createElementNS: function (_, tagName) {{ return new FakeElement(tagName); }}
}};
global.window = {{}};
global.HTMLInputElement = function () {{}};
global.collectText = collectText;
vm.runInThisContext(fs.readFileSync({json.dumps(str(RUNTIME_PATH))}, "utf8"));
const testResult = ({expression});
process.stdout.write(JSON.stringify(testResult));
"""
    completed = subprocess.run(
        ["node", "-"],
        input=harness,
        text=True,
        capture_output=True,
        check=True,
        cwd=PROJECT_ROOT,
    )
    return json.loads(completed.stdout)


def test_softmax_of_equal_values_is_uniform() -> None:
    result = run_runtime("window.lessonRuntime.operations.softmax([0, 0])")

    assert result == pytest.approx([0.5, 0.5])


def test_each_row_softmax_row_sums_to_one() -> None:
    result = run_runtime(
        "window.lessonRuntime.operations.row_softmax([[1, 2, 3], [-2, 0, 2]])"
    )

    assert [sum(row) for row in result] == pytest.approx([1.0, 1.0])


def test_two_by_two_matrix_multiplication() -> None:
    result = run_runtime(
        "window.lessonRuntime.operations.matrix_multiply([[1, 2], [3, 4]], [[5, 6], [7, 8]])"
    )

    assert result == [[19, 22], [43, 50]]


def test_registry_exposes_exact_supported_operations() -> None:
    result = run_runtime("Object.keys(window.lessonRuntime.operations).sort()")

    assert result == sorted(
        [
            "add",
            "subtract",
            "multiply",
            "divide",
            "sqrt",
            "sum",
            "normalize",
            "softmax",
            "row_softmax",
            "transpose",
            "matrix_multiply",
            "matmul_transpose",
        ]
    )


def test_registry_exposes_exact_supported_visualizations() -> None:
    result = run_runtime("Object.keys(window.lessonRuntime.visualizations).sort()")

    assert result == sorted(
        ["bar_chart", "line_chart", "heatmap", "matrix_display", "step_pipeline"]
    )


def test_fixture_computes_expected_output_dimensions() -> None:
    spec = LegacyLessonRenderSpec.model_validate_json(
        FIXTURE_PATH.read_text(encoding="utf-8")
    )
    state = {variable.id: variable.default for variable in spec.variables}
    computations = [
        computation.model_dump(mode="json", exclude_none=True)
        for computation in spec.computations
    ]

    dimensions = run_runtime(
        "[window.lessonRuntime.context.attention_output.length, "
        "window.lessonRuntime.context.attention_output[0].length]",
        state,
        computations,
    )

    assert dimensions == [2, 2]


def test_fixture_scaling_condition_selects_raw_scores_when_disabled() -> None:
    spec = LegacyLessonRenderSpec.model_validate_json(
        FIXTURE_PATH.read_text(encoding="utf-8")
    )
    state = {variable.id: variable.default for variable in spec.variables}
    computations = [
        computation.model_dump(mode="json", exclude_none=True)
        for computation in spec.computations
    ]

    result = run_runtime(
        "(function () { window.lessonRuntime.context.apply_scaling = false; "
        "window.lessonRuntime.recompute(); return { raw: window.lessonRuntime.context.raw_scores, "
        "selected: window.lessonRuntime.context.scaled_scores }; }())",
        state,
        computations,
    )

    assert result["selected"] == result["raw"]


@pytest.mark.parametrize(
    ("expression", "message"),
    [
        (
            "(function () { try { window.lessonRuntime.operations.matrix_multiply([[1, 2]], [[1, 2]]); } "
            "catch (error) { return error.message; } }())",
            "dimension mismatch",
        ),
        (
            "(function () { try { window.lessonRuntime.operations.softmax([0, Number.NaN]); } "
            "catch (error) { return error.message; } }())",
            "invalid numeric value",
        ),
    ],
)
def test_runtime_reports_clear_numeric_and_dimension_errors(
    expression: str, message: str
) -> None:
    assert message in run_runtime(expression)


def test_recompute_reports_missing_ids() -> None:
    computations = [{"id": "result", "op": "sum", "inputs": ["missing"]}]
    expression = (
        "(function () { try { window.lessonRuntime.recompute(); } "
        "catch (error) { return error.message; } }())"
    )

    assert "references missing ID 'missing'" in run_runtime(
        expression, {"x": 1}, computations
    )


def test_computations_execute_in_declared_order() -> None:
    computations = [
        {"id": "first", "op": "sum", "inputs": ["later"]},
        {"id": "later", "op": "sum", "inputs": ["x"]},
    ]
    expression = (
        "(function () { try { window.lessonRuntime.recompute(); } "
        "catch (error) { return error.message; } }())"
    )

    assert "references missing ID 'later'" in run_runtime(
        expression, {"x": [1, 2]}, computations
    )


def test_runtime_never_uses_eval_or_topic_specific_dispatch() -> None:
    runtime_source = RUNTIME_PATH.read_text(encoding="utf-8").lower()

    assert "eval(" not in runtime_source
    assert "attention" not in runtime_source


def test_visualization_references_resolve_in_both_fixtures() -> None:
    for fixture_path in (CALL1_FIXTURE_PATH, NUMERIC_FIXTURE_PATH):
        _, state, computations, outputs = full_page_runtime_payload(fixture_path)
        available_ids = set(state) | {item["id"] for item in computations}
        referenced_ids = set()
        for definition in outputs["visualizations"]:
            data = definition["data"]
            referenced_ids.update(data if isinstance(data, list) else [data])
        for definition in outputs["intermediate_values"]:
            referenced_ids.add(definition["data"])

        assert referenced_ids <= available_ids


def test_matrix_display_renders_current_computed_value() -> None:
    _, state, computations, outputs = full_page_runtime_payload(CALL1_FIXTURE_PATH)
    definition = next(
        item for item in outputs["visualizations"] if item["type"] == "matrix_display"
    )
    expression = (
        "({ text: collectText(elements["
        + json.dumps(definition["element_id"])
        + "]), value: window.lessonRuntime.context["
        + json.dumps(definition["data"])
        + "] })"
    )

    result = run_runtime(expression, state, computations, outputs)
    expected_text = str(round(result["value"][0][0], 4))

    assert expected_text in result["text"]


def test_bar_chart_receives_current_runtime_values_and_safe_labels() -> None:
    _, state, computations, outputs = full_page_runtime_payload(NUMERIC_FIXTURE_PATH)
    definition = next(
        item for item in outputs["visualizations"] if item["type"] == "bar_chart"
    )
    expression = (
        "({ text: collectText(elements["
        + json.dumps(definition["element_id"])
        + "]), total: window.lessonRuntime.context[\"block_2_1.total\"] })"
    )

    result = run_runtime(expression, state, computations, outputs)

    assert result["total"] == 7
    assert "Left: 2" in result["text"]
    assert "Right: 5" in result["text"]
    assert "Total: 7" in result["text"]


def test_heatmap_renders_current_runtime_weights() -> None:
    _, state, computations, outputs = full_page_runtime_payload(CALL1_FIXTURE_PATH)
    definition = next(
        item for item in outputs["visualizations"] if item["type"] == "heatmap"
    )
    expression = (
        "({ text: collectText(elements["
        + json.dumps(definition["element_id"])
        + "]), weights: window.lessonRuntime.context["
        + json.dumps(definition["data"])
        + "] })"
    )

    result = run_runtime(expression, state, computations, outputs)

    for value in result["weights"][0]:
        assert str(round(value, 4)) in result["text"]


def test_intermediate_values_update_after_recomputation() -> None:
    _, state, computations, outputs = full_page_runtime_payload(NUMERIC_FIXTURE_PATH)
    definition = next(
        item
        for item in outputs["intermediate_values"]
        if item["label"] == "Sum"
    )
    expression = (
        "(function () { const target = elements["
        + json.dumps(definition["element_id"])
        + "]; const before = collectText(target); "
        "window.lessonRuntime.context[\"block_2_1.left\"] = 10; "
        "window.lessonRuntime.recompute(); window.lessonRuntime.render(); "
        "return { before: before, after: collectText(target), "
        "value: window.lessonRuntime.context[\"block_2_1.total\"] }; }())"
    )

    result = run_runtime(expression, state, computations, outputs)

    assert result["value"] == 15
    assert "7" in result["before"]
    assert "15" in result["after"]
    assert result["before"] != result["after"]


def test_two_substantially_different_fixtures_use_same_renderer() -> None:
    call1_html, _, _, _ = full_page_runtime_payload(CALL1_FIXTURE_PATH)
    numeric_html, _, _, _ = full_page_runtime_payload(NUMERIC_FIXTURE_PATH)

    assert "Query-Dependent Weighted Memory" in call1_html
    assert "A Small Arithmetic Dataflow" in numeric_html
    assert "const visualizationRegistry" in call1_html
    assert "const visualizationRegistry" in numeric_html
    assert "if topic" not in call1_html.lower()
    assert "if topic" not in numeric_html.lower()


def test_both_fixture_pages_have_no_remote_dependencies() -> None:
    for fixture_path in (CALL1_FIXTURE_PATH, NUMERIC_FIXTURE_PATH):
        html, _, _, _ = full_page_runtime_payload(fixture_path)
        lowered = html.lower()
        assert "<script src=" not in lowered
        assert "<link" not in lowered
        assert "@import" not in lowered
