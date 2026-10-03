# Codex Implementation Plan — Person 2

## Scope

You are implementing everything from the **output of LLM 1 onward**:

`LLM1 JSON -> LLM2 -> LessonRenderSpec JSON -> validation -> renderer -> self-contained index.html`

The first goal is a **working prototype**, not the final optimized architecture.

## Core architecture rules

1. LLM 2 must output **JSON only**, never HTML/CSS/JavaScript.
2. The renderer owns all design choices: colors, fonts, layout, graph styling, spacing, and section order.
3. The renderer must understand **component types**, not scientific concepts.
4. Do not hard-code logic for "attention", "entropy", or any paper name.
5. Numerical values shown in the final page must be produced by executable calculations in the page runtime, not copied from an LLM.
6. The final page must be one self-contained HTML file and must not need internet access.
7. Build and test each stage before moving to the next one.
8. Do not refactor unrelated code unless explicitly requested.

---

# Temporary upstream input contract

During development, use:

`tests/fixtures/dummy_llm1_output.json`

This is a mock of what Person 1 will eventually give us.

The real upstream contract can later replace the mock, but the rest of this project should continue to depend on a clearly defined JSON input.

---

# Target LessonRenderSpec

Conceptually LLM 2 should produce:

```json
{
  "schema_version": "0.1",
  "meta": {
    "title": "string",
    "subtitle": "string"
  },
  "intro": {
    "why_it_matters": "string",
    "overview": "string"
  },
  "symbols": [
    {
      "symbol": "string",
      "label": "string",
      "description": "string"
    }
  ],
  "variables": [
    {
      "id": "string",
      "type": "scalar | boolean | vector | matrix",
      "default": "type-dependent value"
    }
  ],
  "controls": [
    {
      "id": "string",
      "type": "slider | number_input | toggle | matrix_editor",
      "variable": "variable-id",
      "label": "string",
      "min": "optional number",
      "max": "optional number",
      "step": "optional number"
    }
  ],
  "computations": [
    {
      "id": "string",
      "op": "supported-operation-name",
      "inputs": ["ids"]
    }
  ],
  "visualizations": [
    {
      "id": "string",
      "type": "bar_chart | line_chart | heatmap | matrix_display | step_pipeline",
      "data": "id or list of ids",
      "title": "string"
    }
  ],
  "intermediate_values": [
    {
      "label": "string",
      "data": "id"
    }
  ],
  "guided_explorations": [
    {
      "title": "string",
      "instruction": "string",
      "observe": "string",
      "explanation": "string"
    }
  ],
  "limitation": {
    "text": "string"
  },
  "source": {
    "paper": "string",
    "section": "string",
    "url": "string"
  }
}
```

## Initial supported operations

- `add`
- `subtract`
- `multiply`
- `divide`
- `sqrt`
- `sum`
- `normalize`
- `softmax`
- `row_softmax`
- `transpose`
- `matrix_multiply`
- `matmul_transpose`

Do not use `eval()`.

---

# Fixed visual platform decisions

## Fixed structure

1. Header
2. Why this matters
3. Symbols / definitions
4. Interactive exploration
5. Intermediate values
6. Guided explorations
7. Limitation / assumption
8. Source

## Fixed design principles

- System font stack only
- No remote fonts
- No remote scripts
- No CDN
- Consistent spacing and border radius
- One fixed primary/accent color
- One fixed chart style
- One fixed page width
- Responsive enough for a normal laptop browser

The JSON must not contain CSS, colors, pixel dimensions, fonts, or layout instructions.

---

# STAGE 1 — Repository scaffold + schema

## Codex task

Implement the basic project structure and the Pydantic schema for `LessonRenderSpec`.

Create:

```text
src/
  schema.py
  renderer.py
  llm2.py
  runtime/
    runtime.js
  templates/
    base.html

tests/
  fixtures/
    dummy_llm1_output.json
    attention_render_spec.json
  test_schema.py
  test_renderer.py
```

Requirements:
- Implement typed Pydantic models.
- Restrict control types to slider, number_input, toggle, matrix_editor.
- Restrict visualization types to bar_chart, line_chart, heatmap, matrix_display, step_pipeline.
- Restrict computation operations to the initial supported-operation registry.
- Enforce at least 2 controls, 1 visualization, 2 guided explorations, a limitation, and a source.
- Add useful validation errors.
- Do NOT implement LLM calls yet.
- Do NOT implement the renderer yet beyond placeholders.

