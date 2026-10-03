# Small Transmit influence on Research lab

User direction, 2026-10-03: "adapt a little bit to transmit but not a lot." This selects a restrained influence on the existing Research lab design. Original reference: https://transmit.tailwindui.com/ . The companion preview is `research-lab-transmit.html` in this directory. It reuses our existing attention calculation and diagrams; its changes are presentation only.

## Apply these changes

1. On desktop, give the reading page a narrow, quiet context rail (about 190–220px, at most 22% of available width). Include the paper title, available author/year metadata, the actual requested focus, and the existing section outline. Keep it in normal page flow with a sticky inner block where space permits. Keep a single document scrollbar.
2. Let the reading column dominate. Separate successive explanations with space and fine rules. Keep diagrams beside their explanation only when both have enough room; stack them at smaller widths. Use roughly 32–40px section spacing and 24–30px between text and figures.
3. Preserve our Research lab palette: pale neutral surfaces, slate text and header, teal interaction accents, and consistent query/key/value colors. Retain the current fonts, computation engine, controls, graph family, paper figures and continuous scrolling. Transmit is the reference for the rail and spacing, not a replacement theme.
4. Collapse the rail to the existing compact wrapping outline below roughly 860px; retain the paper title and requested focus in the main header. No miniature sidebar, clipped labels, or separate scrolling pane on mobile.
5. Populate the outline from the selected request scope. For a focused question, show its relevant sections and necessary prerequisites. Do not fill the rail with unrelated paper chapters.

Do not introduce the podcast cover, audio controls, pink branding, decorative waveform, large 40% split panel, or episode/date metadata. No new framework or external runtime is needed. Implement in the shared renderer rather than editing generated output. Reuse the existing outline instead of adding a duplicate navigation system.

## Correct the concept-map interaction

The user reported two separate problems in our earlier preview: narrow widths substituted cards for the graph, and clicking a node replaced the graph with its immediate neighborhood (sometimes only two nodes). They found both broken.

The requested default is now a stable full map of the current request's concepts. Selecting any node must keep the same node set and positions, highlight its incident relationships, and update the detail area. Do not hide unrelated nodes or rerun layout on selection. Recompute layout only when the dataset or available width changes. If a neighborhood view is retained, make it a separately named, explicit mode; it must not be the default node-click behavior. Keep real nodes and edges visible on smaller screens.

The updated `research-diagram-family.html` demonstrates the stable-selection behavior with 12 concepts. Its example-specific coordinates are not a general layout algorithm. Preserve evidence-backed edge directions and use a proper generic layout in production; route edges outside intermediate nodes. Do not silently alter relationship semantics to improve a drawing.

## Remove white accordion boxes

Explicit user correction, based on the screenshot of "Your learning scope" and "What you will learn": remove the white bordered accordion panels and the requirement to press headings to reveal their content.

- Render the requested focus as a concise, always-visible line near the lesson title. Render outcomes as a short, ordinary list in the reading flow. Audience context can be a quiet metadata line if it helps the learner.
- Render explanations, equations and variable guides, relevant assumptions, concept connections, and paper figures directly in the continuous page. Use headings, whitespace and occasional subtle rules instead of repeated white cards.
- Remove disclosure triangles and clickable `summary` headings from reading content. Adding `open` to existing `details` is not enough: remove the accordion interaction and its boxed styling. Do not replace it with another "read more" gate.
- Place large advanced input editors later in the page, after the first useful explanation, rather than hiding the explanation or overwhelming the opening screen. Keep relevant direct controls beside their graph.
- Reserve bounded surfaces for actual diagrams, controls or the concept canvas. Ordinary prose, learning scope and outcomes should not each become a separate card.
- Apply this in the shared renderer and styles, then regenerate the output. The screenshot is a concrete regression case: scope and outcomes must be visible immediately, without accordion buttons or boxed disclosure panels.

This supersedes any earlier handoff recommendation to hide learning content or paper figures inside progressive-disclosure panels. Clarity should come from concise content and hierarchy, not repeated click-to-open containers.

## n8n-style concept canvas

Additional user direction: "also the mindmap make it close to n8n design". Use `research-concept-canvas.html` as the new visual reference for the map, replacing the older card-like map presentation. Reference: https://docs.n8n.io/build/understand-workflows/workflow-components/work-with-nodes .

Use a restrained dotted canvas, compact square nodes with meaningful symbols and labels, circular input/output connection ports, curved connectors, a clear selected outline, a Find a concept selector, fit/zoom controls, background panning, and a readable detail inspector. Keep the research-lab neutral/teal palette. Connections represent paper relationships, not executable workflow steps; do not invent run buttons, execution status, integrations or credentials. Retain the full graph and stable coordinates on selection. The reference is a small offline prototype, not a general automatic layout engine. For small screens, fit is an overview; users can zoom or select a concept to read its full label and details. Production should support touch panning, keyboard navigation, focus visibility, and connector routing around intervening nodes.

The previous neighborhood-on-click and narrow-screen card substitution are superseded by this requirement.

## Verification

- At 1024px and a larger desktop width, the rail remains narrow and the diagrams are legible; at 736/390/320px the outline reflows without document overflow.
- Query direction, temperature and matrix changes still update every linked diagram. Navigation never resets the experiment. Original paper figures remain available with captions, alt text and enlargement.
- Select every concept in turn: the full node count and every node position remain unchanged, while selection/details update. Include keyboard activation and narrow-width graph checks.
- The exported learner page still works offline. No downloaded fonts, template runtime or new network requests are introduced.

Preview status: a visual reference based on the existing 2D teaching example. It is not proof of integration into the production renderer. Apply these incremental changes within the current implementation work rather than restarting it.

Local preview verification: offline Edge checks passed at 1024, 736, 390 and 320px. The reading preview has zero `details`/`summary` elements; linked geometry, weights, temperature, input validation and embedded paper image checks pass. The concept canvas retains all 12 nodes and their coordinates across every selection; native keyboard activation and fit/zoom controls pass. These checks cover the reference previews, not the production page. Production must still verify touch panning and general graph layouts.
