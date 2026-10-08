"""Isolated exact-duplicate review; originals preserved, no final approval."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from PIL import Image, ImageDraw


def apply_review(manifest, inventory, decisions, output):
    manifest, output = Path(manifest), Path(output)
    if output.exists():
        raise ValueError('Refusing to overwrite an existing review')
    records = [json.loads(line) for line in manifest.read_text(encoding='utf-8').splitlines() if line.strip()]
    by_id = {row['id']: row for row in records}
    if len(by_id) != len(records):
        raise ValueError('Duplicate record IDs')
    groups = json.loads(Path(inventory).read_text(encoding='utf-8'))['identical_pixel_groups']
    decision = json.loads(Path(decisions).read_text(encoding='utf-8'))
    ref_w, ref_h = decision['reference_size']
    if ref_w <= 0 or ref_h <= 0:
        raise ValueError('Invalid reference dimensions')
    if {g['members'][0]['name'] for g in groups} != set(decision['frames']):
        raise ValueError('Manual frame identities do not match exact groups')
    changes, render = {}, []
    for group in groups:
        members = group['members']
        if len(members) != 2 or {m['split'] for m in members} != {'train', 'val'}:
            raise ValueError('Expected one original train/val pair')
        if len({m['name'] for m in members}) != 1:
            raise ValueError('Frame identities disagree')
        pixels = []
        for member in members:
            row = by_id[member['id']]
            if row['platform_name'] != member['name'] or row['split'] != member['split']:
                raise ValueError('Inventory identity changed')
            path = Path(row['path'])
            if not path.is_absolute():
                path = manifest.parent/path
            if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
                raise ValueError('Original bytes changed')
            with Image.open(path) as source:
                rgb = source.convert('RGB')
                if rgb.size != (row['width'], row['height']):
                    raise ValueError('Dimensions changed')
                pixels.append((rgb.size, hashlib.sha256(rgb.tobytes()).hexdigest()))
        if pixels[0] != pixels[1]:
            raise ValueError('Pair pixels differ')
        canonical = next(m for m in members if m['split'] == 'train')
        duplicate = next(m for m in members if m['split'] == 'val')
        frame = decision['frames'][canonical['name']]
        boxes = []
        for cls, left, top, right, bottom in frame['boxes']:
            if cls not in (0, 1, 2, 3) or not 0 <= left < right <= ref_w or not 0 <= top < bottom <= ref_h:
                raise ValueError('Invalid manually redrawn box')
            boxes.append([cls, (left+right)/2/ref_w, (top+bottom)/2/ref_h, (right-left)/ref_w, (bottom-top)/ref_h])
        common = dict(group=decision['group'], viewpoint='ground_level_close',
                      individual_visual_review_date=decision['date'], review_reason=frame['note'],
                      approved_for_training=False, confirmed_negative=False)
        changes[canonical['id']] = dict(common, status='pending_redraw_overlay_review',
            proposed_boxes=boxes, proposed_coverage_complete=frame['coverage_complete'],
            annotation_review_complete=False, canonical_of=[m['id'] for m in members])
        changes[duplicate['id']] = dict(common, status='excluded_exact_duplicate',
            duplicate_of=canonical['id'], annotation_review_complete=False)
        render.append((canonical, frame))
    # Validate all pairs before producing any output. This is a review, not a final dataset.
    output.mkdir(parents=True)
    revised, ledger = [], []
    for row in records:
        updated = dict(row)
        path = Path(row['path'])
        updated['path'] = str(path.resolve() if path.is_absolute() else (manifest.parent/path).resolve())
        updated['source_dataset'] = 'https://platform.ultralytics.com/felipe-souza-nascimento/datasets/edge-security'
        if row['id'] in changes:
            updated.update(changes[row['id']])
            ledger.append(dict(id=row['id'], name=row['platform_name'], source_sha256=row['sha256'],
                action=updated['status'], reason=updated['review_reason'], original_preserved=True,
                canonical_id=updated.get('duplicate_of', row['id'])))
        revised.append(updated)
    for member, frame in render:
        row = next(row for row in revised if row['id'] == member['id'])
        with Image.open(row['path']) as source:
            image = source.convert('RGB').resize((ref_w, ref_h), Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(image)
        for cls, left, top, right, bottom in frame['boxes']:
            color = ['#00ff70', '#ffaa00', '#00cfff', '#dd77ff'][cls]
            draw.rectangle((left, top, right, bottom), outline=color, width=2)
            draw.text((left, top), str(cls), fill=color)
        image.save(output/(member['name']+'-redraw.png'))
    (output/'manifest.ndjson').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in revised), encoding='utf-8')
    (output/'manual-decisions.json').write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding='utf-8')
    with (output/'decisions.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(ledger[0]))
        writer.writeheader()
        writer.writerows(ledger)
    report = dict(originals_preserved=len(records), exact_pairs=len(groups),
                  duplicate_occurrences_excluded=len(groups), redrawn_proposals=len(render),
                  overlay_approvals=0, training_ready=False, platform_mutated=False,
                  by_status=dict(Counter(r['status'] for r in revised)),
                  input_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                  manual_decisions_sha256=hashlib.sha256(Path(decisions).read_bytes()).hexdigest())
    (output/'statistics.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'inventory', 'decisions', 'output'):
        parser.add_argument('--'+name, required=True)
    print(json.dumps(apply_review(**vars(parser.parse_args()))))
