# Current build progress

Updated 2026-10-03. Team: Jawad Marji and Ali Zahreddine.

## Completed

- [x] Two-stage OpenRouter generation: source/teaching content, then declarative interactions; deterministic offline renderer.
- [x] Continuous reading with inline experiments, native scientific diagrams, stable directed concept map, final-result assessment, source-image filtering, and mathematical notation.
- [x] Latest UI requests: no map icons, branching and merging links, enlarged reading/control text, corrected equation limits and variable notation, navy/blue/white palette.
- [x] Both current local lessons reproduce byte for byte from their unchanged JSON. Matching portable Attention input/output pair included in Git.
- [x] Retired prototypes, design proposals, duplicate inputs and obsolete outputs moved outside the repository. Active entry points have explicit names; documentation links work from a fresh checkout.
- [x] Professor-facing interface and pinned dependencies checked against the hackathon PDF. Team names supplied. The optional source/Call 1 utility is `content_agent.py`; the required complete entry point remains `agent.py`.

## Verification

Python checks, deterministic layout checks and four final browser runs passed. Browser runs covered both papers' interactions and six assessment questions each; all map concepts stayed present and stable; touch/keyboard controls worked; no runtime network requests, JS errors, horizontal overflow, overlapping map nodes or clipped mathematical labels occurred. Rail/text checks covered 1360, 1024, 736, 390 and 320 pixels. Light and dark equation/map screenshots are retained locally under each current output's `verification/final-ui` directory.

The final professor-command smoke test performs a fresh retrieval and live generation; its latest result is recorded below. An earlier fresh check correctly rejected an inconsistent numeric quiz answer. Call 2 had contradictory choice-only and numeric-grading instructions; those are now removed and the model-facing schema permits choice questions only. Saved numerical assessments remain supported by the canonical contract and validator.

## Accounting and reproducibility

Latest previously successful Attention generation: two requests, no repairs, 29,252/9,051 input/output tokens for Call 1 and 19,213/6,272 for Call 2. Combined 63,788 tokens, $0.017303145, 78.297 seconds. Current UI revisions alone used zero model calls. New submission smoke tests are accounted separately; failed calls remain in their traces.

Each run saves `summary.json`, `trace.jsonl`, `reports/`, `requests/` and `responses/`; renderer revisions record exact file and asset hashes. Tokens and cost come from provider usage; timing is locally measured. Working run folders are ignored by Git.

## Scope of evidence

These checks establish the tested examples and local environment. They do not guarantee every model response, scientific claim, hidden paper, or instructor environment. The final page is offline; generation retrieves the paper online under the user's clarified requirement. Full prior progress and failed-run evidence remain recoverable in the workspace archive; see [cleanup](CLEANUP.md). No work inside the independent `claude` directory was included.


Submission hardening: distinct mathematical IDs such as q/Q are now normalized to collision-free lowercase IDs with exact typed-reference updates and an audit; notation and prose remain unchanged. The original failing candidate passes validation after normalization. Call 2 receives a choice-only generation schema and its bounded repair cycle can resolve up to three successive issues, with separate artifacts for every request. Existing request/token/time caps still govern the whole run. Empty/no-change repairs stop immediately. These changes followed three failed fresh smoke runs; those candidates and accounting remain in the workspace archive.


## Final submission status

118 Python tests pass; the current showcased lessons pass offline browser checks. Four additional fresh live checks were attempted during submission cleanup. They exposed numeric-question generation, identifier casing, downstream shape, and diagram-label failures. The first three classes received fixes with regression tests; the latest fresh run still failed because its diagram labels did not match the required key count and its repair repeated the same values. No additional live calls were made after the user's urgent submission instruction. The command interface, dependency installation integrity, previously successful complete generation, and current offline showcases are verified; the latest fresh generation is not claimed successful. Per-attempt candidates, traces, and usage remain recoverable in the workspace archive. The repository is delivered with this reliability limitation explicitly recorded.
