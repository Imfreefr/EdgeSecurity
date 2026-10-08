"""Lossless pixel rotation and joint YOLO box transform; not annotation approval."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from PIL import Image


def rotate_box(box):
    cls, cx, cy, width, height = box
    if cls not in (0, 1, 2, 3) or not all(math.isfinite(v) for v in box):
        raise ValueError('Invalid class or coordinates')
    if width <= 0 or height <= 0 or cx-width/2 < 0 or cx+width/2 > 1 or cy-height/2 < 0 or cy+height/2 > 1:
        raise ValueError('Out-of-bounds source box; requires manual correction')
    return [cls, cy, 1-cx, height, width]


def correct(manifest, output, ids, defer_invalid_boxes=False):
    manifest, output = Path(manifest), Path(output)
    if output.exists():
        raise ValueError('Refusing to overwrite review')
    if len(set(ids)) != len(ids):
        raise ValueError('Repeated selection')
    rows = [json.loads(line) for line in manifest.read_text(encoding='utf-8').splitlines() if line.strip()]
    indexed = {r['id']: r for r in rows}
    if len(indexed) != len(rows):
        raise ValueError('Duplicate record IDs')
    prepared = []
    for identity in ids:
        row = indexed[identity]
        if row['status'] != 'pending_individual_visual_review' or row.get('geometry_corrected'):
            raise ValueError('Selection already changed or reviewed')
        path = Path(row['path'])
        if not path.is_absolute():
            path = manifest.parent/path
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Source bytes changed')
        with Image.open(path) as source:
            source.load()
            if source.size != (row['width'], row['height']):
                raise ValueError('Source dimensions changed')
            rotated = source.convert('RGB').transpose(Image.Transpose.ROTATE_90)
        deferred = None
        try:
            boxes = [rotate_box(b) for b in row['boxes']]
        except ValueError as error:
            if not defer_invalid_boxes:
                raise
            # Do not silently clip or reuse invalid labels. Preserve all original
            # boxes in geometry_source and require a complete manual redraw.
            boxes, deferred = [], str(error)
        prepared.append((row, path, rotated, boxes, deferred))
    output.mkdir(parents=True)
    ledger = []
    for row, path, rotated, boxes, deferred in prepared:
        target = output/(row['id']+'-upright.png')
        rotated.save(target)
        preview = rotated.copy()
        preview.thumbnail((768, 1024))
        preview.save(output/(row['id']+'-preview.png'))
        source = dict(path=str(path), sha256=row['sha256'], pixel_sha256=row['pixel_sha256'],
                      width=row['width'], height=row['height'], boxes=row['boxes'])
        row.update(geometry_source=source, path=str(target.resolve()), width=rotated.width,
                   height=rotated.height, boxes=boxes, geometry_corrected='90_degrees_counterclockwise',
                   sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                   pixel_sha256=hashlib.sha256(rotated.tobytes()).hexdigest(),
                   annotation_review_complete=False, approved_for_training=False,
                   confirmed_negative=False)
        if deferred:
            row.update(annotation_redraw_required=True, geometry_box_deferral_reason=deferred)
        ledger.append(dict(id=row['id'], source=source, corrected_path=str(target.resolve()),
                           action='manual_orientation_correction', annotation_approval=False,
                           invalid_boxes_deferred=bool(deferred)))
    (output/'manifest.ndjson').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')
    report = dict(originals_preserved=len(rows), rotations_corrected=len(prepared),
                  annotation_approvals=0, training_ready=False, platform_mutated=False,
                  input_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(), decisions=ledger)
    (output/'geometry-decisions.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return {k: v for k, v in report.items() if k != 'decisions'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--ids', required=True, nargs='+')
    parser.add_argument('--defer-invalid-boxes', action='store_true',
                        help='Preserve invalid originals but leave corrected labels empty pending manual redraw; never a negative')
    print(json.dumps(correct(**vars(parser.parse_args()))))
