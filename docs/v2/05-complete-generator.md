# Complete generator implementation

The user authorized one owner for input, both model calls, the deterministic renderer, and final verification on 2026-10-03. The Research lab handoff remains the visual reference. This document records the implemented integration contract.

## Flow

1. Validate the three-field input and retrieve public HTML/PDF evidence and local images.
2. Call 1 produces the existing section-first 2.1 teaching-content handoff. Existing-path validation repair is bounded to one request.
3. Call 2 selects renderer-owned interactions, mathematical expressions, section placements, source-figure descriptions, and assessment questions. It references Call 1 IDs and does not duplicate the reading prose or emit executable code.
4. Validate references, calculations, controls, scenarios, and assessment. One bounded Call 2 repair may address a rejected parsed candidate.
5. Render a single offline `index.html` with embedded assets and retain JSON, traces, and usage beside it.

## Entry points and iteration

- `agent.py --input CASE --output DIR --model MODEL` runs the complete pipeline.
- `--from-content DIR/paper_content.json` starts from an existing validated handoff and avoids paying for Call 1 again.
- `--experience FILE` with `--from-content` validates and renders a saved interaction specification without a model request.
- `--review-notes FILE` with `--experience` applies one explicit source-review revision to a saved candidate before validation and rendering. The original candidate, feedback, patch, response, and usage are preserved.
- `agent_v2.py` retains source-preparation and Call 1 prompt-iteration commands.

## Interface and budgets

The renderer accepts `render(handoff, experience, output_dir)` with declared images present in that output directory. Call 2 uses the same provider transport and supplied model as Call 1. Native browser controls, SVG, local system fonts, and readable mathematical notation avoid per-run build steps and runtime downloads.

The complete pipeline enforces 10 attempted requests, 30,000 completion tokens, and a 590-second deadline. An unknown token count retains its requested allowance. Default initial allowances are 18,000 for Call 1 and 6,000 for Call 2, with up to 2,000 for each bounded repair. Prior reused runs are linked, and their historical usage is distinguished from requests made by the current invocation.

## Completion checks

Use a real Call 1 handoff to generate and review Call 2, exercise the resulting reading/map/experiment/assessment views, then run a fresh offline browser context and a narrow mobile viewport. Verify two meaningful controls, at least two explorations, source images and references, baseline behavior, final-only assessment feedback, and no runtime network dependencies. Broader scientific reliability remains a separate feedback cycle; structural checks do not certify every claim.
