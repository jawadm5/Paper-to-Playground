import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.schema import LessonRenderSpec


FIXTURES = Path(__file__).parent / "fixtures"
RENDER_SPEC_FIXTURE = "call1_render_spec.json"


def load_fixture(name: str = RENDER_SPEC_FIXTURE) -> dict:
    with (FIXTURES / name).open(encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def test_full_paper_render_spec_passes() -> None:
    spec = LessonRenderSpec.model_validate(load_fixture())

    assert len(spec.learning_outcomes) == 5
    assert len(spec.sections) == 7
    assert len(spec.mind_map.concepts) == 10
    assert len(spec.mind_map.relationships) == 12
    assert len(spec.assessment) == 3

    method_section = next(
        section for section in spec.sections if section.id == "proposed_reader"
    )
    assert method_section.equations is not None
    assert len(method_section.equations) == 3
    assert method_section.interactive_blocks is not None
    assert len(method_section.interactive_blocks) == 1

    block = method_section.interactive_blocks[0]
    assert len(block.controls) == 5
    assert block.computations[2].condition == "apply_scaling"
    assert block.computations[2].otherwise == "raw_scores"

    relationship = spec.mind_map.relationships[0]
    assert relationship.from_id == "weighted_sum_background"
    assert relationship.to_id == "value_readout"


def test_second_numeric_render_spec_passes_same_schema() -> None:
    spec = LessonRenderSpec.model_validate(load_fixture("numeric_render_spec.json"))

    assert spec.meta.title == "A Small Arithmetic Dataflow"
    assert spec.sections[1].interactive_blocks is not None
    assert spec.sections[1].interactive_blocks[0].visualizations[0].type == "bar_chart"


@pytest.mark.parametrize(
    "required_field",
    ["meta", "learning_outcomes", "sections", "mind_map", "assessment"],
)
def test_required_top_level_document_fields(required_field: str) -> None:
    data = load_fixture()
    del data[required_field]

    with pytest.raises(ValidationError) as exc_info:
        LessonRenderSpec.model_validate(data)

    assert required_field in str(exc_info.value)


def test_unknown_top_level_fields_are_rejected() -> None:
    data = load_fixture()
    data["html"] = "<script>alert('not allowed')</script>"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        LessonRenderSpec.model_validate(data)


def test_interactive_block_restricts_operations() -> None:
    data = load_fixture()
    data["sections"][3]["interactive_blocks"][0]["computations"][0][
        "op"
    ] = "execute_python"

    with pytest.raises(ValidationError, match="Input should be"):
        LessonRenderSpec.model_validate(data)


def test_interactive_block_requires_two_controls() -> None:
    data = load_fixture()
    block = data["sections"][3]["interactive_blocks"][0]
    block["controls"] = block["controls"][:1]

    with pytest.raises(ValidationError, match="at least 2 items"):
        LessonRenderSpec.model_validate(data)


def test_nested_matrix_defaults_must_be_rectangular() -> None:
    data = load_fixture()
    block = data["sections"][3]["interactive_blocks"][0]
    block["variables"][0]["default"] = [[1.0, 2.0], [3.0]]

    with pytest.raises(ValidationError, match="matrix rows must all have the same length"):
        LessonRenderSpec.model_validate(data)


def test_conditional_computation_requires_condition_and_otherwise() -> None:
    data = load_fixture()
    computation = data["sections"][3]["interactive_blocks"][0]["computations"][2]
    del computation["otherwise"]

    with pytest.raises(
        ValidationError,
        match="condition and otherwise must either both be provided or both be omitted",
    ):
        LessonRenderSpec.model_validate(data)


def test_section_parent_must_resolve() -> None:
    data = load_fixture()
    data["sections"][0]["parent_id"] = "missing_section"

    with pytest.raises(ValidationError, match="references missing parent section"):
        LessonRenderSpec.model_validate(data)


def test_valid_concept_graph_preserves_call_one_relationships() -> None:
    spec = LessonRenderSpec.model_validate(load_fixture())

    relationship = next(
        item
        for item in spec.mind_map.relationships
        if item.label == "supplies scores to"
    )
    assert relationship.from_id == "query_key_matching"
    assert relationship.to_id == "normalized_coefficients"
    assert relationship.source_refs == ["s_formula"]


def test_mind_map_relationship_from_must_resolve() -> None:
    data = load_fixture()
    data["mind_map"]["relationships"][0]["from"] = "missing_concept"

    with pytest.raises(ValidationError, match="references missing concept 'missing_concept'"):
        LessonRenderSpec.model_validate(data)


def test_mind_map_relationship_to_must_resolve() -> None:
    data = load_fixture()
    data["mind_map"]["relationships"][0]["to"] = "missing_concept"

    with pytest.raises(ValidationError, match="references missing concept 'missing_concept'"):
        LessonRenderSpec.model_validate(data)


def test_mind_map_concept_section_must_resolve_when_present() -> None:
    data = load_fixture()
    data["mind_map"]["concepts"][0]["section_id"] = "missing_section"

    with pytest.raises(ValidationError, match="references missing section 'missing_section'"):
        LessonRenderSpec.model_validate(data)


def test_mind_map_concept_may_have_no_section_reference() -> None:
    data = load_fixture()
    data["mind_map"]["concepts"][0]["section_id"] = None

    spec = LessonRenderSpec.model_validate(data)

    assert spec.mind_map.concepts[0].section_id is None


def test_duplicate_mind_map_concept_ids_fail_clearly() -> None:
    data = load_fixture()
    data["mind_map"]["concepts"][1]["id"] = data["mind_map"]["concepts"][0]["id"]

    with pytest.raises(ValidationError, match="Duplicate mind-map concept id"):
        LessonRenderSpec.model_validate(data)


def test_assessment_learning_outcomes_must_resolve() -> None:
    data = load_fixture()
    data["assessment"][0]["learning_outcome_ids"] = ["missing_outcome"]

    with pytest.raises(ValidationError, match="references missing learning outcome"):
        LessonRenderSpec.model_validate(data)
