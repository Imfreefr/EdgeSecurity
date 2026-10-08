"""Apply hash-bound manual selection exclusions without deleting source images."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def apply(manifest, decisions, output):
    manifest, output = Path(manifest), Path(output)
    if output.exists():
        raise ValueError('Refusing to overwrite review output')
    decision = json.loads(Path(decisions).read_text(encoding='utf-8'))
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != decision['input_manifest_sha256']:
        raise ValueError('Input manifest changed')
    rows = [json.loads(line) for line in manifest.read_text(encoding='utf-8').splitlines() if line.strip()]
    indexed = {row['id']: row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError('Duplicate record IDs')
    ledger = []
    excluded_ids = {item['id'] for item in decision['exclusions']}
    if len(excluded_ids) != len(decision['exclusions']):
        raise ValueError('Repeated exclusion')
    for item in decision['exclusions']:
        row = indexed[item['id']]
        source = Path(row['path'])
        if not source.is_absolute():
            source = manifest.parent / source
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != row['sha256'] or digest != item['source_sha256']:
            raise ValueError('Source image changed')
        if row['status'] != 'pending_individual_visual_review':
            raise ValueError('Refusing to replace an existing review decision')
        if not item['reason'].strip():
            raise ValueError('Exclusion needs a reason')
        action = item.get('action', 'excluded_editorial_obstruction')
        if action not in ('excluded_editorial_obstruction', 'excluded_confirmed_near_duplicate'):
            raise ValueError('Unsupported exclusion action')
        if action == 'excluded_confirmed_near_duplicate':
            canonical = indexed[item['canonical_id']]
            if canonical['id'] in excluded_ids or canonical['status'].startswith('excluded'):
                raise ValueError('Canonical image is excluded')
            canonical_path = Path(canonical['path'])
            if not canonical_path.is_absolute():
                canonical_path = manifest.parent/canonical_path
            canonical_digest = hashlib.sha256(canonical_path.read_bytes()).hexdigest()
            if canonical_digest != canonical['sha256'] or canonical_digest != item['canonical_sha256']:
                raise ValueError('Canonical image changed')
            if not item['group'].strip() or not item['comparison_evidence'].strip():
                raise ValueError('Manual comparison and grouping evidence required')
            row.update(near_duplicate_of=canonical['id'], group=item['group'],
                       comparison_evidence=item['comparison_evidence'])
            if canonical['group'] not in ('original-origin-grouping-pending', item['group']):
                raise ValueError('Canonical group conflicts with manual comparison')
            canonical['group'] = item['group']
        row.update(status=action, approved_for_training=False,
                   confirmed_negative=False, annotation_review_complete=False,
                   individual_visual_review_date=decision['date'], review_reason=item['reason'])
        ledger.append(dict(item, original_preserved=True, action=row['status']))
    output.mkdir(parents=True)
    (output / 'manifest.ndjson').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
    (output / 'decisions.json').write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding='utf-8')
    report = dict(originals_preserved=len(rows), new_exclusions=len(ledger),
                  by_status=dict(Counter(row['status'] for row in rows)),
                  training_ready=False, platform_mutated=False,
                  input_manifest_sha256=decision['input_manifest_sha256'])
    (output / 'statistics.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'decisions', 'output'):
        parser.add_argument('--' + name, required=True)
    print(json.dumps(apply(**vars(parser.parse_args()))))
