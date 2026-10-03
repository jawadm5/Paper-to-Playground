# Repository cleanup

The submission contains the current generator, pinned dependencies, prompts and schemas, current developer documentation, tests, and the current example input/output pair. The independent `claude` directory was not inspected or changed.

Canonical entry points:
- `agent.py`: professor-facing complete generator.
- `content_agent.py`: optional source/Call 1 development utility.
- `examples/attention-input.json` and `examples/attention-output.html`: showcase pair.
- `examples/attention-overview-input.json` and `examples/entropy-input.json`: distinct additional practice inputs.

Retired files were moved recoverably outside the repository, under the workspace `archive/` directory. They are not required to install or run the submitted project:
- `2026-10-03-prototype` and `2026-10-03-development`: earlier implementations and logs.
- `2026-10-03-retired-pages`: old generated lesson folders and pre-polish HTML copies.
- `2026-10-03-submission-cleanup`: historical design previews/briefs, the old review note, and duplicate or obsolete input examples. A manifest records the exact moves.

Active model-stage fixtures in `docs/v2/examples/` remain because the automated tests use them. Generated runs in `out/`, local environments, credentials and caches are excluded from Git. The current Attention and Entropy previews remain available locally.
