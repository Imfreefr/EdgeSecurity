"""Apply scoped local label corrections and quarantine unsafe training records.

This creates a new review revision. It does not modify originals or pretend
that unknown operator labels have been reviewed.
"""
import csv
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from prepare_cctv_v2 import ROOT, sheet

EMPTY_TARGETS = {6, 31, 51, 53, 72, 84, 117, 137, 167, 179, 190, 239, 278, 315}
SHOP_GROUPS = {'VID-20260825-WA0010', 'VID-20260825-WA0011'}


def recovered_unlabeled_review(manifest, decisions, output):
    """Bind individual decisions to recovered IDs/hashes, never old indices."""
    manifest, output = Path(manifest), Path(output)
    decision = json.loads(Path(decisions).read_text(encoding='utf-8'))
    originals = [json.loads(line) for line in manifest.read_text(encoding='utf-8').splitlines() if line.strip()]
    names = decision['images']
    empty = [record for record in originals if not record['boxes']]
    if len(empty) != 14 or len(names) != 14 or {record['platform_name'] for record in empty} != set(names):
        raise ValueError('Fourteen individually reviewed identities do not match empty originals')
    if output.exists():
        raise ValueError('Review output already exists; refusing overwrite')
    revised, rows = [], []
    for original in originals:
        updated = dict(original, source_dataset='https://platform.ultralytics.com/felipe-souza-nascimento/datasets/edge-security')
        if original['platform_name'] in names:
            path = manifest.parent/original['path']
            if hashlib.sha256(path.read_bytes()).hexdigest() != original['sha256']:
                raise ValueError('Reviewed original bytes changed')
            reason = decision['reason']+' '+names[original['platform_name']]
            updated.update(status=decision['decision'], group=decision['group'],
                source_dataset='https://platform.ultralytics.com/felipe-souza-nascimento/datasets/edge-security',
                individual_visual_review_date=decision['date'],
                individual_visual_review_method=decision['method'],
                review_reason=reason, approved_for_training=False, confirmed_negative=False)
            rows.append({'id': original['id'], 'name': original['platform_name'],
                'source_sha256': original['sha256'], 'action': decision['decision'],
                'reason': reason, 'original_preserved': True, 'confirmed_negative': False,
                'approved_for_training': False})
        updated['path'] = str((manifest.parent/original['path']).resolve())
        revised.append(updated)
    output.mkdir(parents=True)
    (output/'manifest.ndjson').write_text(''.join(json.dumps(row, ensure_ascii=False)+'\n' for row in revised), encoding='utf-8')
    (output/'review-decisions.json').write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding='utf-8')
    with (output/'decisions.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report = {'originals_preserved': len(originals), 'individually_reviewed_unlabeled': len(rows),
              'excluded_from_selection': len(rows), 'confirmed_negatives': 0,
              'originals_still_pending_individual_review': len(originals)-len(rows),
              'training_ready': False, 'platform_mutated': False,
              'source_manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest()}
    (output/'statistics.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


def revise(item):
    updated = {**item, 'boxes': [box.copy() for box in item['boxes']],
               'approved_for_final_training': False, 'confirmed_negative': False,
               'collision_review_status': 'pending_individual_label_review',
               'collision_review_reason': 'Not promoted by contact-sheet triage'}
    index = item['index']
    if item['group'] in SHOP_GROUPS:
        updated.update(collision_review_status='excluded_viewpoint',
                       collision_review_reason='Eye-level footage excluded from CCTV selection; targets present')
    if index in EMPTY_TARGETS:
        if item['boxes']:
            raise ValueError(f'Expected empty original labels at index {index}')
        updated.update(collision_review_status='excluded_unlabeled_targets',
                       collision_review_reason='Visible targets with missing labels; NOT a confirmed negative')
    if index == 7:
        operators = [box for box in updated['boxes'] if int(box[0]) == 2]
        if len(operators) != 1:
            raise ValueError('Unexpected original annotation for IMG_0346')
        operators[0][0] = 0
        updated.update(collision_review_status='partial_correction_pending_occupant',
                       collision_review_reason='Outside pedestrian reclassified 2 to 0; seated occupant needs contextual review')
    if index == 26:
        updated.update(collision_review_status='excluded_ambiguous_operator',
                       collision_review_reason='Single frame shows seated person reaching down, not visibly conducting; no speculative relabeling')
    return updated


def main():
    originals = json.loads((ROOT / 'review/originals.json').read_text(encoding='utf-8'))
    output = ROOT / 'collision-review'
    output.mkdir(exist_ok=True)
    revised = [revise(item) for item in originals]
    (output / 'originals-revised.json').write_text(
        json.dumps(revised, ensure_ascii=False, indent=2), encoding='utf-8')
    rows = [{'index': item['index'], 'file': item['file'],
             'action': item['collision_review_status'],
             'reason': item['collision_review_reason'],
             'final_training_approved': item['approved_for_final_training'],
             'confirmed_negative': item['confirmed_negative'],
             'labels_changed': item['boxes'] != originals[item['index']]['boxes'],
             'original_preserved': True} for item in revised]
    with (output / 'decisions.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    patches = [{'index': 7, 'original_file': originals[7]['file'],
                'before': originals[7]['boxes'], 'after': revised[7]['boxes'],
                'complete_annotation_review': False,
                'reason': revised[7]['collision_review_reason']}]
    (output / 'label-patches.json').write_text(json.dumps(patches, indent=2), encoding='utf-8')
    sheet([revised[7], revised[26]], output / 'targeted-corrections.jpg', columns=2)
    stats = {'originals': len(originals), 'changed_labels_records': 1,
             'unlabeled_target_records_excluded': len(EMPTY_TARGETS),
             'final_training_approved': 0,
             'by_status': dict(Counter(item['collision_review_status'] for item in revised)),
             'original_preserved': True}
    (output / 'original-statistics.json').write_text(json.dumps(stats, indent=2), encoding='utf-8')
    print(json.dumps(stats, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recovered-manifest')
    parser.add_argument('--decisions')
    parser.add_argument('--output')
    args = parser.parse_args()
    if args.recovered_manifest:
        if not args.decisions or not args.output:
            parser.error('Recovered review requires --decisions and --output')
        recovered_unlabeled_review(args.recovered_manifest, args.decisions, args.output)
    else:
        main()
