# Cleanup record — 2026-10-03

Obsolete project files were moved to recoverable archives outside the active repository, within the same workspace. The independent `claude` directory and the user's `out/my-paper` handoff were left untouched.

- `../archive/2026-10-03-prototype` relative to the repository root contains retired V1 code, schemas, tests, preview fixtures, superseded design documents, and earlier generation runs. Its `cleanup-manifest.json` records original and archive paths.
- `../archive/2026-10-03-development` contains intermediate V2 output runs and scratch files. Its `cleanup-manifest.json` records the moves. The earlier progress log is preserved as `docs/PROGRESS-history.md` inside this archive.
- The prototype manifest originally included `tmp`; it was restored while verification was active, then archived under the development archive. The development manifest is authoritative for that path.

Active code is `playground_v2/`, root `agent.py`, and the retained `agent_v2.py` Call 1 utility. Active outputs are the user's `out/my-paper`, the reviewed `out/attention-final` and `out/entropy-final`, and the fresh full-generation evidence in `out/entropy-playground`. The portable submission example is `examples/attention-output.html` with matching `examples/attention-input.json`.

Historical summaries may contain original absolute paths for archived candidates. Use the manifests to locate those files; originals and model responses remain recoverable. No commits, pushes, or remote submission were performed.


2026-10-03 follow-up: retired generated outputs moved recoverably to `../../archive/2026-10-03-retired-pages` relative to this document's directory. The manifest lists prior locations. Only `out/attention-current` and `out/entropy-current` remain active. Extra pre-polish HTML copies were archived too; design handoff references remain available. No claude files were accessed or moved.