## Test after Stage 1

Run:

```bash
pytest tests/test_schema.py -q
```

Also test one intentionally invalid JSON:
- only one control
- unsupported visualization type
- unsupported computation operation

Expected:
- valid fixture passes
- invalid fixture fails with clear validation errors

## What should change after Stage 1

Before: `JSON is just an idea`

After: `LessonRenderSpec is a strict executable contract`

Do not move on until schema tests pass.

---

# STAGE 2 — Static renderer + fixed platform design

## Codex task

Implement the renderer for **static content only**.

Input: `LessonRenderSpec`

Output: `index.html`

For this stage render:
- Header
- Intro / why it matters
- Symbols
- Guided explorations
- Limitation
- Source

Do NOT implement interactive controls or calculations yet.

Requirements:
- Use `base.html`.
- Embed CSS inside the final HTML.
- Use one fixed visual theme.
- No remote URLs for JS/CSS/fonts/images.
- Renderer must not check concept names.
- Renderer must dispatch based only on schema/component types.

Implement:

```python
render_to_html(spec: LessonRenderSpec) -> str
write_html(spec, output_path)
```

## Test after Stage 2

Run:

```bash
pytest tests/test_renderer.py -q
```

Then:

```bash
python -m src.renderer tests/fixtures/attention_render_spec.json out/index.html
```

Open `out/index.html` manually.

Check:
- page opens locally
- title is correct
- fixed style is visible
- symbols appear
- guided exploration cards appear
- limitation appears
- source appears
- browser dev tools show no failed network request
- disconnect internet and reload the page

## What should change after Stage 2

Before: `Valid render spec exists`

After: `Valid render spec can already become a consistent offline webpage`

---

# STAGE 3 — Variables + controls + state runtime

## Codex task

Add interactive state and controls.

Implement runtime support for:
- slider
- number_input
- toggle
- matrix_editor

Use one central JS state object generated from `variables`.

Interaction rule:

`control change -> update state -> recompute -> rerender dependent outputs`

For now `recompute()` may be a placeholder.

Requirements:
- controls initialize from variable defaults
- controls update state
- no React or external frameworks
- all JS embedded into final `index.html`
- no arbitrary JavaScript from JSON

## Test after Stage 3

Use `attention_render_spec.json`.

Open page and verify:
- slider changes its state value
- toggle changes true/false
- matrix cells are editable
- browser console has no errors

Also check generated HTML contains expected control IDs and embedded initial state.

## What should change after Stage 3

Before: `Page is static`

After: `Page has working learner controls connected to a shared state model`

---

# STAGE 4 — Computation engine

## Codex task

Implement the supported computation registry in `runtime.js`.

Implement:
- add
- subtract
- multiply
- divide
- sqrt
- sum
- normalize
- softmax
- row_softmax
- transpose
- matrix_multiply
- matmul_transpose

Requirements:
- NO `eval()`
- references resolve by ID
- variables and computation results live in one data context
- computations run in declared order
- useful errors for missing IDs / shape mismatch
- recompute all calculations after each control change

For the attention fixture:
- compute QK^T
- optionally scale
- row-softmax
- multiply by V

If conditional computation is needed for the scaling toggle, implement one minimal explicit mechanism rather than arbitrary code execution.

## Test after Stage 4

Minimum known tests:

### Softmax
Input: `[0, 0]`
Expected: approximately `[0.5, 0.5]`

### Row softmax
Every output row should sum approximately to 1.

### Matrix multiply
Use a simple hand-checkable 2x2 example.

### Attention invariant
- attention weight rows sum to 1
- final output dimensions are correct

Run:

```bash
pytest -q
```

Then manually change Q/K values in browser and verify intermediate values change.

## What should change after Stage 4

Before: `Controls change state`

After: `Controls cause real executable scientific calculations`

---

# STAGE 5 — Visualizations + intermediate values

## Codex task

Implement visualization components:
- matrix_display
- heatmap
- bar_chart
- line_chart
- step_pipeline

Use vanilla HTML/SVG/Canvas, or a locally embedded library if already chosen by the team.

