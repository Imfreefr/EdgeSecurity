"""Research previews from the two explicitly real SmartSpaces scenes only.

Never use synthetic Warehouse_000..025 or count simultaneous cameras as scenes.
No automatic class annotations/approval. Publisher CC BY 4.0 is checked first.
"""
import hashlib
import json
from pathlib import Path
import requests
import cv2
from prepare_cctv_v2 import ROOT

REPO = 'nvidia/PhysicalAI-SmartSpaces'
REAL_SCENES = ('Warehouse_026', 'Warehouse_027')
BASE = 'https://huggingface.co/datasets/'+REPO+'/resolve/main/'


def main():
    card_response = requests.get(BASE+'README.md', timeout=30)
    card_response.raise_for_status()
    card = card_response.text
    if 'license: cc-by-4.0' not in card or '**real-world** test captures' not in card:
        raise ValueError('Publisher licence/real-scene declaration changed; blocked')
    root = ROOT/'research'/'smartspaces-real'
    root.mkdir(parents=True, exist_ok=True)
    records = []
    for scene in REAL_SCENES:
        route = f'MTMC_Tracking_2026/test/{scene}/videos'
        listing_response = requests.get('https://huggingface.co/api/datasets/'+REPO+'/tree/main/'+route, timeout=30)
        listing_response.raise_for_status()
        assets = [item for item in listing_response.json() if item['path'].startswith(route+'/') and item['path'].endswith('.mp4')]
        asset = min(assets, key=lambda item: item['size'])
        if asset['size'] > 64*1024*1024:
            raise ValueError('Pilot video exceeds 64 MiB limit')
        filename = root/(scene+'-'+Path(asset['path']).name)
        if not filename.exists():
            partial = filename.with_suffix('.mp4.part')
            if partial.exists():
                raise ValueError('Partial pilot exists; inspect before retrying')
            url = BASE+asset['path']
            received = 0
            with requests.get(url, stream=True, timeout=(30, 60)) as response, partial.open('xb') as output:
                response.raise_for_status()
                for chunk in response.iter_content(1024*1024):
                    received += len(chunk)
                    if received > asset['size']:
                        raise ValueError('Unexpected pilot size')
                    output.write(chunk)
            if received != asset['size']:
                raise ValueError('Pilot incomplete')
            partial.rename(filename)
        if filename.stat().st_size != asset['size']:
            raise ValueError('Cached video size mismatch')
        with filename.open('rb') as stream:
            checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
        expected = asset.get('lfs', {}).get('oid')
        if expected and checksum != expected:
            raise ValueError('Publisher SHA-256 mismatch')
        capture = cv2.VideoCapture(str(filename))
        try:
            for seconds in (5, 25, 45):
                capture.set(cv2.CAP_PROP_POS_MSEC, seconds*1000)
                success, frame = capture.read()
                if not success:
                    raise ValueError('Pilot frame cannot be decoded')
                image = root/f'{scene}-{filename.stem.split("-")[-1]}-{seconds}s.jpg'
                if not image.exists() and not cv2.imwrite(str(image), frame):
                    raise ValueError('Pilot frame write failed')
                records.append({'id': image.stem, 'path': str(image), 'source_url': BASE+asset['path'],
                                'source_dataset': 'https://huggingface.co/datasets/'+REPO,
                                'authors': 'NVIDIA', 'license': 'CC-BY-4.0',
                                'source_video_sha256': checksum, 'timestamp_seconds': seconds,
                                'width': frame.shape[1], 'height': frame.shape[0],
                                'source_scene': scene, 'group': 'smartspaces-'+scene,
                                'synthetic': False, 'status': 'pending_visual_review',
                                'approved_for_training': False})
        finally:
            capture.release()
        print(scene+' pilot video verified and 3 frames decoded', flush=True)
    (root/'preview-manifest.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    print(json.dumps({'preview_images': len(records), 'approved_images': 0,
                      'scenes_pending_independence_review': list(REAL_SCENES)}), flush=True)


if __name__ == '__main__':
    main()
