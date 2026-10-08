"""Public GitHub footage pilots; unknown media rights, private review only."""
import hashlib
import io
import json
import zipfile
from pathlib import Path
import cv2
import requests
from prepare_cctv_v2 import ROOT

SOURCES = [
    ('sana-public', 'https://github.com/Sanaurrehmanarain/forklift-safety-ai',
     'https://github.com/Sanaurrehmanarain/forklift-safety-ai/releases/download/v1.0.0/warehouse_assets.zip', True),
    ('yangga-public', 'https://github.com/YanggaY/Forklift-Safety-Monitoring-System-Using-YOLO-and-OpenCV',
     'https://raw.githubusercontent.com/YanggaY/Forklift-Safety-Monitoring-System-Using-YOLO-and-OpenCV/main/sample.mp4', False),
]
LIMIT = 25*1024*1024


def bounded_download(url):
    response = requests.get(url, stream=True, timeout=30)
    response.raise_for_status()
    if int(response.headers.get('Content-Length', 0)) > LIMIT:
        raise ValueError('Pilot exceeds bounded download size')
    data = bytearray()
    for chunk in response.iter_content(256*1024):
        data.extend(chunk)
        if len(data) > LIMIT:
            raise ValueError('Pilot stream exceeded size limit')
    return bytes(data)


def main():
    output = ROOT/'private-github-pilots-2026-10-08'
    if output.exists():
        raise ValueError('Refusing to overwrite pilot evidence')
    output.mkdir(parents=True)
    records, sources = [], []
    for name, origin, url, archive in SOURCES:
        data = bounded_download(url)
        downloaded_hash = hashlib.sha256(data).hexdigest()
        if archive:
            with zipfile.ZipFile(io.BytesIO(data)) as package:
                videos = [i for i in package.infolist() if i.filename.lower().endswith('.mp4')]
                if len(videos) != 1 or videos[0].file_size > LIMIT:
                    raise ValueError('Expected exactly one bounded video in pilot archive')
                data = package.read(videos[0])
        path = output/(name+'.mp4')
        path.write_bytes(data)
        video = cv2.VideoCapture(str(path))
        count, fps = int(video.get(cv2.CAP_PROP_FRAME_COUNT)), video.get(cv2.CAP_PROP_FPS)
        if not video.isOpened() or count <= 0 or fps <= 0:
            raise ValueError('Pilot is not a readable video')
        sources.append(dict(id=name, source_url=origin, download_url=url,
            download_sha256=downloaded_hash, video_sha256=hashlib.sha256(data).hexdigest(),
            media_license='unknown', training_allowed=None, redistribution_allowed=None,
            duration_seconds=count/fps, frames=count, fps=fps))
        for fraction in (.1, .5, .9):
            index = round((count-1)*fraction)
            video.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, image = video.read()
            if not ok:
                raise ValueError('Cannot decode pilot frame')
            image_path = output/f'{name}-frame-{index:06d}.png'
            if not cv2.imwrite(str(image_path), image):
                raise ValueError('Cannot save pilot frame')
            records.append(dict(id=image_path.stem, path=str(image_path), width=image.shape[1],
                height=image.shape[0], source_id=name, source_url=origin, frame=index,
                timestamp_seconds=index/fps, sha256=hashlib.sha256(image_path.read_bytes()).hexdigest(),
                status='pending_individual_visual_review', approved_for_training=False,
                confirmed_negative=False, media_license='unknown', synthetic=None,
                group='github-pilot-origin-relationships-pending', independence_verified=False,
                boxes=[], usage='private'))
        video.release()
    (output/'sources.json').write_text(json.dumps(sources, indent=2), encoding='utf-8')
    (output/'candidates.ndjson').write_text(''.join(json.dumps(r)+'\n' for r in records), encoding='utf-8')
    print(json.dumps({'videos': len(sources), 'candidate_frames': len(records), 'approved_new_images': 0,
                      'verified_new_groups': 0, 'output': str(output)}))


if __name__ == '__main__':
    main()
