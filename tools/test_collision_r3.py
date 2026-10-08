import unittest
from apply_collision_review_r3 import apply_decision


class ConeCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.record = {'file': 'IMG_0495.jpg', 'index': 2, 'boxes': [[2, .5, .5, .2, .2], [1, .5, .5, .8, .8]]+[[3, .1, .1, .05, .05] for _ in range(4)]}
        self.decision = {'file': 'IMG_0495.jpg', 'decision': 'pending', 'reason': 'manual fixture', 'remove_class3_cones': True}

    def test_scoped_correction_keeps_original_and_remains_pending(self):
        result = apply_decision(self.record, self.decision)
        self.assertEqual(len(result['boxes']), 2)
        self.assertEqual(len(self.record['boxes']), 6)
        self.assertFalse(result['approved_for_final_training'])
        self.assertFalse(result['confirmed_negative'])

    def test_unexpected_input_fails_closed(self):
        for modified in ({**self.record, 'index': 3}, {**self.record, 'file': 'other.jpg'},
                         {**self.record, 'boxes': self.record['boxes'][:-1]}):
            with self.assertRaises(ValueError):
                apply_decision(modified, self.decision)


if __name__ == '__main__':
    unittest.main()
