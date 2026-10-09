"""Testes isolados do pipeline OpenCode: fixtures sinteticas, sem dataset real."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from opencode_pipeline import (
    acquisition_gates, ambiguity_report, assign_splits, build_dupe_worklist,
    check_split_leakage, check_write_origin, cluster_dupe_pairs,
    compact_report, compute_hashes, dupe_tier, export_approved,
    export_ultralytics, find_duplicates, find_duplicates_scalable,
    find_inconsistencies, flag_ambiguous_boxes, import_images,
    import_ultralytics, is_human_approved, load_dupe_decisions,
    load_working_state, pair_sig, pending_dupe_items, pixels_to_yolo,
    plan_acquisition, preannotate_batch, read_manifest, review_state,
    save_checkpoint, save_decision, save_dupe_decision, score_group_priority,
    unresolved_ambiguities, validate_acquisition, validate_decision,
    validate_record, validate_source, write_manifest, yolo_to_pixels,
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
                         annotation_review_complete=True, approved_for_training=False,
                         review_method="human", reviewer="humano-teste",
                         review_reason="confere"),
                    # flags ligadas mas metodo auto: NAO pode exportar (regressao)
                    dict(id="auto", platform_name="auto", path="x", width=10, height=10,
                         sha256="w", status="visually_reviewed_pending_final_gates",
                         boxes=[[0, 0.5, 0.5, 0.5, 0.5]],
                         annotation_review_complete=True, approved_for_training=True,
                         review_method="auto", reviewer=None),
                    dict(id="bad", platform_name="bad", path="x", width=10, height=10,
                         sha256="y", status="pending_individual_visual_review",
                         boxes=[[1, 9.0, 0.5, 0.2, 0.2]],
                         annotation_review_complete=True, approved_for_training=False)]
            rep = export_approved(rows, root / "yolo")
            self.assertEqual(rep["exported"], 1)
            self.assertTrue((root / "yolo" / "classes.txt").exists())
            self.assertEqual(rep["skipped_by_state"].get("auto"), 2)  # auto + sem metodo
            self.assertTrue(is_human_approved(rows[0]))
            self.assertFalse(is_human_approved(rows[1]))
            self.assertEqual(review_state(rows[0]), "human-approved")
            self.assertEqual(review_state(rows[1]), "auto")
            self.assertIn("auto/draft counted as approved",
                          validate_record(rows[1]))
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
        rows = self._pool(ngroups=20, per=5)
        a = assign_splits(rows)
        b = assign_splits(rows)
        self.assertEqual(a["splits"], b["splits"])  # deterministico
        self.assertEqual(len(a["splits"]), len(rows))
        # REGRESSAO: nenhum grupo em dois splits (nivel de grupo)
        self.assertEqual(check_split_leakage(rows, a["splits"]), {})
        for g, info in a["per_group"].items():
            got = {a["splits"][r["id"]] for r in rows if r["group"] == g}
            self.assertEqual(len(got), 1, g)  # grupo inteiro num split so
        self.assertAlmostEqual(sum(a["ratios"].values()), 1.0, places=3)
        v = validate_acquisition(rows, a["splits"])
        self.assertTrue(v["valid"], v["issues"])

    def test_split_leak_detector_catches_manual_mix(self):
        rows = self._pool(ngroups=2, per=4)
        bad = {r["id"]: ("train" if i % 2 == 0 else "test")
               for i, r in enumerate(rows)}  # alternado = vaza por grupo
        leak = check_split_leakage(rows, bad)
        self.assertEqual(set(leak), {"g0", "g1"})
        v = validate_acquisition(rows, bad)
        self.assertFalse(v["valid"])
        self.assertTrue(any("leak" in e for e in v["issues"]))

    def test_frozen_guard_and_group_coverage(self):
        rows = self._pool(ngroups=8, per=10)
        with self.assertRaises(ValueError):
            assign_splits(rows, frozen_groups=["g0"])
        with self.assertRaises(ValueError):
            assign_splits(rows, frozen_ids=["g0-0"])
        ok = assign_splits(rows, frozen_groups=["g0"], allow_frozen_mix=True)
        self.assertEqual(ok["per_group"]["g0"]["split"], "test")  # congelado fica
        v = validate_acquisition(rows, ok["splits"])
        self.assertTrue(v["valid"], v["issues"])
        tiny = self._pool(ngroups=2, per=10)
        v2 = validate_acquisition(tiny, assign_splits(tiny)["splits"])
        self.assertFalse(v2["valid"])  # so 2 grupos em val/teste

    def test_row_without_group_rejected(self):
        rows = self._pool(ngroups=2, per=2)
        del rows[0]["group"]
        with self.assertRaises(ValueError):
            assign_splits(rows)


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
        rep = ambiguity_report(boxes, 100, 100)
        self.assertEqual(rep["box_idx"], [0, 1])
        self.assertTrue(rep["box_reasons"][0].startswith("duplicata"))
        self.assertEqual(len(rep["pairs"]), 1)
        self.assertIn("pair_sig", rep["pairs"][0])
        # assinatura ordem-invariante
        self.assertEqual(pair_sig([boxes[0], boxes[1]]), pair_sig([boxes[1], boxes[0]]))
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


class WhiteScreenRegressionTests(unittest.TestCase):
    """Regressao tela branca: clique deve chamar openImg (nunca window.open nativo)."""

    def _page(self):
        import opencode_review_server as srv
        return srv.PAGE

    def test_no_native_open_collision(self):
        import re
        html = self._page()
        self.assertIn("function openImg(", html)
        self.assertNotRegex(html, r'onclick="open\(')
        self.assertNotRegex(html, r'function open\(')
        self.assertNotRegex(html, r'[^a-zA-Z]open\(ROWS')
        self.assertIn("IMG.onerror", html)  # falha de carga exibe erro, sem branca
        # controles vivos: sem onclick no container + nomes legiveis + drag/alcas
        self.assertNotRegex(html, r'class="box[^"]*" onclick')
        for name in ("pedestre", "empilhadeira", "operador", "carga"):
            self.assertIn(name, html)
        for fn in ("boxAt", "cornerAt", "markDirty", "onmousedown", "onmousemove",
                   "onmouseup", "updateDirty"):
            self.assertIn(fn, html)

    def test_routes_serve_ten_images(self):
        import threading
        import urllib.request
        from http.server import HTTPServer
        import opencode_review_server as srv
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rows = []
            for i in range(10):
                # inclui vertical grande p/ cobrir dimensionamento
                size = (600, 900) if i % 2 else (64, 48)
                p = make_img(root / f"img{i}.png", size=size)
                rows.append(dict(id=f"img{i}", platform_name=f"img{i}", path=str(p),
                                 width=size[0], height=size[1],
                                 sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                                 status="pending_individual_visual_review",
                                 boxes=[[i % 4, 0.5, 0.5, 0.4, 0.4]]))
            man = root / "m.ndjson"
            write_manifest(man, rows)
            srv.Handler.rows, _ = load_working_state(man, root / "out")
            srv.Handler.outdir = root / "out"
            srv.Handler.outdir.mkdir(exist_ok=True)
            srv.Handler.dupes = None
            httpd = HTTPServer(("127.0.0.1", 0), srv.Handler)
            port = httpd.server_address[1]
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{port}"
            try:
                page = urllib.request.urlopen(base + "/").read().decode("utf-8")
                self.assertIn("openImg", page)
                q = json.loads(urllib.request.urlopen(base + "/api/queue").read())
                self.assertEqual(len(q["rows"]), 10)
                for r in q["rows"]:
                    resp = urllib.request.urlopen(base + "/img?id=" + r["id"])
                    self.assertEqual(resp.status, 200)
                    self.assertGreater(int(resp.headers["Content-Length"]), 0)
                # navega+decide em todas sem erro
                for r in q["rows"]:
                    body = json.dumps({"image_id": r["id"], "boxes": [], "note": "n",
                                       "coverage_complete": True}).encode()
                    req = urllib.request.Request(
                        base + "/api/decide", data=body,
                        headers={"Content-Type": "application/json"}, method="POST")
                    self.assertTrue(json.loads(urllib.request.urlopen(req).read())["ok"])
                q2 = json.loads(urllib.request.urlopen(base + "/api/queue").read())
                self.assertEqual(q2["decided"], 10)
            finally:
                httpd.shutdown()
                httpd.server_close()


class AmbiguityResolutionTests(unittest.TestCase):
    """Resolucao explicita de ambiguidade: com nota, persistente, sem auto."""

    def _row(self):
        return dict(id="i", platform_name="i", path="p", width=100, height=100,
                    sha256="s", status="pending_individual_visual_review",
                    boxes=[[0, 0.5, 0.5, 0.4, 0.4], [0, 0.52, 0.52, 0.4, 0.4]],
                    annotation_review_complete=False, approved_for_training=False)

    def test_save_with_resolution_persists(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            row = self._row()
            man = root / "m.ndjson"
            write_manifest(man, [row])
            out = root / "out"
            res = [dict(pair=[row["boxes"][0], row["boxes"][1]],
                        note="duplicata real, mantidas as duas")]
            dec, upd = save_decision(out, row, [], note="vazio", coverage_complete=True,
                                     amb_resolutions=res)
            self.assertEqual(len(dec["amb_resolved"]), 1)
            self.assertEqual(dec["amb_resolved"][0]["note"], "duplicata real, mantidas as duas")
            self.assertIn("pair_sig", dec["amb_resolved"][0])
            write_manifest(out / "review-manifest.ndjson", [upd])
            state, resumed = load_working_state(man, out)  # reload
            self.assertEqual(resumed, 1)
            self.assertEqual(state["i"]["amb_resolved"], dec["amb_resolved"])

    def test_resolution_errors_and_no_auto(self):
        row = self._row()
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            # sem nota -> erro; par invalido -> erro
            with self.assertRaises(ValueError):
                save_decision(out, row, [], note="n", coverage_complete=True,
                              amb_resolutions=[dict(pair=[row["boxes"][0], row["boxes"][1]],
                                                    note="  ")])
            with self.assertRaises(ValueError):
                save_decision(out, row, [], note="n", coverage_complete=True,
                              amb_resolutions=[dict(pair=[[9, 0.5, 0.5, 0.2, 0.2],
                                                           row["boxes"][1]], note="n")])
            # sem resolucoes -> nada resolvido (troca de classe nao resolve sozinha)
            dec, _ = save_decision(out, row, [], note="n", coverage_complete=True)
            self.assertEqual(dec["amb_resolved"], [])

    def test_unresolved_ambiguity_blocks_export(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            row = dict(self._row(), review_method="human", reviewer="hum",
                       review_reason="ok", annotation_review_complete=True)
            self.assertEqual(review_state(row), "unresolved-ambiguity")
            self.assertEqual(len(unresolved_ambiguities(row)), 1)
            rep = export_approved([row], root / "yolo")
            self.assertEqual(rep["exported"], 0)
            self.assertEqual(rep["skipped_by_state"].get("unresolved-ambiguity"), 1)
            # com resolucao humana vinculada -> exporta
            sig = pair_sig([row["boxes"][0], row["boxes"][1]])
            row2 = dict(row, amb_resolved=[dict(pair_sig=sig, note="ok",
                                                date="2026-10-09")])
            self.assertEqual(review_state(row2), "human-approved")
            rep2 = export_approved([row2], root / "yolo2")
            self.assertEqual(rep2["exported"], 1)


class WriteOriginTests(unittest.TestCase):
    """Bloqueante 3: gravacao so da interface local."""

    def test_pure_origin_checks(self):
        self.assertTrue(check_write_origin("127.0.0.1:8787")[0])
        self.assertTrue(check_write_origin("localhost", "http://localhost:8787/")[0])
        self.assertTrue(check_write_origin("127.0.0.1", None, None)[0])  # curl/scripts
        self.assertFalse(check_write_origin("192.168.1.5:8787")[0])
        self.assertFalse(check_write_origin("example.com")[0])
        self.assertFalse(check_write_origin("127.0.0.1:8787", "https://evil.test/")[0])
        self.assertFalse(check_write_origin("127.0.0.1:8787", None, "http://evil.test/x")[0])
        self.assertFalse(check_write_origin("", "http://127.0.0.1:8787/")[0])

    def test_live_rejects_foreign_origin(self):
        import threading
        import urllib.request
        from http.server import HTTPServer
        import opencode_review_server as srv
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = make_img(root / "a.png", size=(64, 48))
            row = dict(id="a", platform_name="a", path=str(p), width=64, height=48,
                       sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                       status="pending_individual_visual_review", boxes=[])
            man = root / "m.ndjson"
            write_manifest(man, [row])
            srv.Handler.rows, _ = load_working_state(man, root / "out")
            srv.Handler.outdir = root / "out"
            srv.Handler.outdir.mkdir(exist_ok=True)
            srv.Handler.dupes = None
            httpd = HTTPServer(("127.0.0.1", 0), srv.Handler)
            port = httpd.server_address[1]
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{port}"
            body = json.dumps({"image_id": "a", "boxes": [], "note": "n",
                               "coverage_complete": True}).encode()

            def post(origin=None):
                req = urllib.request.Request(
                    base + "/api/decide", data=body,
                    headers={"Content-Type": "application/json",
                             **({"Origin": origin} if origin else {})}, method="POST")
                try:
                    return urllib.request.urlopen(req).status, None
                except urllib.request.HTTPError as e:
                    return e.code, e.read().decode("utf-8", "replace")

            code, _ = post("https://evil.test/")
            self.assertEqual(code, 403)
            self.assertFalse((root / "out" / "decisions" / "a.json").exists())
            code, _ = post("http://127.0.0.1:%d/" % port)
            self.assertEqual(code, 200)
            code, _ = post(None)  # sem Origin (curl/scripts locais)
            self.assertEqual(code, 200)
            httpd.shutdown()
            httpd.server_close()


class UltralyticsIOTests(unittest.TestCase):
    """Export compativel + import como draft (nunca aprovado)."""

    def _human_row(self, i, img, group="g-ultra"):
        return dict(id=f"u{i}", platform_name=f"u{i}", path=str(img),
                    width=64, height=48, sha256=hashlib.sha256(img.read_bytes()).hexdigest(),
                    status="visually_reviewed_pending_final_gates",
                    boxes=[[0, 0.5, 0.5, 0.4, 0.4]], approved_for_training=False,
                    annotation_review_complete=True, confirmed_negative=False,
                    source="origem-teste", license="CC-BY-4.0", group=group,
                    review_method="human", reviewer="hum", review_reason="ok")

    def test_export_only_human_and_roundtrip_is_draft(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            img = make_img(root / "src.png")
            rows = [self._human_row(0, img),
                    dict(self._human_row(1, img), id="u1", platform_name="u1",
                         review_method="draft", reviewer=None, review_reason="")]
            splits = {"u0": "train", "u1": "val"}
            rep = export_ultralytics(rows, root / "pkg", splits)
            self.assertEqual(rep["labels"], 1)
            self.assertEqual(rep["pending_review"], 1)
            self.assertTrue((root / "pkg" / "labels" / "train" / "u0.txt").exists())
            self.assertFalse((root / "pkg" / "labels" / "val" / "u1.txt").exists())
            yaml = (root / "pkg" / "data.yaml").read_text(encoding="utf-8")
            self.assertIn("nc: 4", yaml)
            meta = json.loads((root / "pkg" / "review-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["u0"]["review_state"], "human-approved")
            self.assertEqual(meta["u0"]["license"], "CC-BY-4.0")
            # round-trip: importado volta como draft e NAO exporta sem revisao
            rep2 = import_ultralytics(root / "pkg", root / "store", root / "imp.ndjson")
            self.assertEqual(rep2["imported"], 2)  # u0 rotulada + u1 sem txt
            back = read_manifest(root / "imp.ndjson")
            self.assertTrue(all(r["review_method"] == "draft" for r in back))
            self.assertTrue(all(r["status"] == "pending_individual_visual_review" for r in back))
            self.assertEqual(export_approved(back, root / "yolo")["exported"], 0)

    def test_import_rejects_bad_labels_and_missing_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            imgs = root / "pkg" / "images"
            labs = root / "pkg" / "labels"
            imgs.mkdir(parents=True)
            labs.mkdir(parents=True)
            make_img(imgs / "good.png")
            (labs / "good.txt").write_text("0 0.5 0.5 0.4 0.4\n", encoding="utf-8")
            make_img(imgs / "bad.png")
            (labs / "bad.txt").write_text("9 0.5 0.5 0.4 0.4\n", encoding="utf-8")
            with self.assertRaises(ValueError):  # sem proveniencia
                import_ultralytics(root / "pkg", root / "s1", root / "m1.ndjson")
            rep = import_ultralytics(root / "pkg", root / "s2", root / "m2.ndjson",
                                     default_source="s", default_license="CC-BY-4.0",
                                     default_group="g")
            self.assertEqual(rep["imported"], 1)
            self.assertEqual(rep["skipped"][0]["file"], "bad.png")
            back = read_manifest(root / "m2.ndjson")
            self.assertEqual(back[0]["boxes"], [[0, 0.5, 0.5, 0.4, 0.4]])


if __name__ == "__main__":
    unittest.main()
