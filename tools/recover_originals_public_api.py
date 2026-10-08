"""Recover owner's PUBLIC dataset read-only, without credentials or remote writes.

No signed URL is logged or persisted. API recovery is not visual approval and
cannot reconstruct missing local corrections or the order of an older NDJSON.
"""
import hashlib
import json
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

import requests
from PIL import Image
from prepare_cctv_v2 import ROOT

BASE = 'https://platform.ultralytics.com'
ROUTE = '/api/datasets/felipe-souza-nascimento/edge-security'
DEST = ROOT/'original-api-recovery-2026-10-08'


def get(route, **params):
    response = requests.get(BASE+route, params=params, timeout=30)
    if response.status_code != 200:
        raise ValueError(f'Public API HTTP {response.status_code}; no authenticated fallback')
    return response.json()


def validate_geometry(item, pixels):
    with Image.open(BytesIO(pixels)) as image:
        image.load()
        if image.size != (item['width'], item['height']):
            raise ValueError('Recovered image dimensions differ from API')
        rgb = image.convert('RGB')
        digest = hashlib.sha256(str(rgb.size).encode()+rgb.tobytes()).hexdigest()
    return digest


def download(item):
    identifier = item['id']
    extension = item['ext']
    if not re.fullmatch(r'[0-9a-f]{24}', identifier) or extension not in {'webp', 'jpg', 'jpeg', 'png'}:
        raise ValueError('Unexpected public image identifier/extension')
    path = DEST/'images'/(identifier+'.'+extension)
    if path.exists():
        pixels = path.read_bytes()
    else:
        url = item.get('imageUrl', '')
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Unexpected full-size URL; thumbnail fallback forbidden')
        partial = path.with_suffix(path.suffix+'.part')
        if partial.exists():
            raise ValueError('Partial recovery file exists; inspect before resuming')
        with requests.get(url, stream=True, timeout=(30, 60)) as response:
            if response.status_code != 200:
                raise ValueError(f'Image download HTTP {response.status_code}; signed URL omitted')
            data = bytearray()
            for chunk in response.iter_content(1024*1024):
                data.extend(chunk)
                if len(data) > 64*1024*1024:
                    raise ValueError('Individual image exceeds recovery size limit')
        pixels = bytes(data)
        if len(pixels) != item['bytes']:
            raise ValueError('Recovered image byte count differs from API')
        validate_geometry(item, pixels)
        with partial.open('xb') as stream:
            stream.write(pixels)
        partial.rename(path)
    if len(pixels) != item['bytes']:
        raise ValueError('Cached recovery byte count differs from API')
    pixel_hash = validate_geometry(item, pixels)
    labels = item.get('labels', [])
    if len(labels) != item['labelCount']:
        raise ValueError('Preview labels are truncated; full labels required')
    boxes = [[label['classId'], *label['bbox']] for label in labels]
    geometry_issues = []
    for index, (cls, x, y, w, h) in enumerate(boxes):
        if cls not in range(4) or not (0 < w <= 1 and 0 < h <= 1
                and x-w/2 >= -0.00002 and y-h/2 >= -0.00002
                and x+w/2 <= 1.00002 and y+h/2 <= 1.00002):
            # Recovery preserves flawed originals; never silently clip or certify.
            geometry_issues.append({'box_index': index, 'reason': 'Original box outside strict bounds or invalid class/extent; inspect before correction'})
    print('Recovered image '+identifier, flush=True)
    return {'id': identifier, 'platform_name': item['name'],
            'path': path.relative_to(DEST).as_posix(), 'width': item['width'],
            'height': item['height'], 'split': item['split'], 'boxes': boxes,
            'sha256': hashlib.sha256(pixels).hexdigest(), 'pixel_sha256': pixel_hash,
            'platform_hash': item['hash'], 'platform_bytes': item['bytes'],
            'source_dataset': BASE+'/felipe-souza-nascimento/datasets/edge-security',
            'source_image_id': identifier, 'is_original': True,
            'status': 'pending_individual_visual_review',
            'approved_for_training': False, 'confirmed_negative': False,
            'original_geometry_issues': geometry_issues,
            'redistribution_rights_verified': False,
            'group': 'original-origin-grouping-pending'}


def identity(dataset):
    return {key: dataset.get(key) for key in
            ['id', 'name', 'visibility', 'imageCount', 'annotationCount', 'classNames', 'splits', 'updatedAt']}


