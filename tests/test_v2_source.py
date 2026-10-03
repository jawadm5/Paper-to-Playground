"""V2 evidence preparation checks: no network, model calls, or external papers."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from playground_v2.retrieval import SourceError
from playground_v2.source import MAX_IMAGE_EDGE, _encode_image, _select_text, _table_text, prepare_source


ROOT = Path(__file__).resolve().parents[1]
CASE = {"source_url": "https://example.org/paper", "focus": "Explain matrix attention and its limitations", "audience": "Engineering undergraduate"}
PARAGRAPH = "The method defines a weighted combination of values. Its assumptions matter when interpreting the result. " * 4
HTML = ("""<!doctype html><html><head><title>Example mechanism</title>
<meta name="citation_title" content="A synthetic paper"></head><body><nav>Ignore navigation</nav><article>
<h1>Example mechanism</h1><h2>1 Introduction</h2><p>""" + PARAGRAPH + """</p>
<h2>2 Method</h2><p>The score is defined before normalization.</p>
<table class="ltx_equation"><tr><td><math alttext="y = A x"><mi>bad flattened tokens</mi></math></td><td class="ltx_tag_equation">(1)</td></tr></table>
<table><tr><th>Quantity</th><th>Units</th></tr><tr><td>Time</td><td>seconds</td></tr></table>
<figure><img src="/figure.png"><figcaption>Figure 1. Matrix attention calculation.</figcaption></figure>
<h2>3 Results</h2><p>""" + PARAGRAPH + """</p><h2>4 Conclusion</h2><p>""" + PARAGRAPH + """</p>
</article></body></html>""").encode()


def image_bytes(size=(2400, 600)):
    image = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, size[0] - 20, size[1] - 20), outline="black", width=4)
    draw.text((30, 30), "Synthetic figure: inputs -> scores -> output", fill="black")
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    image.close()
    return buffer.getvalue()


def text_pdf(pages=3):
    writer = PdfWriter()
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    for number in range(pages):
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        text = f"Page {number + 1}: " + ("matrix attention definitions and source conclusions " * 8)
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 30 700 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = stream
    writer.add_metadata({"/Title": "Synthetic PDF"})
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def scan_pdf(pages=2):
    images = []
    for number in range(pages):
        image = Image.new("RGB", (350, 450), "white")
        ImageDraw.Draw(image).text((20, 20), f"Synthetic scanned page {number + 1}", fill="black")
        images.append(image)
    output = io.BytesIO()
    images[0].save(output, "PDF", save_all=True, append_images=images[1:])
    for image in images:
        image.close()
    return output.getvalue()


class SourcePreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        context_schema = json.loads((ROOT / "docs/v2/schemas/call1-input.schema.json").read_text(encoding="utf-8"))
        envelope = json.loads((ROOT / "docs/v2/schemas/paper-content.schema.json").read_text(encoding="utf-8"))
        cls.context_validator = Draft202012Validator(context_schema)
        cls.source_validator = Draft202012Validator({"$ref": "#/$defs/HandoffSource", "$defs": envelope["$defs"]})

    def check_schema(self, context, source):
        self.context_validator.validate(context)
        self.source_validator.validate(source)
        self.assertEqual(context["source_blocks"], source["references"])

    def test_html_whole_paper_math_table_and_reusable_figure(self):
        def fetch(url, deadline):
            if url == CASE["source_url"]:
                return HTML, url, "text/html"
            self.assertEqual(url, "https://example.org/figure.png")
            return image_bytes(), url, "image/png"
        with tempfile.TemporaryDirectory() as directory, patch("playground_v2.source._fetch", side_effect=fetch):
            output = Path(directory)
            context, source = prepare_source(CASE, output)
            self.check_schema(context, source)
            self.assertEqual(source["title"], "A synthetic paper")
            self.assertTrue(any("4 Conclusion" == block["locator"]["section"] for block in context["source_blocks"]))
            self.assertTrue(any(block["kind"] == "equation" and "y = A x" in block["text"] and block["locator"]["equation"] == "(1)" for block in context["source_blocks"]))
            tables = [block for block in context["source_blocks"] if block["kind"] == "table"]
            self.assertEqual([[cell.strip() for cell in row.split("|")] for row in tables[0]["text"].splitlines()], [["Quantity", "Units"], ["Time", "seconds"]])
            self.assertNotIn("Ignore navigation", " ".join(block["text"] for block in context["source_blocks"]))
            visual = source["visuals"][0]
            self.assertEqual(visual["provided_as"], "image_and_caption")
            self.assertEqual(visual["kind"], "figure")
            self.assertNotIn("asset_path", context["visuals"][0])
            with Image.open(output / visual["asset_path"]) as saved:
                self.assertLessEqual(max(saved.size), MAX_IMAGE_EDGE)
            self.assertTrue((output / "source-extraction.json").is_file())

    def test_context_selection_keeps_coverage_and_reports_omissions(self):
        blocks = []
        for number in range(6):
            for text in (f"Section {number}: " + "background " * 8, "attention " * 140):
                blocks.append({"id": f"s{len(blocks)}", "kind": "paragraph", "text": text,
                               "locator": {"section": f"section {number}", "page": None, "equation": None, "figure": None}})
        selected, notes = _select_text(blocks, "attention", 1600)
        self.assertEqual({b["locator"]["section"] for b in selected}, {f"section {i}" for i in range(6)})
        self.assertLessEqual(sum(len(b["text"]) for b in selected), 1600)
        self.assertTrue(any("omitted material" in note for note in notes))
        self.assertTrue(all(block in blocks for block in selected), "Source blocks must not be silently rewritten")

    def test_unavailable_or_over_budget_image_is_truthful_caption_only(self):
        def fetch(url, deadline):
            if url == CASE["source_url"]:
                return HTML, url, "text/html"
            return image_bytes(), url, "image/png"
        with tempfile.TemporaryDirectory() as directory, patch("playground_v2.source._fetch", side_effect=fetch):
            context, source = prepare_source(CASE, Path(directory), max_image_bytes=1)
            self.check_schema(context, source)
            self.assertEqual(context["visuals"][0]["provided_as"], "caption_only")
            self.assertIsNone(source["visuals"][0]["asset_path"])
            self.assertTrue(any("not supplied" in warning for warning in source["warnings"]))

    def test_transparent_diagram_flattens_onto_white(self):
        image = Image.new("RGBA", (3, 1), (0, 0, 0, 0))
        image.putpixel((1, 0), (255, 0, 0, 128))
        image.putpixel((2, 0), (0, 0, 0, 255))
        raw, extension, mime = _encode_image(image, 1000000)
        self.assertEqual((extension, mime), ("png", "image/png"))
        with Image.open(io.BytesIO(raw)) as saved:
            self.assertEqual(saved.getpixel((0, 0)), (255, 255, 255))
            self.assertEqual(saved.getpixel((1, 0)), (255, 127, 127))
            self.assertEqual(saved.getpixel((2, 0)), (0, 0, 0))
        image.close()

    def test_merged_table_headers_groups_and_empty_cells_keep_alignment(self):
        html = """<table><tr><th rowspan="2">Model</th><th colspan="2">BLEU</th><th colspan="2">Cost</th></tr>
        <tr><th>DE</th><th>FR</th><th>DE</th><th>FR</th></tr>
        <tr><td rowspan="2">Group C</td><td>25.3</td><td>38.1</td><td colspan="2">3.3e18</td></tr>
        <tr><td>25.5</td><td>40.0</td><td></td><td>1e20</td></tr></table>"""
        text, notes = _table_text(BeautifulSoup(html, "html.parser").table)
        self.assertEqual(notes, [])
        self.assertEqual([[cell.strip() for cell in row.split("|")] for row in text.splitlines()], [
            ["Model", "BLEU", "BLEU", "Cost", "Cost"],
            ["Model", "DE", "FR", "DE", "FR"],
            ["Group C", "25.3", "38.1", "3.3e18", "3.3e18"],
            ["Group C", "25.5", "40.0", "", "1e20"],
        ])
        invalid = BeautifulSoup('<table><tr><td colspan="10000000">x</td></tr></table>', "html.parser")
        text, notes = _table_text(invalid.table)
        self.assertEqual(text, "")
        self.assertTrue(any("omitted" in note for note in notes))

    def test_table_figure_wrapper_does_not_fabricate_visual(self):
        table_wrapper = b'<figure class="ltx_table"><table><tr><td>25.3</td></tr></table><figcaption>Table 2: Numeric result.</figcaption></figure>'
        html = HTML.replace(b'</article>', table_wrapper + b'</article>')
        with tempfile.TemporaryDirectory() as directory, patch("playground_v2.source._fetch", return_value=(html, CASE["source_url"], "text/html")):
            context, source = prepare_source(CASE, Path(directory), max_images=0)
            self.check_schema(context, source)
            self.assertFalse(any((visual["caption"] or "").startswith("Table") for visual in source["visuals"]))
            self.assertTrue(any(block["kind"] == "table" and "25.3" in block["text"] for block in source["references"]))
            self.assertTrue(any(block["kind"] == "caption" and "Table 2" in block["text"] for block in source["references"]))

    def test_small_scan_supplies_actual_images_for_all_pages(self):
        raw = scan_pdf(2)
        with tempfile.TemporaryDirectory() as directory, patch("playground_v2.source._fetch", return_value=(raw, CASE["source_url"], "application/pdf")):
            output = Path(directory)
            context, source = prepare_source(CASE, output, max_images=2)
            self.check_schema(context, source)
            self.assertEqual(context["source_blocks"], [])
            self.assertEqual([v["locator"]["page"] for v in context["visuals"]], [1, 2])
            self.assertTrue(all(v["kind"] == "page_image" and v["provided_as"] == "image_only" for v in context["visuals"]))
            self.assertTrue(all((output / visual["asset_path"]).is_file() for visual in source["visuals"]))
            self.assertLessEqual(sum((output / visual["asset_path"]).stat().st_size for visual in source["visuals"]), 8000000)

    def test_long_scan_fails_instead_of_selecting_arbitrary_pages(self):
        raw = scan_pdf(3)
        with tempfile.TemporaryDirectory() as directory, patch("playground_v2.source._fetch", return_value=(raw, CASE["source_url"], "application/pdf")):
            with self.assertRaisesRegex(SourceError, "cannot cover it reliably"):
                prepare_source(CASE, Path(directory), max_images=2)

    def test_arxiv_fallback_keeps_version_and_pdf_page_provenance(self):
        raw = text_pdf(3)
        urls = []
        case = {**CASE, "source_url": "https://arxiv.org/abs/1234.56789v2"}
        def fetch(url, deadline):
            urls.append(url)
            if "/html/" in url:
                raise SourceError("HTML unavailable")
            return raw, url, "application/pdf"
        with tempfile.TemporaryDirectory() as directory, patch("playground_v2.source._fetch", side_effect=fetch):
            context, source = prepare_source(case, Path(directory), max_images=1)
            self.check_schema(context, source)
            self.assertEqual(urls, ["https://arxiv.org/html/1234.56789v2", "https://arxiv.org/pdf/1234.56789v2"])
            self.assertEqual({b["locator"]["page"] for b in context["source_blocks"]}, {1, 2, 3})
            self.assertTrue(all(b["locator"]["section"] is None for b in context["source_blocks"]))
            self.assertEqual(len(context["visuals"]), 1)
            self.assertTrue(any("other PDF pages" in note for note in source["warnings"]))


if __name__ == "__main__":
    unittest.main()
