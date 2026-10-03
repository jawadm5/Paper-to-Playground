"""One reviewable, bounded OpenRouter request for V2 Call 1.

The editable prompt is read on every invocation. Bare JSON is required: only
surrounding whitespace is removed; Markdown fences, duplicate keys, and
nonfinite JSON numbers are rejected. The caller validates the returned content
schema and source references before publishing the handoff.
"""
from __future__ import annotations

import base64
import json
import math
import re
import time
from pathlib import Path
from typing import Any

from .transport import ENDPOINT, run_worker

from .validation import load_schema

MAX_IMAGES = 6
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_CONTENT_BYTES = 512 * 1024
PATCH_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["patches"],
    "properties": {"patches": {
        "type": "array", "minItems": 0, "maxItems": 8,
        "items": {"type": "object", "additionalProperties": False,
                  "required": ["path", "value"],
                  "properties": {
                      "path": {"type": "string", "maxLength": 512,
                               "pattern": r"^/(?:[^~/]|~[01])+(?:/(?:[^~/]|~[01])+)*$"},
                      "value": {}}}}},
}


class ProviderError(RuntimeError):
    """A failed call with preserved public accounting and snapshot locations."""

    def __init__(self, message: str, *, report: dict):
        super().__init__(message)
        self.report = report


def _redact(value: Any, key: str) -> Any:
    if isinstance(value, str):
        return value.replace(key, "[REDACTED]") if isinstance(key, str) and key else value
    if isinstance(value, list):
        return [_redact(item, key) for item in value]
    if isinstance(value, dict):
        return {str(name): _redact(item, key) for name, item in value.items()}
    return value


def _write(path: Path, value: dict, key: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_redact(value, key), ensure_ascii=False,
                               allow_nan=False, indent=2) + "\n", encoding="utf-8")


def _usage(value: Any) -> dict | None:
    """Retain accounting only, never arbitrary provider metadata or reasoning."""
    if not isinstance(value, dict):
        return None

    def counts(data, names):
        return {name: data[name] for name in names if name in data
                and isinstance(data[name], (int, float)) and not isinstance(data[name], bool)
                and math.isfinite(data[name]) and data[name] >= 0}

    result = counts(value, ("prompt_tokens", "completion_tokens", "total_tokens", "cost"))
    details = {
        "prompt_tokens_details": ("cached_tokens", "cache_write_tokens", "audio_tokens"),
        "completion_tokens_details": ("reasoning_tokens", "audio_tokens", "accepted_prediction_tokens", "rejected_prediction_tokens"),
    }
    for name, allowed in details.items():
        if isinstance(value.get(name), dict):
            result[name] = counts(value[name], allowed)
    return result or None


