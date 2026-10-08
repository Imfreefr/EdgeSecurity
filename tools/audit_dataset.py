"""Read-only source audit. Artifacts and downloaded copies go to --output."""
import argparse
import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from PIL import Image, ImageDraw, ImageOps


def load(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def source(file):
    # Frames from one recording belong together, regardless of split.
    return re.split(r'[_-]frame[_-]', Path(file).stem, flags=re.I)[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('exports', nargs='+')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    cache = out / 'images'
    cache.mkdir(exist_ok=True)
    versions = [load(p) for p in args.exports]
    datasets = [next(r for r in v if r['type'] == 'dataset') for v in versions]
    images = [[r for r in v if r['type'] == 'image'] for v in versions]
    records = images[-1]
    def canonical(r):
        return json.dumps({k: v for k, v in r.items() if k != 'url'}, sort_keys=True)
    differences = []
    if len(images) > 1:
        old = {(r['file'], r['split']): r for r in images[0]}
        for r in records:
            key = (r['file'], r['split'])
            if key not in old or canonical(r) != canonical(old[key]):
                differences.append(r['file'])

    def download(item):
        i, r = item
        path = cache / f'{i:03d}.webp'
        try:
            if not path.exists():
                parsed = urlparse(r['url'])
                if parsed.scheme != 'https' or parsed.hostname != 'cdn.ul.run':
                    raise ValueError('Unexpected image source')
                with urlopen(r['url'], timeout=45) as response:
                    if urlparse(response.url).hostname != 'cdn.ul.run':
                        raise ValueError('Unexpected redirect')
                    data = response.read()
                with Image.open(io.BytesIO(data)) as im:
                    im.verify()
                path.write_bytes(data)
            data = path.read_bytes()
            with Image.open(io.BytesIO(data)) as im:
                oriented = ImageOps.exif_transpose(im).convert('RGB')
                gray = oriented.resize((9, 8)).convert('L')
                pixels = list(gray.get_flattened_data()) if hasattr(gray, 'get_flattened_data') else list(gray.getdata())
                dhash = 0
                for y in range(8):
                    for x in range(8):
                        dhash = (dhash << 1) | (pixels[y * 9 + x] > pixels[y * 9 + x + 1])
                return i, hashlib.sha256(data).hexdigest(), dhash, oriented.size, None
        except Exception as exc:
            # Do not log signed URLs or response bodies.
            return i, None, None, None, type(exc).__name__

    downloaded = list(ThreadPoolExecutor(max_workers=10).map(download, enumerate(records)))
    stats = {i: (digest, dhash, size, error) for i, digest, dhash, size, error in downloaded}
    exact = defaultdict(list)
    groups = defaultdict(list)
    counts = Counter()
    invalid = []
    review = []
    for i, r in enumerate(records):
        digest, dhash, size, error = stats[i]
        if digest:
            exact[digest].append(i)
        groups[source(r['file'])].append(i)
        boxes = r.get('annotations', {}).get('boxes', [])
        flags = []
        if not boxes:
            flags.append('sem_caixas_revisar_negativo_ou_sem_rotulo')
        if error:
            flags.append('imagem_inacessivel_' + error)
        if size and tuple(size) != (r['width'], r['height']):
            flags.append('dimensoes_divergentes')
        for b in boxes:
            if len(b) != 5:
                invalid.append({'index': i, 'file': r['file'], 'reason': 'box_length'})
                continue
            cls, x, y, w, h = b
            counts[int(cls)] += 1
            if cls not in [int(k) for k in datasets[-1]['class_names']] or not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
                invalid.append({'index': i, 'file': r['file'], 'box': b, 'reason': 'invalid_values'})
            elif x - w / 2 < -0.002 or y - h / 2 < -0.002 or x + w / 2 > 1.002 or y + h / 2 > 1.002:
                flags.append('caixa_fora_da_imagem')
        max_area = max((b[3] * b[4] for b in boxes if len(b) == 5), default=0)
        if max_area > 0.45:
            flags.append('objeto_grande_revisar_enquadramento')
        review.append({'index': i, 'file': r['file'], 'split': r['split'], 'source': source(r['file']),
                       'width': r['width'], 'height': r['height'], 'boxes': len(boxes),
                       'largest_box_fraction': round(max_area, 4), 'flags': ';'.join(sorted(set(flags)))})
    duplicates = [ids for ids in exact.values() if len(ids) > 1]
    leakage = [{'source': key, 'splits': dict(Counter(records[i]['split'] for i in ids)), 'indices': ids}
               for key, ids in groups.items() if len({records[i]['split'] for i in ids}) > 1]
    pairs = []
    for i in range(len(records)):
        if stats[i][1] is None:
            continue
        for j in range(i + 1, len(records)):
            if stats[j][1] is None or stats[i][0] == stats[j][0]:
                continue
            distance = (stats[i][1] ^ stats[j][1]).bit_count()
            if distance <= 3:
                pairs.append({'a': i, 'b': j, 'distance': distance,
                              'same_recording': source(records[i]['file']) == source(records[j]['file']),
                              'cross_split': records[i]['split'] != records[j]['split']})
    summary = {'exports': [{'file': Path(p).name, 'images': len(v), 'updated_at': d.get('updated_at')}
                           for p, v, d in zip(args.exports, images, datasets)],
               'changed_records_between_exports': differences,
               'splits': dict(Counter(r['split'] for r in records)),
               'class_names': datasets[-1]['class_names'], 'class_box_counts': dict(counts),
               'unannotated_images': sum(not r.get('annotations', {}).get('boxes') for r in records),
               'downloads_ok': sum(s[0] is not None for s in stats.values()),
               'exact_duplicate_groups': duplicates, 'near_duplicate_candidate_pairs': pairs,
               'recording_groups': [{'source': key, 'count': len(ids)} for key, ids in groups.items()],
               'recordings_in_multiple_splits': leakage, 'invalid_boxes': invalid}
    (out / 'audit.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    with (out / 'review.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(review[0]))
        writer.writeheader()
        writer.writerows(review)
    # A deliberately conservative candidate: exclude byte-identical images only
    # when annotations are also identical. Near matches need visual review.
    exclude = set()
    for ids in duplicates:
        seen = set()
        for i in ids:
            annotation = json.dumps(records[i].get('annotations', {}), sort_keys=True)
            if annotation in seen:
                exclude.add(i)
            seen.add(annotation)
    with (out / 'candidate-exact-deduplicated.ndjson').open('w', encoding='utf-8') as f:
        header = dict(datasets[-1])
        header['name'] += ' - exact duplicate review candidate'
        f.write(json.dumps(header, ensure_ascii=False) + '\n')
        for i, record in enumerate(records):
            if i not in exclude:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
    for start in range(0, len(records), 40):
        sheet = Image.new('RGB', (1200, 1120), '#141820')
        draw = ImageDraw.Draw(sheet)
        for position, i in enumerate(range(start, min(start + 40, len(records)))):
            x, y = (position % 8) * 150, (position // 8) * 224
            if stats[i][0]:
                with Image.open(cache / f'{i:03d}.webp') as im:
                    im = ImageOps.exif_transpose(im).convert('RGB')
                    im.thumbnail((146, 196))
                    sheet.paste(im, (x + (150 - im.width) // 2, y))
            draw.text((x + 3, y + 198), f'{i:03d} {records[i]["split"]} {len(records[i].get("annotations", {}).get("boxes", []))} boxes', fill='white')
        sheet.save(out / f'contact-{start // 40 + 1:02d}.jpg', quality=90)
    print(json.dumps({k: summary[k] for k in ['splits', 'class_box_counts', 'unannotated_images', 'downloads_ok']}, ensure_ascii=False))
    print('changed_records', len(differences), 'exact_groups', len(duplicates), 'near_pairs', len(pairs), 'cross_split_recordings', len(leakage), 'invalid_boxes', len(invalid), 'candidate_exclusions', len(exclude))
    print('artifacts', str(out))


if __name__ == '__main__':
    main()
