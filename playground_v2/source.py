"""Prepare paper-wide text and bounded visual evidence for V2's first call.

This module performs no model calls. Public downloads reuse V1's checked,
DNS-pinned fetcher; V1 extraction and focus-only selection are not reused.
"""
from __future__ import annotations

from collections import Counter, OrderedDict
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import re
import time
from urllib.parse import urljoin
import warnings as python_warnings

from bs4 import BeautifulSoup
from PIL import Image, ImageOps
from pypdf import PdfReader

from .retrieval import SourceError, _arxiv_identity, _fetch


MAX_EXTRACTED_CHARS = 1_200_000
MAX_PDF_PAGES = 160
MAX_IMAGE_EDGE = 1800
MAX_IMAGE_PIXELS = 40_000_000
MAX_VISUAL_RECORDS = 64


def _deadline(deadline):
    if time.monotonic() >= deadline:
        raise SourceError("Source preparation exceeded its time allowance")


def _clean(text):
    return re.sub(r"\s+", " ", text).strip()


def _locator(section=None, page=None, equation=None, figure=None):
    return {"section": section or None, "page": page, "equation": equation or None, "figure": figure or None}


def _block(blocks, kind, text, locator):
    text = text.strip()
    if text:
        blocks.append({"id": f"s{len(blocks) + 1:04d}", "kind": kind,
                       "text": text, "locator": deepcopy(locator)})


def _score(text, focus):
    stop = {"paper", "explain", "using", "with", "this", "that", "their", "about", "show", "understand", "section"}
    terms = {word.rstrip("s") for word in re.findall(r"[a-z][a-z-]{2,}", focus.lower()) if word not in stop}
    words = {word.rstrip("s") for word in re.findall(r"[a-z][a-z-]{2,}", text.lower())}
    return len(terms & words)


def _coverage_key(block):
    loc = block["locator"]
    return loc["section"] or (f"PDF page {loc['page']}" if loc["page"] else "Unlocated text")