Requirements:
- no CDN dependencies
- visualization components read data by ID
- update after recomputation
- use fixed design system
- same visualization type always uses same style
- intermediate_values render current computed values

## Test after Stage 5

For attention:
- changing Q or K changes score matrix
- heatmap updates
- output matrix updates
- scaling toggle changes values

Create a second manual fixture:
`entropy_render_spec.json`

It should use:
- numeric controls
- a bar chart
- an executable entropy calculation if supported

Critical test:
The renderer should handle the second fixture **without adding code that checks for "entropy"**.

## What should change after Stage 5

Before: `Calculations work`

After: `Calculations drive visual explanations`

---

# STAGE 6 — LLM 2 integration

## Codex task

Implement `src/llm2.py`.

Input:
`dummy_llm1_output.json`

Output:
valid `LessonRenderSpec`

Requirements:
- use supplied model ID
- request JSON only
- include exact allowed controls, visualizations, and operations in prompt
- include the LessonRenderSpec JSON schema
- instruct model:
  - no HTML
  - no CSS
  - no JavaScript
  - no invented component names
  - no unsupported operations
  - >=2 meaningful controls
  - >=2 guided explorations
  - source grounding
  - one limitation/assumption/misunderstanding
- validate output immediately with Pydantic
- fail clearly if invalid for now

Expose something like:

```python
generate_render_spec(
    concept_json: dict,
    model_id: str
) -> LessonRenderSpec
```

## Test after Stage 6

First use a mocked LLM response:
- confirm JSON -> Pydantic -> renderer works

Then use one real model call on `dummy_llm1_output.json`.

Verify:
1. valid JSON
2. schema passes
3. no unsupported component
4. renderer accepts it unchanged
5. generated HTML opens
6. controls work
7. computations update
8. page still works offline

## What should change after Stage 6

Before: `Human-written LessonRenderSpec -> HTML`

After: `LLM1-style scientific JSON -> LLM2-generated LessonRenderSpec -> HTML`

---

# STAGE 7 — End-to-end hardening

## Codex task

Add lightweight output checks.

Check:
- HTML exists
- HTML non-empty
- no remote dependency URLs
- no OpenRouter/API calls inside final page
- at least 2 controls rendered
- guided explorations present
- limitation present
- source present
- all computation references resolve
- all visualization data references resolve

Return clear validation failures.

Optional only after everything works:
- one LLM 2 retry when schema validation fails

Do not add complex multi-agent behavior.

## Test after Stage 7

Run:
- Attention fixture
- Entropy fixture
- malformed upstream JSON
- invalid LessonRenderSpec
- missing computation reference
- unsupported visualization
- fake remote dependency

Expected:
- valid cases pass
- invalid cases fail clearly
- no silent corruption

## What should change after Stage 7

Before: `Happy-path prototype`

After: `Prototype that detects common failures before submission`

---

# Final acceptance test

A fresh run should demonstrate:

```text
dummy_llm1_output.json
        |
        v
      LLM 2
        |
        v
LessonRenderSpec
        |
  Pydantic validation
        |
        v
     Renderer
        |
        v
   out/index.html
```

Open `out/index.html` with internet disconnected.

Verify:
- fixed design
- correct title
- explanation appears
- symbols defined
- >=2 meaningful controls
- controls change values
- computations update
- visualization updates
- intermediate values update
- 2 guided explorations
- limitation
- source grounding
- no console errors
- no network requests

---

# Recommended Git commits

1. `feat: define lesson render schema`
2. `feat: add static lesson renderer`
3. `feat: add interactive control runtime`
4. `feat: add computation engine`
5. `feat: add reusable visualizations`
6. `feat: integrate llm2 planner`
7. `test: add renderer validation and failure checks`

Commit only after the stage tests pass.

---

# What Codex should NOT decide

Humans own:
- final JSON contract
- supported components
- supported operations
- validity rules
- fixed design system
- whether a new feature is necessary
- whether a failure indicates an architecture problem

Codex implements bounded tasks against those decisions.

---

# Development rule

At the end of every stage:

1. Run automated tests.
2. Open generated HTML if rendering changed.
3. Check browser console.
4. Commit only if tests pass.
5. Then give Codex the next stage.

Do not ask Codex to implement all stages in one prompt.
