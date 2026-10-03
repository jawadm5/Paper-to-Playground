"""V2.1 wire-contract, reference, and local-asset checks.

These checks establish a usable, traceable handoff, not independent scientific
verification of the model's prose. The JSON Schemas in docs/v2 are authoritative.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit
import warnings

from jsonschema import Draft202012Validator, FormatChecker
from PIL import Image


class ValidationError(ValueError):
    """An input, generated content, or handoff needs an actionable correction."""


_SCHEMAS = Path(__file__).resolve().parents[1] / "docs" / "v2" / "schemas"
_NAMES = {"input", "call1-input", "call1-content", "paper-content"}


def load_schema(name: str) -> dict:
    if name not in _NAMES:
        raise ValidationError("Unknown V2 schema name: " + str(name))
    try:
        return json.loads((_SCHEMAS / (name + ".schema.json")).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValidationError("Could not load the V2 " + name + " schema") from error


def _shape(name: str, value: object, definition: str | None = None) -> None:
    schema = load_schema(name)
    if definition is not None:
        schema = {"$schema": schema["$schema"], "$defs": schema["$defs"],
                  "$ref": "#/$defs/" + definition}
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = []
    for error in validator.iter_errors(value):
        path = "/" + "/".join(str(part) for part in error.absolute_path)
        errors.append(path + ": " + error.message.replace("\n", " ")[:280])
        if len(errors) == 8:
            break
    if errors:
        raise ValidationError(name + ("." + definition if definition else "") + " contract: " + "; ".join(errors))


def _unique(items: list[dict], label: str) -> set[str]:
    seen: set[str] = set()
    for item in items:
        if item["id"] in seen:
            raise ValidationError(label + ": duplicate ID " + item["id"])
        seen.add(item["id"])
    return seen


def _refs(values, allowed: set[str], label: str) -> None:
    missing = set(values) - allowed
    if missing:
        raise ValidationError(label + ": unknown or unavailable reference(s): " + ", ".join(sorted(missing)))


def validate_input(data: dict) -> dict:
    """Consume three trimmed strings; the CLI reports ignored field names."""
    if not isinstance(data, dict):
        raise ValidationError("Input must be a JSON object")
    normalized = {}
    for key in ("source_url", "focus", "audience"):
        if not isinstance(data.get(key), str):
            raise ValidationError(key + " must be a nonempty string")
        normalized[key] = data[key].strip()
    _shape("input", normalized)
    try:
        parsed = urlsplit(normalized["source_url"])
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username is not None or parsed.password is not None:
            raise ValueError()
        parsed.port
    except ValueError as error:
        raise ValidationError("source_url must be a valid HTTP(S) URL without embedded credentials") from error
    return normalized


def validate_context(context: dict) -> None:
    _shape("call1-input", context)
    texts = _unique(context["source_blocks"], "source_blocks")
    visuals = _unique(context["visuals"], "visuals")
    collision = texts & visuals
    if collision:
        raise ValidationError("Text and visual evidence IDs must be distinct: " + ", ".join(sorted(collision)))


def validate_content(content: dict, context: dict) -> None:
    validate_context(context)
    _shape("call1-content", content)
    sections = _unique(content["sections"], "sections")
    outcomes = _unique(content["learning_outcomes"], "learning_outcomes")
    concepts = _unique(content["concepts"], "concepts")
    if not outcomes or not concepts:
        raise ValidationError("Content needs at least one learning outcome and one concept anchor")
    evidence = {item["id"] for item in context["source_blocks"] + context["visuals"]}
    visual_ids = {item["id"] for item in context["visuals"]}
    position = {section["id"]: index for index, section in enumerate(content["sections"])}
    covered = set()
    models = []

    def check_evidence(value, path="content"):
        if isinstance(value, dict):
            if "source_refs" in value:
                _refs(value["source_refs"], evidence, path + ".source_refs")
            for key, child in value.items():
                check_evidence(child, path + "." + key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                check_evidence(child, path + "[" + str(index) + "]")

    check_evidence(content)
    for index, section in enumerate(content["sections"]):
        label = "section " + section["id"]
        parent = section["parent_id"]
        if parent is not None and (parent not in position or position[parent] >= index):
            raise ValidationError(label + ": parent_id must identify an earlier section")
        if section["kind"] != "prerequisites" and not section["source_refs"]:
            raise ValidationError(label + ": a paper section requires supporting source_refs")
        _refs(section["learning_outcome_ids"], outcomes, label + ".learning_outcome_ids")
        covered.update(section["learning_outcome_ids"])
        _refs(section["visual_ids"], visual_ids, label + ".visual_ids")
        for connection in section["connections"]:
            if connection["section_id"] is not None:
                _refs([connection["section_id"]], sections, label + ".connections")
        for boundary_index, boundary in enumerate(section["boundaries"]):
            if boundary["kind"] == "missing_information":
                raise ValidationError(f"/sections/{index}/boundaries/{boundary_index} ({label}): essential missing information must be resolved before publication: " + boundary["description"][:300])
        if "mathematical_model" in section:
            models.append((label, section["mathematical_model"]))
    if covered != outcomes:
        raise ValidationError("Learning outcomes not covered by any section: " + ", ".join(sorted(outcomes - covered)))
    for concept in content["concepts"]:
        _refs([concept["section_id"]], sections, "concept " + concept["id"] + ".section_id")
    linked = set()
    for relationship in content["relationships"]:
        endpoints = {relationship["from"], relationship["to"]}
        _refs(endpoints, concepts, "relationship endpoints")
        linked.update(endpoints)
    if len(concepts) > 1 and concepts - linked:
        raise ValidationError("Concepts without a map relationship: " + ", ".join(sorted(concepts - linked)))

    variables = [v for _, model in models for v in model["variables"]]
    equations = [e for _, model in models for e in model["equations"]]
    variable_ids = _unique(variables, "mathematical variables across sections")
    equation_ids = _unique(equations, "mathematical equations across sections")
    for equation in equations:
        _refs(equation["variable_ids"], variable_ids, "equation " + equation["id"] + ".variable_ids")
    available = set()
    for label, model in models:
        # Local inputs and parameters start available. Earlier section results
        # remain available without redeclaring their globally unique IDs.
        available.update(v["id"] for v in model["variables"] if v["role"] in ("input", "parameter"))
        for index, step in enumerate(model["steps"]):
            step_label = label + ".steps[" + str(index) + "]"
            _refs(step["input_ids"], available, step_label + ".input_ids (defined before this step)")
            _refs(step["output_ids"], variable_ids, step_label + ".output_ids")
            _refs(step["equation_ids"], equation_ids, step_label + ".equation_ids")
            available.update(step["output_ids"])
        if model["steps"]:
            expected = {v["id"] for v in model["variables"] if v["role"] in ("intermediate", "output")}
            _refs(expected, available, label + ": computed variables require defining steps")


def _asset(visual: dict, output: Path) -> None:
    if visual["asset_path"] is None:
        return
    base = output.resolve()
    try:
        path = (base / visual["asset_path"]).resolve(strict=True)
        relative = path.relative_to(base)
        if len(relative.parts) < 2 or relative.parts[0] != "assets" or not path.is_file():
            raise ValueError()
    except (OSError, ValueError) as error:
        raise ValidationError("Visual " + visual["id"] + ": asset must exist inside the handoff assets directory") from error
    formats = {"PNG": ("image/png", {".png"}), "JPEG": ("image/jpeg", {".jpg", ".jpeg"}), "WEBP": ("image/webp", {".webp"}), "GIF": ("image/gif", {".gif"})}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as picture:
                actual = formats.get(picture.format)
                if actual is None or visual["mime_type"] != actual[0] or path.suffix.lower() not in actual[1]:
                    raise ValidationError("Visual " + visual["id"] + ": declared MIME type and extension must match the actual image format")
                picture.verify()
    except ValidationError:
        raise
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValidationError("Visual " + visual["id"] + ": asset is not a valid supported image") from error


def validate_source(source: dict, output: Path) -> None:
    """Check prepared source metadata and local assets before a provider call."""
    _shape("paper-content", source, "HandoffSource")
    texts = _unique(source["references"], "handoff source references")
    visuals = _unique(source["visuals"], "handoff source visuals")
    if texts & visuals:
        raise ValidationError("Handoff text and visual evidence IDs must be distinct")
    for visual in source["visuals"]:
        _asset(visual, Path(output))


def validate_handoff(handoff: dict, output: Path) -> None:
    _shape("paper-content", handoff)
    normalized = validate_input(handoff["input"])
    if handoff["input"] != normalized:
        raise ValidationError("Handoff input must contain only the three trimmed input strings")
    source = handoff["source"]
    validate_source(source, output)
    supplied = [{key: item[key] for key in ("id", "kind", "caption", "locator", "provided_as")}
                for item in source["visuals"] if item["provided_as"] != "not_provided"]
    context = {"focus": normalized["focus"], "audience": normalized["audience"],
               "source_blocks": source["references"], "visuals": supplied,
               "extraction_warnings": source["warnings"]}
    validate_content(handoff["content"], context)