def _select_text(blocks, focus, budget):
    """Preserve whole small papers; allocate coverage before focused detail."""
    total = sum(len(block["text"]) for block in blocks)
    if total <= budget:
        return list(blocks), [f"All {len(blocks)} extracted text blocks ({total} characters) supplied; text extraction limitations still apply."]
    groups = OrderedDict()
    for index, block in enumerate(blocks):
        groups.setdefault(_coverage_key(block), []).append(index)
    selected, used = set(), 0

    def add(index, limit=budget):
        nonlocal used
        size = len(blocks[index]["text"])
        if index not in selected and used + size <= limit:
            selected.add(index)
            used += size
            return True
        return index in selected

    # One substantive representative from each section/page comes before extra
    # focus detail. Reserve half the context for that paper-wide coverage.
    coverage_limit = max(1, budget // 2)
    for indices in groups.values():
        content = [i for i in indices if blocks[i]["kind"] != "heading"]
        if content:
            # Prefer a short coherent paragraph if a giant table would consume
            # all the space. Never cut a block halfway through an equation.
            representative = min(content[:3], key=lambda i: len(blocks[i]["text"]))
            add(representative, coverage_limit)
    # Cover both ends when a very long PDF has more pages than fit the budget.
    for indices in (next(iter(groups.values())), next(reversed(groups.values()))):
        content = [i for i in indices if blocks[i]["kind"] != "heading"]
        if content:
            add(content[0])
    ranked = sorted(range(len(blocks)), key=lambda i: (-_score(blocks[i]["text"] + " " + (_coverage_key(blocks[i])), focus), i))
    for index in ranked:
        if _score(blocks[index]["text"] + " " + _coverage_key(blocks[index]), focus) == 0:
            break
        if add(index):
            for neighbor in (index - 1, index + 1):
                if 0 <= neighbor < len(blocks) and _coverage_key(blocks[neighbor]) == _coverage_key(blocks[index]):
                    add(neighbor)
    # Attach headings to the retained section content, then use remaining room
    # for source-order context without discarding previously selected coverage.
    represented = {_coverage_key(blocks[i]) for i in selected}
    for index, block in enumerate(blocks):
        if block["kind"] == "heading" and _coverage_key(block) in represented:
            add(index)
    for index in range(len(blocks)):
        add(index)
    retained = [blocks[i] for i in sorted(selected)]
    missing = [name for name, indices in groups.items() if not any(i in selected and blocks[i]["kind"] != "heading" for i in indices)]
    notes = [f"Context budget selected {len(retained)} of {len(blocks)} blocks ({used}/{total} characters), preserving section/page coverage before extra focus detail; omitted material was not supplied."]
    if missing:
        notes.append("No substantive text could be supplied for these source sections/pages: " + "; ".join(missing[:30]) + ("; additional sections omitted" if len(missing) > 30 else "") + ". Do not reconstruct their content.")
    oversize = [block["id"] for block in blocks if len(block["text"]) > budget]
    if oversize:
        notes.append("Oversized intact blocks omitted rather than cutting equations/tables: " + ", ".join(oversize[:20]))
    return retained, notes


def _table_text(table):
    """Expand genuine merged cells so headers and data keep their columns."""
    rows = [row for row in table.find_all("tr") if row.find_parent("table") is table]
    if len(rows) > 1000:
        return "", ["A table with more than 1000 rows was omitted; its values were not supplied."]
    cells, notes, width = {}, [], 0
    for row_index, row in enumerate(rows):
        column = 0
        for cell in row.find_all(["th", "td"], recursive=False):
            while (row_index, column) in cells:
                column += 1
            try:
                row_span = int(cell.get("rowspan", 1))
                col_span = int(cell.get("colspan", 1))
            except (TypeError, ValueError):
                return "", ["A table with malformed row/column spans was omitted; column assignments could not be trusted."]
            if row_span == 0:
                # HTML defines zero as spanning the remaining rows of its group.
                group = row.parent
                row_span = sum(other.parent is group for other in rows[row_index:])
            if not 1 <= row_span <= 100 or not 1 <= col_span <= 100 or column + col_span > 100:
                return "", ["A table exceeding the 100-column/100-span limit was omitted; its values were not supplied."]
            text = _clean(cell.get_text(" "))
            for target_row in range(row_index, min(len(rows), row_index + row_span)):
                for target_column in range(column, column + col_span):
                    if (target_row, target_column) in cells:
                        return "", ["A table with overlapping merged cells was omitted; column assignments could not be trusted."]
                    cells[target_row, target_column] = text
            column += col_span
            width = max(width, column)
    # Column padding is bounded; original values are never truncated. Repeated
    # values in merged cells are the source cell itself, not inferred defaults.
    widths = [min(120, max((len(cells.get((row, col), "")) for row in range(len(rows))), default=0)) for col in range(width)]
    lines, total = [], 0
    for row in range(len(rows)):
        values = [cells.get((row, col), "") for col in range(width)]
        estimate = sum(max(len(value), widths[col]) for col, value in enumerate(values)) + 3 * max(0, width - 1)
        if total + estimate > MAX_EXTRACTED_CHARS:
            notes.append("Table expansion reached the text limit; later table rows were not supplied.")
            break
        lines.append(" | ".join(value.ljust(widths[col]) for col, value in enumerate(values)).rstrip())
        total += estimate + 1
    return "\n".join(lines), notes


def _html(body, resolved):
    soup = BeautifulSoup(body, "html.parser")
    title_meta = soup.find("meta", attrs={"name": "citation_title"}) or soup.find("meta", attrs={"property": "og:title"})
    title = _clean(title_meta.get("content", "")) if title_meta else (_clean(soup.title.get_text(" ")) if soup.title else None)
    pdf_meta = soup.find("meta", attrs={"name": "citation_pdf_url"})
    pdf_url = urljoin(resolved, pdf_meta.get("content")) if pdf_meta and pdf_meta.get("content") else None
    for node in soup.select("script, style, nav, footer, noscript, form, iframe, button, .ltx_page_navbar, .ltx_page_footer"):
        node.decompose()
    for node in soup.find_all("math"):
        annotation = node.find("annotation", attrs={"encoding": "application/x-tex"})
        latex = node.get("alttext") or (annotation.get_text() if annotation else None)
        if latex:
            node.replace_with(" " + latex + " ")
    root = soup.find("article") or soup.find("main") or soup.body or soup
    blocks, figures, section, total = [], [], None, 0
    notes = ["HTML text, readable table rows, and available TeX math annotations extracted. Unannotated mathematics and complex table spans may require visual review."]
    consumed = set()
    candidates = root.select("h1,h2,h3,h4,h5,h6,p,li,table,pre,figcaption,.ltx_equation,.ltx_equationgroup,.ltx_caption")
    for node in candidates:
        if any(id(parent) in consumed for parent in node.parents):
            continue
        consumed.add(id(node))
        heading = bool(re.fullmatch(r"h[1-6]", node.name or ""))
        classes = node.get("class", [])
        equation = node.select_one(".ltx_tag_equation")
        equation_label = _clean(equation.get_text(" ")) if equation else None
        is_equation = equation_label is not None or any("equation" in cls for cls in classes)
        is_caption = node.name == "figcaption" or "ltx_caption" in classes
        if node.name == "table" and not is_equation:
            text, table_notes = _table_text(node)
            notes.extend(table_notes)
        elif node.name == "pre":
            text = node.get_text().strip()
        else:
            text = _clean(node.get_text(" "))
        if not text:
            continue
        if heading:
            section = text
        kind = "heading" if heading else "equation" if is_equation else "caption" if is_caption else "table" if node.name == "table" else "paragraph"
        figure_match = re.match(r"(?:Figure|Fig\.)\s*([\w.-]+)", text, re.I) if is_caption else None
        if total + len(text) > MAX_EXTRACTED_CHARS:
            notes.append("Text extraction reached the 1.2 million character limit; later source material is missing.")
            break
        _block(blocks, kind, text, _locator(section, equation=equation_label,
                                          figure=figure_match.group(0) if figure_match else None))
        total += len(text)
    # Restrict images to source figure containers, not logos or site controls.
    for container in root.select("figure,.ltx_figure"):
        if any(parent.name == "figure" or "ltx_figure" in parent.get("class", []) for parent in container.parents if getattr(parent, "attrs", None)):
            continue
        caption_node = container.select_one("figcaption,.ltx_caption")
        caption = _clean(caption_node.get_text(" ")) if caption_node else None
        if "ltx_table" in container.get("class", []) or re.match(r"^Table\s+\S", caption or "", re.I) or (container.find("table") and not container.find("img") and not container.find("svg")):
            # Publishers often wrap tables in <figure>. Their rows and captions
            # remain source blocks; a table is not a fabricated figure asset.
            continue
        heading = container.find_previous(re.compile(r"^h[1-6]$"))
        section = _clean(heading.get_text(" ")) if heading else None
        label = re.match(r"(?:Figure|Fig\.)\s*([\w.-]+)", caption or "", re.I)
        locator = _locator(section, figure=label.group(0) if label else None)
        image_nodes = container.find_all("img")
        urls = []
        for image in image_nodes:
            src = image.get("src") or image.get("data-src")
            if src:
                url = urljoin(resolved, src)
                if url not in urls:
                    urls.append(url)
        # Multi-panel figures preserve all image components as separate evidence
        # records with the shared caption; do not pretend one panel is the whole.
        for panel, image_url in enumerate(urls or [None]):
            figures.append({"caption": caption or None, "locator": locator,
                            "image_url": image_url, "panel": panel if len(urls) > 1 else None})
        if len(figures) >= MAX_VISUAL_RECORDS:
            notes.append("Additional HTML figures omitted after the 64-record visual limit.")
            figures = figures[:MAX_VISUAL_RECORDS]
            break
    if not blocks:
        raise SourceError("HTML has no extractable article text; it may require unsupported script rendering")
    # Metadata PDF links are useful for abstract-only publisher landing pages.
    has_sections = sum(block["kind"] == "heading" for block in blocks) >= 3
    likely_landing = pdf_url and (total < 2500 or not has_sections)
    return blocks, figures, title or None, notes, pdf_url if likely_landing else None


def _pdf(body, deadline):
    try:
        reader = PdfReader(io.BytesIO(body), strict=False)
    except Exception as error:
        raise SourceError("Downloaded PDF could not be decoded") from error
    if reader.is_encrypted:
        raise SourceError("Encrypted PDFs are unsupported")
    notes = ["PDF text preserves page locators, not inferred section/equation labels. Reading order, equations, superscripts, and tables may be imperfect; page images are supporting visual evidence, not verified OCR."]
    pages, total = [], 0
    for index in range(min(len(reader.pages), MAX_PDF_PAGES)):
        _deadline(deadline)
        try:
            text = reader.pages[index].extract_text() or ""
        except Exception:
            text = ""
            notes.append(f"Text extraction failed on PDF page {index + 1}; inspect its image if supplied.")
        text = "\n".join(line.rstrip() for line in text.replace("\x00", "").splitlines()).strip()
        if total + len(text) > MAX_EXTRACTED_CHARS:
            notes.append(f"PDF extraction reached its text limit before page {index + 1}; later pages were not read.")
            break
        pages.append(text)
        total += len(text)
    if len(reader.pages) > len(pages):
        notes.append(f"Only {len(pages)} of {len(reader.pages)} PDF pages were extracted; paper-wide coverage is incomplete.")
    # Remove exact repeated marginal lines only, leaving body repetitions intact.
    margins = Counter(line for text in pages for line in set(text.splitlines()[:2] + text.splitlines()[-2:]) if 2 <= len(line.strip()) <= 120)
    repeated = {line for line, count in margins.items() if count >= max(3, len(pages) * .6)}
    blocks = []
    for number, text in enumerate(pages, 1):
        lines = text.splitlines()
        clean_lines = [line for i, line in enumerate(lines) if not (line in repeated and (i < 2 or i >= len(lines) - 2))]
        # Split large pages only at existing line boundaries, retaining page IDs.
        chunk = []
        size = 0
        for line in clean_lines:
            if chunk and size + len(line) > 7000:
                _block(blocks, "page", "\n".join(chunk), _locator(page=number))
                chunk, size = [], 0
            chunk.append(line)
            size += len(line) + 1
        _block(blocks, "page", "\n".join(chunk), _locator(page=number))
    metadata = reader.metadata
    title = _clean(str(metadata.title)) if metadata and metadata.title else None
    return blocks, pages, len(reader.pages), title or None, notes


def _encode_image(image, allowance):
    if image.width * image.height > MAX_IMAGE_PIXELS:
        raise SourceError("Source image exceeds the decoded pixel limit")
    image = ImageOps.exif_transpose(image)
    image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)
    if image.mode in ("RGBA", "LA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        image = background
    else:
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, "PNG", compress_level=6)
    raw = buffer.getvalue()
    if len(raw) <= allowance:
        return raw, "png", "image/png"
    # Keep dimensions/readability; use JPEG rather than shrinking tiny labels.
    for quality in (90, 80):
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=quality, optimize=True)
        raw = buffer.getvalue()
        if len(raw) <= allowance:
            return raw, "jpg", "image/jpeg"
    raise SourceError("Image does not fit the remaining image-byte budget")


