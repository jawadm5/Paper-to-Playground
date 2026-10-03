"""Complete, bounded two-call generator and saved-artifact iteration."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time

from .cli import _load_api_key
from .pipeline import ROOT, read_json, run as run_content, write_json
from .provider import PATCH_SCHEMA, ProviderError, _generate
from .repair import apply_replacements
from .validation import validate_handoff, validate_input

CALL2_PROMPT = ROOT / "docs/v2/prompts/call2-experience.md"
REPAIR_PROMPT = ROOT / "docs/v2/prompts/call2-repair.md"
CALL2_SCHEMA = ROOT / "docs/v2/schemas/experience.schema.json"
MAX_REQUESTS, MAX_COMPLETION, DEADLINE = 10, 30_000, 590.0


class RunBudget:
    def __init__(self, started, on_report=None):
        self.started = started
        self.reports = []
        self.charged_tokens = 0
        self.on_report = on_report

    @property
    def seconds_left(self):
        return DEADLINE - (time.monotonic() - self.started)

    def allowance(self, requested, timeout):
        if sum(r.get("attempts", 0) for r in self.reports) >= MAX_REQUESTS:
            raise ValueError("The run reached its request limit")
        available = MAX_COMPLETION - self.charged_tokens
        if available < 256 or self.seconds_left < 3:
            raise ValueError("The remaining run budget cannot support another request")
        return min(requested, available), min(timeout, self.seconds_left - 1)

    def record(self, report, reservation):
        self.reports.append(report)
        usage = report.get("usage") or {}
        if report.get("attempts", 0):
            self.charged_tokens += usage.get("completion_tokens", reservation)
        if self.on_report:
            self.on_report(report)
        if self.charged_tokens > MAX_COMPLETION:
            raise ValueError("Provider-reported completion usage exceeded the run limit")

    def usage(self):
        if not self.reports:
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost": 0}
        usages = [report.get("usage") for report in self.reports]
        if not all(isinstance(value, dict) for value in usages):
            return None
        return {name: sum(value[name] for value in usages)
                for name in ("prompt_tokens", "completion_tokens", "total_tokens", "cost")
                if all(isinstance(value.get(name), (int, float)) for value in usages)}


def copy_handoff(path, case, output):
    handoff = read_json(path)
    validate_handoff(handoff, path.parent)
    if handoff["input"] != case:
        raise ValueError("The saved handoff input differs from this case")
    root = path.parent.resolve()
    for visual in handoff["source"]["visuals"]:
        relative = visual.get("asset_path")
        if relative is None:
            continue
        origin, destination = (root / relative).resolve(), (output / relative).resolve()
        if not origin.is_relative_to(root / "assets") or not destination.is_relative_to(output / "assets"):
            raise ValueError("A source image is outside the declared assets directory")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, destination)
    for filename, value in (("input.json", case), ("source.json", handoff["source"]),
                            ("paper_content.json", handoff)):
        write_json(output / filename, value)
    return handoff


def generate_experience(handoff, output, *, model, key, budget, prompt_path=CALL2_PROMPT,
                        candidate=None, diagnostic=None):
    """Call 2 sees validated teaching content and trusted visual metadata."""
    context = {"input": handoff["input"], "content": handoff["content"],
               "visuals": handoff["source"]["visuals"],
               "source": {"title": handoff["source"]["title"],
                          "resolved_url": handoff["source"]["resolved_url"]}}
    repairing = candidate is not None
    stage = "call2-repair" if repairing else "call2"
    schema = read_json(CALL2_SCHEMA)
    extra = (json.dumps({"candidate": candidate, "diagnostic": str(diagnostic),
                         "experience_schema": schema}, ensure_ascii=False, allow_nan=False)
             if repairing else None)
    tokens, timeout = budget.allowance(2000 if repairing else 7000, 60 if repairing else 150)
    try:
        result, report = _generate(context, handoff["source"], output, model=model, key=key,
                                  prompt_path=REPAIR_PROMPT if repairing else prompt_path,
                                  max_tokens=tokens, timeout=timeout, stage=stage,
                                  response_schema=PATCH_SCHEMA if repairing else schema,
                                  extra_text=extra, attach_images=True)
    except ProviderError as error:
        budget.record(error.report, tokens)
        raise
    budget.record(report, tokens)
    return result


def build(case, output, *, model, key, from_content=None, experience_path=None,
          prompt_path=CALL2_PROMPT, repair=True, started=None, review_notes=None):
    from .experience import validate_experience
    from .renderer import render

    started = time.monotonic() if started is None else started
    budget = RunBudget(started)
    summary = {"status": "running", "model": model,
               "started_at": datetime.now(timezone.utc).isoformat(),
               "run_kind": "review_experience" if review_notes else "render_saved" if experience_path else "from_content" if from_content else "generation",
               "scientific_review": "not_run", "browser_checks": "not_run",
               "limits": {"requests": MAX_REQUESTS, "completion_tokens": MAX_COMPLETION, "seconds": DEADLINE}}

    def event(stage, action, result, **details):
        with (output / "trace.jsonl").open("a", encoding="utf-8") as handle:
            payload = json.dumps({"elapsed_seconds": round(time.monotonic() - started, 3),
                                  "stage": stage, "action": action, "result": result, **details}, ensure_ascii=False)
            handle.write((payload.replace(key, "[REDACTED]") if key else payload) + "\n")

    def finish(status, error=None):
        summary.update(status=status, duration_seconds=round(time.monotonic() - started, 3),
                       attempts=sum(r.get("attempts", 0) for r in budget.reports),
                       usage=budget.usage(), charged_completion_tokens=budget.charged_tokens,
                       provider_reports=budget.reports)
        if error:
            summary["error"] = str(error).replace(key, "[REDACTED]") if key else str(error)
        write_json(output / "summary.json", summary)

    budget.on_report = lambda report: event(
        report.get("stage", "provider"), "api_finished", report.get("status", "unknown"),
        attempts=report.get("attempts", 0), usage=report.get("usage"),
        duration_seconds=report.get("duration_seconds"),
        report_path=report.get("report_path"), request_path=report.get("request_path"),
        response_path=report.get("response_path"))

    try:
        if from_content:
            handoff = copy_handoff(from_content, case, output)
            summary["content_source"] = str(from_content.resolve())
            event("call1", "reuse_handoff", "validated", source=summary["content_source"])
        else:
            code = run_content(case, output, model=model, key=key, repair=repair)
            content_summary = read_json(output / "summary.json")
            write_json(output / "call1-summary.json", content_summary)
            for report in content_summary.get("provider_reports", []):
                request = read_json(output / report["request_path"])
                budget.record(report, request.get("max_completion_tokens", 18000))
            if code:
                raise ValueError(content_summary.get("error", "Call 1 failed; inspect call1-summary.json"))
            handoff = read_json(output / "paper_content.json")
        validate_handoff(handoff, output)
        if experience_path:
            candidate = read_json(experience_path)
            summary["experience_source"] = str(experience_path.resolve())
            event("call2", "reuse_experience", "loaded")
        else:
            event("call2", "generate", "started")
            candidate = generate_experience(handoff, output, model=model, key=key, budget=budget, prompt_path=prompt_path)
        write_json(output / "call2-candidate.json", candidate)
        if review_notes:
            notes = review_notes.read_text(encoding="utf-8-sig")
            if not notes.strip() or len(notes) > 20_000:
                raise ValueError("Review notes must contain 1–20,000 characters")
            (output / "review-notes.txt").write_text(notes, encoding="utf-8")
            event("call2", "source_review_revision", "started")
            replacements = generate_experience(handoff, output, model=model, key=key, budget=budget,
                                               candidate=candidate, diagnostic=notes)
            write_json(output / "call2-repair.json", replacements)
            candidate = apply_replacements(candidate, replacements)
            write_json(output / "call2-candidate-repaired.json", candidate)
            summary["experience_repaired"] = True
        try:
            validate_experience(candidate, handoff)
        except ValueError as error:
            summary["initial_experience_error"] = str(error)
            if not repair or experience_path:
                raise
            event("call2", "repair", "started", diagnostic=str(error))
            replacements = generate_experience(handoff, output, model=model, key=key, budget=budget,
                                               candidate=candidate, diagnostic=error)
            write_json(output / "call2-repair.json", replacements)
            candidate = apply_replacements(candidate, replacements)
            write_json(output / "call2-candidate-repaired.json", candidate)
            validate_experience(candidate, handoff)
            summary["experience_repaired"] = True
        write_json(output / "experience.json", candidate)
        event("call2", "validate", "passed", questions=len(candidate["questions"]), experiments=len(candidate["experiments"]))
        if budget.seconds_left <= 1:
            raise ValueError("No time remains for rendering within the run limit")
        summary["render"] = render(handoff, candidate, output)
        event("renderer", "package_offline_html", "passed", **summary["render"])
        finish("complete")
        return 0
    except (ValueError, OSError, ProviderError) as error:
        event("run", "finish", "failed", error=str(error))
        finish("failed", error)
        return 4


def main(argv=None):
    started = time.monotonic()
    parser = argparse.ArgumentParser(description="Turn a paper into a complete offline Research lab lesson.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", help="OpenRouter model used for every generated stage")
    parser.add_argument("--from-content", type=Path, help="Reuse a validated paper_content.json and its assets")
    parser.add_argument("--experience", type=Path, help="With --from-content, render saved experience JSON without API calls")
    parser.add_argument("--review-notes", type=Path, help="With --experience, make one targeted model revision from review feedback")
    parser.add_argument("--call2-prompt", type=Path, default=CALL2_PROMPT)
    parser.add_argument("--no-repair", action="store_true")
    args = parser.parse_args(argv)
    key = ""
    try:
        case = validate_input(read_json(args.input, limit=100_000))
        if args.experience and not args.from_content:
            raise ValueError("--experience requires --from-content")
        if args.review_notes and (not args.experience or args.no_repair):
            raise ValueError("--review-notes requires --experience and enabled repair")
        for path in (args.from_content, args.experience, args.call2_prompt, args.review_notes):
            if path is not None and not path.is_file():
                raise ValueError(f"Required file does not exist: {path}")
        if not args.experience or args.review_notes:
            if not args.model or not args.model.strip():
                raise ValueError("--model is required for generation")
            key = _load_api_key()
            if not key:
                raise ValueError("Set OPENROUTER_API_KEY in the terminal or Windows user environment")
        output = args.output.resolve()
        if output.exists() and (not output.is_dir() or any(output.iterdir())):
            raise ValueError("Output must be a new or empty directory")
        output.mkdir(parents=True, exist_ok=True)

        def expire():
            with (output / "trace.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"stage": "run", "action": "deadline", "result": "failed",
                                         "elapsed_seconds": DEADLINE}) + "\n")
            os._exit(4)

        timer = threading.Timer(max(0.1, DEADLINE - (time.monotonic() - started)), expire)
        timer.daemon = True
        timer.start()
        try:
            code = build(case, output, model=args.model.strip() if args.model else None, key=key,
                         from_content=args.from_content, experience_path=args.experience,
                         prompt_path=args.call2_prompt, repair=not args.no_repair, started=started,
                         review_notes=args.review_notes)
        finally:
            timer.cancel()
        print(f"{'Ready' if code == 0 else 'Failed; inspect summary.json'}: {output / 'index.html' if code == 0 else output}")
        return code
    except (ValueError, OSError) as error:
        text = str(error)
        print(text.replace(key, "[REDACTED]") if key else text, file=sys.stderr)
        return 2
