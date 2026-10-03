"""Lossless identifier casing correction for known Call 1 content fields."""
from copy import deepcopy
import re

from .validation import ValidationError


_SAFE_ID = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}", re.ASCII)


def normalize_content_ids(content: dict) -> tuple[dict, list[dict]]:
    """Lowercase safe definition IDs and their typed references, with an audit.

    Source/visual identifiers and all free text remain byte-for-byte unchanged.
    Unknown fields and structurally malformed values remain for normal validation.
    """
    if not isinstance(content, dict):
        raise ValidationError("Content identifier normalization requires a JSON object")
    result = deepcopy(content)
    definitions = []
    references = []

    def records(parent, key, path):
        values = parent.get(key, [])
        if isinstance(values, list):
            for index, value in enumerate(values):
                if isinstance(value, dict):
                    yield value, path + "/" + key + "/" + str(index)

    def definition(item, path, kind):
        if isinstance(item.get("id"), str):
            definitions.append((item, path + "/id", kind, item["id"]))

    def reference(item, key, path, kind, many=False):
        value = item.get(key)
        if many:
            if isinstance(value, list):
                for index, identifier in enumerate(value):
                    if isinstance(identifier, str):
                        references.append((value, index, path + "/" + key + "/" + str(index), kind, identifier))
        elif isinstance(value, str):
            references.append((item, key, path + "/" + key, kind, value))

    for outcome, path in records(result, "learning_outcomes", ""):
        definition(outcome, path, "outcome")
    for section, path in records(result, "sections", ""):
        definition(section, path, "section")
        reference(section, "parent_id", path, "section")
        reference(section, "learning_outcome_ids", path, "outcome", many=True)
        for connection, connection_path in records(section, "connections", path):
            reference(connection, "section_id", connection_path, "section")
        model = section.get("mathematical_model")
        if not isinstance(model, dict):
            continue
        model_path = path + "/mathematical_model"
        for variable, variable_path in records(model, "variables", model_path):
            definition(variable, variable_path, "variable")
        for equation, equation_path in records(model, "equations", model_path):
            definition(equation, equation_path, "equation")
            reference(equation, "variable_ids", equation_path, "variable", many=True)
        for step, step_path in records(model, "steps", model_path):
            reference(step, "input_ids", step_path, "variable", many=True)
            reference(step, "output_ids", step_path, "variable", many=True)
            reference(step, "equation_ids", step_path, "equation", many=True)
    for concept, path in records(result, "concepts", ""):
        definition(concept, path, "concept")
        reference(concept, "section_id", path, "section")
    for relationship, path in records(result, "relationships", ""):
        reference(relationship, "from", path, "concept")
        reference(relationship, "to", path, "concept")

    mappings = {}
    canonical_names = {}
    for _item, path, kind, identifier in definitions:
        canonical = identifier.lower() if _SAFE_ID.fullmatch(identifier) else identifier
        previous = canonical_names.setdefault(canonical, identifier)
        if previous != identifier:
            raise ValidationError("Content identifier casing collision: " + repr(previous) +
                                  " and " + repr(identifier) + " would both identify " + repr(canonical))
        if canonical != identifier:
            mappings[(kind, identifier)] = canonical
    changes = []
    for item, path, kind, identifier in definitions:
        if (kind, identifier) in mappings:
            canonical = mappings[(kind, identifier)]
            item["id"] = canonical
            changes.append({"path": path, "before": identifier, "after": canonical})
    for parent, key, path, kind, identifier in references:
        if (kind, identifier) in mappings:
            canonical = mappings[(kind, identifier)]
            parent[key] = canonical
            changes.append({"path": path, "before": identifier, "after": canonical})
    return result, changes
