"""Testes isolados do pipeline OpenCode: fixtures sinteticas, sem dataset real."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from opencode_pipeline import (
    compact_report, export_approved, find_duplicates, find_inconsistencies,
    import_images, preannotate_batch, save_checkpoint, validate_decision,
    validate_record, write_manifest,
)


def make_img(path, size=(64, 48), color=(200, 100, 50)):
    Image.new("RGB", size, color).save(path)
    return path


class PipelineTests(unittest.TestCase):
    def test_import_checkpoint_report(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            s1, s2 = make_img(root / "a.jpg"), make_img(root / "b.jpg", color=(10, 20, 30))
            man = root / "imp.ndjson"
            r = import_images([s1, s2], root / "store", "fonte-teste", "CC-BY-4.0",
                              "grupo-teste-1", man)
            self.assertEqual(r["imported"], 2)
            rows = [json.loads(l) for l in man.read_text(encoding="utf-8").splitlines()]
            self.assertTrue(all(x["license"] == "CC-BY-4.0" for x in rows))
            cp = root / "resume.json"
            save_checkpoint(man, cp)
            rep = compact_report(man, root / "compact.json")
            self.assertEqual(rep["records"], 2)
            self.assertIn("pending_individual_visual_review", rep["by_status"])

    def test_duplicates_and_inconsistencies(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a = make_img(root / "a.png")
            b = root / "b.png"
            Image.open(a).save(b)  # byte-identico? PNG deterministico aqui
            c = make_img(root / "c.png", color=(1, 2, 3))
            rows = [dict(id="a", platform_name="a", path=str(a),
                         sha256=hashlib.sha256(a.read_bytes()).hexdigest(),
                         status="pending_individual_visual_review", boxes=[]),
                    dict(id="b", platform_name="b", path=str(b),
                         sha256=hashlib.sha256(b.read_bytes()).hexdigest(),
                         status="pending_individual_visual_review", boxes=[]),
                    dict(id="c", platform_name="c", path=str(c),
                         sha256=hashlib.sha256(c.read_bytes()).hexdigest(),
                         status="pending_individual_visual_review",
                         boxes=[[9, 0.5, 0.5, 0.2, 0.2]])]
            dup = find_duplicates(rows)
            self.assertIn("a", str(dup["exact"]) + str(dup["near"]))
            inc = find_inconsistencies(rows)
            self.assertEqual([x["id"] for x in inc], ["c"])
            self.assertTrue(validate_record(rows[0]) == [])

    def test_preannotate_wrapper_never_approves(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            img = make_img(root / "s.png", size=(32, 32))
            man = root / "m.ndjson"
            write_manifest(man, [dict(id="s", platform_name="s", path=str(img),
                                      width=32, height=32,
                                      sha256=hashlib.sha256(img.read_bytes()).hexdigest(),
                                      status="pending_individual_visual_review")])
            model = root / "m.pt"
            model.write_bytes(b"fake")
            rep = preannotate_batch(man, model, root / "out",
                                    predictor=lambda p: [[0, 0.9, 2, 2, 20, 20]])
            self.assertEqual(rep["approved"], 0)
            art = json.loads((root / "out" / "s.json").read_text(encoding="utf-8"))
            self.assertFalse(art["approved_for_training"])

    def test_validate_export_and_decision(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rows = [dict(id="ok", platform_name="ok", path="x", width=10, height=10,
                         sha256="x", status="visually_reviewed_pending_final_gates",
                         boxes=[[0, 0.5, 0.5, 0.5, 0.5]],
                         annotation_review_complete=True, approved_for_training=False),
                    dict(id="bad", platform_name="bad", path="x", width=10, height=10,
                         sha256="y", status="pending_individual_visual_review",
                         boxes=[[1, 9.0, 0.5, 0.2, 0.2]],
                         annotation_review_complete=True, approved_for_training=False)]
            rep = export_approved(rows, root / "yolo")
            self.assertEqual(rep["exported"], 1)
            self.assertTrue((root / "yolo" / "classes.txt").exists())
            row = dict(id="i", width=100, height=100, sha256="z")
            kept = validate_decision(row, [dict(class_id=2, xc=0.5, yc=0.5, w=0.2, h=0.2,
                                                approved=True),
                                           dict(class_id=0, xc=0.1, yc=0.1, w=0.1, h=0.1,
                                                approved=False)],
                                     note="confere", coverage_complete=True)
            self.assertEqual(kept, [[2, 0.5, 0.5, 0.2, 0.2]])
            with self.assertRaises(ValueError):
                validate_decision(row, [], note=" ", coverage_complete=True)


if __name__ == "__main__":
    unittest.main()
