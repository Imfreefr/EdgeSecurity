"""Render manual public-footage proposals; export only hash-bound visual approvals."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from PIL import Image, ImageDraw
from build_cctv_review import normalize, check_integrity
from prepare_cctv_v2 import ROOT

BASE = ROOT/'private-github-pilots-2026-10-08'
PROPOSALS = ROOT/'private-white-hall-proposals-r1'


def render():
    if PROPOSALS.exists():
        raise ValueError('Refusing proposal overwrite')
    decision = json.loads(Path(__file__).with_name('private_github_visual_review_2026_10_08.json').read_text())
    candidates = {r['id']:r for r in map(json.loads,(BASE/'candidates.ndjson').read_text().splitlines())}
    records = []
    for name, review in decision['frames'].items():
        row = candidates[name]
        if hashlib.sha256(Path(row['path']).read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Source frame changed')
        boxes = normalize(review['boxes_xyxy'], row['width'], row['height'])
        records.append(dict(row, boxes=boxes, split='train', is_original=False, synthetic=False,
            framing='elevated_medium', status='pending_overlay_review', review_reason=review['note'],
            group='private-white-hall-all-related-origin-pending', independence_verified=False))
    PROPOSALS.mkdir()
    for row in records:
        with Image.open(row['path']) as source:
            image = source.convert('RGB')
        draw = ImageDraw.Draw(image)
        for cls,x,y,w,h in row['boxes']:
            draw.rectangle(((x-w/2)*image.width,(y-h/2)*image.height,
                            (x+w/2)*image.width,(y+h/2)*image.height), outline='#00ff70', width=4)
        image.thumbnail((1024,1024))
        image.save(PROPOSALS/(row['id']+'-overlay.png'))
    (PROPOSALS/'manifest.ndjson').write_text(''.join(json.dumps(r)+'\n' for r in records),encoding='utf-8')
    print(json.dumps({'proposals':len(records),'approved_new_images':0,'output':str(PROPOSALS)}))


def approve(approval_path):
    output = ROOT/'private-white-hall-reviewed-r1'
    if output.exists():
        raise ValueError('Refusing reviewed pilot overwrite')
    approval = json.loads(Path(approval_path).read_text())
    manifest = PROPOSALS/'manifest.ndjson'
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != approval['manifest_sha256']:
        raise ValueError('Proposal metadata changed')
    records = list(map(json.loads,manifest.read_text().splitlines()))
    if set(approval['overlays']) != {r['id'] for r in records}:
        raise ValueError('Approval identities mismatch')
    for row in records:
        overlay = PROPOSALS/(row['id']+'-overlay.png')
        if hashlib.sha256(overlay.read_bytes()).hexdigest() != approval['overlays'][row['id']]:
            raise ValueError('Inspected overlay changed')
        if hashlib.sha256(Path(row['path']).read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Source changed after review')
        row.update(status='approved_visual_review', annotation_review_complete=True,
            individual_visual_review_date=approval['date'], approved_for_training=False,
            inspected_overlay_sha256=approval['overlays'][row['id']])
    check_integrity(records)
    output.mkdir()
    (output/'manifest.ndjson').write_text(''.join(json.dumps(r)+'\n' for r in records),encoding='utf-8')
    shutil.copy2(approval_path, output/'visual-approval.json')
    stats = dict(images=len(records), reviewed_pedestrian_boxes=sum(int(b[0])==0 for r in records for b in r['boxes']), verified_independent_groups=0,
                 usage='private', rights='unknown', final_dataset=False, platform_imported=False)
    (output/'statistics.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
    print(json.dumps(stats))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['render','approve'])
    parser.add_argument('--approval')
    args = parser.parse_args()
    if args.operation == 'render':
        render()
    elif not args.approval:
        parser.error('Explicit visual approval file required')
    else:
        approve(args.approval)