def audit_local():
    """Inventory recovered bytes and duplicate pixels; never merge annotations."""
    manifest = DEST/'manifest.ndjson'
    rows = [json.loads(line) for line in manifest.read_text(encoding='utf-8').splitlines() if line.strip()]
    if len(rows) != 340 or len({row['id'] for row in rows}) != 340:
        raise ValueError('Recovery manifest incomplete')
    groups = defaultdict(list)
    for row in rows:
        path = DEST/row['path']
        pixels = path.read_bytes()
        if hashlib.sha256(pixels).hexdigest() != row['sha256']:
            raise ValueError('Recovered bytes changed before inventory')
        groups[row['pixel_sha256']].append(row)
    duplicates = []
    for digest, members in groups.items():
        if len(members) < 2:
            continue
        duplicates.append({'pixel_sha256': digest,
            'members': [{'id': row['id'], 'name': row['platform_name'], 'split': row['split'], 'boxes': row['boxes']} for row in members],
            'cross_split': len({row['split'] for row in members}) > 1,
            'label_sets_differ': len({json.dumps(row['boxes'], sort_keys=True) for row in members}) > 1,
            'decision': 'pending_individual_label_consolidation_originals_preserved'})
    report = {'images': len(rows), 'identical_pixel_groups': duplicates,
        'unique_decoded_images': len(groups),
        'empty_original_labels': [{'id': row['id'], 'name': row['platform_name'], 'confirmed_negative': False} for row in rows if not row['boxes']],
        'geometry_issues': [{'id': row['id'], 'name': row['platform_name'], 'issues': row['original_geometry_issues']} for row in rows if row['original_geometry_issues']],
        'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
        'visual_review_complete': False, 'training_ready': False,
        'old_index_order_available': False}
    (DEST/'original-inventory.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'recovered_images': len(rows), 'unique_decoded_images': len(groups),
        'identical_pixel_groups': len(duplicates), 'cross_split_duplicate_groups': sum(group['cross_split'] for group in duplicates),
        'empty_original_labels': len(report['empty_original_labels']),
        'images_with_geometry_issues': len(report['geometry_issues'])}), flush=True)


def main():
    schema = get('/openapi.json')
    for route in ['/api/datasets/{owner}/{dataset}', '/api/datasets/{owner}/{dataset}/images']:
        if 'get' not in schema['paths'].get(route, {}):
            raise ValueError('Public read absent from current official API contract')
    before = get(ROUTE)['dataset']
    if before.get('visibility') != 'public' or before['imageCount'] != 340:
        raise ValueError('Dataset visibility/count changed; recovery requires review')
    listing = get(ROUTE+'/images', limit=5000, includeImageUrls='true',
                  includeLabels='true', includeThumbnails='false', sort='oldest')
    items = listing['images']
    if listing.get('hasMore') or listing['total'] != len(items) or len(items) != 340:
        raise ValueError('Incomplete API listing; do not silently recover a subset')
    if len({item['id'] for item in items}) != len(items):
        raise ValueError('Duplicate image identifiers in API listing')
    if any(len(item.get('labels', [])) != item['labelCount'] for item in items):
        raise ValueError('API preview annotations truncated; blocked')
    if sum(item['labelCount'] for item in items) != before['annotationCount']:
        raise ValueError('Annotation count differs from dataset metadata')
    (DEST/'images').mkdir(parents=True, exist_ok=True)
    # Storage downloads only; no key, no paid requests and no dataset mutation.
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(download, items))
    after = get(ROUTE)['dataset']
    if identity(before) != identity(after):
        raise ValueError('Public dataset changed during recovery; final manifest not written')
    (DEST/'manifest.ndjson').write_text(''.join(json.dumps(row, ensure_ascii=False)+'\n' for row in records), encoding='utf-8')
    report = {'status': 'ORIGINAL_PUBLIC_COPY_RECOVERED_NOT_REVIEWED',
              'dataset': identity(before), 'images': len(records),
              'boxes': sum(len(row['boxes']) for row in records),
              'by_class_id': dict(Counter(int(box[0]) for row in records for box in row['boxes'])),
              'by_split': dict(Counter(row['split'] for row in records)),
              'empty_original_labels': sum(not row['boxes'] for row in records),
              'images_with_geometry_issues': sum(bool(row['original_geometry_issues']) for row in records),
              'same_dataset_metadata_before_after': True,
              'old_export_index_order_recovered': False,
              'missing_local_corrections_recovered': False,
              'platform_mutated': False, 'credentials_used': False,
              'visual_review_complete': False, 'training_ready': False}
    (DEST/'recovery-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Do not expose signed storage URLs in Requests exception messages.
        print('Public recovery stopped: '+(str(exc) if isinstance(exc, ValueError) else type(exc).__name__), flush=True)
        raise SystemExit(2)
