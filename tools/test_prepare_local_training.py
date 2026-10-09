import unittest
from prepare_local_training import dataset_issues


class TrainingGateTests(unittest.TestCase):
    def row(self, identity, group, split, cls):
        return dict(id=identity, group=group, split=split, status="visually_reviewed_pending_final_gates",
                    annotation_review_complete=True, approved_for_training=True,
                    redistribution_rights_verified=True, boxes=[[cls, .5, .5, .1, .1]],
                    viewpoint="cftv_elevado", confirmed_negative=False)

    def pool(self):
        rows = [self.row(str(i), f"group-{i//2}", "train" if i<28 else "val" if i<34 else "test", i%2)
                for i in range(40)]
        for i in (0, 2, 4, 6):
            rows[i].update(boxes=[], confirmed_negative=True)
        return rows

    def test_valid_independent_groups(self):
        self.assertEqual(dataset_issues(self.pool()), [])

    def test_group_leakage_rejected(self):
        rows = self.pool()
        rows[-1]["group"] = rows[8]["group"]
        self.assertTrue(any("split leakage" in e for e in dataset_issues(rows)))

    def test_incomplete_negative_and_unapproved_rejected(self):
        rows = self.pool()
        rows[0].update(boxes=[], confirmed_negative=False, annotation_review_complete=False, approved_for_training=False)
        issues = dataset_issues(rows)
        self.assertTrue(any("scientific approval incomplete" in e for e in issues))
        self.assertTrue(any("empty labels" in e for e in issues))

    def test_nonfinite_boxes_and_close_test_rejected(self):
        rows = self.pool()
        rows[-1].update(viewpoint="ground_level_close", boxes=[[0, float('nan'), .5, .1, .1]])
        issues = dataset_issues(rows)
        self.assertTrue(any("invalid class/coordinates" in e for e in issues))
        self.assertTrue(any("close view outside train" in e for e in issues))


if __name__ == '__main__':
    unittest.main()
