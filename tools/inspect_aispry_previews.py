"""Fetch three publisher-linked licensed previews for triage, never training approval."""
import json
from pathlib import Path
import requests
from PIL import Image
from prepare_cctv_v2 import ROOT, sheet


def main():
    output = ROOT/'research/aispry-previews'
    output.mkdir(parents=True, exist_ok=True)
    publisher = 'https://universe.roboflow.com/aispry-inb32/forklift-monitoring-system'
    base = 'https://source.roboflow.com/byyJ5WmKiNXGNaMpVOFCWsyOrbt2/'
    previews = {
        '0EfkwcX7IuGkXee0GxZH': ('excluded_eye_level', 'Outdoor eye-level forklift, not elevated CCTV'),
        '0LkPLC8AgoRxVIs0citz': ('pending_full_resolution_and_origin', 'Elevated CCTV candidate; 200px preview insufficient for final labels and provenance'),
        '0QZjamalu8IJaZJKjPNV': ('excluded_not_scene', 'Browser/YouTube error screenshot, not a forklift monitoring scene')}
    records = []
    for identifier in previews:
        url = base+identifier+'/thumb.jpg'
        path = output/(identifier+'.jpg')
        record = {'id': 'aispry-'+identifier, 'publisher': publisher, 'source_url': url,
                  'license_declaration': 'CC BY 4.0 on publisher page',
                  'status': 'pending_full_resolution_origin_and_label_review',
                  'boxes': [], 'approved_for_training': False}
        try:
            if not path.exists():
                response = requests.get(url, timeout=20)
                response.raise_for_status()
                with Image.open(__import__('io').BytesIO(response.content)) as image:
                    image.verify()
                path.write_bytes(response.content)
            with Image.open(path) as image:
                record.update(path=str(path), width=image.width, height=image.height)
            record.update(visual_triage=previews[identifier][0], visual_reason=previews[identifier][1])
        except (requests.RequestException, OSError) as exc:
            record.update(status='download_failed', reason=str(exc))
        records.append(record)
    (output/'candidates.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    downloaded = [record for record in records if 'path' in record]
    if downloaded:
        sheet(downloaded, output/'previews.jpg', columns=3)
    print(json.dumps({'previews_downloaded': len(downloaded), 'approved_for_training': 0,
                      'output': str(output)}))


if __name__ == '__main__':
    main()
