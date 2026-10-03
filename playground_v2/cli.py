"""Noninteractive CLI for our V2 workstream."""
import argparse
import math
import os
from pathlib import Path
import sys

from .pipeline import DEFAULT_PROMPT, read_json, run
from .validation import validate_input


def _load_api_key():
    """Prefer the process key, then the Windows user value saved by setx."""
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key or sys.platform != "win32":
        return key
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as user_environment:
            value, _ = winreg.QueryValueEx(user_environment, "OPENROUTER_API_KEY")
        return value.strip() if isinstance(value, str) else ""
    except (ImportError, OSError):
        return ""


def main(argv=None):
    parser = argparse.ArgumentParser(description="Prepare a paper and generate section-first V2 content for call two.")
    parser.add_argument("--input", required=True, type=Path, help="JSON: source_url, focus, audience")
    parser.add_argument("--output", required=True, type=Path, help="New or empty output directory")
    parser.add_argument("--model", help="OpenRouter model, e.g. deepseek/deepseek-v4.1-flash")
    parser.add_argument("--prepare-only", action="store_true", help="Extract evidence and images without an API call")
    parser.add_argument("--prepared-dir", type=Path, help="Reuse a saved preparation from the same case")
    parser.add_argument("--candidate", type=Path, help="Validate a saved Call 1 candidate; skip initial generation and attempt at most one repair")
    parser.add_argument("--review-notes", type=Path, help="With --candidate, request one targeted source-grounded revision from saved feedback")
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT, help="Editable Call 1 prompt")
    parser.add_argument("--response-format", choices=("json_object", "json_schema"), default="json_object",
                        help="Provider JSON mode; both modes are checked against the same local schema")
    parser.add_argument("--max-tokens", type=int, default=18000)
    parser.add_argument("--no-repair", action="store_true", help="Disable the one bounded validation-repair attempt")
    parser.add_argument("--call-timeout", type=float, default=180)
    parser.add_argument("--source-timeout", type=float, default=60)
    parser.add_argument("--max-text-chars", type=int, default=90000)
    parser.add_argument("--max-images", type=int, default=6)
    parser.add_argument("--max-image-bytes", type=int, default=8_000_000)
    args = parser.parse_args(argv)
    key = ""
    try:
        raw = read_json(args.input, limit=100_000)
        case = validate_input(raw)
        if args.prepare_only and args.candidate:
            raise ValueError("--candidate cannot be combined with --prepare-only")
        if args.candidate and not args.candidate.is_file():
            raise ValueError("The saved candidate file does not exist")
        if args.review_notes and (not args.candidate or args.no_repair or not args.review_notes.is_file()):
            raise ValueError("--review-notes requires --candidate, an existing notes file, and repair enabled")
        if not args.prepare_only:
            if not args.model or not args.model.strip():
                raise ValueError("--model is required for generation")
            key = _load_api_key()
            if not key:
                raise ValueError("Set OPENROUTER_API_KEY in this terminal's environment "
                                 "or save it as a Windows user environment variable before generation")
            if not args.prompt.is_file():
                raise ValueError("The Call 1 prompt file does not exist")
        for name, value, lower, upper in (
            ("max-tokens", args.max_tokens, 1000, 30000),
            ("call-timeout", args.call_timeout, 1, 360),
            ("source-timeout", args.source_timeout, 1, 120),
            ("max-text-chars", args.max_text_chars, 4000, 180000),
            ("max-images", args.max_images, 0, 6),
            ("max-image-bytes", args.max_image_bytes, 100000, 8_000_000),
        ):
            if not math.isfinite(value) or not lower <= value <= upper:
                raise ValueError(f"--{name} must be between {lower} and {upper}")
        output = args.output.resolve()
        if output.exists() and (not output.is_dir() or any(output.iterdir())):
            raise ValueError("Output must be a new or empty directory; previous results are never overwritten")
        output.mkdir(parents=True, exist_ok=True)
        code = run(case, output, model=args.model.strip() if args.model else None, key=key,
                   prepare_only=args.prepare_only, prepared_dir=args.prepared_dir,
                   prompt_path=args.prompt, max_tokens=args.max_tokens, call_timeout=args.call_timeout,
                   response_format=args.response_format,
                   repair=not args.no_repair, candidate_path=args.candidate, review_notes=args.review_notes,
                   source_timeout=args.source_timeout, max_text_chars=args.max_text_chars,
                   max_images=args.max_images, max_image_bytes=args.max_image_bytes,
                   ignored_fields=sorted(set(raw) - set(case)))
        label = "Prepared evidence" if args.prepare_only else "Validated handoff"
        print(f"{label if code == 0 else 'Run failed; inspect summary.json'}: {output}")
        return code
    except (ValueError, OSError) as error:
        message = str(error)
        print(message.replace(key, "[REDACTED]") if key else message, file=sys.stderr)
        return 2
