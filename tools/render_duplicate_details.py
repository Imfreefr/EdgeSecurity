"""Original-resolution detail views for manual review, not new training scenes."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw
from prepare_cctv_v2 import ROOT

REGIONS = {
    '010': {'distant-person': [130,135,200,205]},
    '011': {'left-background': [0,100,300,250]},
    '012': {'distant-person': [565,155,630,230], 'left-background': [0,170,265,300]},
    '013': {'distant-person': [760,150,815,220], 'left-background': [0,140,180,300]},
    '014': {'distant-person': [975,165,1024,235], 'left-background': [0,160,210,310]},
    '015': {'left-background': [0,150,490,310]},
    '016': {'background': [520,160,750,310], 'left-background': [200,140,450,290]},
}


def main(manifest=None, output=None, overlays=False):
    manifest = Path(manifest) if manifest else ROOT/'original-review-r6-duplicates-partial/manifest.ndjson'
    rows = {r['platform_name']: r for r in map(json.loads, manifest.read_text(encoding='utf-8').splitlines()) if r['split']=='train'}
    output = Path(output) if output else ROOT/'duplicate-review-details-2026-10-08'
    output.mkdir(exist_ok=True)
    for number, regions in REGIONS.items():
        name = 'IMG_0457_frame_'+number
        with Image.open(rows[name]['path']) as source:
            source = source.convert('RGB')
            if overlays:
                draw = ImageDraw.Draw(source)
                for cls,x,y,w,h in rows[name]['proposed_boxes']:
                    color = ['#00ff70','#ffaa00','#00cfff','#dd77ff'][int(cls)]
                    draw.rectangle(((x-w/2)*source.width,(y-h/2)*source.height,
                                    (x+w/2)*source.width,(y+h/2)*source.height), outline=color, width=3)
            for label, coords in regions.items():
                crop = tuple(round(v*(source.width/1024 if i%2==0 else source.height/576)) for i,v in enumerate(coords))
                image = source.crop(crop)
                image.save(output/(name+'-'+label+'.png'))
    print(json.dumps({'output': str(output), 'source_frames': len(REGIONS), 'new_scenes': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest')
    parser.add_argument('--output')
    parser.add_argument('--overlays', action='store_true')
    main(**vars(parser.parse_args()))
