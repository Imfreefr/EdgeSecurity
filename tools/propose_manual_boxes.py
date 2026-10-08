"""Render manually specified boxes for individual, hash-bound overlay review."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw


def propose(manifest, decisions, output):
    manifest, output = Path(manifest), Path(output)
    if output.exists():
        raise ValueError('Refusing to overwrite proposals')
    decision = json.loads(Path(decisions).read_text(encoding='utf-8'))
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != decision['manifest_sha256']:
        raise ValueError('Input manifest changed')
    rows = [json.loads(line) for line in manifest.read_text(encoding='utf-8').splitlines() if line.strip()]
    indexed = {row['id']: row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError('Duplicate image IDs')
    width, height = decision['reference_size']
    if width <= 0 or height <= 0:
        raise ValueError('Invalid reference size')
    prepared = []
    for identity, item in decision['frames'].items():
        row = indexed[identity]
        if row['status'] != 'pending_individual_visual_review':
            raise ValueError('Image already reviewed')
        path = Path(row['path'])
        if not path.is_absolute():
            path = manifest.parent/path
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Source image changed')
        with Image.open(path) as source:
            source.load()
            if source.size != (row['width'], row['height']):
                raise ValueError('Dimensions changed')
            if source.width*height != source.height*width:
                raise ValueError('Reference aspect ratio differs')
            preview = source.convert('RGB').resize((width, height), Image.Resampling.LANCZOS)
        boxes = []
        for cls, left, top, right, bottom in item['boxes']:
            if cls not in (0, 1, 2, 3) or not all(math.isfinite(v) for v in (left, top, right, bottom)):
                raise ValueError('Invalid class or nonfinite box')
            if not 0 <= left < right <= width or not 0 <= top < bottom <= height:
                raise ValueError('Invalid box bounds')
            boxes.append([cls, (left+right)/2/width, (top+bottom)/2/height,
                          (right-left)/width, (bottom-top)/height])
        if not boxes or not item['note'].strip():
            raise ValueError('This command requires positive boxes and a reason')
        prepared.append((row, item, preview, boxes))
    output.mkdir(parents=True)
    for row, item, preview, boxes in prepared:
        draw = ImageDraw.Draw(preview)
        for cls, left, top, right, bottom in item['boxes']:
            color = ['#00ff70', '#ffaa00', '#00cfff', '#dd77ff'][cls]
            draw.rectangle((left, top, right, bottom), outline=color, width=2)
            draw.text((left, top), str(cls), fill=color)
        preview.save(output/(row['platform_name']+'-redraw.png'))
        row.update(status='pending_redraw_overlay_review', proposed_boxes=boxes,
                   proposed_coverage_complete=item['coverage_complete'],
                   annotation_review_complete=False, approved_for_training=False,
                   group=decision['group'], viewpoint=decision['viewpoint'],
                   split='train', individual_visual_review_date=decision['date'],
                   review_reason=item['note'], confirmed_negative=False)
    (output/'manifest.ndjson').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')
    (output/'manual-decisions.json').write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding='utf-8')
    return dict(proposed_images=len(prepared), originals_preserved=len(rows), training_ready=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'decisions', 'output'):
        parser.add_argument('--'+name, required=True)
    print(json.dumps(propose(**vars(parser.parse_args()))))
