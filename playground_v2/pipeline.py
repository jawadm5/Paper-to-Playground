"""One source preparation step, one model call, and a validated local handoff."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from . import SCHEMA_VERSION
from .validation import ValidationError, validate_context, validate_content, validate_handoff, validate_source
from .provider import ProviderError, generate_content, generate_patch
from .repair import apply_replacements
from .normalization import normalize_content_ids

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROMPT = ROOT / "docs" / "v2" / "prompts" / "call1-content.md"
REPAIR_PROMPT = ROOT / "docs" / "v2" / "prompts" / "call1-repair.md"


def read_json(path: Path, limit: int = 12_000_000):
    if path.stat().st_size > limit:
        raise ValueError(f"JSON file exceeds its {limit}-byte limit: {path.name}")
    return json.loads(path.read_text(encoding="utf-8-sig"),
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f"Invalid JSON number: {value}")))


def write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def prepare_in_worker(case: dict, output: Path, limits: dict):
    environment = os.environ.copy()
    environment.pop("OPENROUTER_API_KEY", None)
    environment["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.Popen([sys.executable, "-m", "playground_v2.source_worker"],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", cwd=ROOT, env=environment,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        stdout, _ = process.communicate(json.dumps({"case": case, "output": str(output), "limits": limits}),
                                        timeout=limits["timeout"] + 5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate(timeout=3)
        raise ValueError("Paper preparation exceeded its time limit; no model call was made") from None
    if process.returncode:
        raise ValueError(f"Paper preparation worker failed with exit code {process.returncode}")
    result = json.loads(stdout)
    if "error" in result:
        raise ValueError(f"Paper preparation failed: {result['message']}")
    return result["context"], result["source"]


def reuse_prepared(directory: Path, case: dict, output: Path, limits: dict):
    """Explicitly reuse a saved preparation for prompt iteration without another fetch."""
    directory = directory.resolve()
    if read_json(directory / "input.json") != case:
        raise ValueError("Prepared input differs from this case; prepare the paper again")
    context = read_json(directory / "call1-input.json")
    source = read_json(directory / "source.json")
    validate_context(context)
    validate_source(source, directory)
    images = [v for v in source["visuals"] if v["provided_as"] in ("image_only", "image_and_caption")]
    asset_bytes = sum((directory / v["asset_path"]).stat().st_size
                      for v in source["visuals"] if v["asset_path"] is not None)
    if (sum(len(b["text"]) for b in context["source_blocks"]) > limits["max_text_chars"]
            or len(images) > limits["max_images"] or asset_bytes > limits["max_image_bytes"]):
        raise ValueError("Prepared evidence exceeds the requested text/image limits; prepare again with these limits or use the original limits")
    for visual in source["visuals"]:
        relative = visual.get("asset_path")
        if relative is None:
            continue
        # Assets are copied by declared path only, never by recursive directory traversal.
        source_path = (directory / relative).resolve()
        destination = (output / relative).resolve()
        if (not source_path.is_relative_to(directory / "assets")
                or not destination.is_relative_to(output / "assets")
                or not source_path.is_file()):
            raise ValueError("Prepared visual asset is missing or outside the assets directory")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination)
    return context, source


def check_preparation(case: dict, context: dict, source: dict):
    validate_context(context)
    expected_visuals = [{k: visual[k] for k in ("id", "kind", "caption", "locator", "provided_as")}
                        for visual in source["visuals"] if visual["provided_as"] != "not_provided"]
    if (context["focus"] != case["focus"] or context["audience"] != case["audience"]
            or context["source_blocks"] != source["references"]
            or context["visuals"] != expected_visuals
            or context["extraction_warnings"] != source["warnings"]):
        raise ValidationError("Prepared source and first-call context are inconsistent")


def run(case: dict, output: Path, *, model: str | None, key: str = "", prepare_only: bool = False,
        prepared_dir: Path | None = None, prompt_path: Path = DEFAULT_PROMPT,
        response_format: str = "json_object",
        max_tokens: int = 18000, call_timeout: float = 180.0, source_timeout: float = 60.0,
        max_text_chars: int = 90000, max_images: int = 6, max_image_bytes: int = 8_000_000,
        repair: bool = True, candidate_path: Path | None = None, review_notes: Path | None = None,
        ignored_fields: list[str] | None = None) -> int:
    started = time.monotonic()
    summary = {"schema_version": SCHEMA_VERSION, "status": "running", "model": model,
               "started_at": datetime.now(timezone.utc).isoformat(), "attempts": 0,
               "usage": None, "scientific_review": "not_run", "warnings": [],
               "run_kind": "candidate_review" if candidate_path else "generation"}

    def record_report(report):
        reports = summary.setdefault("provider_reports", [])
        reports.append(report)
        summary["provider"] = reports[0]
        summary["attempts"] = sum(item.get("attempts", 0) for item in reports)
        usages = [item.get("usage") for item in reports]
        summary["usage"] = ({name: sum(usage[name] for usage in usages)
                             for name in ("prompt_tokens", "completion_tokens", "total_tokens", "cost")
                             if all(isinstance(usage.get(name), (int, float)) for usage in usages)}
                            if all(isinstance(usage, dict) for usage in usages) else None)

    def safe(value):
        text = str(value)
        return text.replace(key, "[REDACTED]") if key else text

    def event(stage, status, **details):
        record = {"elapsed_seconds": round(time.monotonic() - started, 3),
                  "stage": stage, "action": stage, "result": status, "status": status, **details}
        with (output / "trace.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(safe(json.dumps(record, ensure_ascii=False)) + "\n")

    try:
        write_json(output / "input.json", case)
        if ignored_fields:
            event("input", "ignored_extra_fields", fields=ignored_fields)
        event("source", "started", reuse=prepared_dir is not None)
        limits = dict(max_text_chars=max_text_chars, max_images=max_images,
                      max_image_bytes=max_image_bytes, timeout=source_timeout)
        context, source = (reuse_prepared(prepared_dir, case, output, limits) if prepared_dir
                           else prepare_in_worker(case, output, limits))
        validate_source(source, output)
        check_preparation(case, context, source)
        write_json(output / "call1-input.json", context)
        write_json(output / "source.json", source)
        summary["warnings"] = source["warnings"]
        summary["source"] = {"resolved_url": source["resolved_url"], "title": source["title"],
                             "blocks": len(source["references"]), "visuals": len(source["visuals"])}
        event("source", "ready", **summary["source"])
        if prepare_only:
            summary["status"] = "prepared"
            return 0
        if candidate_path:
            summary["candidate_source"] = str(candidate_path.resolve())
            content = read_json(candidate_path, limit=512 * 1024)
            event("candidate", "loaded", path=summary["candidate_source"])
        else:
            event("call1", "started", model=model)
            content, report = generate_content(context, source, output, model=model, key=key,
                                               prompt_path=prompt_path, max_tokens=max_tokens, timeout=call_timeout,
                                               response_format=response_format)
            record_report(report)
        # Always retain the candidate before validation, so rejected responses are reviewable.
        write_json(output / "call1-content.json", content)
        content, id_changes = normalize_content_ids(content)
        if id_changes:
            write_json(output / "call1-content-normalized.json", content)
            write_json(output / "call1-id-normalization.json", {"changes": id_changes})
            summary["normalized_identifiers"] = len(id_changes)
            event("call1", "identifiers_normalized", changes=len(id_changes))
        diagnostic = None
        try:
            validate_content(content, context)
        except ValidationError as error:
            if not repair:
                raise
            summary["initial_validation_error"] = safe(error)
            diagnostic = str(error)
        if review_notes:
            if review_notes.stat().st_size > 30000:
                raise ValueError("Review notes exceed the 30,000-byte limit")
            notes = review_notes.read_text(encoding="utf-8-sig").strip()
            if not notes:
                raise ValueError("Review notes are empty")
            (output / "review-notes.txt").write_text(safe(notes) + "\n", encoding="utf-8")
            summary["review_notes_source"] = str(review_notes.resolve())
            diagnostic = (diagnostic + "\n\n" if diagnostic else "") + "Source-review feedback to verify against the supplied evidence:\n" + notes
        if diagnostic:
            event("call1-repair", "started", diagnostic=safe(diagnostic))
            patch, repair_report = generate_patch(content, diagnostic, context, source, output,
                                                  model=model, key=key, prompt_path=REPAIR_PROMPT,
                                                  max_tokens=2000, timeout=min(60.0, call_timeout),
                                                  response_format=response_format)
            record_report(repair_report)
            write_json(output / "call1-repair.json", patch)
            content = apply_replacements(content, patch)
            write_json(output / "call1-content-repaired.json", content)
            validate_content(content, context)
            summary["repaired"] = True
            event("call1-repair", "validated", replacements=len(patch["patches"]))
        handoff = {"schema_version": SCHEMA_VERSION, "input": case, "source": source, "content": content}
        validate_handoff(handoff, output)
        write_json(output / "paper_content.json", handoff)
        summary.update(status="complete", sections=len(content["sections"]),
                       learning_outcomes=len(content["learning_outcomes"]), concepts=len(content["concepts"]))
        event("handoff", "complete", sections=summary["sections"])
        return 0
    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as error:
        if isinstance(error, ProviderError):
            record_report(error.report)
        summary.update(status="failed", error=safe(error))
        event("run", "failed", error=safe(error))
        print(safe(error), file=sys.stderr)
        return 4
    finally:
        summary["duration_seconds"] = round(time.monotonic() - started, 3)
        # Guard even provider metadata against an accidental secret echo.
        (output / "summary.json").write_text(safe(json.dumps(summary, ensure_ascii=False, indent=2)) + "\n",
                                             encoding="utf-8")
