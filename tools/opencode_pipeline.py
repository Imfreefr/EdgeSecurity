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
    if row.get("approved_for_training") and not is_human_approved(row):
        errs.append("auto/draft counted as approved")
    if row.get("approved_for_training") and not row.get("boxes") and not row.get("confirmed_negative"):
        errs.append("approved empty without negative confirmation")
    return errs


REVIEW_METHODS = {"auto", "draft", "human"}


def is_human_approved(row):
    """So conta como aprovada: flag de revisao + metodo humano + revisor + motivo.
    Proposta automatica ou rascunho nunca passam, mesmo com flags ligadas."""
    return bool(row.get("annotation_review_complete")
                and row.get("review_method") == "human"
                and row.get("reviewer")
                and (row.get("review_reason") or row.get("note")))


def unresolved_ambiguities(row):
    """Pares ambiguos da geometria atual sem resolucao humana vinculada."""
    rep = ambiguity_report(row.get("boxes", []), row.get("width", 0) or 0,
                           row.get("height", 0) or 0)
    done = {r.get("pair_sig") for r in row.get("amb_resolved", [])}
    return [p for p in rep["pairs"] if p["pair_sig"] not in done]


def review_state(row):
    """auto | draft | human-approved | unresolved-ambiguity | rejected."""
    if str(row.get("status", "")).startswith("excluded"):
        return "rejected"
    if is_human_approved(row):
        return "unresolved-ambiguity" if unresolved_ambiguities(row) else "human-approved"
    if row.get("review_method") == "draft":
        return "draft"
    return "auto"


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
            group=group, import_date=date, review_method="draft",
            review_decision=None, reviewer=None))
        n_group += 1
    write_manifest(manifest_out, rows)
    return dict(imported=len(src_paths), group=group, total=len(rows))


# --- 4. duplicatas e inconsistencias ---
def ahash(path, size=8):
    with Image.open(path) as im:
        g = im.convert("L").resize((size, size), Image.Resampling.BILINEAR)
        px = list(g.get_flattened_data() if hasattr(g, "get_flattened_data") else g.getdata())
    avg = sum(px) / len(px)
    bits = "".join("1" if p > avg else "0" for p in px)
    return int(bits, 2)


def _resolve_path(row, root):
    p = Path(row["path"])
    if not p.is_file() and root:
        p = Path(root) / p.name
    return p


