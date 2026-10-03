# Paper-to-Playground

**Team: Jawad Marji and Ali Zahreddine**

Turn a research paper into a self-contained, offline learning page. Students can read a simpler explanation, explore a connected concept map, adjust working experiments, and complete an assessment. The requested focus determines whether the lesson covers one mechanism or a broader paper overview.

## Run

Use Python 3.11. Set `OPENROUTER_API_KEY` in the environment before generation. On Windows, an existing user environment value saved with `setx` is also supported.

Create `case.json` with these three fields, or copy [the attention input](examples/attention-input.json):

```json
{
  "source_url": "https://arxiv.org/abs/1706.03762v7",
  "focus": "Explain scaled dot-product attention and the roles of queries, keys, and values.",
  "audience": "Engineering undergraduates familiar with vectors."
}
```

Run the submission interface from the repository root:

```sh
python -m pip install -r requirements.txt
python agent.py --input case.json --output out --model MODEL_ID
```

Replace `MODEL_ID` with the OpenRouter model identifier. The tested profile is **`deepseek/deepseek-v4.1-flash`**. The output directory must be new or empty; use another path for subsequent runs.

Open `out/index.html` directly in a current Chromium or Edge browser. All scripts, styles, data, equations, and selected source images are embedded. The final page needs no server, API key, or internet connection. Generation uses the internet to retrieve the paper and call OpenRouter. No Node, npm, browser installation, or frontend build is required to run the generator.

## Included examples

- [Attention input](examples/attention-input.json) and [offline output](examples/attention-output.html): the matching submission example pair.
- [Attention overview input](examples/attention-overview-input.json): a broader learning request.
- [Entropy input](examples/entropy-input.json): probability and uncertainty from Shannon's paper.

Generated working directories are local and ignored by Git. The committed HTML example can be opened from a fresh checkout.

## How it works

1. Python retrieves a public HTML/PDF or arXiv source and prepares text, equations, captions, and bounded image evidence.
2. **Call 1** produces validated teaching JSON: outcomes, sections, simple explanations, intuition, technical detail, and concept relationships.
3. **Call 2** produces validated interaction JSON: controls, calculations, graphs, guided challenges, and assessment questions.
4. A deterministic renderer builds the offline HTML using project-owned components. Models do not generate executable HTML, CSS, or JavaScript.

The normal path uses two model calls. Call 1 allows one bounded validation repair; Call 2 allows up to three, stopping when valid or when a repair makes no change. The run enforces a 590-second deadline, at most 10 attempted requests, and a 30,000 completion-token budget. Default initial allowances are 18,000 tokens for Call 1 and 7,000 for Call 2, plus up to 2,000 for each repair, capped by the remaining whole-run budget. All calls use the supplied model.

## Output and iteration

| File | Purpose |
| --- | --- |
| `index.html` | Student-facing offline lesson |
| `paper_content.json` | Validated Call 1 teaching content |
| `experience.json` | Validated Call 2 interaction design |
| `assets/` | Extracted source-image handoff |
| `summary.json` | Status, timing, aggregate token usage, costs, and validation results |
| `reports/`, `requests/`, `responses/` | Per-call accounting and key-free request/response artifacts |
| `trace.jsonl` | Recorded pipeline events and timing |

Edit [Call 1's prompt](docs/v2/prompts/call1-content.md), [Call 2's prompt](docs/v2/prompts/call2-experience.md), or the renderer assets in `playground_v2/assets/`. The contracts and schemas are documented in [the documentation index](docs/README.md).

To render saved JSON without a model request, use the same input case and its saved artifacts:

```sh
python agent.py --input case.json --from-content previous-run/paper_content.json --experience previous-run/experience.json --output rendered-again
```

Omit `--experience` and supply `--model MODEL_ID` to regenerate only Call 2. `content_agent.py` is the separate source-preparation and Call 1 development utility; see [the runtime guide](docs/v2/04-runtime.md).

## Verification and limits

The local Python suite has **118 passing tests**. Responsive, offline, interaction, assessment, and concept-layout browser checks are recorded separately in [the progress log](docs/PROGRESS.md).

```sh
python -m unittest discover -s tests -p "test_v2*.py" -v
python -m pip check
```

Validation checks source references, image paths, component contracts, expression dependencies, dimensions, and numerical scenarios. Structural and calculation checks do not certify every scientific explanation. Unsupported computations and evidence that cannot fit the extraction limits fail with diagnostics. Full PDF page images are model evidence; they are not presented as extracted figures. The bounded MathML renderer retains visible notation when it cannot format an equation.

Exit codes are `0` for completion, `2` for invalid input/configuration, and `4` for generation or validation failure. Failed runs preserve available candidates and diagnostics.

## Credits

Dependencies are pinned in [requirements.txt](requirements.txt). The browser interface, concept layout, diagrams, and calculation components are project-owned and use no CDN libraries or web fonts. Original paper images retain source attribution. [Design references](docs/06-design-references.md) document the learning and interface patterns that informed the project.
