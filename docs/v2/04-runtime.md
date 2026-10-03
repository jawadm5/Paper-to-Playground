# V2 input and Call 1 runtime

This workstream retrieves the paper, prepares evidence and images, makes the first content request, and saves the version 2.1 handoff. A rejected parsed candidate can receive one small validation-repair request. The complete generator consumes this handoff for Call 2 and the offline renderer through `agent.py`. `agent_v2.py` retains the first-stage development workflow described here.

## Setup and generate

Use Python 3.11 and the pinned project dependencies:

```powershell
python -m pip install -r requirements.txt
# OPENROUTER_API_KEY must be set in this terminal or saved as a Windows user variable.
python agent_v2.py --input examples/v2-attention.json --output out/my-paper --model deepseek/deepseek-v4.1-flash
```

The prepared workspace uses `.\.venv\Scripts\python.exe` in place of `python`. The CLI first reads the current process environment. On Windows, if that key is absent or blank, it reads the saved user environment value directly, so a key saved with `setx` works immediately in an already-open terminal. A nonblank terminal value takes precedence. For other programs that only read the process environment, import the saved value without printing it:

```powershell
$env:OPENROUTER_API_KEY = [Environment]::GetEnvironmentVariable('OPENROUTER_API_KEY', 'User')
```

Input JSON contains `source_url`, `focus`, and `audience`. Only those fields are consumed. Focus sets both breadth and depth: ask for an overview to cover the paper's narrative, or specify one concept/equation/result for a focused explanation with necessary prerequisites. Outcomes and the concept map follow the chosen scope. Use a full-text HTML/PDF URL or an arXiv URL; pin the paper version when reproducibility matters. Real, version-pinned cases are provided in `examples/v2-attention.json` (overview) and `examples/v2-attention-focused.json` (one mechanism). The example.org files in `docs/v2/examples/` are synthetic contract fixtures, not retrieval targets.

Output must be a new or empty directory. No run overwrites an earlier result. The supplied model is used for every request. The normal path uses one content request. If a parsed candidate fails content validation, one bounded repair may replace up to eight existing JSON locations, followed by full validation. Use `--no-repair` to disable it. There are no transport retries, model switches, code-generation calls, or separate OCR services.

## Inspect evidence and iterate on the prompt

Preparation does not need a key or a model call:

```powershell
python agent_v2.py --input examples/v2-attention.json --output out/paper-prepared --prepare-only
```

Inspect `call1-input.json`, `source.json`, and the images in `assets/`. Edit `docs/v2/prompts/call1-content.md`, then reuse the same preparation with a new output directory:

```powershell
python agent_v2.py --input examples/v2-attention.json --prepared-dir out/paper-prepared --output out/paper-revision-1 --model deepseek/deepseek-v4.1-flash
```

The input must match the saved preparation. Changing the audience or focus requires another preparation. Reuse also checks the requested text/image limits; an existing preparation that exceeds them is rejected before a model call rather than silently trimmed. A custom prompt can be supplied with `--prompt path/to/prompt.md`. Each request saves the exact current prompt, evidence, schema, and actual labeled image data URLs; editing a prompt never rewrites a previous run.

