import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from apply_source_exclusions import apply


class SelectionExclusionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        rows = []
        for identity, color in [('canonical', 'blue'), ('redundant', 'green')]:
            path = self.root/(identity+'.png')
            Image.new('RGB', (8, 6), color).save(path)
            rows.append(dict(id=identity, path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                             status='pending_individual_visual_review', group='original-origin-grouping-pending'))
        self.manifest = self.root/'manifest.ndjson'
        self.manifest.write_text(''.join(json.dumps(r)+'\n' for r in rows), encoding='utf-8')
        self.decision = dict(date='fixture', input_manifest_sha256=hashlib.sha256(self.manifest.read_bytes()).hexdigest(),
                             exclusions=[dict(id='redundant', source_sha256=rows[1]['sha256'],
                                action='excluded_confirmed_near_duplicate', canonical_id='canonical',
                                canonical_sha256=rows[0]['sha256'], group='fixture-session',
                                comparison_evidence='Software fixture only, not an actual visual approval',
                                reason='Test selection exclusion')])

    def run_review(self):
        decisions = self.root/'decisions.json'
        decisions.write_text(json.dumps(self.decision), encoding='utf-8')
        return apply(self.manifest, decisions, self.root/'review')

    def test_preserves_sources_and_groups_related_records(self):
        before = {p.name: p.read_bytes() for p in self.root.glob('*.png')}
        report = self.run_review()
        self.assertEqual(report['new_exclusions'], 1)
        self.assertFalse(report['training_ready'])
        rows = [json.loads(line) for line in (self.root/'review/manifest.ndjson').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(rows[1]['near_duplicate_of'], 'canonical')
        self.assertFalse(rows[1]['confirmed_negative'])
        self.assertEqual({row['group'] for row in rows}, {'fixture-session'})
        for name, data in before.items():
            self.assertEqual((self.root/name).read_bytes(), data)

    def test_rejects_changed_canonical_before_output(self):
        Image.new('RGB', (8, 6), 'red').save(self.root/'canonical.png')
        with self.assertRaisesRegex(ValueError, 'Canonical image changed'):
            self.run_review()
        self.assertFalse((self.root/'review').exists())

    def test_rejects_self_reference(self):
        self.decision['exclusions'][0]['canonical_id'] = 'redundant'
        with self.assertRaisesRegex(ValueError, 'Canonical image is excluded'):
            self.run_review()
        self.assertFalse((self.root/'review').exists())
