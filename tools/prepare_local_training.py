"""Prepare a hash-bound training/comparison contract; never train or download."""
import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

CLASSES = ("pedestre", "empilhadeira", "operador", "carga")


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_manifest(path):
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf8").splitlines() if line.strip()]
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate image IDs")
    return rows


def dataset_issues(rows):
    issues = []
    selected = [row for row in rows if not row["status"].startswith("excluded")]
    groups = defaultdict(set)
    split_groups = defaultdict(set)
    split_classes = defaultdict(set)
    for row in selected:
        name = row["id"]
        if not row.get("annotation_review_complete") or not row.get("approved_for_training"):
            issues.append(f"{name}: scientific approval incomplete")
        if not row.get("redistribution_rights_verified"):
            issues.append(f"{name}: source rights not verified")
        group, split = row.get("group"), row.get("split")
        if not group or split not in ("train", "val", "test"):
            issues.append(f"{name}: missing group/split")
        groups[group].add(split)
        split_groups[split].add(group)
        if row.get("viewpoint") == "ground_level_close" and split != "train":
            issues.append(f"{name}: close view outside train")
        boxes = row.get("boxes", [])
        if not boxes and not row.get("confirmed_negative"):
            issues.append(f"{name}: empty labels without visually confirmed negative")
        for box in boxes:
            if len(box) != 5:
                issues.append(f"{name}: malformed box")
                continue
            c, x, y, w, h = box
            if c not in range(4) or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (x, y, w, h)):
                issues.append(f"{name}: invalid class/coordinates")
                continue
            if not (w > 0 and h > 0 and x-w/2 >= -1e-9 and y-h/2 >= -1e-9 and x+w/2 <= 1+1e-9 and y+h/2 <= 1+1e-9):
                issues.append(f"{name}: out-of-bounds box")
            split_classes[split].add(c)
    for group, splits in groups.items():
        if len(splits) > 1:
            issues.append(f"group {group}: split leakage")
    if len(groups) < 20:
        issues.append("Need at least 20 independent groups")
    for split in ("val", "test"):
        if len(split_groups[split]) < 3 or not {0, 1} <= split_classes[split]:
            issues.append(f"{split}: need >=3 independent groups and pedestrian/forklift coverage")
    train = [r for r in selected if r.get("split") == "train"]
    if train and sum(r.get("viewpoint") == "ground_level_close" for r in train) / len(train) > .2:
        issues.append("Close views exceed 20 percent of train")
    negatives = sum(bool(r.get("confirmed_negative")) for r in selected)
    if selected and not .05 <= negatives / len(selected) <= .15:
        issues.append("Confirmed negatives outside documented approximately 10 percent target")
    return issues


def prepare(manifest, output, baseline, frozen_test_manifest=None, candidate_weights=None):
    import ultralytics
    manifest, output, baseline = map(Path, (manifest, output, baseline))
    if output.exists():
        raise ValueError("Refusing to overwrite training evidence")
    rows = read_manifest(manifest)
    issues = dataset_issues(rows)
    for row in rows:
        if not Path(row["path"]).is_file() or digest(row["path"]) != row["sha256"]:
            issues.append(f"{row['id']}: image bytes differ from manifest")
    config = Path(ultralytics.__file__).parent / "cfg/models/26/yolo26.yaml"
    if not config.is_file():
        issues.append("Installed Ultralytics lacks YOLO26 architecture")
    weights = Path(candidate_weights) if candidate_weights else None
    if not weights or not weights.is_file():
        issues.append("YOLO26n pretrained weights not supplied locally; no automatic download")
    frozen = None
    if frozen_test_manifest:
        frozen_path = Path(frozen_test_manifest)
        frozen_rows = read_manifest(frozen_path)
        if not frozen_rows or any(r.get("split") != "test" for r in frozen_rows):
            issues.append("Frozen comparison manifest must contain only test images")
        frozen_ids = {r["id"] for r in frozen_rows}
        test_ids = {r["id"] for r in rows if r.get("split") == "test" and not r["status"].startswith("excluded")}
        if frozen_ids != test_ids:
            issues.append("Frozen comparison IDs differ from candidate test split")
        for row in frozen_rows:
            if digest(row["path"]) != row["sha256"]:
                issues.append("Frozen test image hash changed")
        frozen = {"path": str(frozen_path.resolve()), "sha256": digest(frozen_path), "ids": sorted(frozen_ids)}
    else:
        issues.append("Frozen independent comparison manifest not supplied")
    if not baseline.is_file():
        issues.append("edgev1 baseline missing")
    report = {"status": "BLOCKED" if issues else "PREPARED_NOT_EXECUTED", "issues": issues,
              "manifest": str(manifest.resolve()), "manifest_sha256": digest(manifest),
              "records": len(rows), "by_status": dict(Counter(r["status"] for r in rows)),
              "model": {"name": "YOLO26n", "architecture_available": config.is_file(),
                        "architecture_sha256": digest(config) if config.is_file() else None,
                        "ultralytics": ultralytics.__version__, "weights": str(weights) if weights else None,
                        "weights_sha256": digest(weights) if weights and weights.is_file() else None},
              "baseline_sha256": digest(baseline) if baseline.is_file() else None,
              "frozen_test": frozen, "classes": list(CLASSES),
              "training": {"smoke_epochs": 10, "main_epochs": 100, "patience": 20, "imgsz": 640,
                           "seed": 42, "deterministic": True, "pretrained": True},
              "comparison": {"same_frozen_ids": True, "metrics": ["mAP50", "mAP50-95", "precision", "recall", "per_class_recall", "CPU_latency"],
                             "require_same_hardware_preprocessing_thresholds": True},
              "export": {"format": "onnx", "imgsz": 640, "batch": 1, "half": False, "int8": False, "dynamic": False},
              "paid_jobs_started": 0, "training_launched": False, "production_deployed": False,
              "budget": "US$24 cumulative; historical billing reconciliation and explicit paid-job authorization remain mandatory"}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "output", "baseline"):
        parser.add_argument("--"+name, required=True)
    parser.add_argument("--frozen-test-manifest")
    parser.add_argument("--candidate-weights")
    report = prepare(**vars(parser.parse_args()))
    print(json.dumps({"status": report["status"], "issues": len(report["issues"]), "training_launched": False}))