Default provider mode is `--response-format json_object`, with the full authoritative schema included in the model-visible input. `--response-format json_schema` explicitly requests provider-side schema enforcement as well. Both modes use exactly the same local schema and reference checks. There is no automatic mode fallback. OpenRouter documents [JSON schema responses](https://openrouter.ai/docs/guides/features/structured-outputs) and [image attachments](https://openrouter.ai/docs/guides/overview/multimodal/image-understanding).

To review an existing parsed candidate without paying for another full generation, add `--candidate path/to/call1-content.json`. It revalidates the candidate and attempts at most one repair if needed. This also lets a refined repair prompt be tested against an unchanged failing example.

For source-review feedback, save concise notes with exact content-relative JSON pointers and supporting evidence, then use:

```powershell
python agent_v2.py --input examples/v2-attention-focused.json --prepared-dir out/focused-prepared --candidate out/previous/call1-content.json --review-notes review-notes.txt --output out/focused-reviewed --model deepseek/deepseek-v4.1-flash
```

This explicitly requests one targeted revision even if the candidate already passes structural checks. It saves the original, notes, patch, revised content, and accounting separately. The candidate must match the prepared paper's evidence IDs. Model-applied feedback still needs review; schema validation does not certify that the feedback was understood correctly. `summary.json.run_kind` distinguishes a fresh generation from candidate review, and its usage counts only requests in that invocation. Prior runs remain linked through `candidate_source`.

## Files to review and hand off

The current real teaching handoff is [the user's attention run](../../out/my-paper/paper_content.json). The complete reviewed lesson and its Call 2 JSON are in `out/attention-final/`. Earlier focused/overview development examples and their original responses are retained in the workspace archive; see the cleanup record in `docs/PROGRESS.md`.

The repair adapter accepts existing-path replacements only. If the provider adds the known non-operative `basis` or `source_refs` annotations beside a replacement, it records them separately and keeps the original response. It does not turn those annotations into content citations. Other unknown operation fields remain invalid.

| Output | Purpose |
| --- | --- |
| `paper_content.json` | Validated 2.1 envelope for Call 2; created only on success |
| `assets/` | Local figure or page images referenced by the envelope |
| `input.json` | Normalized three-field case |
| `call1-input.json` | Exact text evidence, visual metadata, and extraction warnings |
| `source.json` | Source references, asset paths, provenance, and warnings |
| `source-extraction.json` | Full extraction and selection audit on fresh preparation |
| `requests/call1.json` | Exact key-free API payload, including image bytes |
| `responses/call1.json` | Public response content and usage, including rejected responses |
| `reports/call1.json` | Provider attempt, chosen mode, image IDs, timing, and usage |
| `call1-content.json` | Original parsed model candidate, also retained when local validation rejects it |
| `call1-id-normalization.json`, `call1-content-normalized.json` | Optional recorded identifier casing correction; prose/math/source IDs are unchanged, ambiguous collisions fail |
| `requests/call1-repair.json`, `responses/call1-repair.json`, `reports/call1-repair.json` | Separate evidence, response, and accounting if a repair was attempted |
| `call1-repair.json`, `call1-content-repaired.json` | Proposed replacements and revalidated candidate; the original remains unchanged |
| `summary.json`, `trace.jsonl` | Final run state and stage progress |

Pass `paper_content.json` together with `assets/` to the next stage. Resolve `content.sections[].visual_ids` through `source.visuals`. Null asset paths mean only a caption is available. A `page_image` is an entire PDF page, not an extracted figure. The renderer embeds selected local image bytes into the final HTML so that it remains usable offline.

## Limits and failure behavior

Defaults are 90,000 text characters, six images, 8,000,000 image bytes, 18,000 completion tokens for content, 60 seconds for preparation, and 180 seconds for the content call. A validation repair has at most 2,000 completion tokens and 60 seconds; it is attempted once only. The CLI exposes bounded overrides; `--help` lists them. Paper preparation and provider transport run in bounded subprocesses. Source workers do not inherit the API key. The total first-stage default completion allowance, including repair, is 20,000 tokens; the complete generator accounts for Call 2 within the remaining global budget.

Short papers retain all extracted text. Longer papers prioritize section/page coverage before extra focus detail and disclose omitted material. HTML preserves available TeX annotations and readable table rows. PDF extraction preserves page locations; selected pages are rendered as images to support diagrams and mathematical layout. Small scans can use complete page-image evidence within the image budget; larger scans fail explicitly. There is no OCR service. Unsupported HTML visual formats remain caption-only with warnings.

Text extraction, table layout, and visual interpretation can still be imperfect. Unavailable image pixels are never represented as inspected figures. Schema/reference/asset checks do not establish scientific or pedagogical correctness; review the explanations, assumptions, reported results, and simplifications against the source.

Exit codes: `0` means prepared evidence or a validated handoff, depending on mode; `2` means invalid input/configuration; `4` means retrieval, provider, or content validation failed. `summary.json.status` distinguishes `prepared`, `complete`, and `failed`. Essential `missing_information` blocks publication of `paper_content.json`, while the candidate remains inspectable. The repair prompt at `docs/v2/prompts/call1-repair.md` forbids fabricating evidence or hiding genuine gaps; an unresolved repair still fails. Truncated/invalid JSON and transport failures do not enter the repair path. Timeouts and provider errors retain the attempted-call accounting; unknown token usage remains null. Summary attempt counts and token/cost usage include both requests when repair is used.

## Focused checks

```powershell
python -m unittest discover -s tests -p "test_v2*.py" -v
python -m pip check
```

Mocked tests verify retrieval/extraction, real local PDF rasterization, evidence selection, schema/reference checks, local assets, one-call orchestration, failure artifacts, and provider request construction. They do not prove live provider behavior. Actual live results and the reviewed output are recorded in `docs/PROGRESS.md`.
