# Build progress — 2026-10-03

## Enhancement cycle — 2026-10-03

User deadline: 20 minutes from 17:04:35 Beirut, ending 17:24:35. Code and main checks completed inside that window; final label polish verification is recorded with the artifacts.

- Complete: continuous visible reading; no source appendix or evidence chips; full-page PDF images excluded from learner figures while retained for model evidence; same experiment DOM and input state inline and in Experiment mode; redesigned assessment headers.
- Complete: stable full concept canvas with ported nodes, routed connectors, pan/zoom/fit, accessible selector and selection details. All nodes and section-based positions remain present on selection. No external layout dependency. Computational process views show actual dependencies; they do not fabricate arbitrary lifecycle cycles.
- Complete: native vector comparison, probability distribution, weighted geometry, contribution flow and selectable process journey. All scientific views bind validated engine inputs/outputs, and numerical probes verify raw dot products, probability weights, and weighted results. Zero/coincident vectors retain honest coordinates. The final source revision combines coincident query/key labels and improves mobile text size.
- Tests: 111 local tests passed (25.123 seconds), including meaningful false-binding rejection, PDF-page exclusion, and byte-reproducible rendering.
- Fresh successful attention run: `out/attention-current`; two API calls, no repairs, 78.297 seconds; 48,465 input tokens and 15,323 completion tokens; provider cost $0.017303145. Source was retrieved again, Call 1 and Call 2 ran normally, and no review notes or manual content/HTML changes were used.
- Reproduction: generated JSON rerendered locally through the standard renderer into `out/attention-reproduced`; exact HTML byte equality confirmed. Source asset hashes, HTML hashes, and renderer-only revision metadata are retained. The original successful generation HTML is preserved as `index.before-label-polish.html`.
- Browser: fresh offline Edge checks on attention and entropy passed all four modes at 1360/390/320 px with zero HTTP requests, page errors, console errors, or page-wide overflow. Inline/bench state, rotation, process selection, concept navigation, and six assessment answers per lesson passed. Reports/screenshots are in each final folder's `verification/`.
- Reliability boundary: three earlier fresh attention attempts were rejected (numeric vector binding and matrix operation errors); retained in `out/attention-enhanced`, `out/attention-updated`, and `out/attention-release`. Prompts now include explicit linear algebra recipes and select multiple-choice predictions. Numeric question support remains in the renderer/schema. One successful final run is evidence of working integration, not a 100% model reliability guarantee.
- Final examples: `out/attention-current/index.html`, `out/entropy-current/index.html`; actual Call 2 JSON is `experience.json` alongside each. Entropy reused the previously reviewed content/experience with the current renderer and no new API requests.
- Broader scientific review and arbitrary-paper reliability remain feedback-cycle work. No commits/pushes. Independent `claude` work untouched.

## Previous verified build

The complete V2 generator and offline Research lab are implemented and verified locally. The user authorized ownership of both model stages and the renderer, cleanup, and live DeepSeek testing. The independent `claude` work remains untouched.

| Task | Status | Evidence |
| --- | --- | --- |
| Review the other conversation, Research lab handoff, and both PDFs | Complete | Integrated the selected reading layout, four modes, embedded figures, learning outcomes, and submission constraints |
| Input, retrieval, extraction, and Call 1 | Complete | `playground_v2/pipeline.py`, source evidence, section-first teaching JSON and reusable images |
| Call 2 designed backward from the UI | Complete | `docs/v2/schemas/experience.schema.json`, editable prompt, actual `experience.json` in both final output folders |
| Deterministic renderer | Complete | Continuous reading, linked concept map, calculations with controls/baselines/reset, assessment feedback and revisiting explanations |
| Complete CLI, budgets, traces, and bounded repairs | Complete | Root `agent.py`; supplied model; 10 requests / 30,000 completion tokens / 590 seconds; no generated executable code |
| Local verification | Complete | 104 tests passed in 13.052 seconds; pinned dependency integrity passed |
| Attention example | Complete | Targeted source review, three independent numerical scenarios, offline browser report, matching repository input/output example |
| Fresh entropy generation | Complete | Full retrieval → Call 1 → Call 2 → HTML in 95.203 seconds; two model calls and no validation repair |
| Entropy source review | Complete | 16 independent arithmetic cases; one separate model revision fixed exactly two misleading challenge sentences; originals preserved |
| Final offline browser verification | Complete | Both final lessons: zero HTTP/JS/CSP errors; no overflow at 1360/390/320 px; controls, navigation, state and assessments pass |
| Cleanup and handoff | Complete | Recoverable archives and manifests; see `CLEANUP.md` and root `README.md` |

