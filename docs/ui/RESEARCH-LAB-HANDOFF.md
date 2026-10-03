# Research lab UI component handoff

Implementation update, 2026-10-03: the user transferred full ownership to the main workstream. The production renderer now lives in `playground_v2/renderer.py` and `playground_v2/assets/`, uses the approved native/offline component approach, and is integrated through `agent.py`. This handoff remains the historical design reference; the runtime guide and progress record supersede its earlier statements about outstanding integration or person 2 ownership.

This guide is for person 2, who owns Call 2 and the deterministic renderer. It records the user's selected visual direction, the agreed component shortlist, and the behavior demonstrated by the component preview. The implementation target is a continuous, source-grounded learning guide whose coverage follows the learner's request.

The user selected Research lab and agreed to the six initial component examples below, then confirmed that extracted paper images are supported. A source-figure block now joins the preview. Its exact implementation and final renderer integration remain review candidates. This document does not change Call 1 schemas or production runtime code.

## Product decisions

- Use continuous reading, with an outline that jumps to sections and indicates the active section.
- Let the request determine coverage. A whole-paper request gets the paper's coherent narrative. A specific request gets the requested concept or section plus the prerequisites and context needed to understand it. The map, experiments, and assessment follow that same scope.
- Use the Research lab visual direction: teal accents, slate text and header, pale neutral surfaces, clear sans-serif prose, and restrained monospace labels and computed numbers.
- Keep explanations and experiments beside each other when useful on desktop; stack them on small screens. Do not manufacture an experiment for a section that needs prose or a figure instead.
- Keep simpler explanations visible and technical depth available on demand. Preserve scientific qualifications and identify teaching examples and simplifications.
- Use extracted paper images where they help the requested explanation. Preserve proportions, readable labels, captions, source locators, and attribution. Provide an enlarged view and descriptive alternative text. Keep original artwork visually distinct from synthetic experiments.
- Keep free navigation and state preservation across reading, map, experiment, and assessment. Feedback remains withheld until final assessment submission.

**Integration correction:** the earlier V2 contract says focus changes depth without discarding the rest of the paper's story. The user's later instruction in this design conversation explicitly allows a focused guide. Align that coverage policy with the input and Call 1 workstream before freezing the final end-to-end behavior. This handoff records the correction; it does not claim those upstream documents or prompts have been changed.

## Review source

The companion `research-lab-components.html` is the editable HTML fragment used by the in-chat component preview. It contains synthetic teaching data, native browser controls and SVG diagrams, Research lab styles, and an embedded original paper image. It is a component demonstration, not the production renderer or a completed explanation of a paper.

The revised preview has no external script, stylesheet, font, or image dependencies. It uses a native range input, SVG charts and concept map, native MathML, and a PNG data URL. Host persistence is optional and guarded against synchronous and asynchronous failures. To inspect outside the conversation, use a standards-mode document with a viewport meta tag; the actual inline sandbox wrapper should also be checked.

The user reported an inline runtime failure in the earlier CDN-based preview. That failure did not reproduce in the local sandbox wrapper, so its exact cause is unconfirmed. Removing runtime library downloads and their initialization removes those dependencies from this review surface. It does not change the recommended production library shortlist below or prove that those libraries caused the original failure.

The preview is not the final offline artifact. See the packaging requirements below. Its source should be adapted into renderer-owned components rather than copied as paper-specific generated output.

## Seven reusable blocks