def _save_image(image, visual_id, output, remaining):
    if remaining <= 0:
        raise SourceError("Image-byte budget exhausted")
    raw, extension, mime = _encode_image(image, remaining)
    folder = output / "assets"
    if folder.is_symlink():
        raise SourceError("Image asset directory cannot be a symbolic link")
    folder.mkdir(exist_ok=True)
    target = folder / f"{visual_id}.{extension}"
    with target.open("xb") as handle:
        handle.write(raw)
    return target.relative_to(output).as_posix(), mime, len(raw)


def _asset(visual_id, kind, caption, locator, resolved, title):
    return {"id": visual_id, "kind": kind, "caption": caption, "locator": deepcopy(locator),
            "provided_as": "caption_only" if caption else "not_provided", "asset_path": None,
            "mime_type": None, "source_url": resolved,
            "attribution": f"Source: {title or 'the supplied paper'} — {resolved}"}


def _html_visuals(figures, focus, output, resolved, title, max_images, byte_limit, deadline):
    assets = [_asset(f"v{i + 1:04d}", "figure", f["caption"], f["locator"], resolved, title) for i, f in enumerate(figures)]
    notes, used, count = [], 0, 0
    # Focus figures first, with source-order ties; text coverage is handled
    # independently so scarce images do not determine narrative coverage.
    ranked = sorted(range(len(figures)), key=lambda i: (-_score((figures[i]["caption"] or "") + " " + (figures[i]["locator"]["section"] or ""), focus), i))
    section_representatives = {}
    for i in ranked:
        section_representatives.setdefault(figures[i]["locator"]["section"], i)
    order = list(dict.fromkeys(ranked[:1] + list(section_representatives.values()) + ranked))
    for i in order:
        figure, asset = figures[i], assets[i]
        if count >= max_images or used >= byte_limit:
            continue
        if not figure["image_url"]:
            notes.append(f"{asset['id']}: no supported raster image URL found; caption only where available.")
            continue
        if time.monotonic() >= deadline:
            notes.append("Remaining HTML figure images omitted because the preparation time allowance was exhausted; extracted text and completed images remain available.")
            break
        try:
            raw, image_url, media = _fetch(figure["image_url"], min(deadline, time.monotonic() + 8))
            with python_warnings.catch_warnings():
                python_warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as image:
                    if image.width * image.height > MAX_IMAGE_PIXELS:
                        raise SourceError("Source image exceeds the decoded pixel limit")
                    image.load()
                    path, mime, size = _save_image(image, asset["id"], output, byte_limit - used)
            asset.update(asset_path=path, mime_type=mime, source_url=image_url,
                         provided_as="image_and_caption" if asset["caption"] else "image_only")
            count += 1
            used += size
            if figure["panel"] is not None:
                notes.append(f"{asset['id']} is image component {figure['panel'] + 1} of a multi-image figure; its caption describes the whole figure.")
        except (SourceError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
            notes.append(f"{asset['id']}: image could not be safely fetched/decoded within limits; visual details were not supplied.")
    omitted = [asset["id"] for asset in assets if asset["provided_as"] not in ("image_and_caption", "image_only")]
    notes.append(f"Supplied {count} HTML figure images ({used} bytes, maximum edge {MAX_IMAGE_EDGE}px).")
    if omitted:
        notes.append("Image pixels not supplied for " + ", ".join(omitted) + "; captions remain evidence only for their stated text.")
    return assets, notes


def _page_indices(pages, count, focus, max_images):
    text_amount = sum(len(re.sub(r"\W", "", text)) for text in pages)
    scanned = text_amount < max(100, count * 40)
    if scanned:
        if count > max_images or len(pages) != count:
            raise SourceError(f"Scanned PDF has {count} pages without usable text; the {max_images}-image budget cannot cover it reliably. Supply a smaller readable paper or relevant page subset.")
        return list(range(count)), True
    if max_images == 0:
        return [], False
    # Pages with little readable text need inspection most. Otherwise prefer
    # pages with figures/complex formulas and high focus relevance, plus a
    # representative introduction/conclusion when capacity remains.
    poor = [i for i, text in enumerate(pages) if len(re.sub(r"\W", "", text)) < 40]
    ranked = sorted(range(len(pages)), key=lambda i: (-(_score(pages[i], focus) + 3 * bool(re.search(r"\b(?:fig(?:ure)?\.?|diagram|plot)\b", pages[i], re.I)) + 2 * bool(re.search(r"[∑∫√]|\\(?:frac|sum)|\bsoftmax\b", pages[i]))), i))
    selected = []
    for index in poor + ranked[:min(3, max_images)] + [0, len(pages) - 1] + ranked:
        if 0 <= index < len(pages) and index not in selected and len(selected) < max_images:
            selected.append(index)
    return sorted(selected), False


def _pdf_visuals(body, pages, count, focus, output, resolved, title, max_images, byte_limit, deadline):
    indices, scanned = _page_indices(pages, count, focus, max_images)
    if not indices:
        return [], ["PDF image preparation disabled by the configured image budget; mathematical layout and diagrams have text-only evidence."]
    try:
        import pypdfium2 as pdfium
    except ImportError as error:
        if scanned:
            raise SourceError("Scanned PDF requires the bundled pypdfium2 page renderer") from error
        return [], ["PDF page images were not supplied because pypdfium2 is unavailable; text extraction limitations remain."]
    assets, notes, used = [], [], 0
    document = pdfium.PdfDocument(body)
    try:
        for index in indices:
            if time.monotonic() >= deadline:
                if scanned:
                    raise SourceError("Scanned PDF could not be rendered completely within the preparation time allowance")
                notes.append("Remaining PDF page images omitted because the preparation time allowance was exhausted; extracted text and completed images remain available.")
                break
            asset = _asset(f"v{index + 1:04d}", "page_image", None, _locator(page=index + 1), resolved, title)
            page, bitmap, image = None, None, None
            try:
                page = document[index]
                width, height = page.get_size()
                scale = min(2.5, MAX_IMAGE_EDGE / max(width, height))
                bitmap = page.render(scale=scale)
                image = bitmap.to_pil()
                path, mime, size = _save_image(image, asset["id"], output, byte_limit - used)
                asset.update(asset_path=path, mime_type=mime, provided_as="image_only")
                assets.append(asset)
                used += size
            except (SourceError, OSError, ValueError, RuntimeError) as error:
                if scanned:
                    raise SourceError("Scanned PDF could not be rendered completely within the image budget") from error
                notes.append(f"PDF page {index + 1} image unavailable within rendering/byte limits; do not infer its visual details.")
            finally:
                if image is not None:
                    image.close()
                if bitmap is not None:
                    bitmap.close()
                if page is not None:
                    page.close()
    finally:
        document.close()
    supplied = [asset["locator"]["page"] for asset in assets]
    notes.append(f"Supplied full-page images for PDF pages {supplied} ({used} bytes, maximum edge {MAX_IMAGE_EDGE}px); these are page images, not detected figures or OCR results.")
    if len(supplied) < count:
        notes.append(f"Images for {count - len(supplied)} other PDF pages were not supplied; their visual-only details are unavailable.")
    if scanned:
        notes.append("This small PDF lacks usable extracted text. All pages were supplied as images; image interpretation remains unverified and may miss fine details.")
    return assets, notes


def prepare_source(case: dict, output: Path, *, max_text_chars=90000, max_images=6,
                   max_image_bytes=8000000, timeout=60.0):
    """Return (call-one context, handoff source); persist images and extraction audit."""
    output = Path(output)
    if not output.is_dir():
        raise SourceError("Source output directory must already exist")
    if not 1 <= max_text_chars <= MAX_EXTRACTED_CHARS or not 0 <= max_images <= 32 or not 0 <= max_image_bytes <= 32_000_000:
        raise SourceError("Invalid source context or image limits")
    deadline = time.monotonic() + max(.1, min(float(timeout), 120.0))
    paper_id, version = _arxiv_identity(case["source_url"])
    urls = [f"https://arxiv.org/html/{paper_id}", f"https://arxiv.org/pdf/{paper_id}"] if paper_id else [case["source_url"]]
    failures = []
    for attempt, url in enumerate(urls):
        _deadline(deadline)
        try:
            allowance = min(deadline, time.monotonic() + 20) if attempt + 1 < len(urls) else deadline
            body, resolved, media = _fetch(url, allowance)
            is_pdf = body.lstrip().startswith(b"%PDF-") or media == "application/pdf"
            if not is_pdf and media not in ("text/html", "application/xhtml+xml", ""):
                raise SourceError("The source is neither readable HTML nor a PDF")
            if not is_pdf:
                blocks, figures, title, notes, pdf_link = _html(body, resolved)
                if pdf_link:
                    body, resolved, media = _fetch(pdf_link, deadline)
                    if not body.lstrip().startswith(b"%PDF-"):
                        raise SourceError("The article's full-text PDF link did not return a PDF")
                    is_pdf = True
                elif sum(len(block["text"]) for block in blocks) < 300:
                    raise SourceError("HTML has too little paper text; a full-text source is required")
            if is_pdf:
                blocks, pages, page_count, title, notes = _pdf(body, deadline)
                assets, visual_notes = _pdf_visuals(body, pages, page_count, case["focus"], output, resolved,
                                                   title, max_images, max_image_bytes, deadline)
            else:
                assets, visual_notes = _html_visuals(figures, case["focus"], output, resolved, title,
                                                    max_images, max_image_bytes, deadline)
            selected, coverage_notes = _select_text(blocks, case["focus"], max_text_chars)
            notes += coverage_notes + visual_notes
            if paper_id and version is None:
                notes.append("The requested arXiv URL did not pin a version; retrieval used the current representation and exact version identity is unresolved.")
            if failures:
                notes.append("A preferred representation was unavailable; a fallback representation of the requested paper was used.")
            notes = list(dict.fromkeys(notes))
            visual_context = [{key: asset[key] for key in ("id", "kind", "caption", "locator", "provided_as")}
                              for asset in assets if asset["provided_as"] != "not_provided"]
            if not selected and not any(item["provided_as"] in ("image_only", "image_and_caption") for item in visual_context):
                raise SourceError("No readable paper text or usable page images could be supplied")
            context = {"focus": case["focus"], "audience": case["audience"], "source_blocks": selected,
                       "visuals": visual_context, "extraction_warnings": notes}
            source = {"resolved_url": resolved, "title": title, "references": selected,
                      "visuals": assets, "warnings": notes}
            audit = {"requested_url": case["source_url"], "resolved_url": resolved,
                     "content_sha256": hashlib.sha256(body).hexdigest(), "extraction_method": "pdf_text_and_pages" if is_pdf else "html",
                     "blocks": blocks, "selected_block_ids": [block["id"] for block in selected], "warnings": notes}
            (output / "source-extraction.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
            return context, source
        except SourceError as error:
            failures.append(str(error))
    raise SourceError("; ".join(failures) or "Source preparation failed")