## Artifacts to review

- Student UI: `out/attention-final/index.html` and `out/entropy-final/index.html`.
- Actual Call 2 outputs: the `experience.json` in each final directory. Layout, styles, behavior, and allowed component kinds are owned by the renderer; Call 2 supplies bindings, teaching text, safe calculations, challenges, and questions.
- Portable submission example: `examples/attention-input.json` and `examples/attention-output.html`.
- Generation accounting: each run's `summary.json`, `trace.jsonl`, and `requests/`, `responses/`, `reports/` directories.
- Source review and offline verification: `quality-review.json` and `browser-verification.json` alongside final artifacts. These are post-run checks; they do not overwrite the generator's original `not_run` review fields.
- Prompts for iteration: `docs/v2/prompts/call1-content.md` and `call2-experience.md`.
- Renderer templates: `playground_v2/assets/research-lab.css` and `research-lab.js`.

## Verification details

Final browser verification used fresh offline Edge contexts: zero HTTP requests, page errors, or console errors; no page-wide horizontal overflow at 1360, 390, or 320 px in all four modes. Controls, invalid-input behavior, baseline/reset, mode state, figures, concept links, and all seven attention / six entropy assessment answers passed. Screenshots and artifact hashes are recorded alongside the lessons.

Attention source review compared three calculations with independent Python dot products, stable softmax, and weighted values (maximum absolute error 1.11e-16). Independent entropy arithmetic checked 16 weight pairs. Source review identified two false premises in entropy's guided challenges despite correct calculations; the separate review invocation replaced exactly those two strings. This is why schema/functional validation and scientific review remain separate.

Fresh entropy generation used 59,337 input tokens and 11,410 completion tokens (70,747 total), with provider-reported cost $0.013081848. The subsequent explicit source-review request used 21,885 input and 181 completion tokens, reported cost $0.006707436, and took 9.875 seconds. These are this example's runs, not cumulative development costs. The competition's completion-token budget does not count input tokens.

## Remaining external checks

No implementation task remains in this build. Team member names and the selected submission commit still need the team's input. Direct push to origin/main is authorized for this release; course submission remains with the team. The target instructor environment and hidden papers have not been exercised; live evidence covers two papers, and source review is targeted rather than exhaustive. Broader paper coverage belongs to the next feedback cycle.

## History

Previous detailed V1/V2 progress is retained at `../archive/2026-10-03-development/docs/PROGRESS-history.md` relative to the repository root. Old outputs are mapped by the cleanup manifests. Earlier development outcomes are historical evidence, not current completion status.

Final user corrections: logarithms and sized parentheses now typeset in native MathML; compact sticky controls share the viewport with results; repeated experiment introductions/control notes removed; final canvas keeps every node visible.


## 2026-10-03 final design adaptation and cleanup

- [x] Applied TRANSMIT-LIGHT-ADAPTATION in the shared renderer: narrow paper/focus rail, continuous unboxed prose, full labels and directed ports on the stable concept canvas, centered zoom and viewport preservation.
- [x] Rebuilt Attention and Entropy from unchanged validated JSON; independent fresh renderer output matches both HTML files byte for byte. No new model requests.
- [x] Archived old generated pages outside the repository under ../archive/2026-10-03-retired-pages; only attention-current and entropy-current remain under out. Closed old preview tabs. The independent claude directory was untouched.
- [x] Call 1 and repair prompts now prefer simple, direct, concise wording. Current examples retain their original generated prose; this style change applies on the next generation.

Latest successful Attention generation: Call 1 input 29,252 / output 9,051 / total 38,303 tokens, 31.750 seconds, $0.011056704. Call 2 input 19,213 / output 6,272 / total 25,485 tokens, 35.718 seconds, $0.006246441. Combined 63,788 tokens, $0.017303145; request stages sum to 67.468 seconds; entire pipeline 78.297 seconds. Tokens/cost are OpenRouter usage fields; elapsed times are local measurements, not provider inference durations. Entropy's current renderer update used zero model calls.

Verification for this revision: 111 Python tests pass. Attention offline regression passes with zero network/console/page errors, no overflow at 1360/390/320, all six assessment questions and experiment state verified. Both lessons reproduce byte for byte from saved JSON. Context rail and stable concept selection checks passed at 1360/1024/736/390/320; detailed browser reports remain with each current local artifact.

Final concept-canvas verification passes for both lessons: every concept (Attention 14, Entropy 10) at desktop and 320px, selection keeps all coordinates, zoom/Fit/keyboard navigation, real touch pan and zoom at 390px. Zero HTTP requests, runtime errors, document overflow, or nested outline scrolling.
