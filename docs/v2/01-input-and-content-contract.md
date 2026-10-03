# V2 learning-paper contract — version 2.1

Status: the user agreed to a section-first educational edition of the paper. Version 2.1 replaces the earlier eight-field knowledge inventory. Our scope is input/source preparation and call 1. Person 2 owns call 2 and the renderer. The implementation is documented in the [V2 runtime guide](04-runtime.md); verification evidence is recorded in the progress log.

## What the student should receive

For a paper overview, the main experience retains a recognizable paper structure: title, prerequisites, introduction, problem, solution or method sections, results, discussion, conclusion, and other relevant parts. For a focused request, select the sections that teach the requested concept, equation, method component, or result, together with the necessary prerequisites and context. Do not force unrelated paper sections or invent results. Identify added prerequisite explanations as teaching additions.

Each section provides accessible teaching content alongside a faithful, more detailed explanation. Intuition, reasoning, connections, figures, and mathematics support that section. The mind map links important ideas back to their explanations. Assessment comes at the end of the recommended learning journey; free navigation remains available.

The focus controls both scope and depth. A broad request covers the paper's story; a narrow request gets a focused explanation with sufficient context to remain faithful. Learning outcomes and the concept map follow that same scope. The audience controls language and prerequisite support. This clarification supersedes the earlier rule that focus could affect depth only. No additional mandatory input field or model call is introduced.

## Input and evidence

The external input remains three required strings: `source_url`, `focus`, and `audience`. The model ID is a CLI argument; the API key is an environment variable. Extra input fields are ignored by the adapter, with a names-only warning, and are not copied into the normalized handoff.

Call 1 receives `focus`, `audience`, `source_blocks`, `visuals`, and `extraction_warnings`, plus separately labeled image attachments and the response schema. Source blocks preserve text and available section/page/equation/figure locators. Preparation retains broad evidence when affordable and prioritizes relevant detail; providing whole-paper context does not require a whole-paper output. The model selects the teaching scope from the user's request. See [document ingestion](02-document-ingestion.md).

Code owns evidence IDs, source metadata, asset paths, and the record of what the model actually received. Source text and images are evidence, not instructions.

## The five content fields

| Field | Purpose |
| --- | --- |
| `title` | Title of the educational paper experience |
| `learning_outcomes` | Observable understand, apply, and analyze goals |
| `sections` | The ordered, finished learning narrative; this is the main content |
| `concepts` | A compact index of important ideas with a destination section for each |
| `relationships` | Meaningful labeled links between those concepts |

The concept index supports the map and navigation. Full explanations belong in sections, rather than being duplicated in another concept dictionary.

## Each learning section

| Field | Meaning |
| --- | --- |
| `id`, `title`, `kind` | Stable destination, readable heading, and semantic section role |
| `parent_id` | An earlier parent section, or null for a top-level section |
| `paper_explanation` | Faithful detailed explanation of that part of the paper; identify any added prerequisite/background material |
| `simple_explanation` | The same meaning in accessible, finished prose for the student |
| `intuition` | Optional explanatory reasoning or analogy, labeled by its basis; null when it adds no value |
| `connections` | Links to other sections or related background ideas, explaining the connection |
| `learning_outcome_ids` | Outcomes this section teaches |
| `visual_ids` | Relevant source figures/page images/captions to accompany the explanation |
| `source_refs` | Evidence supporting this section |
| `boundaries` | Assumptions, simplifications, limitations, misconceptions, or essential missing information in context |
| `mathematical_model` | Optional variables, equations, calculation steps, and constraints when this section needs them |

Section kinds are prerequisites, introduction, problem, background, method, results, discussion, conclusion, and other. They are semantic labels, not mandatory quotas or UI components. Use readable source-aligned titles. Array order defines the reading sequence; an earlier parent allows method subsections without recursively nested JSON.

Intuition and connections are teaching content. A connection has a topic, explanation, basis, source references, and `section_id`; the target is null for an outside/background idea. Both simple and detailed explanations must preserve the same claims and qualifications. A source's reported rationale and our explanatory interpretation must remain distinguishable.

A section can include a small qualitative example or analogy. It must not invent paper findings, exact chart values, or numerical answer keys. Call 2 owns the concrete interactive scenario and the questions.

## Mathematics, evidence, and teaching additions

The optional mathematical model retains the agreed variable/equation/step/constraint shapes. Equations reference variable IDs; calculation steps identify inputs, outputs, and equations. Domains include relevant dimensions and units. Constraints preserve conventions such as normalization axes and zero handling. Variable and equation IDs are unique across the content, including across different sections.

Items with `basis` use one of:

- `source_supported`: directly supported by supplied evidence.
- `derived`: follows from cited evidence; explain the derivation when needed.
- `simplified`: an educational adaptation; state what it changes.
- `background`: clearly identified standard prerequisite or related knowledge.
- `analogy`: clearly identified teaching comparison; describe its limits where needed.

Source-supported, derived, and simplified items require evidence references. Background and analogy items may have none; these labels do not authorize inventing paper claims or external study results. A missing-information boundary may also have no reference when the evidence itself is absent. These labels describe the model's interpretation, not independent verification.

An essential source gap uses `missing_information`; preserve the output for inspection and resolve the gap before designing a complete experience. Incidental omissions use limitation. Empty math is acceptable where the section does not need math; omit the optional field rather than adding decorative equations.

## Map and assessment connections

Each concept contains `id`, `name`, `summary`, and `section_id`. Its destination must contain the corresponding explanation. The map represents the important ideas within the requested scope: the wider paper for an overview, or the selected topic and its necessary context for a focused request. Relationships connect concept IDs with meaningful labels, basis, and evidence references.

Learning outcomes contain `id`, `level`, and `description`. Sections reference these IDs. Call 2 uses them to design the assessment and revisit links. Call 1 does not write quiz questions, grading rules, UI layouts, or executable code.

## Handoff to Call 2

The application produces `paper_content.json` with `schema_version: "2.1"`, normalized `input`, code-owned `source`, and the model-authored `content`. Available relevant images live in an accompanying `assets/` folder.

The source object retains selected text evidence, visual metadata, and warnings. Visual records use stable IDs, captions, locators, relative asset paths, MIME types, and attribution. `provided_as` records image_and_caption, image_only, or caption_only. The final manifest may additionally retain not_provided assets for display; call 1 cannot cite those assets as inspected evidence.

Call 2 preserves the agreed section destinations and narrative meaning while designing presentation, interactions, mind-map layout, and assessment. The renderer resolves selected visual IDs and embeds the image bytes in the final offline HTML.

The four [JSON Schemas and example files](03-schema-and-prompt.md) define the exact format. The previous 2.0 content shape is incompatible with 2.1. The current Call 2 and renderer consume 2.1 directly; the earlier person 2 workstream is now integrated under one owner.
