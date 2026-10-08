"""Read a publicly shared archive via its normal download form; private triage only."""
import hashlib
import html
import json
import re
import zipfile
from pathlib import Path
from urllib.parse import urlparse
import requests
from PIL import Image
from prepare_cctv_v2 import ROOT

ORIGIN = 'https://github.com/SelimSavas/forklift-and-people-detection-with-YOLOv5'
FILE_ID = '1b5-plGXRc4u5CjxOvDp3xEuAdsyA1eRs'
URL = 'https://drive.usercontent.google.com/download'
LIMIT = 512*1024*1024


def main():
    output = ROOT/'research/public-selim-forklift-2026-10-08'
    output.mkdir(parents=True, exist_ok=True)
    package = output/'dataforkliftv19.zip'
    if package.exists():
        raise ValueError('Existing download preserved; do not redownload automatically')
    session = requests.Session()
    response = session.get(URL, params={'id': FILE_ID, 'export': 'download'}, timeout=30)
    response.raise_for_status()
    if 'Google Drive - Virus scan warning' not in response.text:
        raise ValueError('Unexpected page; no access restrictions or CAPTCHA bypass supported')
    form = re.search(r'<form[^>]+action="([^"]+)"[^>]*>(.*?)</form>', response.text, re.S)
    if not form:
        raise ValueError('Normal public download form not found')
    action = html.unescape(form.group(1))
    if urlparse(action).scheme != 'https' or urlparse(action).hostname != 'drive.usercontent.google.com':
        raise ValueError('Unexpected download host')
    params = dict((html.unescape(a), html.unescape(b)) for a, b in
                  re.findall(r'<input[^>]+name="([^"]+)"[^>]+value="([^"]*)"', form.group(2)))
    if params.get('id') != FILE_ID:
        raise ValueError('Download identity changed')
    with session.get(action, params=params, stream=True, timeout=(15, 45)) as download:
        download.raise_for_status()
        if 'text/' in download.headers.get('Content-Type', ''):
            raise ValueError('Download denied or requires interactive access')
        if int(download.headers.get('Content-Length', 0)) > LIMIT:
            raise ValueError('Archive exceeds download limit')
        received, digest = 0, hashlib.sha256()
        with package.open('xb') as stream:
            for chunk in download.iter_content(1024*1024):
                received += len(chunk)
                if received > LIMIT:
                    raise ValueError('Stream exceeds limit; partial file retained, not approved')
                digest.update(chunk)
                stream.write(chunk)
    sources = dict(source_url=ORIGIN, public_share_url=f'https://drive.google.com/file/d/{FILE_ID}/view',
                   archive_sha256=digest.hexdigest(), archive_bytes=received, media_license='unknown',
                   training_allowed=None, redistribution_allowed=None, usage='private',
                   author_description='Images assembled from ImageNet, Roboflow and Kaggle; no independent-scene count inferred',
                   approved_new_images=0, verified_new_groups=0)
    with zipfile.ZipFile(package) as archive:
        members = archive.infolist()
        images = sorted((m for m in members if m.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))), key=lambda m: m.filename)
        sources.update(image_members=len(images), label_members=sum(m.filename.lower().endswith('.txt') for m in members))
        candidates = []
        for index in sorted({round((len(images)-1)*fraction/11) for fraction in range(12)}):
            member = images[index]
            if member.file_size > 20*1024*1024:
                raise ValueError('Oversized image member')
            # Never extract arbitrary archive paths or execute its contents.
            path = output/f'candidate-{index:05d}{Path(member.filename).suffix.lower()}'
            path.write_bytes(archive.read(member))
            with Image.open(path) as image:
                image.load()
                width, height = image.size
            candidates.append(dict(path=str(path), archive_member=member.filename, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                   width=width, height=height, status='pending_individual_visual_review',
                                   approved_for_training=False, confirmed_negative=False, synthetic=None,
                                   source_url=ORIGIN, media_license='unknown', usage='private',
                                   group='selim-mixed-origin-relationships-pending', independence_verified=False))
    (output/'sources.json').write_text(json.dumps(sources, indent=2), encoding='utf-8')
    (output/'candidates.ndjson').write_text(''.join(json.dumps(row)+'\n' for row in candidates), encoding='utf-8')
    print(json.dumps(sources))


if __name__ == '__main__':
    main()
