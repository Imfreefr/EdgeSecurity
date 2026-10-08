"""Validate final-TCC criteria and freeze a grouped YOLO package. Never train/upload.

Input: reviewed manifest(s), plus an explicit independent-scene/rights registry.
An unsuccessful check never produces a final ZIP or changes input annotations.
"""
import argparse
import hashlib
import json
import random
import shutil
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from PIL import Image
from build_cctv_review import check_integrity, CLASSES


def original(record):
    return record.get('is_original', record['id'].startswith('original-'))


def close_view(record):
    return (record.get('framing', '').startswith('close_')
            or record.get('viewpoint') == 'ground_level_close')


def rights_errors(group, name, usage):
    """Unknown rights are recorded, not invented; known prohibitions still apply."""
    errors = []
    if not group.get('source_url'):
        errors.append('Missing source provenance: '+name)
    if usage == 'private':
        if group.get('training_allowed') is False or group.get('cloud_training_allowed') is False:
            errors.append('Source prohibits intended training: '+name)
        if group.get('access_restricted') is True:
            errors.append('Source requires unresolved access permission: '+name)
    elif usage == 'redistributable':
        if not (group.get('training_allowed') is True and group.get('redistribution_allowed') is True
                and group.get('license_url') and group.get('source_url')):
            errors.append('Missing verified rights: '+name)
    else:
        raise ValueError('Unknown dataset usage policy')
    return errors


def usage_report(records, registry, usage):
    groups = registry.get('groups', {})
    unverified = sorted({r['group'] for r in records
        if not (groups.get(r['group'], {}).get('training_allowed') is True
                and groups.get(r['group'], {}).get('redistribution_allowed') is True
                and groups.get(r['group'], {}).get('license_url'))})
    return {'usage': usage, 'required_platform_visibility': 'private' if usage == 'private' else None,
            'public_distribution_permitted_by_this_workflow': usage != 'private',
            'groups_without_verified_training_and_redistribution_rights': unverified,
            'notice': 'Private selection does not establish permission; original rights declarations are preserved.'}


def copy_image(record, directory):
    """Preserve decoded pixels and actual encoding; never disguise WebP as JPEG."""
    with Image.open(record['path']) as image:
        suffix = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp'}.get(image.format)
    if suffix is None:
        raise ValueError('Unsupported final image encoding: '+record['id'])
    relative = f"images/{record['split']}/{record['id']}{suffix}"
    destination = directory/relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(record['path'], destination)
    return relative, destination


def plan_split(records):
    groups = defaultdict(list)
    for record in records:
        groups[record['group']].append(record)
    eligible = [group for group, items in groups.items()
                if all(not original(item) and not close_view(item) for item in items)
                and {0, 1} <= {int(box[0]) for item in items for box in item['boxes']}]
    if len(eligible) < 6:
        raise ValueError('Need six new elevated groups containing both target classes for val/test')
    rng = random.Random(42)
    rng.shuffle(eligible)
    # Choose three independent groups per holdout near 15% of total images.
    target = len(records) * .15
    assignment = {group: 'train' for group in groups}
    for split in ('test', 'val'):
        selected = []
        while len(selected) < 3:
            slots = 3-len(selected)
            remaining_target = target-sum(len(groups[group]) for group in selected)
            group = min(eligible, key=lambda g: abs(len(groups[g])-remaining_target/slots))
            eligible.remove(group)
            selected.append(group)
            assignment[group] = split
    return [{**record, 'split': assignment[record['group']]} for record in records]


