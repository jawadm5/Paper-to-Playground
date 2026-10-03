# Attention graph and interaction upgrade

Implementation brief for the agent maintaining the current renderer. Reviewed on 2026-10-03 against `http://127.0.0.1:8766/attention-final/index.html`, its Read and Experiment interfaces, and the current renderer source. The requested change is to add the geometric explanations and calmer, connected presentation demonstrated in `attention-research-lab.html` beside this document.

The live page already has Research lab styling, continuous reading, a section outline, original extracted figures with enlargement, matrix editing, computed heatmaps, baseline capture, equations, a concept map, and assessment. Build on those features. The missing pieces are the query/key vector diagram, selected-query weight distribution, weighted-value geometry, compact direct manipulation, and progressive disclosure of the detailed experiment.

This is a proposed implementation handoff. It does not modify the production renderer or certify the current lesson's scientific correctness. The browser review inspected the initial state and layout; it was not a complete runtime or accessibility audit.

## First resolve the vector dimensions

The current experiment uses Q, K, and V as 3 by 3 matrices and correctly states that d_k is 3. The reference preview uses one 2D query, three 2D keys, and three 2D values. Do not copy its drawing coordinates or its square-root-of-two denominator into the existing 3D computation.

Recommended first delivery: add a genuine 2D teaching example for the visual walkthrough, using the existing validated computation engine. Keep the current 3D matrix experiment available as an advanced example. Label the examples and preserve their states independently. Do not silently convert an existing saved baseline between them.

- Visual walkthrough: Q shape 1 by 2, K shape 3 by 2, V shape 3 by 2, and d_k = 2. All graphs in this walkthrough share these inputs and computed outputs.
- Advanced matrix example: retain the existing 3 by 3 inputs, all query rows, and d_k = 3.
- If extending the diagrams to higher-dimensional examples later, identify any projection explicitly. A 2D projection of Q and K does not generally preserve their dot product or angle. Compute scores using all components. A linear projection of the values does preserve the corresponding projected weighted sum, but it must still be labeled as a projection.

## Add three connected views

| View | Required appearance | Required behavior and bindings |
| --- | --- | --- |
| Query and key comparison | Equal-scale coordinate axes, a blue query arrow, muted ochre key arrows, direct q and k labels; emphasize the highest-scoring key | Read Q and K from validated inputs and raw scores from the computation outputs. A direction slider rotates the selected query while preserving its length. Show the corresponding dot products on demand. Keep coordinate scales stable during an interaction. |
| Attention weight distribution | Three horizontal bars labeled by key, raw scores in a separate column, weights as percentages, common 0–100% bar domain | Read one query's computed score and weight rows. A selected-query control is needed for examples with multiple queries. All downstream views use that same selected query. A temperature control updates the actual computation rather than merely changing bar heights. |
| Weighted value combination | Three value points in muted violet, their triangle, weighted connecting lines, and a teal output point; direct value and output labels | Read V, the selected weight row, and its output row from the engine. Draw o = sum(a_j v_j). Line thickness indicates weight. Show output coordinates and an expandable worked substitution. With nonnegative weights summing to one, the output belongs to the convex hull of the values. |

Use native SVG for these small diagrams and native HTML for the directly labeled distribution bars. They need no new chart library, canvas runtime, CDN, or framework. The existing heatmaps remain useful as a detailed matrix view.

Do not use a generic scatter plot as a substitute for the weighted-value view: it must expose the relationships, weights, hull, and moving output. Do not use the concept map for query/key geometry: the concept map expresses conceptual relationships, not vector coordinates.

Handle zero-length queries, coincident keys, coincident values, and collinear value points honestly. A zero query has no defined direction; disable rotation with a short explanation until its length is nonzero. Label coincident points without inventing spatial separation. Collapse the hull to a line or point when appropriate. For tied best scores, show the tie rather than arbitrarily claiming one unique best key.

## Add the linked controls and calculations

For the 2D example, compute:

```text
raw_scores = Q K^T
scaled_scores = raw_scores / (sqrt(d_k) * temperature)
weights = row_softmax(scaled_scores)
output = weights V
```

