"""Regression checks for scoped corrections and quarantine without mutation."""
import unittest
from curate_collision_originals import revise, EMPTY_TARGETS
from build_collision_supplement import clip_boxes


class CollisionCurationTests(unittest.TestCase):
    def record(self, index=7, boxes=None, **updates):
        return {'index': index, 'group': 'phone_close_rotated',
                'boxes': [[2, .8, .5, .2, .3], [1, .5, .5, .5, .5]] if boxes is None else boxes,
                **updates}

    def test_outside_person_corrected_without_mutating_original(self):
        original = self.record()
        corrected = revise(original)
        self.assertEqual(corrected['boxes'][0][0], 0)
        self.assertEqual(original['boxes'][0][0], 2)
        self.assertEqual(corrected['boxes'][1], original['boxes'][1])
        self.assertFalse(corrected['approved_for_final_training'])

    def test_all_fourteen_unlabeled_targets_excluded_not_negative(self):
        self.assertEqual(len(EMPTY_TARGETS), 14)
        for index in EMPTY_TARGETS:
            result = revise(self.record(index=index, boxes=[]))
            self.assertEqual(result['collision_review_status'], 'excluded_unlabeled_targets')
            self.assertFalse(result['confirmed_negative'])
            self.assertFalse(result['approved_for_final_training'])

    def test_ambiguous_operator_not_speculatively_relabeled(self):
        original = self.record(index=26)
        result = revise(original)
        self.assertEqual(result['boxes'], original['boxes'])
        self.assertEqual(result['collision_review_status'], 'excluded_ambiguous_operator')

    def test_unexpected_input_fails_closed(self):
        with self.assertRaises(ValueError):
            revise(self.record(index=6))
        with self.assertRaises(ValueError):
            revise(self.record(boxes=[[0, .5, .5, .2, .2]]))

    def test_crop_clips_translates_and_drops_outside_objects(self):
        result = clip_boxes([[0, 5, 5, 20, 20], [1, 30, 30, 40, 40]], [10, 10, 25, 25])
        self.assertEqual(result, [[0, 0, 0, 10, 10]])


if __name__ == '__main__':
    unittest.main()