def compute_hashes(rows, root=None, cache_path=None):
    """aHash por imagem com cache em disco {id: {file_sha, ahash}}.
    So recalcula o que mudou (file_sha divergente). O(n) decodificacoes."""
    cache = {}
    if cache_path and Path(cache_path).exists():
        try:
            cache = json.loads(Path(cache_path).read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    hashes, hits, miss = {}, 0, 0
    for r in rows:
        entry = cache.get(r["id"])
        if entry and entry.get("file_sha") == r["sha256"] and "ahash" in entry:
            hashes[r["id"]] = entry["ahash"]
            hits += 1
            continue
        try:
            h = ahash(_resolve_path(r, root))
        except Exception:
            continue
        hashes[r["id"]] = h
        cache[r["id"]] = dict(file_sha=r["sha256"], ahash=h)
        miss += 1
    if cache_path:
        atomic_json(cache_path, cache)
    return hashes, dict(cache_hits=hits, computed=miss)


def find_duplicates_scalable(rows, root=None, hamming_max=5, cache_path=None):
    """Exatas por SHA-256 (O(n)) + proximas por aHash so dentro do mesmo
    bucket (width,height): quase-duplicatas reais compartilham dimensoes,
    pares entre buckets sao pulados e reportados. Nunca descarta nada:
    retorna candidatos p/ confirmacao humana."""
    by_sha = {}
    for r in rows:
        by_sha.setdefault(r["sha256"], []).append(r["id"])
    exact = {k: v for k, v in by_sha.items() if len(v) > 1}
    hashes, cache_info = compute_hashes(rows, root, cache_path)
    buckets = {}
    for r in rows:
        if r["id"] in hashes:
            buckets.setdefault((r.get("width"), r.get("height")), []).append(r["id"])
    near, comparisons = [], 0
    for ids in buckets.values():
        for i in range(len(ids)):
            for j in range(i):
                comparisons += 1
                d = bin(hashes[ids[i]] ^ hashes[ids[j]]).count("1")
                if d <= hamming_max:
                    near.append(dict(pair=[ids[j], ids[i]], hamming=d))
    n = len(hashes)
    total_pairs = n * (n - 1) // 2
    return dict(exact=exact, near=near, buckets=len(buckets),
                comparisons=comparisons, skipped_cross_bucket=total_pairs - comparisons,
                **cache_info)


def find_duplicates(rows, root=None, hamming_max=5):
    # compat: lotes pequenos usam o mesmo motor escalavel sem cache
    r = find_duplicates_scalable(rows, root, hamming_max)
    return dict(exact=r["exact"], near=r["near"])


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
    """Exporta SOMENTE revisao humana aprovada sem ambiguidade aberta.
    Auto/draft/rejeitado nunca saem, mesmo com flags ligadas."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "classes.txt").write_text("\n".join(CLASSES) + "\n", encoding="utf-8")
    n, skipped, reasons = 0, 0, Counter()
    for r in rows:
        state = review_state(r)
        if state != "human-approved":
            skipped += 1
            reasons[state] += 1
            continue
        if validate_record(r):
            skipped += 1
            reasons["invalid-geometry"] += 1
            continue
        lines = [f"{c} {x} {y} {w} {h}" for c, x, y, w, h in r.get("boxes", [])]
        (outdir / (r["platform_name"] + image_ext)).write_text(
            ("\n".join(lines) + "\n") if lines else "", encoding="utf-8")
        n += 1
    rep = dict(exported=n, skipped=skipped, classes=list(CLASSES),
               skipped_by_state=dict(reasons))
    atomic_json(outdir / "export-report.json", rep)
    return rep


# --- 2b. validacao de decisao da UI (aprovacao por caixa) ---
def yolo_to_pixels(box, width, height):
    """[cls,xc,yc,w,h] normalizado -> [cls,x1,y1,x2,y2] em pixels."""
    cls, xc, yc, w, h = box
    return [cls, (xc - w / 2) * width, (yc - h / 2) * height,
            (xc + w / 2) * width, (yc + h / 2) * height]


def pixels_to_yolo(cls, x1, y1, x2, y2, width, height):
    """Pixels -> [cls,xc,yc,w,h] normalizado. Levanta ValueError se invalido."""
    box = [cls, ((x1 + x2) / 2) / width, ((y1 + y2) / 2) / height,
           (x2 - x1) / width, (y2 - y1) / height]
    if not valid_yolo_box(box):
        raise ValueError(f"bad pixel box {[cls, x1, y1, x2, y2]}")
    return box


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
        # negativo valido = zero caixas APROVADAS + nota (+ coverage True: nada a cobrir)
        pass
    return kept


def save_decision(outdir, image_row, boxes, note, coverage_complete,
                  amb_resolutions=None):
    """Persiste decisao por imagem; retorna (decision, updated_row).
    amb_resolutions: [{pair: [[cls,xc,yc,w,h]x2], note}] — resolucao EXPLICITA
    de ambiguidade com justificativa; nunca automatica. Nunca escreve no
    manifesto oficial: outdir e isolado."""
    kept = validate_decision(image_row, boxes, note, coverage_complete)
    resolved = []
    for r in amb_resolutions or []:
        pair = r.get("pair")
        if (not isinstance(pair, list) or len(pair) != 2
                or any(not valid_yolo_box(b) for b in pair)):
            raise ValueError(f"bad ambiguity pair {pair}")
        if not r.get("note") or not r["note"].strip():
            raise ValueError("ambiguity resolution needs a note")
        resolved.append(dict(pair_sig=pair_sig(pair), note=r["note"].strip(),
                             date=datetime.now(timezone.utc).isoformat()))
    dec = dict(image_id=image_row["id"], platform_name=image_row["platform_name"],
               source_sha256=image_row["sha256"], boxes=kept, note=note,
               coverage_complete=bool(coverage_complete),
               approved_boxes=len(kept), amb_resolved=resolved,
               review_method="human", reviewer="opencode-studio",
               date=datetime.now(timezone.utc).isoformat())
    atomic_json(Path(outdir) / "decisions" / (image_row["id"] + ".json"), dec)
    updated = dict(image_row)
    updated.update(status="visually_reviewed_pending_final_gates", boxes=kept,
                   proposed_boxes=kept, annotation_review_complete=True,
                   review_reason=note, amb_resolved=resolved,
                   review_method="human", review_decision="approved",
                   reviewer="opencode-studio",
                   review_date=datetime.now(timezone.utc).isoformat(),
                   proposed_overlay_sha256=hashlib.sha256(
                       json.dumps(dec, sort_keys=True).encode()).hexdigest()[:16])
    return dec, updated


def load_working_state(manifest_path, outdir):
    """Retoma estado apos restart: manifesto base (somente leitura) +
    copia de trabalho outdir/review-manifest.ndjson, se existir e integra.
    Entradas obsoletas (sha divergente) sao ignoradas, nunca aplicadas."""
    base = {r["id"]: r for r in read_manifest(manifest_path)}
    working = Path(outdir) / "review-manifest.ndjson"
    resumed = 0
    if working.exists():
        for r in read_manifest(working):
            src = base.get(r["id"])
            if src is not None and r.get("sha256") == src["sha256"]:
                if r != src:
                    resumed += 1
                base[r["id"]] = r
    return base, resumed


# --- seguranca do servidor local: gravacao so da interface autorizada ---
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def check_write_origin(host, origin=None, referer=None):
    """POSTs que alteram dados exigem Host loopback; Origin/Referer, quando
    presentes (navegadores sempre enviam em POST), precisam ser mesma-origem
    loopback. Sem depender de CORS. Retorna (ok, motivo)."""
    from urllib.parse import urlparse
    hostname = (host or "").split("@")[-1].split(":")[0].strip("[]").lower()
    if hostname not in LOOPBACK_HOSTS:
        return False, f"forbidden host {host!r}"
    for label, value in (("origin", origin), ("referer", referer)):
        if not value:
            continue
        try:
            parts = urlparse(value)
        except Exception:
            return False, f"bad {label}"
        if parts.scheme not in ("http", "https"):
            return False, f"bad {label} scheme"
        if (parts.hostname or "").strip("[]").lower() not in LOOPBACK_HOSTS:
            return False, f"foreign {label} {value!r}"
    return True, "local"


# --- 7. aquisicao das 1000 novas imagens (planejamento + splits, sem download) ---
ACQ_SPLITS = dict(train=0.70, val=0.15, test=0.15)
ACQ_MIN_GROUPS = 20


def plan_acquisition(groups):
    """groups: [{group, source, license, viewpoint, environments[], count}].
    So planeja e aponta lacunas; nao baixa nada, nao toca no teste congelado."""
    issues = []
    if len(groups) < ACQ_MIN_GROUPS:
        issues.append(f"need >= {ACQ_MIN_GROUPS} groups, have {len(groups)}")
    total = 0
    envs, cctv = set(), 0
    for g in groups:
        for f in ("group", "source", "license", "viewpoint"):
            if not g.get(f):
                issues.append(f"group {g.get('group', '?')}: missing {f}")
        c = g.get("count", 0)
        total += c
        if c > MAX_PER_GROUP:
            issues.append(f"group {g['group']}: {c} > {MAX_PER_GROUP}")
        envs.update(g.get("environments", []))
        if g.get("viewpoint") == "cftv_elevado":
            cctv += c
    if total > 1000:
        issues.append(f"plan total {total} > 1000")
    return dict(groups=len(groups), planned_images=total,
                distinct_environments=sorted(envs),
                cctv_elevado_images=cctv, issues=issues, ready=not issues)


def check_split_leakage(rows, splits):
    """Grupos independentes presentes em mais de um split = vazamento.
    Retorna {grupo: [splits]} vazio quando limpo."""
    seen = {}
    for r in rows:
        seen.setdefault(r.get("group"), set()).add(splits.get(r["id"]))
    return {g: sorted(s - {None}) for g, s in seen.items() if len(s - {None}) > 1}


def assign_splits(rows, frozen_groups=(), frozen_ids=(), allow_frozen_mix=False,
                  min_val_groups=3, min_test_groups=3):
    """Split ~70/15/15 em NIVEL DE GRUPO: cada grupo independente vai INTEIRO
    para um unico split — nenhum grupo aparece em dois splits (sem vazamento).
    Deterministico (ordena por tamanho/nome, sem sorteio). Grupos congelados
    (teste ja fixado) nunca sao redistribuidos: ficam no teste. Val/teste
    recebem os menores grupos ate a cobertura minima; o resto vai ao maior
    deficit. Grupo sem nome e rejeitado (vazamento se esconde em anonimo)."""
    frozen_g, frozen_i = set(frozen_groups), set(frozen_ids)
    by_group = {}
    for r in rows:
        group = r.get("group")
        if not group:
            raise ValueError(f"row {r.get('id', '?')} without independent group")
        if (group in frozen_g or r["id"] in frozen_i) and not allow_frozen_mix:
            raise ValueError(f"frozen test data in new pool (need explicit protocol): {group}")
        by_group.setdefault(group, []).append(r["id"])
    total = sum(len(v) for v in by_group.values())
    targets = {s: total * ACQ_SPLITS[s] for s in ("train", "val", "test")}
    group_split, counts = {}, {s: 0 for s in targets}
    groups_in = lambda s: sum(1 for g, v in group_split.items() if v == s)
    for group in sorted(frozen_g & set(by_group)):
        group_split[group] = "test"
        counts["test"] += len(by_group[group])
    ordered = sorted((g for g in by_group if g not in group_split),
                     key=lambda g: (len(by_group[g]), g))
    for group in ordered:  # cobertura minima primeiro (menores grupos), resto no deficit
        if groups_in("val") < min_val_groups and (
                groups_in("test") >= min_test_groups or len(by_group[group]) <= total * 0.05 + 1):
            group_split[group] = "val"
        elif groups_in("test") < min_test_groups:
            group_split[group] = "test"
        else:
            group_split[group] = max(targets, key=lambda s: targets[s] - counts[s])
        counts[group_split[group]] += len(by_group[group])
    splits = {i: group_split[g] for g, ids in by_group.items() for i in ids}
    assert not check_split_leakage(rows, splits), "internal leak"
    per_group = {g: dict(n=len(ids), split=group_split[g]) for g, ids in by_group.items()}
    return dict(splits=splits, per_group=per_group,
                ratios={s: round(counts[s] / total, 4) if total else 0 for s in counts})


def validate_acquisition(rows, splits, min_val_groups=3, min_test_groups=3):
    """Confere >=3 grupos em val e teste + cobertura pedestre/empilhadeira no teste."""
    by_split_groups = {}
    for r in rows:
        by_split_groups.setdefault(splits.get(r["id"]), set()).add(r.get("group"))
    issues = []
    if len(by_split_groups.get("val", set())) < min_val_groups:
        issues.append(f"val needs >= {min_val_groups} groups")
    if len(by_split_groups.get("test", set())) < min_test_groups:
        issues.append(f"test needs >= {min_test_groups} groups")
    test_ids = {r["id"] for r in rows if splits.get(r["id"]) == "test"}
    cls = set()
    for r in rows:
        if r["id"] in test_ids:
            cls.update(c for c, *_ in r.get("boxes", []))
    if not {0, 1} <= cls:
        issues.append("test split must contain pedestre(0)+empilhadeira(1)")
    for group, where in sorted(check_split_leakage(rows, splits).items()):
        issues.append(f"leak: group {group} in splits {where}")
    unassigned = [r["id"] for r in rows if r["id"] not in splits]
    if unassigned:
        issues.append(f"{len(unassigned)} images without split")
    return dict(issues=issues, groups_per_split={k: sorted(v) for k, v in by_split_groups.items()},
                valid=not issues)


# --- 8. revisao de duplicatas: tiers, clusters, decisoes persistentes ---
DUPE_TIERS = dict(exact="duplicata exata", near="quase-duplicata", similar="cena parecida")
DUPE_VERDICTS = {"duplicate", "not_duplicate"}


def dupe_tier(entry):
    """entry de find_duplicates_scalable -> (tier, score 0..1)."""
    if "sha256" in entry:
        return "exact", 1.0
    d = entry.get("hamming", 64)
    if d <= 2:
        return "near", 1.0 - d / 64.0
    return "similar", 1.0 - d / 64.0


def cluster_dupe_pairs(pairs):
    """Union-find: pares que compartilham imagens viram um cluster.
    Reduz N comparacoes a poucos grupos p/ revisao."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in pairs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    clusters = {}
    for x in list(parent):
        clusters.setdefault(find(x), []).append(x)
    return [sorted(v) for v in clusters.values()]


def build_dupe_worklist(rows, dup_result):
    """Junta exatas + proximas num worklist com tier, score e origem.
    So propoe; nunca exclui."""
    by_id = {r["id"]: r for r in rows}
    items = []
    for sha, ids in dup_result.get("exact", {}).items():
        ids = sorted(ids)
        for i in range(len(ids)):
            for j in range(i):
                a, b = by_id[ids[j]], by_id[ids[i]]
                items.append(dict(key=f"{a['id']}:::{b['id']}", tier="exact", score=1.0,
                                  a=_dupe_side(a), b=_dupe_side(b)))
    for e in dup_result.get("near", []):
        a, b = by_id[e["pair"][0]], by_id[e["pair"][1]]
        tier, score = dupe_tier(e)
        items.append(dict(key=f"{a['id']}:::{b['id']}", tier=tier, score=round(score, 4),
                          hamming=e.get("hamming"), a=_dupe_side(a), b=_dupe_side(b)))
    clusters = cluster_dupe_pairs([tuple(i["key"].split(":::")) for i in items])
    return dict(items=items, clusters=clusters, tiers={t: DUPE_TIERS[t] for t in DUPE_TIERS})


def _dupe_side(r):
    return dict(id=r["id"], platform_name=r["platform_name"], path=r["path"],
                width=r.get("width"), height=r.get("height"),
                group=r.get("group"), source=r.get("source_dataset", r.get("source", "")),
                status=r.get("status"), nboxes=len(r.get("boxes", [])))


def save_dupe_decision(outdir, key, verdict, note=""):
    if verdict not in DUPE_VERDICTS:
        raise ValueError(f"verdict must be one of {sorted(DUPE_VERDICTS)}")
    if not note or not note.strip():
        raise ValueError("note required")
    dec = dict(key=key, verdict=verdict, note=note,
               date=datetime.now(timezone.utc).isoformat())
    atomic_json(Path(outdir) / "dupe-decisions" / (hashlib.sha256(key.encode()).hexdigest()[:16] + ".json"), dec)
    return dec


def load_dupe_decisions(outdir):
    d = Path(outdir) / "dupe-decisions"
    out = {}
    if d.is_dir():
        for f in d.glob("*.json"):
            try:
                dec = json.loads(f.read_text(encoding="utf-8"))
                out[dec["key"]] = dec
            except Exception:
                continue
    return out


def pending_dupe_items(worklist, decisions):
    return [i for i in worklist["items"] if i["key"] not in decisions]


def flag_ambiguous_boxes(boxes_yolo, width, height, iou_min=0.8):
    """Indices de caixas sobrepostas (compat; prefira ambiguity_report)."""
    return sorted(ambiguity_report(boxes_yolo, width, height, iou_min)["box_idx"])


def pair_sig(pair_boxes):
    """Assinatura estavel de um par p/ vincular resolucoes (ordem-invariante)."""
    norm = [[b[0]] + [round(float(v), 4) for v in b[1:5]] for b in pair_boxes]
    return json.dumps(sorted(norm), separators=(",", ":"))


def ambiguity_report(boxes_yolo, width, height, iou_min=0.8):
    """Pares sobrepostos com motivo por caixa:
    'duplicata' (mesma classe) ou 'pessoa x operador' (0/2). Derivado da
    geometria atual — revisao humana resolve via save_decision, nunca sozinha."""
    px = [yolo_to_pixels(b, width, height) for b in boxes_yolo]
    pairs, reasons = [], {}
    for i in range(len(px)):
        for j in range(i):
            _, x1, y1, x2, y2 = px[i]
            _, u1, v1, u2, v2 = px[j]
            inter = max(0, min(x2, u2) - max(x1, u1)) * max(0, min(y2, v2) - max(y1, v1))
            union = (x2 - x1) * (y2 - y1) + (u2 - u1) * (v2 - v1) - inter
            iou = inter / union if union > 0 else 0
            same = px[i][0] == px[j][0]
            person = {px[i][0], px[j][0]} == {0, 2}
            if iou >= iou_min and (same or person):
                reason = ("duplicata (mesma classe, IoU %.2f)" % iou if same
                          else "pessoa x operador (IoU %.2f)" % iou)
                pairs.append(dict(a=j, b=i, iou=round(iou, 4), reason=reason,
                                  pair_sig=pair_sig([boxes_yolo[j], boxes_yolo[i]])))
                reasons.setdefault(j, reason)
                reasons.setdefault(i, reason)
    return dict(pairs=pairs, box_idx=sorted(reasons), box_reasons=reasons)


# --- 9. aquisicao assistida: gates de fonte/licenca, sem downloads ---
ACQ_LICENSE_ALLOW = {"CC-BY-4.0", "CC-BY-SA-4.0", "CC0-1.0", "ODC-BY-1.0"}
ACQ_VIEWPOINT_BONUS = {"cftv_elevado": 3, "cftv_nivel_rua": 1}


def validate_source(group):
    """Valida UMA fonte candidata: exige origem rastreavel + licenca permitida
    (ou autorizacao explicita). Nao baixa nada."""
    issues = []
    if not group.get("source"):
        issues.append("missing source")
    if not group.get("license"):
        issues.append("missing license")
    elif (group["license"] not in ACQ_LICENSE_ALLOW
          and not group.get("authorization_ref")):
        issues.append(f"license {group['license']} needs authorization_ref")
    if not group.get("viewpoint"):
        issues.append("missing viewpoint")
    return issues


def score_group_priority(group, known_environments):
    """Prioridade: CCTV elevado + ambientes novos. Maior = coletar antes."""
    score = ACQ_VIEWPOINT_BONUS.get(group.get("viewpoint", ""), 0)
    score += sum(1 for e in group.get("environments", []) if e not in known_environments)
    score += len(group.get("lighting", []))
    return score


def acquisition_gates(groups):
    """Checklist bloqueante: downloads so com ready=True + decisao humana
    explicita (a flag nunca e setada aqui)."""
    plan = plan_acquisition(groups)
    issues = list(plan["issues"])
    known, ranked = set(), []
    for g in sorted(groups, key=lambda g: g.get("group", "")):
        for e in validate_source(g):
            issues.append(f"{g.get('group', '?')}: {e}")
        ranked.append((score_group_priority(g, known), g.get("group")))
        known.update(g.get("environments", []))
    ranked.sort(reverse=True)
    cctv = sum(1 for g in groups if g.get("viewpoint") == "cftv_elevado")
    gates = dict(plan_ready=plan["ready"],
                 sources_valid=all(not validate_source(g) for g in groups),
                 groups_20_plus=len(groups) >= ACQ_MIN_GROUPS,
                 cctv_priority=cctv > 0,
                 download_allowed=False)  # sempre False: humano autoriza fora daqui
    gates["ready"] = all([gates["plan_ready"], gates["sources_valid"],
                          gates["groups_20_plus"]]) and not issues
    return dict(gates=gates, issues=issues,
                collect_order=[g for _, g in ranked],
                planned_images=plan["planned_images"])


# --- 10. Ultralytics Platform: export compativel + import com metadados ---
def export_ultralytics(rows, outdir, splits=None, dataset_name="edgesecurity-cctv"):
    """Pacote p/ a Ultralytics Platform (interface principal de anotacao):
    images/{split}/ + labels/{split}/ (.txt YOLO so de human-approved) +
    data.yaml + review-manifest.json (metadados de revisao por imagem).
    Rascunhos/auto saem SEM txt e listados em pending-review. Nao faz upload."""
    outdir = Path(outdir)
    splits = splits or {}
    meta, counts = {}, Counter()
    for r in rows:
        split = splits.get(r["id"], "train")
        if split not in ("train", "val", "test"):
            raise ValueError(f"bad split {split} for {r['id']}")
        src = Path(r["path"])
        if not src.is_file():
            counts["missing-image"] += 1
            continue
        idir = outdir / "images" / split
        ldir = outdir / "labels" / split
        idir.mkdir(parents=True, exist_ok=True)
        ldir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, idir / (r["platform_name"] + src.suffix))
        state = review_state(r)
        if state == "human-approved" and not validate_record(r):
            lines = [f"{c} {x} {y} {w} {h}" for c, x, y, w, h in r.get("boxes", [])]
            (ldir / (r["platform_name"] + ".txt")).write_text(
                ("\n".join(lines) + "\n") if lines else "", encoding="utf-8")
            counts["labeled"] += 1
        else:
            counts["pending-review"] += 1
        meta[r["id"]] = dict(platform_name=r["platform_name"], sha256=r["sha256"],
                             width=r["width"], height=r["height"], split=split,
                             source=r.get("source", ""), license=r.get("license", ""),
                             group=r.get("group", ""), review_state=state,
                             review_method=r.get("review_method"),
                             reviewer=r.get("reviewer"),
                             review_date=r.get("review_date"),
                             review_reason=r.get("review_reason", ""))
    (outdir / "data.yaml").write_text(
        f"path: {outdir.resolve()}\ntrain: images/train\nval: images/val\n"
        f"test: images/test\nnc: 4\nnames: [{', '.join(CLASSES)}]\n",
        encoding="utf-8")
    atomic_json(outdir / "review-manifest.json", meta)
    rep = dict(dataset=dataset_name, images=len(meta), labels=counts["labeled"],
               pending_review=counts["pending-review"],
               missing_images=counts["missing-image"], splits=dict(Counter(
                   m["split"] for m in meta.values())))
    atomic_json(outdir / "export-report.json", rep)
    return rep