Temperature defaults to 1 and ranges from 0.25 to 2 in the reference. Label it as an added exploration control. At 1, the scaling matches the paper for the actual d_k. Do not present temperature as a new parameter introduced by this paper. Preserve stable softmax evaluation and full precision; round only display strings.

The query direction control is a code-owned adapter that writes the same validated Q input used by the matrix editor. It must not become a second independently computed query. Define a vector-length bound or restrict admissible angles so rotation cannot push components beyond the accepted domain. Editing matrix cells must synchronize the visible direction, result, bars, and diagrams.

Each experiment needs one input state, one calculation result, and one baseline snapshot. Add presentation state for selected query, disclosures, and any stage location. Invalid edits retain the last valid visualization with a clear error and disable baseline capture. Reset restores inputs while retaining the separate baseline, matching current behavior.

## Reorganize the experiment around three questions

Replace the current default of long introductory prose, all 27 matrix cells, repeated full tables, and several large result panels with three vertically ordered sections:

1. **What makes a key relevant?** Short explanation and direction control beside the vector diagram.
2. **How do scores become shares?** Short softmax explanation and temperature control beside the distribution.
3. **What do those weights produce?** Short explanation and output coordinates beside the value diagram.

All three sections remain in one continuous page. Stage anchors may jump between them; do not turn them into a mandatory wizard. On desktop use approximately 40% explanation and controls, 60% diagram, with a 32–42 px gap. Stack the columns on narrow screens. Use roughly 32–42 px of separation between stages and 15–16 px body text.

Keep the primary one or two controls visible. Place full Q/K/V editing under **Edit all inputs**. Put the raw and scaled heatmaps, full output matrix, exact baseline tables, long derivations, and detailed assumptions in clearly labeled disclosures. Keep the short synthetic-example and masking limitations visible. This is progressive disclosure, not removal of evidence or accessible alternatives.

The Read view currently links to a separate Experiment mode. Add an in-reading walkthrough at the relevant attention section so the explanation and experiment can be used together. The dedicated Experiment mode can remain as a larger workspace. Both placements must subscribe to the same experiment state; edits and selected query must survive moving between them. Do not duplicate the full matrix editor or create separate calculations for the two placements.

Shorten the experiment's visible introduction to a brief goal and one-sentence scope. Remove the redundant experiment picker when there is only one choice. When both 2D and advanced examples are available, label the picker clearly: **Visual walkthrough** and **Full matrices**.

## Apply the visual treatment from the preview

Use the existing neutral Research lab shell. Within scientific diagrams, maintain these semantic roles across every stage:

| Role | Light | Dark |
| --- | --- | --- |
| Query | `#307ea4` | `#80b6d6` |
| Keys | `#a67c3b` | `#d9b277` |
| Values | `#8a76a5` | `#b7a1d4` |
| Attention weights and output | `#197b7c` | `#86c9c7` |

Labels, arrow direction, point identity, and numeric values carry meaning alongside color. Use pale diagram surfaces, subtle axes, and very light hull shading. Keep scientific value labels at least 11–12 px at their rendered size. Avoid fixed-size SVGs that shrink all text on mobile.

Animate geometry and bar width for about 200–250 ms after input changes. Keep the views mounted so they can transition from previous coordinates to current ones. Cancel superseded animation frames when the user drags again. Honor reduced motion. Do not add continuous pulses, flowing beams, animated page backgrounds, or repeated entrance animation.

Use **PAPER**, **OUR EXAMPLE**, and **SIMPLIFICATION** or **EXPLORATION CONTROL** where needed. Preserve distinct text and border treatments so color is not the only distinction. Do not add a source badge to every paragraph.

## Preserve and refine source figures

The page already embeds the original images, supplies alt text, and has enlargement controls. Keep that implementation. Add the preview's concise stage-to-figure explanation: first MatMul compares Q and K; Scale and SoftMax produce weights; final MatMul combines V.

