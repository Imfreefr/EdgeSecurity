"""Full-frame proposal assets for all exact pairs; no automatic label merge."""
import json
from pathlib import Path
from PIL import Image, ImageDraw
from prepare_cctv_v2 import ROOT

BASE = ROOT/'original-api-recovery-2026-10-08'
OUT = ROOT/'duplicate-review-2026-10-08'


def main():
    inventory = json.loads((BASE/'original-inventory.json').read_text(encoding='utf-8'))
    rows = {row['id']: row for row in map(json.loads, (BASE/'manifest.ndjson').read_text(encoding='utf-8').splitlines())}
    OUT.mkdir(exist_ok=True)
    for group in inventory['identical_pixel_groups']:
        member = next(member for member in group['members'] if member['split'] == 'train')
        record = rows[member['id']]
        with Image.open(BASE/record['path']) as source:
            image = source.convert('RGB').resize((1024, 576), Image.Resampling.LANCZOS)
        stem = member['name']
        image.save(OUT/(stem+'-clean.png'))
        draw = ImageDraw.Draw(image)
        for alternative, color in zip(group['members'], ('#ff4444', '#3399ff')):
            for cls, x, y, w, h in alternative['boxes']:
                left, top, right, bottom = (x-w/2)*1024, (y-h/2)*576, (x+w/2)*1024, (y+h/2)*576
                draw.rectangle((left, top, right, bottom), outline=color, width=1)
                draw.text((left, top), f'{alternative["split"]}:{int(cls)}', fill=color)
        image.save(OUT/(stem+'-alternatives.png'))
    print(json.dumps({'pairs': len(inventory['identical_pixel_groups']), 'status': 'pending_individual_redraw', 'directory': str(OUT)}))


if __name__ == '__main__':
    main()
