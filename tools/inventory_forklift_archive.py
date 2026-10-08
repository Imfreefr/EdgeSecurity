"""Read images inside an existing ZIP; never extract or execute archive contents."""
import argparse
import hashlib
import io
import json
import zipfile
import warnings
from pathlib import Path
from PIL import Image


def inventory(package, output):
    if output.exists():
        raise ValueError('Existing inventory preserved')
    rows, seen = [], {}
    with zipfile.ZipFile(package) as archive:
        members = sorted(archive.infolist(), key=lambda item: item.filename)
        for member in members:
            if not member.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                continue
            row = dict(archive_member=member.filename, approved_for_training=False,
                       visual_review_complete=False, independence_verified=False)
            try:
                if member.file_size > 20 * 1024 * 1024:
                    raise ValueError('Image exceeds inspection size limit')
                data = archive.read(member)
                row['sha256'] = hashlib.sha256(data).hexdigest()
                with warnings.catch_warnings(record=True) as notices:
                    warnings.simplefilter('always')
                    with Image.open(io.BytesIO(data)) as image:
                        image.load()
                        rgb = image.convert('RGB')
                        row.update(width=rgb.width, height=rgb.height)
                        digest = hashlib.sha256()
                        digest.update(f'{rgb.width}x{rgb.height}:RGB:'.encode())
                        digest.update(rgb.tobytes())
                        row['pixel_sha256'] = digest.hexdigest()
                    row['decode_warnings'] = [str(notice.message) for notice in notices]
                row['duplicate_of'] = seen.get(row['pixel_sha256'])
                seen.setdefault(row['pixel_sha256'], member.filename)
                row['status'] = 'pending_individual_visual_review'
            except (OSError, ValueError, zipfile.BadZipFile) as error:
                row.update(status='invalid_image', error=str(error))
            rows.append(row)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        for row in rows:
            stream.write(json.dumps(row) + '\n')
    counts = dict(images=len(rows), invalid=sum(r['status']=='invalid_image' for r in rows),
                  duplicate_occurrences=sum(bool(r.get('duplicate_of')) for r in rows),
                  unique_decoded_images=len(seen), approved_images=0, verified_groups=0)
    counts['images_with_decode_warnings'] = sum(bool(r.get('decode_warnings')) for r in rows)
    print(json.dumps(counts))
    return counts


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    inventory(args.package, args.output)
