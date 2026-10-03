"""Deterministic, self-contained Research lab HTML renderer.

The model supplies content and a validated experience specification, never code.
All browser behaviour is owned by the versioned assets alongside this module.
"""
from __future__ import annotations

import base64
import hashlib
import html
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from .validation import ValidationError, validate_handoff

ASSETS = Path(__file__).with_name("assets")


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def _url(value: str) -> str:
    return esc(value) if urlsplit(value).scheme in {"http", "https"} else "#"


def _paragraphs(value: str) -> str:
    return "".join("<p>" + esc(p) + "</p>" for p in value.split("\n") if p.strip())


def _refs(ids: list[str]) -> str:
    return ""  # Provenance remains in the JSON, outside the learner reading flow.



def _math(latex: str) -> str:
    """Small, bounded native MathML adapter; unsupported TeX stays explicit."""
    tokens = re.findall(r"\\[a-zA-Z]+|\\.|[{}_^]|[^{}_^\\]", latex)
    index = 0
    symbols = {"alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "theta": "θ", "lambda": "λ", "mu": "μ", "sigma": "σ", "tau": "τ", "phi": "φ", "omega": "ω", "pi": "π", "sum": "∑", "prod": "∏", "infty": "∞", "times": "×", "cdot": "·", "leq": "≤", "geq": "≥", "neq": "≠", "approx": "≈", "in": "∈", "rightarrow": "→", "mathbb": "", "quad": " ", "qquad": " ", "log": "log", "ln": "ln", "exp": "exp", "sin": "sin", "cos": "cos", "tan": "tan", "max": "max", "min": "min", "cdots": "⋯", "ldots": "…", "partial": "∂", "nabla": "∇", "le": "≤", "ge": "≥"}
    def atom(depth: int = 0) -> str:
        nonlocal index
        if index >= len(tokens) or depth > 32:
            raise ValueError("Incomplete or deeply nested equation")
        token = tokens[index]
        index += 1
        if token == "{":
            return '<mrow>' + group(depth + 1, True) + '</mrow>'
        if token == r"\frac":
            return '<mfrac>' + atom(depth + 1) + atom(depth + 1) + '</mfrac>'
        if token == r"\sqrt":
            return '<msqrt>' + atom(depth + 1) + '</msqrt>'
        if token in {r"\mathrm", r"\mathbf", r"\operatorname", r"\text", r"\mathit", r"\mathcal"}:
            return '<mstyle mathvariant="normal">' + atom(depth + 1) + '</mstyle>'
        if token in {r"\left", r"\right", r"\bigl", r"\bigr", r"\Bigl", r"\Bigr", r"\big", r"\Big", r"\limits", r"\!", r"\,", r"\;", r"\:"}:
            return ''
        if token.startswith("\\"):
            if token[1:] not in symbols:
                raise ValueError("Unsupported TeX command")
            token = symbols[token[1:]]
        tag = "mn" if token.isdigit() else ("mi" if token.isalpha() else "mo")
        return '<' + tag + '>' + esc(token) + '</' + tag + '>'
    def group(depth: int, closing: bool = False) -> str:
        nonlocal index
        parts = []
        while index < len(tokens):
            if tokens[index] == "}":
                if not closing:
                    raise ValueError("Unexpected close brace")
                index += 1
                return ''.join(parts)
            if tokens[index] in {"_", "^"}:
                if not parts:
                    raise ValueError("Missing script base")
                marker = tokens[index]
                index += 1
                base = parts.pop()
                script = atom(depth + 1)
                tag = "msub" if marker == "_" else "msup"
                parts.append('<' + tag + '>' + base + script + '</' + tag + '>')
            else:
                parts.append(atom(depth + 1))
        if closing:
            raise ValueError("Unclosed equation")
        return ''.join(parts)
    try:
        if len(latex) > 6000:
            raise ValueError("Equation too long")
        markup = group(0)
        return '<math display="block" aria-label="' + esc(latex) + '"><mrow>' + markup + '</mrow></math>'
    except (ValueError, RecursionError):
        return '<div class="equation-fallback"><span class="muted">Equation notation (TeX)</span><code>' + esc(latex) + '</code></div>'


def _mathematics(model: dict) -> str:
    result = '<div class="technical prose-block"><h3>The calculation</h3>'
    for eq in model.get("equations", []):
        result += '<div class="equation" id="' + esc(eq["id"]) + '">' + _math(eq["latex"]) + _paragraphs(eq["explanation"]) + _refs(eq.get("source_refs", [])) + '</div>'
    result += '<dl class="variables">'
    for var in model.get("variables", []):
        result += '<div><dt>' + esc(var["notation"]) + '</dt><dd>' + esc(var["meaning"]) + '<small>' + esc(var["domain"]) + '</small></dd></div>'
    result += '</dl><ol class="steps">' + ''.join('<li>' + esc(step["description"]) + '</li>' for step in model.get("steps", [])) + '</ol>'
    for constraint in model.get("constraints", []):
        result += '<p class="qualification">' + esc(constraint["description"]) + _refs(constraint.get("source_refs", [])) + '</p>'
    return result + '</div>'


def render(handoff: dict, experience: dict, output_dir: Path | str, *, source_dir: Path | str | None = None) -> dict:
    """Validate inputs and write index.html, embedding all assets for file:// use."""
    from .experience import validate_experience, compile_experiment
    output_dir = Path(output_dir)
    source_dir = Path(source_dir) if source_dir is not None else output_dir
    validate_handoff(handoff, source_dir)
    validate_experience(experience, handoff)
    content, source = handoff["content"], handoff["source"]
    visuals = {v["id"]: v for v in source["visuals"]}
    images = {}
    for visual in source["visuals"]:
        if visual["kind"] == "page_image" or visual["provided_as"] not in {"image_and_caption", "image_only"}:
            continue
        path = (source_dir / visual["asset_path"]).resolve()
        if not path.is_relative_to(source_dir.resolve()) or path.stat().st_size > 8_000_000:
            raise ValidationError("Source image is outside the handoff or exceeds 8 MB")
        images[visual["id"]] = "data:" + visual["mime_type"] + ";base64," + base64.b64encode(path.read_bytes()).decode("ascii")
    settings = {s["section_id"]: s for s in experience["sections"]}
    experiments = {e["id"]: e for e in experience["experiments"]}
    def figure(visual_id: str, presentation: dict | None = None) -> str:
        v = visuals[visual_id]
        if v["kind"] == "page_image":
            return ""  # Full-page evidence is never an extracted illustration.
        presentation = presentation or {}
        caption = presentation.get("alt") or v.get("caption") or "Original source image; no caption was extracted."
        body = '<figure class="source-figure" id="figure-' + esc(visual_id) + '"><div class="eyebrow">Original paper figure · ' + esc(visual_id) + '</div>'
        if visual_id in images:
            body += '<div class="image-mat"><img loading="lazy" src="' + images[visual_id] + '" alt="' + esc(presentation.get("alt") or caption) + '"></div><button type="button" class="enlarge" aria-expanded="false">Enlarge figure</button>'
        else:
            availability = "Caption available; the original image was not available in the extracted source." if v.get("caption") else "This source visual was referenced, but its image and caption were not available in the extracted source."
            body += '<p class="qualification">' + availability + '</p>'
        if presentation.get("explanation"):
            body += _paragraphs(presentation["explanation"])
        locator = ', '.join(str(value) for value in v.get("locator", {}).values() if value is not None)
        return body + '<figcaption>' + esc(caption) + '<span>' + esc(locator) + '</span><span>' + esc(v.get("attribution", source["title"])) + '</span><a href="' + _url(v.get("source_url") or source["resolved_url"]) + '" target="_blank" rel="noopener noreferrer">View original source ↗</a></figcaption></figure>'
    article = ''
    seen_visuals = set()
    for index, section in enumerate(content["sections"], 1):
        sid = section["id"]
        setting = settings.get(sid, {})
        article += '<section class="paper-section" id="' + esc(sid) + '" tabindex="-1"><div class="eyebrow">' + f'{index:02d}' + ' / ' + esc(section["kind"].replace('_', ' ')) + '</div><h2>' + esc(section["title"]) + '</h2>'
        article += '<div class="simple-explanation">' + _paragraphs(section["simple_explanation"]) + '</div>'
        article += '<div class="technical prose-block"><h3>In more detail</h3>' + _paragraphs(section["paper_explanation"]) + _refs(section["source_refs"]) + '</div>'
        if section.get("intuition"):
            intuition = section["intuition"]
            article += '<aside class="intuition"><h3>Build an intuition <small>' + esc(intuition["basis"].replace('_', ' ')) + '</small></h3>' + _paragraphs(intuition["explanation"]) + _refs(intuition.get("source_refs", [])) + '</aside>'
        presentations = {f["visual_id"]: f for f in setting.get("figures", [])}
        for vid in dict.fromkeys([*section.get("visual_ids", []), *presentations]):
            if visuals[vid]["kind"] == "page_image":
                continue
            if vid in seen_visuals:
                article += '<p><a data-read="true" href="#figure-' + esc(vid) + '">Revisit paper figure ' + esc(vid) + ' ↑</a></p>'
            else:
                article += figure(vid, presentations.get(vid))
                seen_visuals.add(vid)
        if section.get("mathematical_model"):
            article += _mathematics(section["mathematical_model"])
        for eid in setting.get("experiment_ids", []):
            exp = experiments[eid]
            article += '<div class="inline-experiment" id="inline-' + esc(eid) + '" data-inline-experiment="' + esc(eid) + '"></div>'
        if section.get("connections"):
            article += '<div class="connections prose-block"><h3>Connect this idea</h3>'
            for connection in section["connections"]:
                link = '<a data-read="true" href="#' + esc(connection["section_id"]) + '">' + esc(connection["topic"]) + '</a>' if connection.get("section_id") else esc(connection["topic"])
                article += '<p><strong>' + link + '</strong> · ' + esc(connection["explanation"]) + _refs(connection.get("source_refs", [])) + '</p>'
            article += '</div>'
        if section.get("boundaries"):
            article += '<div class="boundaries prose-block"><h3>Where this applies</h3>'
            for boundary in section["boundaries"]:
                article += '<p><span class="tag">' + esc(boundary["kind"].replace('_', ' ')) + '</span> ' + esc(boundary["description"]) + _refs(boundary.get("source_refs", [])) + '</p>'
            article += '</div>'
        article += '</section>'
    references = ''
    plans = {e["id"]: compile_experiment(e)["plan"] for e in experience["experiments"]}
    payload = {"handoff": handoff, "experience": experience, "plans": plans}
    data = _json(payload)
    styles = (ASSETS / 'research-lab.css').read_text(encoding='utf-8') + '\n' + (ASSETS / 'diagram-family.css').read_text(encoding='utf-8')
    script = (ASSETS / 'math-engine.js').read_text(encoding='utf-8') + '\n' + (ASSETS / 'diagram-family.js').read_text(encoding='utf-8') + '\n' + (ASSETS / 'research-lab.js').read_text(encoding='utf-8')
    if '</script' in script.lower() or '</style' in styles.lower():
        raise ValidationError("Trusted renderer assets contain an unsafe closing delimiter")
    script_hash = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    style_hash = base64.b64encode(hashlib.sha256(styles.encode()).digest()).decode()
    outline = ''.join('<a href="#' + esc(s["id"]) + '" data-read="true">' + esc(s["title"]) + '</a>' for s in content["sections"])
    outcomes = ''.join('<li><span class="tag">' + esc(o["level"]) + '</span> ' + esc(o["description"]) + '</li>' for o in content["learning_outcomes"])
    rail_context = '<div class="rail-context"><div class="eyebrow">The paper</div><h2>' + esc(source["title"]) + '</h2><div class="eyebrow">Your focus</div><p>' + esc(handoff["input"]["focus"]) + '</p></div>'
    page = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src data:; script-src \'sha256-' + script_hash + '\'; style-src \'sha256-' + style_hash + '\'; connect-src \'none\'; base-uri \'none\'; form-action \'none\'; font-src \'none\'"><title>' + esc(content["title"]) + ' · Paper / Playground</title><style>' + styles + '</style></head><body>'
    page += '<a class="skip" href="#main">Skip to content</a><header class="topbar"><a class="brand" href="#top" data-read="true">paper <span>/</span> playground</a><span class="edition">Research lab · offline guide</span><button id="theme" type="button" aria-label="Toggle light and dark appearance">◐ Appearance</button></header><nav class="mode-nav" aria-label="Learning modes">' + ''.join('<button type="button" data-mode="' + mode + '" aria-pressed="' + str(mode == 'reading').lower() + '">' + label + '</button>' for mode, label in [('reading', 'Read'), ('map', 'Concept map'), ('experiment', 'Experiment'), ('assessment', 'Assessment')]) + '</nav>'
    page += '<div class="layout"><aside class="outline"><div class="outline-inner">' + rail_context + '<button type="button" class="outline-toggle" aria-expanded="false" aria-controls="section-outline">In this guide +</button><div class="eyebrow outline-label">In this guide</div><nav id="section-outline" aria-label="Section outline">' + outline + '</nav></div></aside><main id="main" tabindex="-1"><div id="reading" class="mode-panel"><header id="top" class="hero"><div class="eyebrow">Read · explore · connect</div><p class="paper-identity">' + esc(source["title"]) + '</p><h1>' + esc(content["title"]) + '</h1>' + _paragraphs(experience["introduction"]) + '<div class="request-context"><p><strong>Focus:</strong> ' + esc(handoff["input"]["focus"]) + '</p><p><strong>Audience:</strong> ' + esc(handoff["input"]["audience"]) + '</p></div><div class="outcomes"><h2>What you will learn</h2><ul>' + outcomes + '</ul></div></header>' + article + references + '</div>'
    page += '<section id="map" class="mode-panel" hidden><div class="eyebrow">See the connections</div><h1>One paper, connected ideas.</h1><p>Select a concept, follow a relationship, then return to its explanation.</p><div id="concept-map" class="map-visual"></div><div id="concept-buttons" class="concept-picker"></div><div id="concept-detail" class="concept-destination" aria-live="polite"></div><div id="relationship-list" hidden></div></section>'
    page += '<section id="experiment" class="mode-panel" hidden><div class="eyebrow">Learn by changing something</div><h1>The experiment bench.</h1><p>These are bounded teaching models. Their assumptions stay visible beside the controls.</p><div id="experiment-tabs" class="experiment-tabs" aria-label="Choose experiment"></div><div id="experiment-panels"></div></section>'
    page += '<section id="assessment" class="mode-panel" hidden><div class="eyebrow">From understanding to prediction</div><h1>Test your understanding.</h1><p>Answer the full set, then submit to see your result and what to revisit. You can explore the other modes at any time.</p><form id="quiz" novalidate><div id="questions"></div><p id="quiz-error" role="alert" hidden></p><button type="submit" class="primary">Submit assessment</button></form><div id="quiz-results" tabindex="-1" hidden></div></section></main></div><footer>Paper / Playground · Original evidence, simplified explanations, and labeled teaching experiments. <a href="' + _url(source["resolved_url"]) + '" target="_blank" rel="noopener noreferrer">Original paper ↗</a></footer><noscript><p class="qualification">Reading works without JavaScript. Enable JavaScript locally for experiments, the concept map and assessment.</p></noscript><script type="application/json" id="lesson-data">' + data + '</script><script>' + script + '</script></body></html>'
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / 'index.html'
    destination.write_text(page, encoding='utf-8')
    return {"status": "complete", "path": str(destination), "bytes": destination.stat().st_size, "sections": len(content["sections"]), "experiments": len(experience["experiments"]), "questions": len(experience["questions"]), "embedded_images": len(images), "runtime_network_dependencies": 0, "renderer": "research-lab-native-v2", "html_sha256": hashlib.sha256(page.encode("utf-8")).hexdigest(), "renderer_assets_sha256": {name: hashlib.sha256((ASSETS / name).read_bytes()).hexdigest() for name in ("research-lab.css", "research-lab.js", "diagram-family.css", "diagram-family.js", "math-engine.js")}, "excluded_page_images": sum(v["kind"] == "page_image" for v in source["visuals"])}