def inspect(records, registry, usage='redistributable'):
    if usage not in {'private', 'redistributable'}:
        raise ValueError('Unknown dataset usage policy')
    errors = []
    source_groups = registry.get('groups', {})
    if not records:
        return ['Empty dataset']
    for record in records:
        group = source_groups.get(record['group'], {})
        if not original(record) and not record.get('framing', '').startswith('elevated_'):
            errors.append('New image not reviewed as elevated CCTV: '+record['id'])
        if not (group.get('independence_verified') is True and group.get('grouping_evidence')):
            errors.append('Unverified independent scene: '+record['group'])
        errors.extend(rights_errors(group, record['group'], usage))
    new = [record for record in records if not original(record)]
    new_groups = Counter(record['group'] for record in new)
    verified_groups = [group for group in new_groups
                       if source_groups.get(group, {}).get('independence_verified') is True
                       and source_groups.get(group, {}).get('grouping_evidence')]
    if len(verified_groups) < 20:
        errors.append(f'Only {len(verified_groups)}/20 verified independent new scene groups')
    if len(new) > 1000:
        errors.append('More than 1000 new images')
    if any(count > 50 for count in new_groups.values()):
        errors.append('More than 50 new images in a group')
    if sum(close_view(record) for record in records)/len(records) > .20:
        errors.append('Close views exceed 20%')
    if any(record.get('synthetic') is True for record in records):
        errors.append('Synthetic imagery prohibited')
    negatives = sum(not record['boxes'] and record.get('confirmed_negative') for record in records)
    if not .05 <= negatives/len(records) <= .15:
        errors.append('Confirmed negatives outside approximately 10% (accepted band 5–15%)')
    for split, fraction in (('train', .70), ('val', .15), ('test', .15)):
        items = [record for record in records if record['split'] == split]
        if abs(len(items)/len(records)-fraction) > .05:
            errors.append('Split not within five percentage points: '+split)
        if split == 'train':
            continue
        if len({record['group'] for record in items}) < 3:
            errors.append('Fewer than three independent groups in '+split)
        if any(original(record) or close_view(record) for record in items):
            errors.append('Holdout must be new elevated CCTV only: '+split)
        if any(source_groups.get(record['group'], {}).get('seen_by_edgev1') is not False for record in items):
            errors.append('Unknown/baseline-exposed scene in '+split)
        if not {0, 1} <= {int(box[0]) for record in items for box in record['boxes']}:
            errors.append('Missing pedestrian/forklift class in '+split)
    try:
        check_integrity(records)
    except (ValueError, OSError, KeyError) as exc:
        errors.append(str(exc))
    return sorted(set(errors))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', action='append', required=True)
    parser.add_argument('--registry', required=True)
    parser.add_argument('--usage', choices=['private', 'redistributable'], default='private',
                        help='Private permits recorded unknown rights; redistribution requires verified permissions')
    parser.add_argument('--assign-splits', action='store_true')
    parser.add_argument('--output', help='New directory; omitted means read-only check')
    args = parser.parse_args()
    records = []
    for filename in args.manifest:
        manifest = Path(filename).resolve()
        for line in manifest.read_text(encoding='utf-8-sig').splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            path = Path(record['path'])
            record['path'] = str(path if path.is_absolute() else manifest.parent/path)
            records.append(record)
    registry = json.loads(Path(args.registry).read_text(encoding='utf-8-sig'))
    if args.assign_splits:
        records = plan_split(records)
    errors = inspect(records, registry, usage=args.usage)
    policy = usage_report(records, registry, args.usage)
    if errors:
        print(json.dumps({'status': 'NOT_FINAL', 'images': len(records), 'blockers': errors, 'usage_policy': policy}, indent=2))
        raise SystemExit(2)
    if not args.output:
        print(json.dumps({'status': 'LOCAL_FINAL_CRITERIA_PASS', 'images': len(records), 'platform_verified': False, 'usage_policy': policy}))
        return
    if any(not record['id'].replace('-', '').replace('_', '').isalnum() for record in records):
        raise ValueError('Unsafe/nonportable image identifier')
    output = Path(args.output).resolve()
    if output.exists():
        raise ValueError('Output must be a new directory; do not overwrite frozen versions')
    archive_path = output.with_suffix('.zip')
    if archive_path.exists():
        raise ValueError('ZIP already exists; refusing overwrite')
    output.mkdir(parents=True)
    portable = []
    for record in records:
        relative, destination = copy_image(record, output)
        label = output/f"labels/{record['split']}/{record['id']}.txt"
        label.parent.mkdir(parents=True, exist_ok=True)
        label.write_text(''.join(str(int(box[0]))+' '+' '.join(f'{value:.8f}' for value in box[1:])+'\n'
                                 for box in record['boxes']), encoding='utf-8')
        portable.append({**record, 'path': relative,
                         'sha256': hashlib.sha256(destination.read_bytes()).hexdigest()})
    yaml = 'path: .\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n'
    yaml += ''.join(f'  {key}: {value}\n' for key, value in CLASSES.items())
    (output/'data.yaml').write_text(yaml, encoding='utf-8')
    (output/'manifest.ndjson').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in portable), encoding='utf-8')
    shutil.copy2(args.registry, output/'sources-licenses.json')
    (output/'usage-policy.json').write_text(json.dumps(policy, indent=2), encoding='utf-8')
    counts = Counter(int(box[0]) for record in records for box in record['boxes'])
    stats = {'status': 'LOCAL_FINAL_CRITERIA_PASS', 'images': len(records),
             'by_class_id': {str(key): counts[key] for key in CLASSES},
             'by_split': dict(Counter(record['split'] for record in records)),
             'by_group': dict(Counter(record['group'] for record in records)),
             'platform_import_verified': False, 'seed': 42, 'usage_policy': policy}
    (output/'statistics.json').write_text(json.dumps(stats, indent=2), encoding='utf-8')
    with zipfile.ZipFile(archive_path, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(output).as_posix())
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    archive_path.with_suffix('.sha256').write_text(digest+'  '+archive_path.name+'\n', encoding='utf-8')
    print(json.dumps(stats, indent=2))


if __name__ == '__main__':
    main()
