# V2 section-first schema and prompt handoff

Version 2.1 replaces the earlier flat 2.0 content shape. It expresses the user's agreed paper-like learning experience. The [V2 runtime](04-runtime.md) implements preparation and the first call; the [complete generator](05-complete-generator.md) implements Call 2 and the renderer.

## Files

| File | Purpose |
| --- | --- |
| `schemas/input.schema.json` | External three-field case input |
| `schemas/call1-input.schema.json` | Source text context and visual metadata for call 1 |
| `schemas/call1-content.schema.json` | Section-first model response |
| `schemas/paper-content.schema.json` | Complete versioned handoff for Call 2 |
| `prompts/call1-content.md` | Editable first-call system prompt |
| `examples/input.json` | Synthetic case; its example.org URL is not a retrieval target |
| `examples/call1-input.json` | Matching synthetic paper evidence |
| `call1-output.example.json` | Hand-written educational version of that fictional paper |
| `examples/paper_content.json` | Complete matching handoff |

Schemas are self-contained Draft 2020-12 documents with local definitions. They do not fetch other schemas. The content schema is authoritative for the model payload; its embedded definition in the handoff must remain synchronized.

## How to read the output

1. Show `content.title`.
2. Use `content.sections` in order for the main narrative. `parent_id` connects subsections to their earlier parent.
3. Present `simple_explanation` as the accessible layer and make `paper_explanation` available for fuller detail. The renderer decides the exact controls for switching depth.
4. Keep useful intuition, connections, visuals, boundaries, and mathematical models alongside the relevant section.
5. Build the mind map from `concepts` and `relationships`; every concept's `section_id` gives the explanation destination.
6. Build the end-of-journey assessment from `learning_outcomes` and the sections that reference them. Preserve free navigation between the modes.

Call 1 supplies finished educational prose, not notes asking call 2 to write the introduction or discover the paper's conclusion.

## First-call assembly

Read `prompts/call1-content.md` as the system message. Supply text context matching `call1-input.schema.json` and actual labeled image attachments for image records. Caption-only records have no corresponding pixels. Include the full content schema as model-visible text. The runtime defaults to JSON-object mode; explicit `--response-format json_schema` also supplies that schema through the provider's structured response parameter. Both modes use the same local validation.

Source preparation retains broad evidence when it fits and gives relevant detail priority within limits. The user's focus determines output breadth as well as depth: an overview follows the paper, while a focused request teaches the selected topic with necessary context. The same schema supports both. Do not claim complete paper coverage for a focused explanation or when important sections were omitted or unreadable.

Validate the returned content, then copy it into the application-owned envelope. Input, evidence metadata, image paths, and attribution never come from model-generated file paths. Actual provider-mode and multimodal run evidence is recorded in the progress log separately from contract-fixture checks.

## Image handoff

Person 2 receives `paper_content.json` and available images in `assets/`. Resolve section `visual_ids` through `source.visuals`. The metadata records asset_path, MIME type, caption, locator, attribution, and what call 1 actually received.

Paths are relative to the handoff folder. Null path/MIME means no image asset is available, such as a caption-only fixture. A not_provided asset may be displayed later, but was not visual evidence available to call 1. Page images retain their page_image kind rather than becoming invented extracted figures.

A figure's source page is the one-based PDF page index, which may differ from printed numbering. Unknown locators remain null. The renderer embeds selected local image bytes and attribution in the final offline HTML; it must not leave an external asset-folder dependency.

## Validation and readiness

- Check schema shape and field types.
- Check unique section/outcome/concept IDs and globally unique mathematical variable/equation IDs.
- Parent sections must already occur in the ordered list. Outcome, connection, concept, and relationship targets must resolve.
- Every map concept must point to its explanatory section. Visual and evidence references must resolve to material actually supplied to call 1.
- Mathematical references and step dependencies must be consistent.
- Ordinary paper sections need evidence. Uncited background/analogies must remain explicitly identifiable as teaching additions.
- Essential missing information must be reported before treating the experience as complete.
- Before packaging, validate asset existence, actual MIME type, and paths within the handoff directory.

These checks cannot prove faithful simplification, good teaching, or accurate visual interpretation; those require review against the source and the audience's learning outcomes.

## Verification

Version 2.1 passed bounded local validation on 2026-10-03: all four schemas and all four fixtures validate. The example has seven sections, five outcomes, ten concepts, twelve relationships, seven source blocks, nine mathematical variables, and three equations. Hierarchy, references, calculation dependencies, embedded-schema equality, and complete handoff synchronization passed. Caption-only metadata has no invented image asset; ordinary limitations are not marked as essential missing information. Synthetic examples contain no live model response or actual paper image. These checks do not validate teaching quality or live provider behavior.
