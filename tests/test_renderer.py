import copy
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

import pytest

from src.renderer import render_to_html, write_html
from src.schema import LessonRenderSpec


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "call1_render_spec.json"


def load_data() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def load_spec() -> LessonRenderSpec:
    return LessonRenderSpec.model_validate(load_data())


class DependencyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.remote_dependencies = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        if tag == "script" and attributes.get("src"):
            self.remote_dependencies.append(attributes["src"])
        if tag == "link" and "stylesheet" in attributes.get("rel", "").split():
            self.remote_dependencies.append(attributes.get("href", ""))
        if tag in {"img", "iframe", "source"} and attributes.get("src"):
            self.remote_dependencies.append(attributes["src"])


class EmbeddedJsonParser(HTMLParser):
    def __init__(self, element_id: str) -> None:
        super().__init__()
        self.element_id = element_id
        self.in_target = False
        self.text: Optional[str] = None

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        if tag == "script" and attributes.get("id") == self.element_id:
            self.in_target = True
            self.text = ""

    def handle_data(self, data: str) -> None:
        if self.in_target and self.text is not None:
            self.text += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.in_target:
            self.in_target = False


def embedded_json(html: str, element_id: str):
    parser = EmbeddedJsonParser(element_id)
    parser.feed(html)
    assert parser.text is not None
    return json.loads(parser.text)


def test_full_paper_header_and_learning_outcomes_render() -> None:
    html = render_to_html(load_spec())

    assert html.startswith("<!doctype html>")
    assert "A teaching edition of Query-Dependent Weighted Memory" in html
    assert "From fixed averaging to a query-dependent weighted readout" in html
    assert "What you will be able to do" in html
    assert "Explain why uniform averaging cannot respond" in html
    assert "7 sections" in html
    assert "5 learning outcomes" in html


def test_all_sections_render_in_parent_child_order() -> None:
    html = render_to_html(load_spec())
    ordered_ids = [
        "prerequisite_tools",
        "paper_introduction",
        "averaging_problem",
        "proposed_reader",
        "algebraic_observations",
        "evidence_limits",
        "paper_conclusion",
    ]

    positions = [html.index(f'data-section-id="{section_id}"') for section_id in ordered_ids]

    assert positions == sorted(positions)
    assert 'data-parent-id="paper_introduction"' in html
    assert 'data-parent-id="proposed_reader"' in html
    assert "depth-1" in html
    assert "depth-2" in html


def test_hierarchical_navigation_links_to_every_section() -> None:
    html = render_to_html(load_spec())

    for index in range(1, 8):
        assert f'href="#section-{index}"' in html
        assert f'id="section-{index}"' in html
    assert '<ol class="nav-children">' in html


def test_section_explanations_intuition_boundaries_and_sources_render() -> None:
    html = render_to_html(load_spec())

    assert "From the paper" in html
    assert "In plain language" in html
    assert "A weighted average preserves averaging" in html
    assert "Boundaries &amp; assumptions" in html
    assert "No empirical evaluation is available" in html
    assert "Section sources" in html
    assert '<code class="source-ref">s_formula</code>' in html
    assert "Key equations" in html
    assert "s_i = \\frac" in html


def test_static_section_renders_without_an_interactive_block() -> None:
    html = render_to_html(load_spec())
    start = html.index('data-section-id="prerequisite_tools"')
    end = html.index('data-section-id="paper_introduction"')
    static_section_html = html[start:end]

    assert "Before the paper: vectors and weighted sums" in static_section_html
    assert "From the paper" in static_section_html
    assert "interactive-block" not in static_section_html


def test_interactive_block_uses_namespaced_stage_four_runtime_data() -> None:
    html = render_to_html(load_spec())
    state = embedded_json(html, "lesson-initial-state")
    computations = embedded_json(html, "lesson-computations")
    outputs = embedded_json(html, "lesson-outputs")

    assert state["block_4_1.q"] == [[1.0, 0.0]]
    assert state["block_4_1.apply_scaling"] is True
    assert computations[0] == {
        "id": "block_4_1.raw_scores",
        "op": "matmul_transpose",
        "inputs": ["block_4_1.q", "block_4_1.keys"],
    }
    assert computations[2]["condition"] == "block_4_1.apply_scaling"
    assert outputs["intermediate_values"][0]["data"] == "block_4_1.raw_scores"
    assert outputs["visualizations"][0]["type"] == "heatmap"
    assert outputs["visualizations"][0]["data"] == "block_4_1.weights"
    assert 'data-interactive-block-id="query_dependent_reader_demo"' in html
    assert 'data-control-type="matrix_editor"' in html
    assert 'data-visualization-type="heatmap"' in html
    assert 'data-visualization-type="matrix_display"' in html
    assert 'data-visualization-type="step_pipeline"' in html
    assert "Change the query" in html


def test_two_interactive_blocks_in_different_sections_are_isolated() -> None:
    data = load_data()
    second_block = copy.deepcopy(data["sections"][3]["interactive_blocks"][0])
    second_block["id"] = "results_reader_demo"
    second_block["title"] = "A second reusable block"
    data["sections"][4]["interactive_blocks"] = [second_block]

    html = render_to_html(LessonRenderSpec.model_validate(data))
    state = embedded_json(html, "lesson-initial-state")
    computations = embedded_json(html, "lesson-computations")
    outputs = embedded_json(html, "lesson-outputs")

    assert html.count('class="interactive-block"') == 2
    assert "block_4_1.q" in state
    assert "block_5_1.q" in state
    assert {item["id"] for item in computations if item["id"].endswith(".readout")} == {
        "block_4_1.readout",
        "block_5_1.readout",
    }
    assert {
        item["data"]
        for item in outputs["intermediate_values"]
        if item["data"].endswith(".readout")
    } == {"block_4_1.readout", "block_5_1.readout"}