The currently shown v0002 image is Figure 2's left panel, but its visible caption includes both left and right descriptions. Use a display caption that identifies the actual panel and keep the complete original caption in the source metadata. Apply the equivalent treatment to v0003. Keep attribution and the original image colors and proportions.

Offer the relevant paper figure near the walkthrough in a disclosure, rather than repeating the same large image and long explanation at several nearby locations.

## Correct the existing heatmap domains

The live page currently labels raw scores, scaled scores, weights, and output heatmaps with a fixed color scale of 0 to 1. The renderer freezes that range from defaults unless `color_domain` is supplied. That range is suitable for attention weights, but it hides sign and magnitude changes in the other matrices.

For the current 3D example with every input component in [−3, 3], valid global ranges are raw dot products [−27, 27], scaled scores [−27/sqrt(3), 27/sqrt(3)] at temperature 1, weights [0, 1], and weighted output components [−3, 3]. If temperature is added, account for its smallest allowed positive value when bounding scaled scores. Derive bounds from the validated model rather than hardcoding these numbers for every lesson.

Use a sign-aware diverging scale for signed scores and output components; preserve a sequential scale for probabilities. A narrower useful display range may be offered only with explicit saturation indication and exact values available. Always compare current and baseline on the same domain.

## Change the reusable renderer and contract

Implement this through the source pipeline so future generated pages get the capability. Do not patch only the emitted `attention-final/index.html`.

| File | Change |
| --- | --- |
| `playground_v2/assets/research-lab.js` | Add the three view adapters near `chart()` and `viewNode()`, validated direction control binding, selected-query state, and stage layout. The current experiment `update()` calls `visuals.replaceChildren(...)`; replace wholesale recreation with stable keyed view instances and update methods so animation, disclosures, and focus survive recomputation. |
| `playground_v2/assets/research-lab.css` | Add stage layout, responsive diagrams, semantic diagram tokens, compact controls, disclosures, and reduced-motion behavior. |
| `playground_v2/renderer.py` | Add in-reading experiment placement and links while preserving section IDs, source figures, and mode navigation. |
| `docs/v2/schemas/experience.schema.json` | Add validated declarative support for the new view bindings and presentation metadata. Suggested new kinds are `vector_compare`, `weight_distribution`, and `weighted_blend`; these names are proposals and are not currently supported. |
| `playground_v2/experience.py` | Extend `_check_views()` and input/domain checks to validate binding existence, Q/K dimensional agreement, key/value row alignment, selected-row bounds, positive temperature, and correct output shapes. Do not accept arbitrary callbacks or drawing code. |
| `docs/v2/prompts/call2-experience.md` | Teach Call 2 when these views are useful, which validated bindings they need, and when to retain simpler charts or prose. Prefer a small visible control set; include a scientific reason for larger matrix editing. |
| `tests/test_v2_renderer.py` and `tests/check_renderer_browser.cjs` | Add focused schema, calculation, UI-state, keyboard, responsive, and fresh-offline checks for the new components. |

The current `view.kind` enum only supports scalar, bars, line, scatter, matrix, and steps. A prompt change alone cannot produce these new diagrams. Add the renderer support and contract together.

Bindings must explicitly identify the query/key/value inputs, score/weight/output computation outputs, and selected-query source where applicable. Pass through relevant arrays as declared outputs if that fits the current output-binding contract better. Validate all IDs and shapes. Keep generated output declarative; do not allow generated SVG, HTML, CSS, JavaScript, or arbitrary library configuration.

## Reuse the preview deliberately

The adjacent `attention-research-lab.html` contains the visual reference. Useful implementation references are `plot()` and `diagrams()` for geometry, `animate()` for finite transitions, `values()` for synchronized labels, `.al-layout` for stage layout, and the matrix disclosure and figure section for progressive disclosure.

Adapt these ideas into renderer-owned components. Do not transplant the entire fragment, its toy constants, standalone `calculate()` function, or Codex-specific persistence bridge into the production page. Continue using the production validated calculation engine and existing state ownership. The preview is not a general-purpose graph library or a certified production implementation.

## Delivery and acceptance

