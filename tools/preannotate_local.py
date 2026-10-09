"""Resume hash-bound edgev1 proposals; never modify or approve the source manifest."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import time

from PIL import Image, ImageDraw, ImageFont

CLASSES = ('pedestre', 'empilhadeira', 'operador', 'carga')
ALIASES = ({'pessoa', 'person', 'human', 'pedestre'},
           {'máquina', 'maquina', 'machine', 'forklift', 'empilhadeira'},
           {'operador', 'operator'}, {'objeto', 'object', 'carga', 'pallet'})


def digest(path):
    with Path(path).open('rb') as stream:
        h = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', encoding='utf8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def validate_names(names):
    names = dict(enumerate(names)) if isinstance(names, list) else names
    if set(names) != {0, 1, 2, 3} or any(
            str(names[i]).lower().strip().lstrip('.') not in ALIASES[i] for i in range(4)):
        raise ValueError('Model does not preserve the four required class IDs: ' + str(names))


def normalized_boxes(detections, width, height):
    boxes, issues = [], []
    for index, detection in enumerate(detections):
        cls, confidence, left, top, right, bottom = detection
        values = (cls, confidence, left, top, right, bottom)
        if (not all(math.isfinite(v) for v in values) or cls not in range(4)
                or not 0 <= confidence <= 1
                or not 0 <= left < right <= width or not 0 <= top < bottom <= height):
            issues.append({'detection': index, 'reason': 'invalid class, confidence or geometry'})
            continue
        boxes.append({'class_id': int(cls), 'class_name': CLASSES[int(cls)],
                      'confidence': confidence,
                      'xyxy': [left, top, right, bottom],
                      'yolo': [int(cls), (left + right) / (2 * width),
                               (top + bottom) / (2 * height),
                               (right - left) / width, (bottom - top) / height]})
    return boxes, issues


def overlap_flags(boxes):
    flags = []
    for i, a in enumerate(boxes):
        for j, b in enumerate(boxes[:i]):
            x1, y1, x2, y2 = a['xyxy']
            u1, v1, u2, v2 = b['xyxy']
            intersection = max(0, min(x2, u2) - max(x1, u1)) * max(0, min(y2, v2) - max(y1, v1))
            union = (x2-x1)*(y2-y1) + (u2-u1)*(v2-v1) - intersection
            iou = intersection / union
            if iou >= .8 and (a['class_id'] == b['class_id'] or {a['class_id'], b['class_id']} == {0, 2}):
                flags.append({'detections': [j, i], 'iou': iou,
                              'reason': 'duplicate box' if a['class_id'] == b['class_id'] else 'conflicting person classes'})
    return flags


def run(manifest, model_path, output, limit=20, start=None, predictor=None, confidence=.15):
    if not 1 <= limit <= 50 or not 0 < confidence <= 1:
        raise ValueError('Require batch size 1..50 and confidence (0,1]')
    manifest, model_path, output = map(lambda p: Path(p).resolve(), (manifest, model_path, output))
    rows = [json.loads(line) for line in manifest.read_text(encoding='utf8').splitlines() if line.strip()]
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate IDs in input manifest')
    pending = [r for r in rows if r['status'].startswith('pending')]
    if start:
        positions = [i for i, r in enumerate(pending) if r['platform_name'] == start]
        if len(positions) != 1:
            raise ValueError('Start must identify one pending image')
        pending = pending[positions[0]:]
    selected = pending[:limit]
    if not selected:
        raise ValueError('No pending images')
    for row in selected:
        if any(Path(str(row[key])).name != str(row[key]) or str(row[key]) in ('', '.', '..')
               for key in ('id', 'platform_name')):
            raise ValueError('Unsafe artifact identity')
    config = dict(schema_version=1, manifest=str(manifest), manifest_sha256=digest(manifest),
                  model=str(model_path), model_sha256=digest(model_path),
                  image_ids=[r['id'] for r in selected], confidence=confidence, imgsz=640,
                  classes=list(CLASSES), device='cpu', training_ready=False)
    output.mkdir(parents=True, exist_ok=True)
    lock = output / '.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.close(fd)
    try:
        config_path = output / 'batch.json'
        if config_path.exists():
            if json.loads(config_path.read_text(encoding='utf8')) != config:
                raise ValueError('Resume inputs differ from frozen batch')
        else:
            atomic_json(config_path, config)
        byte_counts = Counter(r['sha256'] for r in rows)
        pixel_counts = Counter(r.get('pixel_sha256') for r in rows if r.get('pixel_sha256'))
        completed, cached = [], 0
        started = time.perf_counter()
        for row in selected:
            artifact = output / (row['id'] + '.json')
            if artifact.exists():
                item = json.loads(artifact.read_text(encoding='utf8'))
                if (item['source_sha256'] != row['sha256'] or digest(row['path']) != row['sha256']
                        or digest(item['overlay']) != item['overlay_sha256']
                        or item['model_sha256'] != config['model_sha256']):
                    raise ValueError('Cached evidence changed')
                completed.append(item)
                cached += 1
                continue
            if digest(row['path']) != row['sha256']:
                raise ValueError('Original changed: ' + row['platform_name'])
            with Image.open(row['path']) as source:
                source.load()
                if source.size != (row['width'], row['height']):
                    raise ValueError('Dimensions differ from manifest')
                preview = source.convert('RGB')
            if predictor is None:
                from ultralytics import YOLO
                model = YOLO(str(model_path))
                validate_names(model.names)

                def predictor(path):
                    result = model.predict(source=str(path), conf=confidence, imgsz=640,
                                           device='cpu', verbose=False, save=False)[0]
                    return [[float(c), float(p), *map(float, box)] for c, p, box in zip(
                        result.boxes.cls.cpu().tolist(), result.boxes.conf.cpu().tolist(),
                        result.boxes.xyxy.cpu().tolist())]
            image_started = time.perf_counter()
            detections = predictor(row['path'])
            boxes, issues = normalized_boxes(detections, row['width'], row['height'])
            native_width, native_height = preview.size
            preview.thumbnail((1600, 1600))
            sx, sy = preview.width/native_width, preview.height/native_height
            draw = ImageDraw.Draw(preview)
            font = ImageFont.load_default(size=18)
            for index, box in enumerate(boxes):
                color = ('#00ff70', '#ffaa00', '#00cfff', '#dd77ff')[box['class_id']]
                x1, y1, x2, y2 = box['xyxy']
                draw.rectangle((x1*sx, y1*sy, x2*sx, y2*sy), outline=color, width=3)
                label = f"{index}: {box['class_id']} {box['class_name']} {box['confidence']:.2f}"
                position = (min(x1*sx, max(0, preview.width-350)), min(y1*sy, preview.height-22))
                draw.text(position, label, fill=color, font=font, stroke_width=1, stroke_fill='black')
            overlay = output / (row['platform_name'] + '-preannotation.png')
            preview.save(overlay)
            item = dict(image_id=row['id'], platform_name=row['platform_name'],
                        source_path=row['path'], source_sha256=row['sha256'],
                        source_status=row['status'], model_sha256=config['model_sha256'],
                        preannotated=True, visually_reviewed=False, approved_for_training=False,
                        confirmed_negative=False, coverage_complete=False, boxes=boxes,
                        invalid_detections=issues, raw_detections=detections,
                        overlapping_box_flags=overlap_flags(boxes), preview_render_version=2,
                        exact_byte_duplicate=byte_counts[row['sha256']] > 1,
                        recorded_pixel_duplicate=pixel_counts[row.get('pixel_sha256')] > 1,
                        original_geometry_issues=row.get('original_geometry_issues', []),
                        zero_detections_requires_review=not boxes,
                        overlay=str(overlay), overlay_sha256=digest(overlay),
                        seconds=time.perf_counter() - image_started,
                        date=datetime.now(timezone.utc).isoformat())
            atomic_json(artifact, item)
            completed.append(item)
        report = dict(selected=len(selected), preannotated=len(completed), cached=cached,
                      visually_reviewed=0, approved=0, training_ready=False,
                      elapsed_seconds=time.perf_counter() - started,
                      mean_image_seconds=sum(r['seconds'] for r in completed) / len(completed),
                      invalid_detections=sum(len(r['invalid_detections']) for r in completed),
                      overlapping_box_flags=sum(len(r.get('overlapping_box_flags', [])) for r in completed),
                      duplicate_flags=sum(r['exact_byte_duplicate'] or r['recorded_pixel_duplicate'] for r in completed),
                      first=selected[0]['platform_name'], last=selected[-1]['platform_name'])
        statistics_path = output / 'statistics.json'
        # Cache validation must not replace the original processing timings.
        if cached == len(completed) and statistics_path.exists():
            atomic_json(output / 'last-resume-statistics.json', report)
        else:
            atomic_json(statistics_path, report)
        return report
    finally:
        lock.unlink()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'model-path', 'output'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--limit', type=int, default=20)
    p.add_argument('--start')
    p.add_argument('--confidence', type=float, default=.15)
    print(json.dumps(run(**vars(p.parse_args())), ensure_ascii=False))
