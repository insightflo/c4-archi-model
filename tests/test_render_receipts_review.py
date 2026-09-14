"""Receipt integrity regressions: real temporary sources, artifacts and receipts."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate_render_receipts import run


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReceiptReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'diagrams').mkdir()
        (self.root / 'qa').mkdir()
        self.source = self.root / 'diagrams/context.flowmap.json'
        self.source.write_text('{"nodes": []}')
        self.output = self.root / 'diagrams/context.html'
        self.output.write_text('<html>Ordering System</html>')
        self.receipt = {
            'exitCode': 0, 'input': 'diagrams/context.flowmap.json',
            'specification': {'sha256': digest(self.source)},
            'output': 'diagrams/context.html',
            'artifact': {'sha256': digest(self.output), 'bytes': self.output.stat().st_size},
        }
        self.validation = {'ok': True}
        self.data = {'diagrams': [{'viewId': 'context', 'assetPath': 'diagrams/context.html'}]}

    def check(self):
        (self.root / 'qa/repo-flowmap-validate-context.json').write_text(json.dumps(self.validation))
        (self.root / 'qa/repo-flowmap-build-context.json').write_text(json.dumps(self.receipt))
        path = self.root / 'data.json'
        path.write_text(json.dumps(self.data))
        return run(self.root, path)

    def assertCode(self, code):
        report = self.check()
        self.assertIn(code, [f.code for f in report.errors], report.to_dict())

    def test_valid_native_shaped_binding(self):
        self.assertEqual([], self.check().errors)

    def test_size_only_is_not_integrity(self):
        del self.receipt['artifact']['sha256']
        self.output.write_text('<html>Intruder System</html>')
        self.assertCode('RCP-006')

    def test_same_size_tamper_with_hash(self):
        self.output.write_text('<html>Intruder System</html>')
        self.assertCode('RCP-005')

    def test_stale_source_hash(self):
        self.source.write_text('{"nodes": [1]}')
        self.assertCode('RCP-009')

    def test_missing_source_hash(self):
        del self.receipt['specification']
        self.assertCode('RCP-009')

    def test_wrong_source_path_even_with_correct_digest(self):
        other = self.root / 'diagrams/other.json'
        other.write_bytes(self.source.read_bytes())
        self.receipt['input'] = 'diagrams/other.json'
        self.assertCode('RCP-009')

    def test_wrong_view_output_reuse(self):
        self.data['diagrams'].append({'viewId': 'container', 'assetPath': 'diagrams/context.html'})
        self.assertCode('RCP-007')

    def test_failed_orphan_cannot_attribute(self):
        self.source.unlink()
        self.receipt['exitCode'] = 99
        self.assertCode('RCP-007')

    def test_successful_orphan_cannot_attribute(self):
        self.source.unlink()
        self.assertCode('RCP-007')

    def test_explicit_success_required(self):
        del self.receipt['exitCode']
        self.assertCode('RCP-004')

    def test_malformed_success_rejected(self):
        for value in [False, True, '0', 0.0, [], {}]:
            with self.subTest(value=value):
                self.receipt['exitCode'] = value
                self.assertCode('RCP-004')

    def test_contradictory_success_rejected(self):
        self.receipt['ok'] = False
        self.assertCode('RCP-004')

    def test_validate_nonobject_is_error_not_crash(self):
        for value in [[], None, 1, 'ok', True]:
            with self.subTest(value=value):
                self.validation = value
                self.assertCode('RCP-002')

    def test_validate_conflicting_status(self):
        self.validation = {'ok': True, 'exitCode': 1}
        self.assertCode('RCP-002')

    def test_data_uri_only_needs_attribution(self):
        self.source.unlink()
        self.data['diagrams'][0]['assetPath'] = None
        self.data['diagrams'][0]['dataUri'] = 'data:text/html;base64,' + base64.b64encode(self.output.read_bytes()).decode()
        self.assertCode('RCP-007')

    def test_verified_data_uri_only_allowed(self):
        self.data['diagrams'][0]['assetPath'] = None
        self.data['diagrams'][0]['dataUri'] = 'data:text/html;base64,' + base64.b64encode(self.output.read_bytes()).decode()
        self.assertEqual([], self.check().errors)

    def test_preembedded_bytes_must_match(self):
        self.data['diagrams'][0]['dataUri'] = 'data:text/html;base64,' + base64.b64encode(b'unknown').decode()
        self.assertCode('RCP-007')

    def test_print_path_needs_attribution(self):
        (self.root / 'print.svg').write_text('<svg/>')
        self.data['diagrams'][0]['printAssetPath'] = 'print.svg'
        self.assertCode('RCP-007')

    def test_print_uri_needs_attribution(self):
        self.data['diagrams'][0]['printDataUri'] = 'data:image/svg+xml;base64,PHN2Zy8+'
        self.assertCode('RCP-007')

    def test_malformed_artifact_hash(self):
        for value in [[], {}, 2, True, 'invalid']:
            with self.subTest(value=value):
                self.receipt['artifact']['sha256'] = value
                self.assertCode('RCP-006')

    def test_bad_validate_cannot_attribute_otherwise_valid_output(self):
        self.validation = {'ok': False}
        self.assertCode('RCP-007')

    def test_bad_output_digest_cannot_attribute(self):
        self.receipt['artifact']['sha256'] = '0' * 64
        self.assertCode('RCP-007')

    def test_bad_input_binding_cannot_attribute(self):
        self.receipt['specification']['sha256'] = '0' * 64
        self.assertCode('RCP-007')

    def test_claimed_receipt_view_must_match_source(self):
        self.receipt['viewId'] = 'container'
        self.assertCode('RCP-009')

    def test_malformed_data_uri_rejected(self):
        for uri in ['data:text/html;base64,???', 'https://example.com', [], {}, 1]:
            with self.subTest(uri=uri):
                self.data['diagrams'][0]['dataUri'] = uri
                self.assertCode('RCP-007')

    def test_malformed_nested_receipts_rejected(self):
        for field in ['artifact', 'specification']:
            original = self.receipt[field]
            for value in [None, [], 3, True, 'bad']:
                with self.subTest(field=field, value=value):
                    self.receipt[field] = value
                    self.assertCode('RCP-006' if field == 'artifact' else 'RCP-009')
            self.receipt[field] = original

    def test_archify_svg_requires_current_deliver_binding(self):
        self.source.rename(self.root / 'diagrams/context.architecture.json')
        self.source = self.root / 'diagrams/context.architecture.json'
        self.receipt['input'] = 'diagrams/context.architecture.json'
        self.receipt['ok'] = True
        svg = self.root / 'diagrams/context.svg'
        svg.write_text('<svg/>')
        extraction = {'ok': True, 'source': 'diagrams/context.html',
                      'sourceSha256': digest(self.output),
                      'output': 'diagrams/context.svg', 'svgSha256': digest(svg)}
        qa = self.root / 'qa'
        (qa / 'archify-validate-context.json').write_text(json.dumps(self.validation))
        (qa / 'archify-deliver-context.json').write_text(json.dumps(self.receipt))
        receipt_path = qa / 'archify-svg-context.json'
        receipt_path.write_text(json.dumps(extraction))
        self.data['diagrams'][0]['printAssetPath'] = 'diagrams/context.svg'
        self.assertEqual([], self.check().errors)
        extraction['sourceSha256'] = '0' * 64
        receipt_path.write_text(json.dumps(extraction))
        self.assertCode('RCP-009')
        self.assertCode('RCP-007')

    def test_flowmap_print_extraction_chain(self):
        svg = self.root / 'diagrams/context.svg'
        svg.write_text('<svg/>')
        extraction = {'ok': True, 'source': 'diagrams/context.html',
                      'sourceSha256': digest(self.output),
                      'output': 'diagrams/context.svg', 'svgSha256': digest(svg)}
        receipt_path = self.root / 'qa/repo-flowmap-svg-context.json'
        receipt_path.write_text(json.dumps(extraction))
        self.data['diagrams'][0]['printAssetPath'] = 'diagrams/context.svg'
        self.assertEqual([], self.check().errors)
        extraction['sourceSha256'] = '0' * 64
        receipt_path.write_text(json.dumps(extraction))
        self.assertCode('RCP-009')
        self.assertCode('RCP-007')

    def test_duplicate_success_keys_fail_closed(self):
        self.check()
        path = self.root / 'qa/repo-flowmap-build-context.json'
        path.write_text('{"ok":false,"ok":true,' + json.dumps(self.receipt)[1:])
        report = run(self.root, self.root / 'data.json')
        self.assertIn('RCP-004', [f.code for f in report.errors])

    def test_report_nonobject_is_error(self):
        self.data = []
        self.assertCode('RCP-000')

    def test_missing_explicit_default_data_is_error(self):
        report = run(self.root, self.root / 'html/report-data.json')
        self.assertIn('RCP-000', [f.code for f in report.errors])


if __name__ == '__main__':
    unittest.main()
