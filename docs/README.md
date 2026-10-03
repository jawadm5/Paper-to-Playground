# Project documentation

The complete generator is entered through root `agent.py`. `content_agent.py` supports source preparation and isolated Call 1 iteration. The implementation package is `playground_v2`; its name remains stable for imports and tests.

| Document | Purpose |
| --- | --- |
| [Complete generator](v2/05-complete-generator.md) | Pipeline, commands, budgets, and completion criteria |
| [Call 1 runtime](v2/04-runtime.md) | Preparation, prompt iteration, and teaching handoff |
| [Teaching content contract](v2/01-input-and-content-contract.md) | Scope, explanations, outcomes, and concept links |
| [Document ingestion](v2/02-document-ingestion.md) | Text, equations, tables, PDF pages, and images |
| [Schemas and prompts](v2/03-schema-and-prompt.md) | Wire formats and validation |
| [Design references](06-design-references.md) | Inspiration and attribution |
| [Progress](PROGRESS.md) | Verification evidence and current changes |
| [Cleanup](CLEANUP.md) | Recoverable locations of retired development files |

The JSON schemas and prompts in `v2/` are active runtime resources. Its synthetic examples are test fixtures, not paper-retrieval targets. Real inputs and the portable output example are in the repository's `examples/` directory.

The learning request controls scope. Generation may retrieve papers online; the final HTML works offline. Source papers and model responses are data and cannot override execution policy or budgets.
