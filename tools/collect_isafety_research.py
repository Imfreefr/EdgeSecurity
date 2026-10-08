"""Public academic clips for private individual review; no training approval."""
import hashlib
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse
import cv2
import requests
from prepare_cctv_v2 import ROOT


def main(offset=0, limit=12, index_only=False):
    if offset < 0 or not 1 <= limit <= 12:
        raise ValueError('Offset must be nonnegative and batch size between 1 and 12')
    suffix = '-complete-index' if index_only else ('' if offset == 0 else f'-offset-{offset}')
    output = ROOT/f'research/isafety-2026-10-08{suffix}'
    if output.exists():
        raise ValueError('Existing research preserved; inspect before resuming')
    session = requests.Session()
    metadata = {}
    for category in ('hazard', 'normal'):
        url = f'https://raw.githubusercontent.com/iSafetyBench/data/main/annotations_{category}.json'
        response = session.get(url, timeout=30)
        response.raise_for_status()
        metadata[category] = response.json()
    response = session.get('https://huggingface.co/api/datasets/raiyaanabdullah/isafety-bench/tree/main',
                           params={'recursive':'true', 'limit':1000}, timeout=30)
    response.raise_for_status()
    entries = response.json()
    page_count = 1
    next_page = response.links.get('next', {}).get('url')
    while next_page:
        parsed = urlparse(next_page)
        if parsed.scheme != 'https' or parsed.hostname != 'huggingface.co' or parsed.path != '/api/datasets/raiyaanabdullah/isafety-bench/tree/main':
            raise ValueError('Unexpected public inventory pagination URL')
        if page_count >= 10:
            raise ValueError('Pagination inspection cap exceeded')
        response = session.get(next_page, timeout=30)
        response.raise_for_status()
        entries.extend(response.json())
        page_count += 1
        next_page = response.links.get('next', {}).get('url')
    files = {row['path']:row for row in entries if row['type']=='file'}
    selected, origins = [], set()
    for category, rows in metadata.items():
        for row in rows:
            if 'forklift' not in json.dumps(row).lower():
                continue
            name = row['video_name']
            origin = name[:11]
            path = category+'/'+name
            if not re.fullmatch(r'[A-Za-z0-9_-]{11}', origin) or origin in origins or path not in files:
                continue
            if files[path]['size'] > 20*1024*1024:
                continue
            origins.add(origin)
            selected.append((path, row, files[path]))
    output.mkdir(parents=True)
    (output/'annotations.json').write_text(json.dumps(metadata), encoding='utf-8')
    (output/'public-tree.json').write_text(json.dumps(list(files.values())), encoding='utf-8')
    (output/'selected-source-index.json').write_text(json.dumps([
        dict(path=path, annotation=annotation, remote=remote) for path, annotation, remote in selected
    ], indent=2), encoding='utf-8')
    if index_only:
        print(json.dumps(dict(source_ids_found=len(selected), inventory_pages=page_count,
                              inventory_complete=True, downloaded=0, approved_images=0)))
        return
    records, total = [], 0
    for path, annotation, remote in selected[offset:offset+limit]:
        url = 'https://huggingface.co/datasets/raiyaanabdullah/isafety-bench/resolve/main/'+path
        target = output/Path(path).name
        digest, size = hashlib.sha256(), 0
        with session.get(url, stream=True, timeout=(15,45)) as download:
            download.raise_for_status()
            with target.open('xb') as stream:
                for chunk in download.iter_content(1024*1024):
                    size += len(chunk)
                    total += len(chunk)
                    if size > 20*1024*1024 or total > 100*1024*1024:
                        raise ValueError('Research download cap reached')
                    digest.update(chunk)
                    stream.write(chunk)
        if size != remote['size'] or digest.hexdigest() != remote['lfs']['oid']:
            raise ValueError('Downloaded clip differs from public LFS inventory')
        cap = cv2.VideoCapture(str(target))
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, count//2)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            raise ValueError('Clip midpoint cannot decode')
        preview = target.with_suffix('.png')
        if not cv2.imwrite(str(preview), frame):
            raise ValueError('Preview write failed')
        records.append(dict(source_url=url, original_video_id=target.stem[:11],
                            annotation=annotation, video_path=str(target), sha256=digest.hexdigest(),
                            path=str(preview), frame_index=count//2, width=frame.shape[1], height=frame.shape[0],
                            status='pending_individual_visual_review', approved_for_training=False,
                            independence_verified=False, synthetic=None, confirmed_negative=False,
                            license_declared='cc-by-nc-sa-4.0', underlying_media_rights='unknown', usage='private'))
        (output/'candidates.ndjson').write_text(''.join(json.dumps(r)+'\n' for r in records), encoding='utf-8')
        print(json.dumps(dict(downloaded=len(records), video=target.name)), flush=True)
    print(json.dumps(dict(downloaded=len(records), source_ids_found=len(selected),
                          tree_scope='complete public tree', inventory_pages=page_count,
                          approved_images=0, verified_groups=0)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--limit', type=int, default=12)
    parser.add_argument('--index-only', action='store_true')
    args = parser.parse_args()
    main(args.offset, args.limit, args.index_only)