| Block | Demonstrated behavior | Implementation source | Required renderer inputs |
| --- | --- | --- | --- |
| Parameter control | Slider, tick labels, exact numeric input, keyboard changes; invalid input preserves the last valid calculation and disables baseline capture | Native range in preview; [noUiSlider examples](https://refreshless.com/nouislider/examples/) for a richer production control | Stable variable ID, label, unit, domain, step, default, formatting, explanation |
| Comparison chart | Current and saved baseline shares on one scale, hover labels, exact data table | Native SVG in preview; [Apache ECharts examples](https://echarts.apache.org/examples/en/index.html) for production | Title, axis labels and units, categories, data bindings, baseline snapshot, formatting |
| Heatmap | Labeled rows and columns, fixed color domain, visible values, cell inspection, keyboard-accessible table alternative | [ECharts heatmap examples](https://echarts.apache.org/examples/en/index.html#chart-type-heatmap) | Row and column labels, numeric matrix binding, domain, unit, explanation per cell or a bounded template |
| Concept node and links | Meaningful labeled edges, selected-node explanation, readable concept buttons, and a link to the corresponding section | [Cytoscape.js demos](https://js.cytoscape.org/#demos) | Stable concept IDs, names, summaries, relationships, existing section destinations |
| Equation and variables | Expandable typeset equation, live worked substitution, symbol definitions and contextual simplification | [KaTeX browser documentation](https://katex.org/docs/browser) | Equation text, variable IDs, definitions, units/domains, calculation bindings, evidence references |
| Section navigation | Native page scrolling, sticky section outline, active-section indication, normal section anchors | [CSS scrolling and scrollbar styling](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Scrollbars_styling) | Ordered section IDs and titles, hierarchy, current location; no generated CSS or routes |
| Extracted paper figure | Original image, preserved aspect ratio and artwork, contextual explanation, caption, attribution, source link, inline enlarge/reduce | Native `figure`, `img`, and `figcaption`; embedded asset bytes | Existing visual ID, verified available asset, MIME type, caption, locator, attribution, descriptive alt text, related section |

The previously tested library versions were noUiSlider 15.8.1, ECharts 6.0.0, Cytoscape.js 3.33.1, and KaTeX 0.16.32; these remain implementation candidates, not a claim of the latest versions. They are no longer loaded by the inline preview. Its heatmap and graph use native SVG and its equation uses native MathML. Preserve and review upstream licenses and notices if adopting the libraries. The preview does not introduce a framework dependency.

The source figure is `v0002` from `out/v2-attention-prepared/source.json`, resolved to `assets/v0002.png`: Figure 2, left panel, Scaled Dot-Product Attention, from Vaswani et al., *Attention Is All You Need*. The original PNG is embedded unchanged. Its caption identifies only the available left panel; it does not imply that the right panel is present. The generated teaching explanation is separate from the source caption. Retain this distinction for figures extracted as multiple assets.

## Shared state and calculation behavior

The synthetic values are A = 2, B = 8, C = 5. The control sets A's percentage. The remaining percentage is divided between B and C in a 3:2 ratio. The mixture is the sum of each value multiplied by its fractional share.

The current chart, first heatmap row, result, tables, and worked equation all derive from the same validated state. Two additional heatmap rows are fixed synthetic examples, visibly identified as such. The baseline is a separate snapshot and stays unchanged when the current input changes. Reset input restores the default input; it does not overwrite the baseline.

Do not use the example's fixed values or matrix as hidden shortcuts in production. Each generated lesson supplies its own validated calculation model and meaningful controls. The graph relationships in the preview describe a weighted mixture; they are not a complete attention concept map.

## Research lab design tokens

| Role | Light appearance | Dark appearance |
| --- | --- | --- |
| Page background | `#f4f7f8` | `#152126` |
| Surface | `#ffffff` | `#1d3037` |
| Soft surface | `#e6f2f2` | `#263e45` |
| Main text | `#153a44` | `#e3f4f5` |
| Secondary text | `#536b75` | `#afc7ce` |
| Divider | `#d4e2e5` | `#38535c` |
| Accent | `#137b83` | `#8ed9d4` |
| Baseline chart series | `#8c9da3` | `#7d949b` |

Use ordinary sans-serif prose at 15–16 px, larger editable fields on touch devices, 11–12 px supporting labels, and monospace computed values. Keep corners restrained, typically 6–9 px. The preview uses local system fonts. These are design values for adaptation, not a completed contrast or accessibility audit.

Map the same scientific quantity to the same label and color across a lesson. Use series colors only when they encode a meaningful distinction. Show labels and numerical values so color is never the only carrier of meaning.

## Call 2 and renderer responsibilities

Call 2 should choose from named, renderer-owned blocks and provide their validated data and references. It should not emit arbitrary library configuration, callbacks, HTML, CSS, JavaScript, or file paths. The list below describes proposed adapter inputs, not a replacement wire schema:

- Control: variable reference, domain, default, unit, and explanation.
- Chart: visual kind, series bindings, axis semantics, display bounds, and description.
- Heatmap: matrix binding, labels, color domain, and cell-description rule.
- Map: concept references, labeled relationship references, and section destinations.
- Math: equation and variable references, plus computed worked-example bindings.
- Navigation: existing section order, IDs, titles, and hierarchy.
- Source figure: existing visual reference, descriptive alternative text, relevant explanation, and placement. The renderer resolves asset bytes and trusted metadata; Call 2 must not invent asset paths or mark caption-only entries as images.

Continue resolving `source_refs` and `visual_ids` through the code-owned source metadata. Display evidence locators and attribution near the content they support. Do not relabel caption-only metadata as an available image. Keep `section_id` destinations stable so map links, assessment revisit links, and the outline agree.

The renderer owns escaping, state updates, calculation execution, accessible names, focus behavior, responsive chart resizing, theme mapping, and failure states. For KaTeX, keep `trust: false`; validate resource limits and handle unsupported math visibly. Scientific correctness is not established by successful rendering.

## Other resources and conditional choices

- [shadcn/ui components](https://ui.shadcn.com/docs/components) and [blocks](https://ui.shadcn.com/blocks): useful design references and implementation options if person 2 adopts React. They are not dependencies of this preview. Preserve our continuous reading layout when adapting a block.
- [SimpleBar](https://grsmto.github.io/simplebar/): optional for a contained overflow panel. The article should retain native page scrolling. Do not introduce nested scroll areas without a clear need.
- [Lucide vanilla integration](https://lucide.dev/guide/lucide): selected icon source; embed only needed icons in the final page. This preview uses visible text controls and does not require an icon bundle.
- [Official D3 gallery](https://observablehq.com/@d3/gallery): use for a mechanism that standard chart adapters cannot express. D3 is not required for the current preview.
- [React Flow examples](https://reactflow.dev/examples): alternative graph UI if the renderer uses React. Distinguish free examples from those marked Pro. Do not include both graph libraries without a specific need.

## Offline packaging

1. During development, vendor the selected pinned browser distributions, CSS, required fonts, and upstream license/notice files. Record hashes in a dependency manifest.
2. Prepare the browser assets before submission. The assessed Python generator must not require Node, an npm installation, a CDN request, or a build step to render each case.
3. Embed JavaScript and CSS into the generated HTML. Rewrite required KaTeX font URLs to embedded data URLs; the equation CSS alone is insufficient.
4. Embed source image bytes with their captions and attribution. Keep optional source hyperlinks, but no necessary lesson data should depend on following them.
5. Disable or bundle dynamic imports, external data requests, runtime font loads, worker files, and other secondary assets. Use the selected libraries' browser distributions or a prebuilt bundle.
6. Open a new browser context with networking blocked. Exercise controls, charts, concept links, equations, and assessment, and inspect the request log. A cached page is not an offline test.
7. Record full output size and rendering behavior on the target Chromium environment. This preview does not establish final offline readiness or hackathon execution readiness.

## Acceptance checks

- Control endpoints and representative values recompute correctly; invalid text leaves a clearly marked last-valid view.
- Chart scales are consistent across current and baseline; baseline capture and reset semantics are explicit.
- Heatmap labels and tooltips identify row, column, value, and unit; table controls expose the same selections.
- Map selections show the matching summary and valid reading destination. Keyboard users have an equivalent path.
- Equation substitutions agree with calculated output and retain enough precision to avoid contradictory displays.
- Source images resolve to genuine prepared assets, preserve proportions, retain caption and attribution, and enlarge without page overflow. Caption-only metadata produces a clear text reference rather than a broken image.
- Navigation works through native anchors and continuous reading; charts resize without page-wide overflow.
- Check desktop, narrow mobile, dark appearance, keyboard focus, reduced motion, and a fresh offline browser context.

## Verification status

The earlier library-based version passed bounded checks in a regular headless Edge page, but the user subsequently reported an inline runtime failure. A later check of that original fragment in the bundled sandbox wrapper did not reproduce the failure. Regular-page checks alone did not establish live inline-host success.

On 2026-10-03 the revised preview passed headless Edge checks in the bundled sandbox iframe, both normally and in a fresh context with HTTP(S) requests blocked: endpoints and intermediate calculations, baseline capture, invalid input, reset, keyboard slider changes, cell selection, concept destination, native MathML visibility, embedded image decoding, and enlargement/reduction. No page JavaScript errors occurred. There was no page-wide horizontal overflow at 1024, 390, or 320 px. A separate check passed in quirks mode with a host persistence function that throws. The preview is approximately 65 KB including the original 27,871-byte figure. The local wrapper is a proxy for the live inline host, not proof that the user's host accepted the result.

This remains a bounded component demonstration, not a complete accessibility audit. Full renderer integration, final production-library offline packaging, scientific review of generated lessons, and the complete reading/map/assessment experience remain outstanding.
