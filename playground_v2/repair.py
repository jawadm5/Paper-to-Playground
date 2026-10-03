"""Apply one bounded set of replacements to a rejected JSON content object."""
from __future__ import annotations

from copy import deepcopy
import math
import re

from .validation import ValidationError


_ARRAY_INDEX = re.compile(r"0|[1-9][0-9]*")
_BAD_ESCAPE = re.compile(r"~(?![01])")


def _json_value(value) -> bool:
    if value is None or isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _json_value(item) for key, item in value.items())
    return False


def _pointer(path: object) -> tuple[str, ...]:
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValidationError("Each replacement path must be a non-root JSON pointer starting with '/'")
    if _BAD_ESCAPE.search(path):
        raise ValidationError("Replacement path has an invalid JSON pointer escape; use ~0 or ~1")
    return tuple(part.replace("~1", "/").replace("~0", "~") for part in path[1:].split("/"))


def _key(container, token: str):
    if isinstance(container, dict):
        if token not in container:
            raise ValidationError("Replacement path must identify an existing object key")
        return token
    if isinstance(container, list):
        if not _ARRAY_INDEX.fullmatch(token):
            raise ValidationError("Replacement array indices must be canonical nonnegative integers; '-' is not supported")
        # Compare decimal strings before int() to reject arbitrarily large indices.
        last = str(len(container) - 1)
        if not container or len(token) > len(last) or (len(token) == len(last) and token > last):
            raise ValidationError("Replacement array index is outside the existing array")
        return int(token)
    raise ValidationError("Replacement path cannot traverse a scalar value")


def apply_replacements(content: dict, patch: dict) -> dict:
    """Return a deep copy with at most eight existing branches replaced."""
    if not isinstance(content, dict) or not _json_value(content):
        raise ValidationError("Content to repair must be a JSON object")
    if not isinstance(patch, dict) or set(patch) != {"patches"}:
        raise ValidationError("Repair response must contain exactly the 'patches' key")
    replacements = patch["patches"]
    if not isinstance(replacements, list) or len(replacements) > 8:
        raise ValidationError("Repair patches must be an array containing at most 8 replacements")
    decoded = []
    for replacement in replacements:
        if not isinstance(replacement, dict) or set(replacement) != {"path", "value"}:
            raise ValidationError("Each replacement must contain exactly 'path' and 'value'")
        tokens = _pointer(replacement["path"])
        if not _json_value(replacement["value"]):
            raise ValidationError("Replacement value must be valid finite JSON")
        for previous, _ in decoded:
            shorter = min(len(tokens), len(previous))
            if tokens[:shorter] == previous[:shorter]:
                raise ValidationError("Replacement paths must not duplicate or overlap")
        decoded.append((tokens, replacement["value"]))
    result = deepcopy(content)
    for tokens, value in decoded:
        parent = result
        for token in tokens[:-1]:
            parent = parent[_key(parent, token)]
        parent[_key(parent, tokens[-1])] = deepcopy(value)
    return result
