"""Hash-bound review safety with isolated software fixtures, not dataset imagery."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import build_private_github_pilot as pilot


class PrivatePilotTests(unittest.TestCase):
    def prepare(self, root):
        source = root/'fixture.png'
        Image.new('RGB',(16,16),'#121212').save(source)
        proposals = root/'proposals'
        proposals.mkdir()
        overlay = proposals/'fixture-overlay.png'
        Image.new('RGB',(16,16),'#343434').save(overlay)
        row = dict(id='fixture',path=str(source),width=16,height=16,boxes=[[0,.5,.5,.2,.2]],
            split='train',group='fixture',sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            status='pending_overlay_review',approved_for_training=False)
        manifest = proposals/'manifest.ndjson'
        manifest.write_text(json.dumps(row)+'\n',encoding='utf-8')
        approval = root/'approval.json'
        approval.write_text(json.dumps(dict(date='fixture',
            manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
            overlays=dict(fixture=hashlib.sha256(overlay.read_bytes()).hexdigest()))),encoding='utf-8')
        return source, proposals, approval

    def test_approval_preserves_source_and_never_claims_final_or_imported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, proposals, approval = self.prepare(root)
            before = source.read_bytes()
            with patch.object(pilot,'ROOT',root),patch.object(pilot,'PROPOSALS',proposals):
                pilot.approve(approval)
                with self.assertRaises(ValueError):
                    pilot.approve(approval)
            output = root/'private-white-hall-reviewed-r1'
            stats = json.loads((output/'statistics.json').read_text())
            self.assertEqual(stats['images'],1)
            self.assertEqual(stats['reviewed_pedestrian_boxes'],1)
            self.assertFalse(stats['final_dataset'])
            self.assertFalse(stats['platform_imported'])
            self.assertEqual(stats['rights'],'unknown')
            self.assertEqual(source.read_bytes(),before)

    def test_changed_artifacts_rejected_before_approval_output(self):
        for target in ('source','overlay','manifest'):
            with self.subTest(target=target),tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source,proposals,approval = self.prepare(root)
                path = {'source':source,'overlay':proposals/'fixture-overlay.png','manifest':proposals/'manifest.ndjson'}[target]
                path.write_bytes(path.read_bytes()+b'changed')
                with patch.object(pilot,'ROOT',root),patch.object(pilot,'PROPOSALS',proposals):
                    with self.assertRaises(ValueError):
                        pilot.approve(approval)
                self.assertFalse((root/'private-white-hall-reviewed-r1').exists())


if __name__ == '__main__':
    unittest.main()
