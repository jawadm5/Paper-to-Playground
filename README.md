# Paper-to-Playground

A research paper becomes an offline Research lab lesson: continuous reading, a concept map, working experiments, and an outcome-linked assessment. The learner's request determines coverage, from one mechanism to a whole-paper overview.

## Run

Python 3.11 is required. Install the pinned dependencies and set `OPENROUTER_API_KEY` in the terminal or Windows user environment. Windows keys saved with `setx` are read immediately even in an already-open terminal.

```powershell
python -m pip install -r requirements.txt
python agent.py --input examples/v2-attention-focused.json --output out/my-lesson --model deepseek/deepseek-v4.1-flash
```

Use `.\.venv\Scripts\python.exe` instead of `python` for the prepared local environment. Output must be new or empty. Open the resulting `index.html` directly in Chromium/Edge; the page includes its scripts, styles, data, and source images. The learner needs no server, API key, or internet connection.

Input has three strings:

```json
{
  "source_url": "https://arxiv.org/html/1706.03762v7",
  "focus": "Explain scaled dot-product attention and the distinct roles of queries, keys, and values.",
  "audience": "Engineering undergraduates familiar with vectors and matrices."
}
```

Use a public full-text HTML/PDF or arXiv URL. Internet access is used during generation to retrieve the paper and call OpenRouter, consistent with the user's clarification. The final page works offline.

## Architecture

1. Python extracts source blocks, equations, tables, captions, and bounded local images.
2. Call 1 creates validated section-first teaching JSON with simple and technical explanations, intuition, boundaries, learning outcomes, and concept links.
3. Call 2 selects predefined components and supplies controls, safe mathematical expressions, data bindings, guided challenges, figure descriptions, and assessment questions.
4. A deterministic renderer packages the content into one HTML file. Models never generate HTML, CSS, or JavaScript.

The normal path makes two model requests. Each stage permits at most one small validation repair; there are no transport retries or model switches. The complete run enforces a 590-second deadline, 10 attempted requests, and 30,000 completion tokens. Default completion allowances are 18,000 + 2,000 for Call 1 and 7,000 + 2,000 for Call 2. Unknown usage retains its reserved allowance. All calls use the supplied model; the testing profile is DeepSeek V4.1 Flash through OpenRouter.

## Current examples

Start with [the enhanced attention lesson](out/attention-current/index.html) and its [actual Call 2 JSON](out/attention-current/experience.json). It was generated from a fresh source retrieval in two model calls without repairs or manual content changes. Both the initial generation and the final renderer-only label polish are recorded, and rerendering the same JSON reproduces the final HTML byte for byte.

[The entropy lesson](out/entropy-current/index.html) demonstrates the simplified reading flow and PDF-page filtering. Full PDF page images remain internal model evidence; the renderer only displays actual source figures. Its previously reviewed JSON was reused without another API request.

The matching submission pair is [input](examples/attention-input.json) and [self-contained output](examples/attention-output.html). See [progress](docs/PROGRESS.md) for successful and rejected generation attempts, test boundaries, and component coverage. The current prompt selects multiple-choice predictions; numeric grading remains supported for compatible validated experiences.

## Review without repeating work

Reuse an existing teaching handoff to generate only Call 2 and HTML:

```powershell
python agent.py --input examples/v2-attention-focused.json --from-content out/attention-current/paper_content.json --output out/my-lesson --model deepseek/deepseek-v4.1-flash
```

Render saved artifacts without an API call:

```powershell
python agent.py --input examples/v2-attention-focused.json --from-content out/attention-current/paper_content.json --experience out/attention-current/experience.json --output out/rendered-again
```

For one targeted model revision of a saved experience, add `--review-notes path/to/feedback.txt` and `--model MODEL` to the saved-artifact command. This preserves the original and records the feedback and patch before full revalidation.

`agent_v2.py` is retained for source/Call 1 development, including `--prepare-only`, `--prepared-dir`, saved candidates, and explicit review notes. See [the Call 1 guide](docs/v2/04-runtime.md).

## What to inspect

- `index.html`: the student-facing deliverable.
- `paper_content.json` and `assets/`: the validated teaching content and source-image handoff.
- `experience.json`: the validated Call 2 structure. Start here when reviewing controls, charts, and questions.
- `call2-candidate.json` and optional repair files: the original response and exact changes.
- `requests/`, `responses/`, `reports/`: key-free payloads, raw public model responses, and per-call accounting.
- `summary.json`: final status, aggregate usage for this invocation, budgets, checks, and provenance of reused artifacts.
- `trace.jsonl`: stage/action/result events, timing, call usage, validations, and revisions.

Edit [Call 1's prompt](docs/v2/prompts/call1-content.md), [Call 2's prompt](docs/v2/prompts/call2-experience.md), or the renderer-owned components in `playground_v2/assets/`. Contracts are in `docs/v2/schemas/`; calculation operations and semantic checks are in `playground_v2/experience.py`.

## Verification and limits

```powershell
python -m unittest discover -s tests -p "test_v2*.py" -v
python -m pip check
```

Controls and calculations share the same bounded mathematical interpreter during Python validation and in the browser. Validation checks source and section IDs, image paths, expression dependencies, dimensions, endpoint calculations, responsive controls, assessment coverage, and numerical scenario answers. Browser verification is separate from generator execution and is recorded in [progress](docs/PROGRESS.md). Passing structural checks does not certify every scientific claim or teaching choice.

The renderer uses native controls, SVG, system fonts, and a bounded MathML adapter with visible fallback notation. Figures that cannot be extracted remain explicitly caption-only. Longer scanned PDFs beyond the image budget fail. Unsupported computations fail instead of accepting generated executable code. Assessment feedback appears only after final submission; switching modes preserves current answers and experiment state.

Exit codes: 0 complete; 2 invalid input/configuration; 4 failed generation or validation. Failures retain available candidates and diagnostics. A failed Call 2 does not pretend the Call 1 handoff is a complete lesson.

## Submission and credits

Team member names: **to be supplied by the team**. Submit the repository URL and selected full commit SHA through the course process; this task does not commit, push, or submit on the owner's behalf. The root `agent.py` implements the required three-argument invocation. The generator needs no Node/npm or browser installation during assessment; MiniRacer runs portable calculation checks.

Python dependencies are pinned in `requirements.txt`: Requests/urllib3, Beautiful Soup, pypdf, pypdfium2, Pillow, jsonschema, MiniRacer, and their transitive dependencies. Browser UI and calculation components are project-owned; no CDN libraries or fonts are loaded. Source artwork remains attributed to the paper. [Design references](docs/06-design-references.md) and the [Research lab handoff](docs/ui/RESEARCH-LAB-HANDOFF.md) record inspiration and implementation choices.

The independent `claude` directory remains outside this implementation and cleanup. See [documentation](docs/README.md), [integration contract](docs/v2/05-complete-generator.md), and [progress](docs/PROGRESS.md) for current evidence and the cleanup record.
