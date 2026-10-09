"""Pipeline local isolado OpenCode: nunca toca checkpoints/manifestos oficiais.

Reutiliza tools/preannotate_local e tools/save_dataset_checkpoint.
Tudo aqui opera sobre COPIAS ou saidas novas em diretorios isolados.
"""
import hashlib
import json
import math
import os
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

CLASSES = ("pedestre", "empilhadeira", "operador", "carga")
STATUSES = {
    "pending_individual_visual_review",
    "pending_redraw_overlay_review",
    "visually_reviewed_pending_final_gates",
    "excluded_exact_duplicate",
    "excluded_confirmed_near_duplicate",
    "excluded_editorial_obstruction",
    "excluded_mobile_eye_level_from_cctv_selection",
}
MAX_PER_GROUP = 50


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for blk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(blk)
    return h.hexdigest()


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def read_manifest(path):
    rows = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate IDs")
    return rows


def write_manifest(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def valid_yolo_box(b):
    try:
        cls, xc, yc, w, h = b
    except Exception:
        return False
    if cls not in (0, 1, 2, 3):
        return False
    if not all(math.isfinite(float(v)) for v in (xc, yc, w, h)):
        return False
    if not (0 <= xc <= 1 and 0 <= yc <= 1 and 0 < w <= 1 and 0 < h <= 1):
        return False
    if not (xc - w / 2 >= 0 and xc + w / 2 <= 1 and yc - h / 2 >= 0 and yc + h / 2 <= 1):
        return False
    return True


def validate_record(row):
    errs = []
    if row.get("status") not in STATUSES:
        errs.append("bad status")
    for b in row.get("boxes", []):
        if not valid_yolo_box(b):
            errs.append(f"bad box {b}")
            break
    if row.get("approved_for_training") and not row.get("annotation_review_complete"):
        errs.append("approved without review")
    if row.get("approved_for_training") and not row.get("boxes") and not row.get("confirmed_negative"):
        errs.append("approved empty without negative confirmation")
    return errs


# --- 1. pre-anotacao em lote (reusa implementacao existente) ---
def preannotate_batch(manifest, model_path, output, limit=20, start=None, confidence=0.15, predictor=None):
    from preannotate_local import run  # lazy: evita ultralytics nos testes puros
    return run(manifest, model_path, output, limit=limit, start=start,
               predictor=predictor, confidence=confidence)


# --- 3. importacao com proveniencia ---
def import_images(src_paths, dest_dir, source, license, group, manifest_out, date=None):
    dest_dir, manifest_out = Path(dest_dir), Path(manifest_out)
    dest_dir.mkdir(parents=True, exist_ok=True)
    existing = []
    if manifest_out.exists():
        existing = read_manifest(manifest_out)
    n_group = sum(1 for r in existing if r.get("group") == group)
    if n_group >= MAX_PER_GROUP:
        raise ValueError(f"group {group} already at {MAX_PER_GROUP}")
    date = date or datetime.now(timezone.utc).date().isoformat()
    rows = list(existing)
    for src in src_paths:
        if n_group >= MAX_PER_GROUP:
            raise ValueError(f"group {group} cap {MAX_PER_GROUP}")
        src = Path(src)
        with Image.open(src) as im:
            im.load()
            w, h = im.size
        dst = dest_dir / src.name
        if dst.exists():
            raise ValueError("Refusing to overwrite import: " + dst.name)
        shutil.copyfile(src, dst)
        rows.append(dict(
            id=dst.stem, platform_name=dst.stem, path=str(dst.resolve()),
            width=w, height=h, sha256=digest(dst),
            status="pending_individual_visual_review", boxes=[],
            approved_for_training=False, annotation_review_complete=False,
            confirmed_negative=False, source=source, license=license,
            group=group, import_date=date))
        n_group += 1
    write_manifest(manifest_out, rows)
    return dict(imported=len(src_paths), group=group, total=len(rows))


# --- 4. duplicatas e inconsistencias ---
def ahash(path, size=8):
    with Image.open(path) as im:
        g = im.convert("L").resize((size, size), Image.Resampling.BILINEAR)
        px = list(g.getdata())
    avg = sum(px) / len(px)
    bits = "".join("1" if p > avg else "0" for p in px)
    return int(bits, 2)


def find_duplicates(rows, root=None, hamming_max=5):
    by_sha = {}
    for r in rows:
        by_sha.setdefault(r["sha256"], []).append(r["id"])
    exact = {k: v for k, v in by_sha.items() if len(v) > 1}
    # ponytail: O(n^2) aHash, suficiente p/ lotes <=50; subir p/ BK-tree se escalar a 1000+
    hashes, near = {}, []
    for r in rows:
        p = Path(r["path"])
        if not p.is_file() and root:
            p = Path(root) / p.name
        try:
            hashes[r["id"]] = ahash(p)
        except Exception:
            continue
    ids = list(hashes)
    for i in range(len(ids)):
        for j in range(i):
            d = bin(hashes[ids[i]] ^ hashes[ids[j]]).count("1")
            if d <= hamming_max:
                near.append(dict(pair=[ids[j], ids[i]], hamming=d))
    return dict(exact=exact, near=near)


def find_inconsistencies(rows):
    out = []
    for r in rows:
        errs = validate_record(r)
        if errs:
            out.append(dict(id=r["id"], errors=errs))
    return out


# --- 5. checkpoints retomaveis + relatorio compacto ---
def save_checkpoint(manifest_path, checkpoint_path):
    from save_dataset_checkpoint import save  # reuso, sem duplicar logica atomica
    return save(manifest_path, checkpoint_path)


def compact_report(manifest_path, checkpoint_path=None):
    rows = read_manifest(manifest_path)
    by_status = dict(Counter(r["status"] for r in rows))
    pend = [r for r in rows if r["status"].startswith("pending")]
    rep = dict(records=len(rows), by_status=by_status,
               first_pending=pend[0]["platform_name"] if pend else None,
               manifest_sha256=digest(manifest_path))
    if checkpoint_path:
        atomic_json(checkpoint_path, dict(rep, manifest=str(Path(manifest_path).resolve())))
    return rep


# --- 6. validacao das 4 classes + exportacao YOLO ---
def validate_manifest(rows):
    return [dict(id=r["id"], errors=e) for r in rows if (e := validate_record(r))]


def export_approved(rows, outdir, image_ext=".txt"):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "classes.txt").write_text("\n".join(CLASSES) + "\n", encoding="utf-8")
    n, skipped = 0, 0
    for r in rows:
        if not r.get("annotation_review_complete"):
            skipped += 1
            continue
        if validate_record(r):
            skipped += 1
            continue
        lines = [f"{c} {x} {y} {w} {h}" for c, x, y, w, h in r.get("boxes", [])]
        (outdir / (r["platform_name"] + image_ext)).write_text(
            ("\n".join(lines) + "\n") if lines else "", encoding="utf-8")
        n += 1
    rep = dict(exported=n, skipped=skipped, classes=list(CLASSES))
    atomic_json(outdir / "export-report.json", rep)
    return rep


# --- 2b. validacao de decisao da UI (aprovacao por caixa) ---
def validate_decision(image_row, boxes, note, coverage_complete):
    """boxes: [{class_id, xc, yc, w, h, approved}]. Retorna boxes YOLO aprovadas."""
    if not note or not note.strip():
        raise ValueError("note required")
    img_w, img_h = image_row["width"], image_row["height"]
    if img_w <= 0 or img_h <= 0:
        raise ValueError("bad image size")
    kept = []
    for b in boxes:
        yolo = [b["class_id"], b["xc"], b["yc"], b["w"], b["h"]]
        if not valid_yolo_box(yolo):
            raise ValueError(f"bad box {yolo}")
        if b.get("approved", True):
            kept.append(yolo)
    if not kept and not coverage_complete is False:
        # negativo exige marcacao explicita de cobertura incompleta=False? nao:
        # negativo valido = zero caixas APROVADAS + nota + coverage True (nada a cobrir)
        pass
    return kept
