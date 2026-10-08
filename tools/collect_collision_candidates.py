"""Collect extra real, licensed CCTV frames; candidates are never approved automatically."""
import json
from concurrent.futures import ThreadPoolExecutor
from collect_public_cctv import collect
from prepare_cctv_v2 import ROOT, sheet


def main():
    # One frame per clip. The source confirms only two independent cameras;
    # differing clip IDs must not be represented as independent environments.
    files = [f'{category}_te{number}.mp4'
             for category in (3, 7) for number in (2, 3, 5, 8)]
    records = list(ThreadPoolExecutor(max_workers=4).map(collect, files))
    destination = ROOT / 'collision-review'
    destination.mkdir(exist_ok=True)
    (destination / 'candidates.json').write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    sheet(records, destination / 'candidates.jpg', columns=4)
    print(json.dumps({'downloaded': len(records), 'approved': 0,
                      'path': str(destination)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
