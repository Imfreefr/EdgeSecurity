"""Recover a separate public pilot after individual source/overlay review.

Render first. Export requires a separate manual approval file bound to overlay
and source hashes. Never modify previous packages or approve missing originals.
"""
import argparse
import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw
from prepare_cctv_v2 import ROOT
from build_cctv_review import public_records, check_integrity, CLASSES, normalize
from build_collision_supplement import clip_boxes

DEST = ROOT / 'public-recovered-review-2026-10-08'
EXCLUDED = {'public-0_te10': 'Old cargo box covers vehicle door/cab region; driver visibility ambiguous. Retain source, exclude from approved selection.'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records():
    # Previously proposed boxes are reinspection suggestions, not approval.
    items = [dict(record, approved_for_training=False, status='pending_overlay_review',
                 review_date='2026-10-08', review_method='individual_source_and_transformed_overlay_reinspection')
            for record in public_records() if record['id'] not in EXCLUDED]
    for record in items:
        if record['id'] not in {'public-3_te1', 'public-7_te1'}:
            continue
        boxes = [[int(cls), round((x-w/2)*1920), round((y-h/2)*1080),
                  round((x+w/2)*1920), round((y+h/2)*1080)]
                 for cls, x, y, w, h in record['boxes']]
        if record['id'] == 'public-7_te1':
            old = [3, 708, 229, 805, 340]
            if boxes.count(old) != 1:
                raise ValueError('Occluded container correction no longer matches')
            boxes[boxes.index(old)] = [3, 708, 237, 740, 340]
            record['review_reason'] = 'Rear grey container mostly occluded by cab: restrict cargo box to visible left strip; do not label the cab window as cargo.'
        # Remove camera watermark without inventing the cropped-off person extent.
        crop = [0, 120, 1920, 1080]
        path = ROOT/'external/frames'/('recovery-cropped-'+record['id']+'.jpg')
        with Image.open(record['path']) as image:
            image.crop(crop).save(path, quality=95)
        record.update(path=str(path), width=1920, height=960,
                      boxes=normalize(clip_boxes(boxes, crop), 1920, 960),
                      transform={'type': 'frame_extraction_and_crop', 'xyxy_source': crop,
                                 'source_dimensions': [1920, 1080]})
    return items


def render():
    directory = ROOT / 'review/recovery-overlays'
    directory.mkdir(parents=True, exist_ok=True)
    proposed = []
    for record in records():
        with Image.open(record['path']) as source:
            image = source.convert('RGB')
        draw = ImageDraw.Draw(image)
        for cls, x, y, w, h in record['boxes']:
            left, top = (x-w/2)*image.width, (y-h/2)*image.height
            right, bottom = (x+w/2)*image.width, (y+h/2)*image.height
            draw.rectangle((left, top, right, bottom), outline=['#00ff70', '#ffaa00', '#00cfff', '#dd77ff'][int(cls)], width=2)
            draw.text((left, top), str(int(cls)), fill='white', stroke_width=1, stroke_fill='black')
        path = directory / (record['id']+'.png')
        image.save(path)
        proposed.append({'id': record['id'], 'source_sha256': sha(Path(record['path'])),
                         'overlay_sha256': sha(path), 'overlay': str(path),
                         'status': 'pending_overlay_review'})
    (directory/'pending.json').write_text(json.dumps(proposed, indent=2), encoding='utf-8')
    print(json.dumps({'rendered': len(proposed), 'approved': 0, 'directory': str(directory)}))


def export(approval):
    approved = json.loads(Path(approval).read_text(encoding='utf-8'))
    if approved.get('status') != 'approved_individual_overlay_review':
        raise ValueError('Individual overlay approval absent')
    items = records()
    binding = {row['id']: row for row in approved['images']}
    if len(binding) != len(approved['images']) or set(binding) != {row['id'] for row in items}:
        raise ValueError('Approval identifiers do not match recovery selection')
    for record in items:
        row = binding[record['id']]
        overlay = ROOT/'review/recovery-overlays'/(record['id']+'.png')
        if row['source_sha256'] != sha(Path(record['path'])) or row['overlay_sha256'] != sha(overlay):
            raise ValueError('Reviewed pixels changed')
    for record in items:
        record['status'] = 'approved_visual_review'
    integrity = check_integrity(items)
    archive_path = DEST.with_suffix('.zip')
    if DEST.exists() or archive_path.exists():
        raise ValueError('Recovery package exists; refusing overwrite')
    portable = []
    for record in items:
        image_path = DEST/'images/train'/(record['id']+'.jpg')
        label_path = DEST/'labels/train'/(record['id']+'.txt')
        image_path.parent.mkdir(parents=True, exist_ok=True)
        label_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(Path(record['path']).read_bytes())
        label_path.write_text(''.join(str(int(box[0]))+' '+' '.join(f'{v:.8f}' for v in box[1:])+'\n' for box in record['boxes']), encoding='utf-8')
        video = ROOT/'external/videos'/record['video']
        portable.append(dict(record, path=image_path.relative_to(DEST).as_posix(),
                             sha256=sha(image_path), source_video_sha256=sha(video)))
    counts = Counter(int(box[0]) for record in items for box in record['boxes'])
    statistics = {'status': 'RECOVERED_PARTIAL_NOT_FINAL', 'images': len(items),
                  'by_class_id': {str(cls): counts[cls] for cls in CLASSES},
                  'by_camera': dict(Counter(record['group'] for record in items)),
                  'by_split': {'train': len(items), 'val': 0, 'test': 0},
                  'integrity': integrity, 'training_ready': False, 'platform_import_verified': False}
    (DEST/'manifest.ndjson').write_text(''.join(json.dumps(record, ensure_ascii=False)+'\n' for record in portable), encoding='utf-8')
    (DEST/'statistics.json').write_text(json.dumps(statistics, indent=2), encoding='utf-8')
    (DEST/'review-approval.json').write_text(json.dumps(approved, indent=2), encoding='utf-8')
    (DEST/'exclusions.json').write_text(json.dumps(EXCLUDED, indent=2), encoding='utf-8')
    (DEST/'data.yaml').write_text('path: .\ntrain: images/train\n# PARTIAL: no finalized validation/test split\nnames:\n'+''.join(f'  {cls}: {name}\n' for cls, name in CLASSES.items()), encoding='utf-8')
    (DEST/'sources-licenses.json').write_text(json.dumps({
        'source': 'https://data.mendeley.com/datasets/xjmtb22pff/1',
        'authors': 'Önal, Oğuzhan; Dandıl, Emre', 'year': 2024, 'version': 1,
        'doi': '10.17632/xjmtb22pff.1', 'license': 'CC-BY-4.0',
        'license_url': 'https://creativecommons.org/licenses/by/4.0/',
        'license_rechecked': '2026-10-08',
        'modifications': 'Central-frame extraction, documented corridor/floor crops, manual boxes; source clips preserved.',
        'grouping': 'Two previously documented cameras; clips/crops are not independent scenes.'}, ensure_ascii=False, indent=2), encoding='utf-8')
    (DEST/'LEIA-ME.md').write_text('# Recuperação parcial — não treinar\n\n'
        'Pacote separado: não restaura os 340 originais nem todo o suplemento r2. '
        'Somente duas câmeras, sem validação/teste. O recorte negativo de piso não é nova cena. '
        'Revisão individual vinculada aos hashes dos pixels/overlays. '
        'IDs: 0 pedestre, 1 empilhadeira, 2 condutor identificável, 3 carga/caixa/pallet. '
        'Nenhum treino, importação ou endosso dos autores.\n', encoding='utf-8')
    with zipfile.ZipFile(archive_path, 'x', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(DEST.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(DEST).as_posix())
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip():
            raise ValueError('ZIP corrupt')
    archive_path.with_suffix('.sha256').write_text(sha(archive_path)+'  '+archive_path.name+'\n', encoding='utf-8')
    print(json.dumps(statistics))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['render', 'export'])
    parser.add_argument('--approval')
    args = parser.parse_args()
    if args.operation == 'render':
        render()
    elif args.approval:
        export(args.approval)
    else:
        parser.error('export requires --approval')
