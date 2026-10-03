# V2 document to first-call input

Status: implemented on 2026-10-03 in `playground_v2/source.py`. The V2 parser prepares text and actual local images for the first call. The normal architecture still has two model calls across the two team workstreams. See the [runtime guide](04-runtime.md) and progress log for commands and live verification.

## Implemented path

```text
case.json
  → retrieve the paper
  → extract text and preserve locations
  → collect relevant visual evidence
  → choose a bounded context for the requested focus
  → send instructions + schema + evidence + images to call 1
  → validate and save PaperContent
```

Retrieval and preparation are local code. They do not make a separate model call or summarize the paper before call 1.

## Retrieve and parse

1. Resolve the supplied URL to actual article content, not just an abstract landing page. Prefer readable full-text HTML when available; otherwise use the PDF. Keep the same paper version across sources, recording unresolved version ambiguity.
2. For HTML, use the existing Beautiful Soup approach to retain headings, paragraphs, captions, table structure, and available math annotations while removing navigation. Structured math such as a TeX annotation is preferable to flattening individual visual symbols. Readable tables should preserve rows, columns, and units.
3. For PDFs, start with text extraction through pypdf, preserving page boundaries. Reading order, equations, and table structure may be imperfect; extraction warnings must remain visible. Do not claim that extracted paragraphs reliably recover the original sections. [pypdf documents these limitations and does not perform OCR](https://pypdf.readthedocs.io/en/stable/user/extract-text.html).
4. Keep source blocks intact where possible. Each block receives an ID, text, type, and available section/page/equation locator. Remove obvious repeated headers and excess whitespace conservatively; do not silently rewrite equations.

For a short paper that fits the configured input budget, supply the full cleaned text. For a long paper, preserve representative evidence across the actual sections, then allocate extra context to the requested focus and its prerequisites, definitions, equations, and figures. Use headings and local reference/text matching. Record included and omitted material. This is an evidence-selection policy, not an instruction to explain every section. The focus determines output scope as well as depth: broad requests need the paper's main narrative; narrow requests need the selected topic and its necessary context. Disclose gaps that affect the requested explanation instead of inventing missing content.

## Figures, diagrams, and page images

DeepSeek V4.1 Flash accepts text and images according to the [OpenRouter model page](https://openrouter.ai/deepseek/deepseek-v4.1-flash). [OpenRouter image inputs](https://openrouter.ai/docs/guides/overview/multimodal/image-understanding) support images in the message alongside text. The runtime sends actual labeled image bytes together with the schema as model-visible text. Provider-side schema enforcement is an explicit option; both JSON modes use local contract validation. Documented capabilities and actual run outcomes remain distinct; see the progress log.

Handling:

| Source situation | Preparation for the same call 1 |
| --- | --- |
| Relevant HTML figure | Supply its actual image, caption, and surrounding explanation; preserve its source ID |
| PDF diagram, chart, or complex equation | Render the relevant page as an image; include extracted text alongside it |
| Reliable figure crop available | Future refinement; the current PDF implementation uses full pages |
| Decorative or unrelated image | Omit it from the model context and record selection |
| Small scanned paper or a known small set of relevant scanned pages | Supply readable rendered pages within the input/image budget |
| Long scan with no usable text or reliable page selection | Report the unsupported extraction/selection gap; do not pretend an arbitrary subset covers the focus |

For PDFs, page rendering is the implemented baseline. A figure may combine vector drawing commands, text, and embedded bitmap pieces, so extracting bitmap images alone is not a dependable representation of the whole diagram. The pinned local renderer is pypdfium2 4.30.0, whose [page-rendering API](https://pypdfium2.readthedocs.io/en/stable/python_api.html#pypdfium2.PdfPage.render) produces a bitmap. Installation and actual local PDF rasterization passed on the Windows development environment; the eventual assessment environment still needs its own setup check.

Bound the number, dimensions, and total bytes of supplied page images. Keep labels readable; image interpretation can still misread small text or dense charts. Use captions and extracted text together with pixels. Do not manufacture exact chart values or numerical grading targets from uncertain visual estimates. Unreadable required detail becomes `missing_information` in the content boundaries.

For a supplied model without image input, the provider request fails explicitly. The caller can deliberately prepare with `--max-images 0` when text and captions are sufficient; scanned papers require image coverage and fail without it. The runtime never silently switches models or drops declared attachments. All model calls use the supplied model ID.

The baseline proposal prepares images locally and sends them directly. OpenRouter also offers PDF parsing services that can involve separate OCR processing and charges; do not enable these implicitly. [OpenRouter PDF processing documentation](https://openrouter.ai/docs/guides/overview/multimodal/pdfs) describes those routes. They would be a separate infrastructure decision under the submission rules.

## What call 1 actually receives

The system message defines the content task and treats source documents as evidence, not instructions. The user message contains focus, audience, selected evidence, extraction warnings, and image attachments. The version 2.1 response has title, learning_outcomes, sections, concepts, and relationships. Ordered sections contain the main teaching narrative; the concept index supplies mind-map destinations.

Small illustrative text payload (not extracted evidence):

```json
{
  "focus": "Explain scaled dot-product attention",
  "audience": "Engineering undergraduate",
  "source_blocks": [
    {"id": "s1", "kind": "page", "text": "Extracted explanation and equation...", "locator": {"section": null, "page": 4, "equation": null, "figure": null}}
  ],
  "visuals": [
    {"id": "v1", "kind": "page_image", "locator": {"section": null, "page": 4, "equation": null, "figure": null}, "caption": null, "provided_as": "image_only"}
  ],
  "extraction_warnings": []
}
```

The API message also contains the actual image bytes as an `image_url` content part using a base64 data URL, with an adjacent text label identifying `v1`. Listing a filename or ID in JSON alone does not give the model an image. Keep raw bytes in local assets and request snapshots, rather than asking the model to reproduce them in its output.

Call 1 incorporates visual understanding into the relevant section's explanations, intuition, mathematics, and boundaries, citing `v1` as appropriate. Code saves what was supplied; model descriptions remain interpretations rather than verified measurements. Call 2 receives these structured interpretations, source records, and the available labeled image pixels to ground figure placement and descriptions. If the final HTML includes an original figure, the renderer embeds a local asset with attribution so the page remains offline.

## Runtime limits and review

- The accepted strategy is text plus selected images, with local reusable assets for Call 2 and the renderer.
- Defaults: 90,000 text characters, six images, maximum image edge 1,800 pixels, and 8,000,000 total image bytes. Selection and omissions are recorded. No additional model stage is introduced.
- HTML table spans are expanded into aligned columns, repeating original merged-cell values and preserving blank cells. Tables and captions remain source blocks, not invented figure assets. SVG-only figures currently retain captions without pixels.
- Focused tests cover extraction, real PDF rendering, scan limits, image budgets, transparency, table alignment, and metadata. A model's scientific interpretation still requires review against the supplied source.