def _image_type(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _images(context: dict, source: dict, output: Path) -> tuple[list[dict], list[str]]:
    source_visuals = source.get("visuals", [])
    by_id = {visual["id"]: visual for visual in source_visuals}
    if len(by_id) != len(source_visuals):
        raise ValueError("Source contains duplicate visual IDs")
    root = output.resolve()
    parts, attached, total = [], [], 0
    seen = set()
    for visual in context.get("visuals", []):
        identifier = visual["id"]
        if identifier in seen:
            raise ValueError("Context contains duplicate visual IDs")
        seen.add(identifier)
        metadata = by_id.get(identifier)
        if metadata is None or metadata.get("provided_as") != visual.get("provided_as"):
            raise ValueError(f"Visual {identifier} has inconsistent source/context metadata")
        if visual.get("provided_as") not in ("image_only", "image_and_caption"):
            continue
        if len(attached) >= MAX_IMAGES:
            raise ValueError(f"At most {MAX_IMAGES} actual images may be attached")
        asset = metadata.get("asset_path")
        if not isinstance(asset, str) or not asset or Path(asset).is_absolute():
            raise ValueError(f"Visual {identifier} needs an output-relative image asset")
        try:
            image_path = (root / asset).resolve(strict=True)
            image_path.relative_to(root)
            if not image_path.is_file() or image_path.stat().st_size > MAX_IMAGE_BYTES:
                raise ValueError("Unsupported asset size")
            data = image_path.read_bytes()
        except (OSError, ValueError):
            raise ValueError(f"Visual {identifier} has no readable image within the output directory") from None
        total += len(data)
        if total > MAX_IMAGE_BYTES:
            raise ValueError("Attached image bytes exceed the 8 MiB total limit")
        media_type = _image_type(data)
        if media_type is None or metadata.get("mime_type") != media_type:
            raise ValueError(f"Visual {identifier} has unsupported or mismatched image bytes")
        parts.append({"type": "text", "text": f"Actual image attachment for visual ID {identifier}. Interpret it using that visual's caption, locator, and extraction warnings in the context."})
        parts.append({"type": "image_url", "image_url": {
            "url": f"data:{media_type};base64," + base64.b64encode(data).decode("ascii"),
            "detail": "high"}})
        attached.append(identifier)
    return parts, attached


def _parse_content(text: str) -> dict:
    def unique(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError("Duplicate JSON field")
            result[name] = value
        return result

    def nonfinite(_value):
        raise ValueError("Nonfinite JSON number")

    def finite_float(text):
        value = float(text)
        if not math.isfinite(value):
            raise ValueError("Nonfinite JSON number")
        return value

    value = json.loads(text.strip(), object_pairs_hook=unique, parse_constant=nonfinite,
                       parse_float=finite_float)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def generate_content(context: dict, source: dict, output: Path, *, model: str,
                     key: str, prompt_path: Path, max_tokens: int = 18000,
                     timeout: float = 180.0,
                     response_format: str = "json_object") -> tuple[dict, dict]:
    """Make exactly one provider attempt; return content and sanitized report.

    ``source.visuals[].asset_path`` is relative to ``output``. The request
    snapshot is the exact key-free payload sent to OpenRouter, including prompt,
    JSON context, actual image data URLs, and the requested JSON schema. A
    ``response_format`` explicitly selects ``json_object`` (default) or
    ``json_schema``. The authoritative schema is also supplied as model-visible
    text in both modes. A failure raises ``ProviderError``; its report is saved to
    ``reports/call1.json``. No format fallback, model switch, or retry occurs.
    """
    return _generate(context, source, output, model=model, key=key,
                     prompt_path=prompt_path, max_tokens=max_tokens,
                     timeout=timeout, response_format=response_format)


def generate_patch(content: dict, diagnostic: Any, context: dict, source: dict,
                   output: Path, *, model: str, key: str, prompt_path: Path,
                   max_tokens: int = 2000, timeout: float = 60.0,
                   response_format: str = "json_object") -> tuple[dict, dict]:
    """Request one bounded replacement patch without applying or retrying it.

    Existing content and its diagnostic are supplied alongside the complete
    original context and actual images. The caller alone applies existing-path
    replacements and revalidates the full candidate; genuine gaps may remain.
    Snapshots use ``call1-repair.json`` and never overwrite the original call.
    """
    extra_text = "Candidate content and validation diagnostic:\n" + json.dumps(
        {"candidate": content, "diagnostic": diagnostic, "content_schema": load_schema("call1-content")}, ensure_ascii=False,
        allow_nan=False, indent=2)
    return _generate(context, source, output, model=model, key=key,
                     prompt_path=prompt_path, max_tokens=max_tokens,
                     timeout=timeout, response_format=response_format,
                     stage="call1-repair", response_schema=PATCH_SCHEMA,
                     extra_text=extra_text)


def _valid_patch(value: dict) -> bool:
    if set(value) != {"patches"} or not isinstance(value["patches"], list) or not 0 <= len(value["patches"]) <= 8:
        return False
    path_schema = PATCH_SCHEMA["properties"]["patches"]["items"]["properties"]["path"]
    return all(isinstance(item, dict) and set(item) == {"path", "value"}
               and isinstance(item["path"], str) and len(item["path"]) <= 512
               and re.fullmatch(path_schema["pattern"], item["path"]) is not None
               for item in value["patches"])


def normalize_patch(value: dict) -> tuple[dict, list[dict]]:
    """Separate optional provenance annotations from replacement operations.

    Only the two known, non-operative annotation fields are tolerated. Unknown
    operation fields still fail. The raw response and annotations stay in the
    report; they never create or alter content citations by themselves.
    """
    if not isinstance(value, dict) or set(value) != {"patches"} or not isinstance(value["patches"], list):
        return value, []
    patches, annotations = [], []
    for item in value["patches"]:
        if not isinstance(item, dict) or not {"path", "value"} <= set(item) or set(item) - {"path", "value", "basis", "source_refs"}:
            return value, []
        if "basis" in item and item["basis"] not in ("source_supported", "derived", "simplified", "background", "analogy"):
            return value, []
        if "source_refs" in item and (not isinstance(item["source_refs"], list)
                                      or not all(isinstance(ref, str) for ref in item["source_refs"])):
            return value, []
        annotation = {key: item[key] for key in ("basis", "source_refs") if key in item}
        if annotation:
            annotations.append({"path": item["path"], **annotation})
        patches.append({"path": item["path"], "value": item["value"]})
    return {"patches": patches}, annotations


def _generate(context: dict, source: dict, output: Path, *, model: str,
              key: str, prompt_path: Path, max_tokens: int = 18000,
              timeout: float = 180.0, response_format: str = "json_object",
              stage: str = "call1", response_schema: dict | None = None,
              extra_text: str | None = None, attach_images: bool = True) -> tuple[dict, dict]:
    """Shared single-attempt transport for initial content and bounded repair."""
    started = time.monotonic()
    output = Path(output)
    report = {"model": model, "stage": stage, "response_format": response_format, "attempts": 0, "usage": None,
              "duration_seconds": 0.0, "status": "preparing", "http_status": None,
              "finish_reason": None, "attached_image_ids": [],
              "request_path": f"requests/{stage}.json", "response_path": f"responses/{stage}.json",
              "report_path": f"reports/{stage}.json"}

    def finish(status: str):
        report["status"] = status
        report["duration_seconds"] = round(time.monotonic() - started, 3)
        _write(output / report["report_path"], report, key)

    def failed(message: str, code: str):
        report["error_code"] = code
        report["message"] = message
        finish("failed")
        raise ProviderError(message, report=_redact(report, key))

    try:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("OPENROUTER_API_KEY is required")
        if not isinstance(model, str) or not model.strip():
            raise ValueError("A model ID is required")
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be a positive finite number")
        if response_format not in ("json_object", "json_schema"):
            raise ValueError("response_format must be json_object or json_schema")
        prompt = Path(prompt_path).read_text(encoding="utf-8-sig")
        if not prompt.strip():
            raise ValueError("The content prompt is empty")
        image_parts, report["attached_image_ids"] = _images(context, source, output) if attach_images else ([], [])
        schema = response_schema if response_schema is not None else load_schema("call1-content")
        if stage.endswith("-repair"):
            instructions = ("Authoritative replacement-patch response schema follows. Return only "
                            "the patches object, not a rewritten content object or this schema. "
                            "Use at most eight replacements at existing non-root JSON Pointer paths. "
                            "Repair only the diagnosed issue using the supplied evidence; preserve "
                            "unaffected content. Do not invent evidence or conceal a genuine essential "
                            "gap merely to pass validation. Return an empty patches list if no "
                            "evidence-supported correction is available. No add, delete, or append operations are "
                            "available. Every item contains only path and value.\n")
        elif stage == "call2":
            instructions = ("Return the complete renderer experience object matching this schema. "
                            "Use existing Call 1 section, visual and outcome IDs. Choose renderer-owned "
                            "components and bounded mathematical expressions only; never emit executable "
                            "code, markup or invented file paths. Do not rewrite the reading content.\n")
        else:
            instructions = ("Authoritative response schema follows. It describes the output structure; "
                       "do not return this schema or a blank template. Fill the object with finished, "
                       "paper-specific learning outcomes, explanatory sections, concepts, and relationships "
                       "grounded in the supplied source. Use complete prose rather than placeholder "
                       "punctuation or empty narrative sections. Populate learning_outcomes, sections, "
                       "and concepts with supported content; keep empty lists or references only where "
                       "the schema and evidence permit them. Return the content object "
                       "only, without Markdown fences.\n")
        schema_text = instructions + json.dumps(schema, ensure_ascii=False, allow_nan=False, indent=2)
        context_label = "Validated Call 1 handoff:\n" if stage.startswith("call2") else "Call 1 source context:\n"
        user_parts = [{"type": "text", "text": context_label + json.dumps(context, ensure_ascii=False, allow_nan=False, indent=2)},
                      {"type": "text", "text": schema_text}]
        if extra_text is not None:
            user_parts.append({"type": "text", "text": extra_text})
        user_parts += image_parts
        payload = {"model": model, "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_parts}],
            "temperature": 0.2, "max_completion_tokens": max_tokens, "stream": False,
            "reasoning": {"enabled": False, "exclude": True},
            "provider": {"require_parameters": True},
            "response_format": ({"type": "json_schema", "json_schema": {
                "name": stage.replace("-", "_"), "strict": False, "schema": schema}}
                if response_format == "json_schema" else {"type": "json_object"})}
        # Credentials travel only through the worker's private transport input.
        # Accidental literal credentials in editable text are removed from both
        # the transmitted payload and its identical review snapshot.
        payload = _redact(payload, key)
        _write(output / report["request_path"], payload, key)
    except (OSError, ValueError, TypeError, KeyError) as error:
        message = str(error) if isinstance(error, ValueError) else f"Request preparation failed ({type(error).__name__})"
        failed(_redact(message, key), "request_preparation")

    remaining = timeout - (time.monotonic() - started)
    if remaining <= 0:
        failed("The call's time allowance expired before the provider request started", "preparation_timeout")
    report["attempts"] = 1
    report["status"] = "running"
    _write(output / report["report_path"], report, key)
    try:
        response = run_worker("http", {"endpoint": ENDPOINT, "key": key,
                                      "payload": payload, "timeout": remaining}, remaining)
        if not isinstance(response, dict):
            raise ValueError("Invalid worker result")
    except TimeoutError:
        response = {"status": 0, "error_code": "total_timeout"}
    except (RuntimeError, ValueError, OSError):
        response = {"status": 0, "error_code": "worker_failure"}

    public = {"status": response.get("status", 0), "id": response.get("id"),
              "content": response.get("content") if isinstance(response.get("content"), str) else None,
              "usage": _usage(response.get("usage")), "finish_reason": response.get("finish_reason"),
              "error_code": str(response.get("error_code") or "")[:80]}
    public = _redact(public, key)
    _write(output / report["response_path"], public, key)
    report.update(usage=public["usage"], http_status=public["status"],
                  finish_reason=public["finish_reason"], provider_response_id=public["id"])
    if public["status"] != 200:
        if response.get("format_unsupported"):
            failed("The selected provider rejected the structured-output or reasoning parameters. No fallback was attempted; revise the explicit request configuration or model selection before retrying.", "structured_parameters_unsupported")
        if public["error_code"] == "total_timeout":
            failed("The provider request exceeded its total time allowance and its worker was terminated", "total_timeout")
        failed(f"OpenRouter request failed (HTTP {public['status']}). Check the selected model, credentials, and network; no automatic retry occurred.", public["error_code"] or "http_error")
    if public["finish_reason"] == "length":
        failed("The response reached the completion-token limit and was rejected as truncated. Review the saved response before an explicit retry.", "truncated")
    if public["finish_reason"] in ("content_filter", "error", "tool_calls", "function_call"):
        failed("The provider did not finish a usable content response; inspect the saved finish reason", "incomplete_response")
    content = public["content"]
    if not content or not content.strip():
        failed("The provider returned no JSON content", "empty_content")
    if len(content.encode("utf-8")) > MAX_CONTENT_BYTES:
        failed("The provider content exceeds the 512 KiB response limit", "content_too_large")
    try:
        parsed = _parse_content(content)
    except (ValueError, TypeError):
        failed("The provider returned invalid JSON or a non-object response. Bare JSON is required; Markdown fences and duplicate fields are rejected.", "invalid_json")
    if stage.endswith("-repair"):
        parsed, annotations = normalize_patch(parsed)
        if annotations:
            report["patch_annotations"] = annotations
        if not _valid_patch(parsed):
            failed("The repair response must contain only 0–8 replacement items with path and value at non-root JSON Pointers. The candidate was not changed.", "invalid_patch")
    finish("success")
    return parsed, _redact(report, key)
