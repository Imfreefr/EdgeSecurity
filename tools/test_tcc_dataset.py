import tempfile
import unittest
from pathlib import Path
from PIL import Image
from finalize_tcc_dataset import inspect, plan_split, usage_report, close_view, copy_image


class FinalDatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.records = []
        self.registry = {'groups': {}}
        for group_number in range(20):
            group = f'camera-{group_number}'
            self.registry['groups'][group] = {
                'independence_verified': True, 'grouping_evidence': 'test fixture only',
                'training_allowed': True, 'redistribution_allowed': True,
                'license_url': 'https://example.test/license', 'source_url': 'https://example.test/source',
                'seen_by_edgev1': False}
            for number in range(10):
                index = group_number*10+number
                path = Path(self.temp.name)/f'image-{index}.png'
                Image.new('RGB', (16, 16), (index, 40, 80)).save(path)
                self.records.append({'id': f'fixture-{index}', 'path': str(path),
                                     'width': 16, 'height': 16, 'group': group, 'split': 'train',
                                     'framing': 'elevated_distant', 'is_original': False,
                                     'status': 'approved_visual_review', 'confirmed_negative': number == 0,
                                     'boxes': [] if number == 0 else [[0, .25, .25, .2, .2], [1, .7, .7, .3, .3]]})

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_grouped_split_reproducible(self):
        records = plan_split(self.records)
        self.assertEqual(records, plan_split(self.records))
        self.assertEqual(inspect(records, self.registry), [])
        self.assertEqual(sum(item['split'] == 'test' for item in records), 30)

    def test_partial_dataset_cannot_be_final(self):
        errors = inspect(self.records[:20], self.registry)
        self.assertTrue(any('2/20' in error for error in errors))
        with self.assertRaises(ValueError):
            plan_split(self.records[:20])

    def test_source_rights_and_baseline_exposure_enforced(self):
        records = plan_split(self.records)
        group = next(record['group'] for record in records if record['split'] == 'test')
        self.registry['groups'][group]['seen_by_edgev1'] = True
        self.registry['groups'][group]['redistribution_allowed'] = False
        errors = inspect(records, self.registry)
        self.assertTrue(any('rights' in error for error in errors))
        self.assertTrue(any('baseline-exposed' in error for error in errors))

    def test_pending_boxes_duplicates_and_synthetic_rejected(self):
        records = plan_split(self.records)
        records[0]['status'] = 'pending_visual_review'
        records[1]['synthetic'] = True
        errors = inspect(records, self.registry)
        self.assertTrue(any('Unreviewed' in error for error in errors))
        self.assertTrue(any('Synthetic' in error for error in errors))

    def test_missing_negatives_rejected(self):
        records = plan_split(self.records)
        for record in records:
            if not record['boxes']:
                record['boxes'] = [[0, .25, .25, .2, .2]]
                record['confirmed_negative'] = False
        self.assertTrue(any('negatives' in error for error in inspect(records, self.registry)))

    def test_unverified_groups_do_not_inflate_diversity_count(self):
        self.registry['groups']['camera-0']['independence_verified'] = False
        errors = inspect(plan_split(self.records), self.registry)
        self.assertTrue(any('19/20 verified independent' in error for error in errors))

    def test_private_unknown_rights_preserve_registry(self):
        import copy
        for group in self.registry['groups'].values():
            for field in ('license_url', 'training_allowed', 'redistribution_allowed'):
                group.pop(field)
        before = copy.deepcopy(self.registry)
        records = plan_split(self.records)
        self.assertEqual(inspect(records, self.registry, usage='private'), [])
        self.assertTrue(any('rights' in e for e in inspect(records, self.registry)))
        report = usage_report(records, self.registry, 'private')
        self.assertEqual(len(report['groups_without_verified_training_and_redistribution_rights']), 20)
        self.assertEqual(report['required_platform_visibility'], 'private')
        self.assertFalse(report['public_distribution_permitted_by_this_workflow'])
        self.assertEqual(self.registry, before)

    def test_private_still_requires_source_and_rejects_training_prohibition(self):
        group = self.registry['groups']['camera-0']
        group['training_allowed'] = False
        errors = inspect(plan_split(self.records), self.registry, usage='private')
        self.assertTrue(any('prohibits intended training' in e for e in errors))
        group['training_allowed'] = True
        group.pop('source_url')
        self.assertTrue(any('source provenance' in e for e in inspect(plan_split(self.records), self.registry, usage='private')))

    def test_private_does_not_waive_review_or_diversity(self):
        records = plan_split(self.records)
        records[0]['status'] = 'pending'
        self.registry['groups']['camera-0']['independence_verified'] = False
        errors = inspect(records, self.registry, usage='private')
        self.assertTrue(any('19/20' in e for e in errors))
        self.assertTrue(any('Unreviewed' in e for e in errors))

    def test_private_allows_nonredistributable_source_without_claiming_public_permission(self):
        self.registry['groups']['camera-0']['redistribution_allowed'] = False
        records = plan_split(self.records)
        self.assertEqual(inspect(records, self.registry, usage='private'), [])
        self.assertFalse(usage_report(records, self.registry, 'private')['public_distribution_permitted_by_this_workflow'])

    def test_recovered_close_view_alias_is_not_a_quota_bypass(self):
        self.assertTrue(close_view({'viewpoint': 'ground_level_close'}))

    def test_packaged_image_keeps_actual_encoding_and_bytes(self):
        record = self.records[0]
        # Fixtures are PNG, including when a misleading source suffix is used.
        source = Path(record['path'])
        before = source.read_bytes()
        relative, destination = copy_image(record, Path(self.temp.name)/'package')
        self.assertTrue(relative.endswith('.png'))
        self.assertEqual(destination.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