def import_ultralytics(package_dir, dest_dir, manifest_out, default_source="",
                       default_license="", default_group=""):
    """Le pacote images/ + labels/ (+ review-manifest.json p/ proveniencia).
    Proveniencia obrigatoria (mapa ou padrao explicito). Tudo entra como DRAFT,
    nunca aprovado — precisa de revisao humana antes de exportar. Linhas
    invalidas rejeitam a imagem inteira, com motivo no relatorio."""
    package_dir, dest_dir, manifest_out = map(Path, (package_dir, dest_dir, manifest_out))
    known = {}
    pmap = package_dir / "review-manifest.json"
    if pmap.is_file():
        known = json.loads(pmap.read_text(encoding="utf-8"))
    if manifest_out.exists():
        existing = read_manifest(manifest_out)
    else:
        existing = []
    have_ids = {r["id"] for r in existing}
    rows, skipped = list(existing), []
    imgs = sorted(p for p in (package_dir / "images").rglob("*")
                  if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
    if not imgs:
        raise ValueError("no images in package")
    dest_dir.mkdir(parents=True, exist_ok=True)
    for src in imgs:
        ident, meta = src.stem, known.get(src.stem, {})
        if ident in have_ids:
            skipped.append(dict(file=src.name, reason="duplicate id"))
            continue
        source = meta.get("source", default_source)
        license = meta.get("license", default_license)
        group = meta.get("group", default_group)
        if not (source and license and group):
            raise ValueError(f"{src.name}: provenance missing (no map, no default)")
        boxes, bad = [], None
        lab = package_dir / "labels" / (src.stem + ".txt")
        if not lab.is_file():  # layout sem subpastas de split
            lab = next((c for c in package_dir.rglob(src.stem + ".txt")), None)
        if lab is not None:
            for ln, line in enumerate(lab.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                parts = line.split()
                try:
                    cls = int(parts[0])
                    box = [cls] + [float(v) for v in parts[1:5]]
                    assert len(parts) == 5
                except Exception:
                    bad = f"line {ln}: malformed"
                    break
                if not valid_yolo_box(box):
                    bad = f"line {ln}: invalid class/geometry"
                    break
                boxes.append(box)
        if bad:
            skipped.append(dict(file=src.name, reason=bad))
            continue
        with Image.open(src) as im:
            im.load()
            w, h = im.size
        dst = dest_dir / src.name
        if dst.exists():
            skipped.append(dict(file=src.name, reason="duplicate file"))
            continue
        shutil.copyfile(src, dst)
        rows.append(dict(
            id=ident, platform_name=ident, path=str(dst.resolve()),
            width=w, height=h, sha256=digest(dst),
            status="pending_individual_visual_review", boxes=boxes,
            approved_for_training=False, annotation_review_complete=False,
            confirmed_negative=False, source=source, license=license,
            group=group, import_date=datetime.now(timezone.utc).date().isoformat(),
            review_method="draft", review_decision=None, reviewer=None,
            imported_from="ultralytics-platform"))
        have_ids.add(ident)
    write_manifest(manifest_out, rows)
    rep = dict(imported=len(rows) - len(existing), skipped=skipped, total=len(rows))
    atomic_json(manifest_out.parent / "import-report.json", rep)
    return rep
