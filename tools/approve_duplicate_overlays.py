"""Apply explicit hash-bound visual approvals; never release final training."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def approve(manifest, approvals, output):
    manifest, output = Path(manifest), Path(output)
    if output.exists():
        raise ValueError('Refusing review overwrite')
    decision = json.loads(Path(approvals).read_text(encoding='utf-8'))
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != decision['manifest_sha256']:
        raise ValueError('Proposal manifest changed')
    rows = [json.loads(line) for line in manifest.read_text(encoding='utf-8').splitlines() if line.strip()]
    names = decision['approved_overlays']
    selected = [r for r in rows if r['platform_name'] in names and r['status'] == 'pending_redraw_overlay_review']
    if len(selected) != len(names):
        raise ValueError('Approved identities do not match pending canonical frames')
    for row in selected:
        overlay = manifest.parent/(row['platform_name']+'-redraw.png')
        if hashlib.sha256(overlay.read_bytes()).hexdigest() != names[row['platform_name']]:
            raise ValueError('Visually inspected overlay changed')
        if hashlib.sha256(Path(row['path']).read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Original image changed after review')
        if not row['proposed_coverage_complete']:
            raise ValueError('Cannot approve incomplete coverage')
        row.update(original_boxes=row['boxes'], boxes=row['proposed_boxes'],
                   status='visually_reviewed_pending_final_gates', annotation_review_complete=True,
                   overlay_review_date=decision['date'], approved_for_training=False,
                   inspected_overlay_sha256=names[row['platform_name']])
        if row.get('annotation_redraw_required'):
            row.update(annotation_redraw_required=False,
                       deferred_invalid_annotations_resolved_date=decision['date'])
    output.mkdir(parents=True)
    (output/'manifest.ndjson').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')
    (output/'visual-approvals.json').write_text(json.dumps(decision, indent=2), encoding='utf-8')
    report = dict(originals_preserved=len(rows), approved_annotation_reviews=len(selected),
                  by_status=dict(Counter(r['status'] for r in rows)), training_ready=False,
                  platform_mutated=False, source_manifest_sha256=decision['manifest_sha256'])
    (output/'statistics.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'approvals', 'output'):
        parser.add_argument('--'+name, required=True)
    print(json.dumps(approve(**vars(parser.parse_args()))))
