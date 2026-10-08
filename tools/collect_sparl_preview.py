"""Collect one CC-BY-4.0 SPARL experiment for framing triage, not approval.

Source/rights verified in Zenodo API record 16636916. Downloads remain separate
from the training package. No frames are automatically labelled or approved.
"""
import hashlib
import json
import zipfile
from pathlib import Path
import requests
import cv2
from prepare_cctv_v2 import ROOT

RECORD = 'https://zenodo.org/api/records/16636916'


def main():
    metadata_response = requests.get(RECORD, timeout=30)
    metadata_response.raise_for_status()
    metadata = metadata_response.json()
    if metadata['metadata'].get('license', {}).get('id') != 'cc-by-4.0':
        raise ValueError('Source licence changed; download blocked')
    asset = next(item for item in metadata['files'] if item['key'] == 'Experiment1.zip')
    root = ROOT/'research'/'sparl3'
    root.mkdir(parents=True, exist_ok=True)
    target = root/'Experiment1.zip'
    if not target.exists():
        partial = root/'Experiment1.zip.part'
        if partial.exists():
            raise ValueError('Partial download exists; inspect it before restarting')
        received, reported = 0, 0
        url = 'https://zenodo.org/records/16636916/files/Experiment1.zip?download=1'
        with requests.get(url, stream=True, timeout=(30, 60)) as response:
            response.raise_for_status()
            with partial.open('xb') as output:
                for chunk in response.iter_content(4*1024*1024):
                    output.write(chunk)
                    received += len(chunk)
                    if received > asset['size']:
                        raise ValueError('Unexpected download length')
                    if received-reported >= 128*1024*1024:
                        print(f'Downloaded {received//1024//1024} MiB / {asset["size"]//1024//1024} MiB', flush=True)
                        reported = received
        if received != asset['size']:
            raise ValueError('Incomplete download; not promoted')
        with partial.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'md5').hexdigest()
        if 'md5:'+digest != asset['checksum']:
            raise ValueError('Source checksum mismatch; not promoted')
        partial.rename(target)
    with target.open('rb') as stream:
        if 'md5:'+hashlib.file_digest(stream, 'md5').hexdigest() != asset['checksum']:
            raise ValueError('Cached archive checksum mismatch')
    video = root/'Experiment1_Blurred.mp4'
    if not video.exists():
        with zipfile.ZipFile(target) as archive:
            with archive.open('Experiment1/Experiment1_Blurred.mp4') as source, video.open('xb') as output:
                while chunk := source.read(4*1024*1024):
                    output.write(chunk)
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise ValueError('Source video does not open')
    fps = capture.get(cv2.CAP_PROP_FPS)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    records = []
    try:
        for fraction in (.1, .3, .5, .7, .9):
            index = int(frame_count*fraction)
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            success, frame = capture.read()
            if not success:
                raise ValueError('Preview frame does not decode')
            filename = root/f'preview-{index}.jpg'
            if not filename.exists():
                if not cv2.imwrite(str(filename), frame):
                    raise ValueError('Preview image write failed')
            records.append({'path': str(filename), 'frame': index,
                            'timestamp_seconds': index/fps, 'width': frame.shape[1],
                            'height': frame.shape[0], 'status': 'pending_visual_review',
                            'source': 'https://zenodo.org/records/16636916',
                            'license': 'CC-BY-4.0', 'source_archive_md5': asset['checksum'],
                            'group': 'sparl3-experiment1-all-related-cameras',
                            'approved_for_training': False})
    finally:
        capture.release()
    (root/'preview-manifest.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'RESEARCH_PREVIEWS_ONLY', 'previews': len(records),
                      'approved_images': 0, 'group_independence_verified': False,
                      'duration_seconds': frame_count/fps}, indent=2), flush=True)


if __name__ == '__main__':
    main()
