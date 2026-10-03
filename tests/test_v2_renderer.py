from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET

from PIL import Image

from playground_v2.renderer import render, _math, _notation
from playground_v2.validation import ValidationError
from test_v2_experience import fixture


ROOT = Path(__file__).resolve().parents[1]


def renderer_fixture():
    handoff = json.loads((ROOT / 'docs/v2/examples/paper_content.json').read_text(encoding='utf-8'))
    spec, _ = fixture()
    section = 'proposed_reader'
    spec['experiments'][0]['section_id'] = section
    spec['sections'] = [{'section_id': s['id'], 'experiment_ids': ['attention_lab'] if s['id'] == section else [], 'figures': []} for s in handoff['content']['sections']]
    question = deepcopy(spec['questions'][0])
    while len(spec['questions']) < len(handoff['content']['learning_outcomes']):
        extra = deepcopy(question)
        extra['id'] = 'q_extra_' + str(len(spec['questions']))
        spec['questions'].append(extra)
    for q, outcome in zip(spec['questions'], handoff['content']['learning_outcomes']):
        q['outcome_id'] = outcome['id']
        q['section_id'] = next(s['id'] for s in handoff['content']['sections'] if outcome['id'] in s['learning_outcome_ids'])
    exp = spec['experiments'][0]
    exp['computation']['outputs'].append({'id': 'weight_matrix', 'label': 'Attention row', 'unit': ''})
    exp['computation']['steps'].append({'id': 'matrix_step', 'label': 'Make the row visible', 'explanation': 'The same weights form a one-query attention matrix.', 'output_ids': ['weight_matrix'], 'expressions': {'weight_matrix': ['array', '$output.weights']}})
    exp['views'].extend([
        {'id': 'matrix_view', 'kind': 'matrix', 'title': 'Attention matrix', 'output_ids': ['weight_matrix'], 'labels': [], 'row_labels': ['Query'], 'column_labels': ['A', 'B'], 'color_domain': [0, 1]},
        {'id': 'line_view', 'kind': 'line', 'title': 'Weights by position', 'output_ids': ['weights'], 'labels': ['A', 'B']},
        {'id': 'scatter_view', 'kind': 'scatter', 'title': 'Score versus weight', 'output_ids': ['scores', 'weights'], 'labels': ['A', 'B']},
        {'id': 'steps_view', 'kind': 'steps', 'title': 'Worked calculation', 'output_ids': ['scores', 'weights', 'result'], 'labels': []},
    ])
    return handoff, spec


class RendererTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.handoff, self.spec = renderer_fixture()

    def test_complete_offline_page_has_local_evidence_and_no_external_assets(self):
        report = render(self.handoff, self.spec, self.root)
        page = (self.root / 'index.html').read_text(encoding='utf-8')
        self.assertEqual(report['experiments'], 1)
        self.assertEqual(report['runtime_network_dependencies'], 0)
        self.assertIn('Caption available; the original image was not available', page)
        self.assertNotIn('id="source-evidence"', page)
        self.assertNotIn('<details', page.split('<script type=')[0])
        self.assertIn('data-inline-experiment=', page)
        self.assertNotRegex(page, r'<(?:script|img)[^>]*src=["\']https?://')
        self.assertNotIn('<link ', page)
        self.assertIn("connect-src 'none'", page)
        self.assertIn('<math ', page)
        self.assertIn('id="assessment"', page)
        self.assertIn('id="map"', page)

    def test_untrusted_text_cannot_break_script_or_markup(self):
        payload = '</script><script>window.injected=true</script><img src=x onerror=alert(1)>'
        self.handoff['content']['sections'][0]['simple_explanation'] = payload
        self.spec['introduction'] = payload
        render(self.handoff, self.spec, self.root)
        page = (self.root / 'index.html').read_text(encoding='utf-8')
        self.assertNotIn(payload, page)
        self.assertIn('&lt;script&gt;window.injected=true&lt;/script&gt;', page)
        self.assertEqual(page.count('</script>'), 2)
        self.assertIn('\\u003c/script\\u003e', page)

    def test_csp_hashes_match_exact_owned_assets(self):
        render(self.handoff, self.spec, self.root)
        page = (self.root / 'index.html').read_text(encoding='utf-8')
        script = re.search(r'<script>([\s\S]*)</script>', page).group(1)
        style = re.search(r'<style>([\s\S]*)</style>', page).group(1)
        for asset in (script, style):
            digest = base64.b64encode(hashlib.sha256(asset.encode()).digest()).decode()
            self.assertIn("'sha256-" + digest + "'", page)

    def test_image_is_embedded_and_attributed(self):
        (self.root / 'assets').mkdir()
        Image.new('RGB', (20, 30), 'white').save(self.root / 'assets/figure.png')
        visual = self.handoff['source']['visuals'][0]
        visual.update(provided_as='image_and_caption', asset_path='assets/figure.png', mime_type='image/png')
        report = render(self.handoff, self.spec, self.root)
        page = (self.root / 'index.html').read_text(encoding='utf-8')
        self.assertEqual(report['embedded_images'], 1)
        self.assertIn('src="data:image/png;base64,', page)
        self.assertIn(visual['attribution'], page)
        self.assertIn('Enlarge figure', page)

    def test_asset_escape_fails_instead_of_reading_outside_handoff(self):
        visual = self.handoff['source']['visuals'][0]
        visual.update(provided_as='image_and_caption', asset_path='../private.png', mime_type='image/png')
        with self.assertRaises(ValidationError):
            render(self.handoff, self.spec, self.root)
        self.assertFalse((self.root / 'index.html').exists())

    def test_full_pdf_page_stays_evidence_and_is_not_displayed_as_a_figure(self):
        (self.root / 'assets').mkdir()
        Image.new('RGB', (20, 30), 'white').save(self.root / 'assets/page.png')
        visual = self.handoff['source']['visuals'][0]
        visual.update(kind='page_image', provided_as='image_only', caption=None, asset_path='assets/page.png', mime_type='image/png')
        visual['locator']['page'] = 1
        report = render(self.handoff, self.spec, self.root)
        self.assertEqual(report['embedded_images'], 0)
        self.assertNotIn('src="data:image/png', (self.root/'index.html').read_text(encoding='utf-8'))

    def test_render_is_byte_reproducible_without_manual_html_changes(self):
        first = render(self.handoff, self.spec, self.root)
        original = (self.root / 'index.html').read_bytes()
        second_dir = self.root / 'repeat'
        second = render(self.handoff, self.spec, second_dir, source_dir=self.root)
        self.assertEqual(original, (second_dir / 'index.html').read_bytes())
        self.assertEqual(first['html_sha256'], second['html_sha256'])
        self.assertEqual(len(first['renderer_assets_sha256']), 6)

    def test_math_typesets_common_notation_and_has_explicit_fallback(self):
        self.assertIn('<mfrac>', _math(r'\frac{QK^{T}}{\sqrt{d_k}}'))
        self.assertIn('<msqrt>', _math(r'\sqrt{x}'))
        self.assertIn('Equation notation (TeX)', _math(r'\unsupported{x}'))
        self.assertNotIn('<script>', _math('<script>'))

    def test_math_sum_limits_share_one_operator_in_either_order(self):
        for equation in (r'H = -\sum_{i=1}^{n} p_i \log p_i',
                         r'H = -\sum ^{n} _{i=1} p_i \log p_i',
                         r'\sum\limits_{i=1}^{n} p_i'):
            with self.subTest(equation=equation):
                tree = ET.fromstring(_math(equation))
                limits = tree.find('.//munderover')
                self.assertIsNotNone(limits)
                self.assertEqual([child.tag for child in limits], ['mo', 'mrow', 'mrow'])
                self.assertEqual([''.join(child.itertext()) for child in limits], ['∑', 'i=1', 'n'])
                self.assertIsNone(tree.find('.//msup/msub'))
                self.assertIsNone(tree.find('.//msub/msup'))

    def test_math_combines_scripts_inside_fractions_and_rejects_missing_scripts(self):
        for equation in (r'\frac{x_i^2}{\sqrt{d_k}}', r'\frac{x^2_i}{\sqrt{d_k}}'):
            with self.subTest(equation=equation):
                tree = ET.fromstring(_math(equation))
                combined = tree.find('.//mfrac/mrow/msubsup')
                self.assertIsNotNone(combined)
                self.assertEqual([''.join(child.itertext()) for child in combined], ['x', 'i', '2'])
                self.assertIsNotNone(tree.find('.//msqrt/mrow/msub'))
        for invalid in (r'x_', r'x^}', r'x_i_j', r'_i', r'\frac{x}{'):
            self.assertIn('Equation notation (TeX)', _math(invalid))

    def test_math_variable_notation_typesets_functions_fractions_and_scripts(self):
        expected = {'d_k': 'msub', 'QK^T': 'msup', 'QK^T / sqrt(d_k)': 'mfrac',
                    'softmax(QK^T / sqrt(d_k))': 'mfrac', '-p_i log2 p_i': 'msub'}
        for notation, tag in expected.items():
            with self.subTest(notation=notation):
                tree = ET.fromstring(_notation(notation))
                self.assertEqual(tree.attrib['display'], 'inline')
                self.assertIsNotNone(tree.find('.//' + tag))
        softmax = ET.fromstring(_notation('softmax(QK^T / sqrt(d_k))'))
        self.assertEqual(softmax.find('.//mi').text, 'softmax')
        self.assertIsNotNone(softmax.find('.//mfrac/mrow/msqrt/mrow/msub'))
        attention = ET.fromstring(_notation('Attention(Q,K,V)'))
        self.assertEqual(attention.find('.//mi').text, 'Attention')
        self.assertEqual(''.join(attention.itertext()), 'Attention(Q,K,V)')
        self.assertNotIn('<script>', _notation('<script>'))
        self.assertIn('notation-fallback', _notation('sqrt(x'))


if __name__ == '__main__':
    unittest.main()
