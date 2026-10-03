import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.schema import LessonRenderSpec


FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    with (FIXTURES / name).open(encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def error_locations(error: ValidationError) -> set[str]:
    return {".".join(str(part) for part in item["loc"]) for item in error.errors()}


def test_valid_attention_fixture_passes() -> None:
    spec = LessonRenderSpec.model_validate(load_fixture("attention_render_spec.json"))

    assert spec.schema_version == "0.1"
    assert len(spec.controls) >= 2
    assert len(spec.visualizations) >= 1
    assert len(spec.guided_explorations) >= 2
    assert spec.limitation.text
    assert spec.source.paper


def test_invalid_fixture_reports_each_contract_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        LessonRenderSpec.model_validate(load_fixture("invalid_render_spec.json"))

    locations = error_locations(exc_info.value)
    assert "controls" in locations
    assert "computations.0.op" in locations
    assert "visualizations.0.type" in locations


@pytest.mark.parametrize("required_field", ["limitation", "source"])
def test_limitation_and_source_are_required(required_field: str) -> None:
    data = load_fixture("attention_render_spec.json")
    del data[required_field]

    with pytest.raises(ValidationError) as exc_info:
        LessonRenderSpec.model_validate(data)

    assert required_field in error_locations(exc_info.value)


def test_unknown_fields_are_rejected() -> None:
    data = load_fixture("attention_render_spec.json")
    data["html"] = "<script>alert('not allowed')</script>"

    with pytest.raises(ValidationError) as exc_info:
        LessonRenderSpec.model_validate(data)

    assert "html" in error_locations(exc_info.value)


def test_matrix_defaults_must_be_rectangular() -> None:
    data = load_fixture("attention_render_spec.json")
    data["variables"][0]["default"] = [[1.0, 2.0], [3.0]]

    with pytest.raises(ValidationError, match="matrix rows must all have the same length"):
        LessonRenderSpec.model_validate(data)