def test_all_existing_visualization_types_are_dispatched_generically() -> None:
    data = load_data()
    block = data["sections"][3]["interactive_blocks"][0]
    block["variables"].append(
        {"id": "chart_values", "type": "vector", "default": [1.0, 3.0, 2.0]}
    )
    block["visualizations"].extend(
        [
            {
                "id": "generic_bars",
                "type": "bar_chart",
                "data": "chart_values",
                "title": "Generic bars",
            },
            {
                "id": "generic_line",
                "type": "line_chart",
                "data": "chart_values",
                "title": "Generic line",
            },
        ]
    )

    html = render_to_html(LessonRenderSpec.model_validate(data))
    outputs = embedded_json(html, "lesson-outputs")

    assert {item["type"] for item in outputs["visualizations"]} == {
        "bar_chart",
        "line_chart",
        "heatmap",
        "matrix_display",
        "step_pipeline",
    }


@pytest.mark.parametrize("component", ["visualization", "intermediate"])
def test_missing_interactive_data_ids_fail_clearly(component: str) -> None:
    data = load_data()
    block = data["sections"][3]["interactive_blocks"][0]
    if component == "visualization":
        block["visualizations"][0]["data"] = "missing_result"
    else:
        block["intermediate_values"][0]["data"] = "missing_result"

    spec = LessonRenderSpec.model_validate(data)

    with pytest.raises(ValueError, match="references missing data ID 'missing_result'"):
        render_to_html(spec)


def test_mind_map_renders_nodes_labeled_directed_edges_and_click_targets() -> None:
    html = render_to_html(load_spec())

    assert "weight_heatmap" in html
    assert "Algebraic evidence boundary" in html
    assert html.count('class="mind-map-node"') == 10
    assert html.count('class="mind-map-edge-path"') == 12
    assert "supplies scores to" in html
    assert 'marker-end="url(#mind-map-arrow)"' in html
    node = re.search(
        r'<g class="mind-map-node".*?data-concept-id="query_key_matching".*?data-section-target="([^"]*)"',
        html,
        re.DOTALL,
    )
    assert node is not None
    assert node.group(1) == "section-4"
    assert "target.scrollIntoView" in html
    assert 'classList.add("is-selected")' in html
    assert "What happens when every compatibility score is equal?" not in html


def test_mind_map_concept_without_section_has_graceful_empty_target() -> None:
    data = load_data()
    data["mind_map"]["concepts"][0]["section_id"] = None

    html = render_to_html(LessonRenderSpec.model_validate(data))
    node = re.search(
        r'<g class="mind-map-node".*?data-concept-id="weighted_sum_background".*?data-section-target="([^"]*)"',
        html,
        re.DOTALL,
    )

    assert node is not None
    assert node.group(1) == ""
    assert "This concept has no linked section." in html


def test_mind_map_renderer_has_no_topic_specific_dispatch() -> None:
    renderer_source = (
        Path(__file__).parents[1] / "src" / "renderer.py"
    ).read_text(encoding="utf-8").lower()

    assert "query-key matching" not in renderer_source
    assert "weighted memory" not in renderer_source
    assert "entropy" not in renderer_source
    assert "attention" not in renderer_source


def test_page_is_self_contained() -> None:
    html = render_to_html(load_spec())
    parser = DependencyParser()
    parser.feed(html)

    assert "<style>" in html
    assert "system-ui" in html
    assert "<script src=" not in html.lower()
    assert "@import" not in html.lower()
    assert parser.remote_dependencies == []
    assert "eval(" not in html


def test_full_paper_content_is_html_escaped() -> None:
    data = load_data()
    data["meta"]["title"] = '<script>alert("unsafe")</script>'
    data["sections"][0]["paper_explanation"] = "x < y & y > z"
    data["sections"][0]["source_refs"] = ["<unsafe-ref>"]

    html = render_to_html(LessonRenderSpec.model_validate(data))

    assert '<script>alert("unsafe")</script>' not in html
    assert "&lt;script&gt;alert(&quot;unsafe&quot;)&lt;/script&gt;" in html
    assert "x &lt; y &amp; y &gt; z" in html
    assert "&lt;unsafe-ref&gt;" in html


def test_renderer_is_generic_across_paper_content() -> None:
    data = load_data()
    data["meta"] = {
        "title": "A Generic Paper Lesson",
        "subtitle": "A topic-independent rendering check",
    }
    data["sections"][0]["title"] = "Generic prerequisite section"

    html = render_to_html(LessonRenderSpec.model_validate(data))

    assert "A Generic Paper Lesson" in html
    assert "Generic prerequisite section" in html


def test_renderer_rejects_cyclic_section_hierarchy() -> None:
    data = load_data()
    data["sections"][1]["parent_id"] = "averaging_problem"
    spec = LessonRenderSpec.model_validate(data)

    with pytest.raises(ValueError, match="Section hierarchy contains a cycle"):
        render_to_html(spec)


def test_write_html_creates_parent_directories(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "index.html"

    write_html(load_spec(), destination)

    assert destination.is_file()
    assert destination.read_text(encoding="utf-8") == render_to_html(load_spec())
