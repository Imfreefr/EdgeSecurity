"""Testes isolados do pipeline OpenCode: fixtures sinteticas, sem dataset real."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from opencode_pipeline import (
    acquisition_gates, assign_splits, build_dupe_worklist, cluster_dupe_pairs,
    compact_report, compute_hashes, dupe_tier, export_approved,
    find_duplicates, find_duplicates_scalable, find_inconsistencies,
    flag_ambiguous_boxes, import_images, load_dupe_decisions,
    load_working_state, pending_dupe_items, pixels_to_yolo, plan_acquisition,
    preannotate_batch, save_checkpoint, save_decision, save_dupe_decision,
    score_group_priority, validate_acquisition,
    validate_decision, validate_record, validate_source, write_manifest, yolo_to_pixels,
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


class ReviewUITests(unittest.TestCase):
    """P1: coordenadas, persistencia/retomada, erros da UI."""

    def test_yolo_pixel_roundtrip(self):
        for box, W, H in [([0, 0.5, 0.5, 0.5, 0.5], 640, 480),
                          ([3, 0.125, 0.9, 0.25, 0.2], 3840, 2160),
                          ([1, 0.01, 0.01, 0.02, 0.02], 100, 100)]:
            px = yolo_to_pixels(box, W, H)
            back = pixels_to_yolo(px[0], px[1], px[2], px[3], px[4], W, H)
            for a, b in zip(box, back):
                self.assertAlmostEqual(a, b, places=9)

    def test_pixel_box_errors(self):
        with self.assertRaises(ValueError):  # fora da imagem
            pixels_to_yolo(0, -5, 0, 50, 50, 100, 100)
        with self.assertRaises(ValueError):  # classe invalida
            pixels_to_yolo(7, 0, 0, 50, 50, 100, 100)
        with self.assertRaises(ValueError):  # invertida
            pixels_to_yolo(1, 60, 60, 10, 10, 100, 100)

    def test_decision_persist_resume_and_stale(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            man = root / "m.ndjson"
            row = dict(id="i1", platform_name="i1", path="p", width=100, height=80,
                       sha256="s1", status="pending_individual_visual_review",
                       boxes=[[0, 0.5, 0.5, 0.4, 0.4]],
                       annotation_review_complete=False, approved_for_training=False)
            write_manifest(man, [row])
            out = root / "out"
            dec, upd = save_decision(out, row,
                                     [dict(class_id=0, xc=0.5, yc=0.5, w=0.4, h=0.4, approved=True),
                                      dict(class_id=1, xc=0.1, yc=0.1, w=0.1, h=0.1, approved=False)],
                                     note="ok", coverage_complete=True)
            self.assertEqual(dec["approved_boxes"], 1)
            self.assertTrue((out / "decisions" / "i1.json").exists())
            write_manifest(out / "review-manifest.ndjson", [upd])
            state, resumed = load_working_state(man, out)  # restart simulado
            self.assertEqual(resumed, 1)
            self.assertEqual(state["i1"]["boxes"], [[0, 0.5, 0.5, 0.4, 0.4]])
            # copia de trabalho obsoleta (sha divergente) e ignorada
            stale = dict(upd, sha256="adulterado")
            write_manifest(out / "review-manifest.ndjson", [stale])
            state, resumed = load_working_state(man, out)
            self.assertEqual(resumed, 0)
            self.assertEqual(state["i1"]["status"], "pending_individual_visual_review")

    def test_decision_error_cases(self):
        row = dict(id="i", width=100, height=100, sha256="z")
        bad = dict(class_id=0, xc=0.5, yc=0.5, w=0.4, h=0.4, approved=True)
        for boxes, note in [([dict(bad, class_id=9)], "n"),  # classe
                            ([dict(bad, w=9.0)], "n"),        # geometria
                            ([bad], "   "),                   # nota vazia
                            ([dict(bad, xc=float("nan"))], "n")]:
            with self.assertRaises(ValueError):
                validate_decision(row, boxes, note=note, coverage_complete=True)
        with self.assertRaises(ValueError):  # imagem degenerada
            validate_decision(dict(id="i", width=0, height=0, sha256="z"),
                              [], note="n", coverage_complete=True)

    def test_zero_detection_negative(self):
        row = dict(id="i", width=100, height=100, sha256="z")
        self.assertEqual(validate_decision(row, [], note="vazio confirmado",
                                           coverage_complete=True), [])


class DuplicateScaleTests(unittest.TestCase):
    """P2: cache + buckets, equivalencia, sem auto-descarte."""

    def _rows(self, root):
        a = make_img(root / "a.png")
        b = root / "b.png"
        Image.open(a).save(b)
        c = make_img(root / "c.png", size=(128, 128), color=(1, 2, 3))
        def _sz(p):
            with Image.open(p) as im:
                return im.size
        mk = lambda i, p, s: dict(id=i, platform_name=i, path=str(p),
                                  width=_sz(p)[0], height=_sz(p)[1],
                                  sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                                  status="pending_individual_visual_review", boxes=[])
        return [mk("a", a, None), mk("b", b, None), mk("c", c, None)]

    def test_scalable_matches_bruteforce(self):
        with tempfile.TemporaryDirectory() as d:
            rows = self._rows(Path(d))
            brute = find_duplicates(rows)
            fast = find_duplicates_scalable(rows)
            self.assertEqual(brute["exact"], fast["exact"])
            self.assertEqual({tuple(sorted(x["pair"])) for x in brute["near"]},
                             {tuple(sorted(x["pair"])) for x in fast["near"]})
            self.assertIn("a", str(fast["exact"]))  # exata detectada, nada descartado

    def test_cache_reuse_and_buckets(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rows = self._rows(root)
            cache = root / "hashes.json"
            r1 = find_duplicates_scalable(rows, cache_path=cache)
            self.assertEqual(r1["computed"], 3)
            r2 = find_duplicates_scalable(rows, cache_path=cache)
            self.assertEqual(r2["computed"], 0)
            self.assertEqual(r2["cache_hits"], 3)
            # 128x128 cai em outro bucket: comparacoes < total de pares
            self.assertLess(r2["comparisons"], 3)
            self.assertGreaterEqual(r2["skipped_cross_bucket"], 0)


class AcquisitionTests(unittest.TestCase):
    """P3: plano, splits 70/15/15 seed42, guardas."""

    def _pool(self, ngroups=4, per=10):
        rows = []
        for g in range(ngroups):
            for i in range(per):
                cls = 0 if i % 2 == 0 else 1
                rows.append(dict(id=f"g{g}-{i}", platform_name=f"g{g}-{i}", path="p",
                                 width=64, height=48, sha256=f"s{g}-{i}",
                                 status="pending_individual_visual_review",
                                 boxes=[[cls, 0.5, 0.5, 0.4, 0.4]], group=f"g{g}"))
        return rows

    def test_plan_gaps(self):
        groups = [dict(group=f"g{i}", source="s", license="CC-BY-4.0",
                       viewpoint="cftv_elevado", environments=["patio"], count=50)
                  for i in range(20)]
        rep = plan_acquisition(groups)
        self.assertTrue(rep["ready"])
        bad = plan_acquisition(groups[:5] + [dict(group="x", source="", license="",
                                                  viewpoint="rua", environments=[], count=99)])
        self.assertFalse(bad["ready"])
        self.assertTrue(any("50" in e or ">=" in e or "missing" in e for e in bad["issues"]))

    def test_splits_deterministic_no_leak(self):
        rows = self._pool()
        a = assign_splits(rows)
        b = assign_splits(rows)
        self.assertEqual(a["splits"], b["splits"])  # deterministico
        self.assertEqual(len(a["splits"]), len(rows))  # 1 imagem = 1 split
        per = list(a["per_group"].values())[0]
        self.assertEqual((per["train"], per["val"], per["test"]), (7, 1, 2))
        v = validate_acquisition(rows, a["splits"])
        self.assertTrue(v["valid"])

    def test_frozen_guard_and_group_coverage(self):
        rows = self._pool(ngroups=2, per=10)
        with self.assertRaises(ValueError):
            assign_splits(rows, frozen_ids=["g0-0"])
        ok = assign_splits(rows, frozen_ids=["g0-0"], allow_frozen_mix=True)
        self.assertIn("g0-0", ok["splits"])
        v = validate_acquisition(rows, ok["splits"])
        self.assertFalse(v["valid"])  # so 2 grupos em val/teste


class DupeReviewTests(unittest.TestCase):
    """Item 1: tiers, clusters, decisoes, nada auto-excluido."""

    def _row(self, i):
        return dict(id=i, platform_name=i, path=f"/tmp/{i}.jpg", width=64, height=48,
                    sha256="s" + i, status="pending_individual_visual_review",
                    boxes=[], group="g", source_dataset="origem-teste")

    def test_tiers(self):
        self.assertEqual(dupe_tier({"sha256": "x"}), ("exact", 1.0))
        self.assertEqual(dupe_tier({"hamming": 0})[0], "near")
        self.assertEqual(dupe_tier({"hamming": 2})[0], "near")
        self.assertEqual(dupe_tier({"hamming": 3})[0], "similar")
        t, s = dupe_tier({"hamming": 4})
        self.assertEqual(t, "similar")
        self.assertAlmostEqual(s, 1 - 4 / 64)

    def test_clusters(self):
        clusters = cluster_dupe_pairs([("a", "b"), ("b", "c"), ("d", "e")])
        self.assertEqual(sorted(map(sorted, clusters)), [["a", "b", "c"], ["d", "e"]])

    def test_worklist_and_decisions(self):
        rows = [self._row(i) for i in "abc"]
        rows[0] = dict(rows[0], sha256="same")
        rows[1] = dict(rows[1], sha256="same")
        dup = dict(exact={"same": ["a", "b"]}, near=[dict(pair=["b", "c"], hamming=4)])
        wl = build_dupe_worklist(rows, dup)
        self.assertEqual(len(wl["items"]), 2)
        tiers = {i["tier"] for i in wl["items"]}
        self.assertEqual(tiers, {"exact", "similar"})
        self.assertTrue(all(i["a"]["source"] == "origem-teste" for i in wl["items"]))
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            dec = save_dupe_decision(out, "a:::b", "duplicate", note="iguais")
            self.assertEqual(dec["verdict"], "duplicate")
            self.assertEqual(len(pending_dupe_items(wl, load_dupe_decisions(out))), 1)
            with self.assertRaises(ValueError):
                save_dupe_decision(out, "a:::c", "maybe", note="n")
            with self.assertRaises(ValueError):
                save_dupe_decision(out, "a:::c", "duplicate", note="  ")


class AmbiguousAndGatesTests(unittest.TestCase):
    """Itens 3 e 4: caixas ambiguas + gates de aquisicao."""

    def test_flag_ambiguous(self):
        boxes = [[0, 0.5, 0.5, 0.4, 0.4], [0, 0.51, 0.51, 0.4, 0.4],  # mesma classe, IoU alta
                 [1, 0.1, 0.1, 0.1, 0.1]]
        self.assertEqual(flag_ambiguous_boxes(boxes, 100, 100), [0, 1])
        self.assertEqual(flag_ambiguous_boxes([[[0, 0.1, 0.1, 0.1, 0.1]][0]], 100, 100), [])
        # pessoa 0 x operador 2 sobrepostos tambem sinaliza
        self.assertEqual(flag_ambiguous_boxes(
            [[0, 0.5, 0.5, 0.4, 0.4], [2, 0.5, 0.5, 0.4, 0.4]], 100, 100), [0, 1])

    def test_source_gates(self):
        good = dict(group="g1", source="https://exemplo/dataset", license="CC-BY-4.0",
                    viewpoint="cftv_elevado", environments=["patio"], count=50)
        self.assertEqual(validate_source(good), [])
        bad = dict(group="g2", source="", license="todos-direitos", viewpoint="")
        self.assertTrue(len(validate_source(bad)) >= 2)
        auth = dict(group="g3", source="privado", license="proprietaria",
                    authorization_ref="contrato-12", viewpoint="cftv_elevado",
                    environments=["doca"], count=10)
        self.assertEqual(validate_source(auth), [])
        self.assertGreater(score_group_priority(good, set()),
                           score_group_priority(dict(viewpoint="rua", environments=[],
                                                     lighting=[]), {"patio"}))
        groups = [dict(group=f"g{i}", source="s", license="CC-BY-4.0",
                       viewpoint="cftv_elevado", environments=[f"env{i}"], count=50)
                  for i in range(20)]
        g = acquisition_gates(groups)
        self.assertTrue(g["gates"]["ready"])
        self.assertFalse(g["gates"]["download_allowed"])  # humano autoriza fora
        # empate de score: desempate reverso por nome de grupo (deterministico)
        self.assertEqual(g["collect_order"], sorted([f"g{i}" for i in range(20)], reverse=True))
        g2 = acquisition_gates(groups[:3])
        self.assertFalse(g2["gates"]["ready"])


if __name__ == "__main__":
    unittest.main()