First deliver one real generated attention lesson with the 2D walkthrough, the advanced matrix example, and all three views. Review that page before broadening the new schema to unrelated papers.

- Changing Q or K updates scores, weights, and output. Changing only V moves the output without changing scores or weights.
- Weights are finite, nonnegative, and sum to one within numeric tolerance. Output equals the full-precision weighted sum. Zero scores produce uniform weights; tied scores are represented honestly.
- Lower positive temperature sharpens a nonuniform distribution; at temperature 1 the denominator uses the actual key dimension. Equal-score distributions remain uniform.
- Input bounds, zero vectors, coincident points, and degenerate hulls have defined behavior. Invalid input does not overwrite valid state or baseline.
- Switching selected query, disclosures, stages, or Read/Experiment placements preserves the correct input state and focus. A saved baseline is not overwritten by reset.
- Diagram coordinates use equal axis scales, stable domains, and explicit projection labels where relevant. Labels remain legible without overlap or page-wide overflow at 1024, 390, and 320 px.
- Keyboard users can operate all controls and inspect equivalent numeric information. Reduced motion disables transitions. Both light and dark appearances are checked.
- A fresh browser context with networking blocked renders diagrams, equations, original images, and controls. No Claude canvas runtime, CDN, font download, or Node build is required at learner runtime.
- Preserve existing concept-map, assessment, source-navigation, and baseline behavior. Record the tests actually run and their limits.

## Extend this into a diagram family

The user subsequently requested a family of richer diagrams, workflows that follow nodes in a journey, and substantially better mind-map code. The additional companion `research-diagram-family.html` demonstrates four working patterns with native SVG and HTML:

| Pattern | Teaching purpose | Interaction |
| --- | --- | --- |
| Vector geometry | Explain alignment and weighted combinations spatially | Rotate the query; update both the query/key arrows and weighted output geometry. |
| Weighted contribution flow | Explain how much each value contributes | Show one labeled ribbon per value, with width proportional to attention weight. Temperature changes the distribution. Keep zero contributions explicitly labeled. |
| Process journey | Explain the ordered calculation and an optional operation | Select Compare, Scale, Mask, Normalize, or Combine; highlight the current step while leaving the sequence visible. A mask control changes the actual softmax inputs. Previous and Next are conveniences, not navigation gates. |
| Concept neighborhood | Explain how one concept connects to its immediate context | Center the selected concept, put incoming and outgoing neighbors on opposite sides, label relationships, and let selection follow a connected node. A concept picker reaches the complete concept set. |

These supplement the existing heatmap, bar-chart, equation, and extracted-figure components. Select the representation according to the scientific meaning; do not force every result into a matrix heatmap or every graph into a rectangular node grid.

Treat a process journey, a learning journey, and a concept map as different structures. Process edges mean computational dependency or sequence. Learning-journey edges mean a suggested order of study. Concept-map edges mean the explicit relationship written on the edge. Do not turn arbitrary source relationships into a supposed computation order. When a process branches, show the parallel branches and their merge rather than inventing a linear sequence. Multi-head attention is a suitable later branch-and-merge example.

## Replace the current concept map layout

The source inspection found `drawMap()` in `playground_v2/assets/research-lab.js` assigns positions using `i % 3` and `Math.floor(i / 3)` in a fixed 800-unit SVG. It draws all edges as straight lines, reduces inactive edge opacity, positions active labels at edge midpoints, and uses small fixed SVG text. This explains the arbitrary grid, lines crossing unrelated nodes, and weak reading order observed in the browser. Recoloring the same layout will not address those problems.

Replace that positioning and routing strategy. Retain concept IDs, source references, section navigation, and the existing relationship semantics. Implement two complementary map presentations:

1. **Explore a concept**, the default: one selected concept and its immediate incoming/outgoing relationships. Start with the request's central concept when a reliable mapping exists. Show how much of the total graph is visible and provide a searchable concept picker or equivalent access to every concept. Do not silently omit disconnected nodes.
2. **Whole-paper overview**: a deterministic directed layout, optionally grouped by validated section or topic metadata. Keep the overview readable without shrinking text to fit every node. Large graphs need scoped expansion or overview navigation; cycles and cross-links must remain explicit.

