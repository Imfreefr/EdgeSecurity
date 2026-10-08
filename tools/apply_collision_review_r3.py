"""Write an isolated review revision, never overwrite originals or approve guesses."""
import csv
import json
from pathlib import Path
from prepare_cctv_v2 import ROOT


def apply_decision(record, decision):
    if record['file'] != decision['file']:
        raise ValueError('Original filename does not match manual review')
    revised = {**record, 'boxes': [box.copy() for box in record['boxes']],
               'collision_review_status': decision['decision'],
               'collision_review_reason': decision['reason'],
               'approved_for_final_training': False, 'confirmed_negative': False,
               'individual_visual_review_date': '2026-10-07'}
    if decision.get('remove_class3_cones'):
        cones = [box for box in revised['boxes'] if box[0] == 3]
        if len(cones) != 4 or record['index'] != 2:
            raise ValueError('Unexpected cone annotations; do not generalize this correction')
        revised['boxes'] = [box for box in revised['boxes'] if box[0] != 3]
        revised['removed_boxes'] = cones
    return revised


def main():
    decisions = json.loads(Path(__file__).with_name('collision_review_r3.json').read_text(encoding='utf-8'))
    previous = ROOT/'collision-review'/'originals-revised.json'
    records = json.loads(previous.read_text(encoding='utf-8'))
    output = ROOT/'collision-review-r3'
    if output.exists():
        raise ValueError('Review revision already exists; refusing overwrite')
    rows, revised = [], []
    for record in records:
        decision = decisions['originals'].get(str(record['index']))
        updated = apply_decision(record, decision) if decision else record
        revised.append(updated)
        if decision:
            rows.append({'kind': 'original', 'id': str(record['index']),
                         'file': record['file'], 'decision': decision['decision'],
                         'reason': decision['reason'], 'original_preserved': True,
                         'approved_for_training': False})
    for stem, decision in decisions['public_candidates'].items():
        rows.append({'kind': 'public_candidate', 'id': stem, 'file': stem+'.jpg',
                     'decision': decision['decision'], 'reason': decision['reason'],
                     'original_preserved': True, 'approved_for_training': False})
    output.mkdir()
    (output/'originals-revised.json').write_text(json.dumps(revised, indent=2, ensure_ascii=False), encoding='utf-8')
    (output/'review-decisions.json').write_text(json.dumps(decisions, indent=2, ensure_ascii=False), encoding='utf-8')
    with (output/'decisions.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({'individual_frames_reviewed': len(rows), 'new_training_images_approved': 0,
                      'false_cargo_boxes_removed': 4, 'originals_preserved': True,
                      'review_revision': str(output)}, indent=2))


if __name__ == '__main__':
    main()