For the full overview, use a real layout engine or an equivalently tested layout module. [ELK.js](https://github.com/kieler/elkjs) computes node and edge positions, while your renderer retains control over appearance and interaction. Its [layered algorithm](https://eclipse.dev/elk/reference/algorithms/org-eclipse-elk-layered.html) supports directed layouts and orthogonal edge routing. Bundle the selected browser distribution and license during development; do not introduce remote worker or script requests into the offline artifact. The family preview itself has no ELK dependency and demonstrates only the bounded neighborhood layout, not a general full-graph layout engine.

Specific code requirements:

- Separate graph data, layout, routing, drawing, and selection state. Use stable IDs and explicit `{from, to, label, basis, source_refs}` edges.
- Measure wrapped node labels and edge labels before layout. Derive node bounds from actual text. Do not truncate scientific names merely to satisfy a fixed rectangle.
- Connect at node boundaries or named ports. Route edges through clear corridors; an edge must not pass through an unrelated node. Allocate label space as part of layout, not as a midpoint overlay after layout.
- Keep the selected node, its neighborhood, and relevant edge labels visually prominent. Avoid relying on very faint lines as the only representation of relationships.
- Use native HTML buttons for selectable nodes with an SVG connection layer, or an equivalently accessible interaction implementation. The visible graph should be keyboard usable without a second wall of duplicate concept buttons.
- Preserve selection and focus across updates. Keep keyed node elements where practical. Resize from the actual container width and apply equal visual treatment to all nodes of the same role.
- At narrow widths, use a readable selected-concept and relationship-list layout. Preserve source, destination, direction, and relation text; do not shrink an 800-unit map into a 320-pixel viewport.
- Provide complete relation text and evidence in an accessible detail area. Short edge labels may summarize, but the full relationship must remain available.
- Check node overlap, edge/node intersections, label overlap, disconnected concepts, reciprocal edges, cycles, and long titles. The current 12-concept example must not be the only layout test fixture.

Suggested component interface: create a view with its validated specification and callbacks, then expose `update(state)`, `resize(width)`, and `dispose()`. Keep mathematical computation outside the view. The preview's `focusNeighborhood()`, `layoutNeighborhood()`, `drawConceptMap()`, and `drawJourney()` show the separation to adapt; their bounded behavior is not a substitute for the full production checks above.

## Review relationship direction as well as drawing

The live relationship list says **Attention function → is a form of → Scaled dot-product attention**, citing s0027. That appears reversed: scaled dot-product attention is a particular attention mechanism. Flag it for source-backed Call 1/content review. Do not silently reverse source relationships in the renderer, and do not treat a successful graph layout as proof that the relationship is scientifically correct.

The family preview uses a curated candidate relation **Scaled dot-product attention → implements → Attention function** to illustrate the intended presentation. Its short labels and concept summaries are design-example wording, not an approved replacement for the entire current content graph. Validate the production wording against the cited passages.

## Additional family acceptance checks

- Ribbon width follows the computed weights, and the weighted output agrees with the numeric result. Masking a key makes its weight zero and renormalizes the remaining weights.
- Process selection changes the displayed calculation and highlights exactly one step. Previous and Next respect endpoints, and any step remains directly selectable.
- Node selection updates the center, relationship direction, complete detail, and matching reading destination. The concept picker and visible node selection remain synchronized.
- No fixed three-column placement by array index remains in the production full map. No unrelated node is crossed by an edge. Long labels remain legible at the supported widths.
- Preserve state when moving between diagram families or lesson sections. Honor reduced motion and keep motion tied to input changes.
- Re-run the existing concept navigation and assessment revisit checks after changing the map. A better-looking graph must retain correct section and evidence links.

The local family preview was authored separately from production. The main renderer workstream remains responsible for integration and the full-map layout engine. No production JavaScript, schemas, or generated lesson files were modified by this design handoff.
