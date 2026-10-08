"""Render one manually proposed crop for inspection; not a training export."""
import json
from pathlib import Path
from PIL import Image, ImageDraw
from prepare_cctv_v2 import ROOT
from build_collision_supplement import clip_boxes


def main():
    root = ROOT/'research'/'smartspaces-real'
    proposal = json.loads(Path(__file__).with_name('smartspaces_pilot_labels.json').read_text(encoding='utf-8'))
    source = root/(proposal['source_id']+'.jpg')
    with Image.open(source) as image:
        if list(image.size) != proposal['reference_dimensions']:
            raise ValueError('Unexpected frame geometry')
        image = image.crop(proposal['crop']).convert('RGB')
    draw = ImageDraw.Draw(image)
    for cls, left, top, right, bottom in clip_boxes(proposal['boxes_source_xyxy'], proposal['crop']):
        draw.rectangle((left, top, right, bottom), outline='#00ff70', width=2)
        draw.text((left, top), str(cls), fill='white', stroke_width=1, stroke_fill='black')
    image.save(root/'pilot-proposed-overlay.png')
    print(root/'pilot-proposed-overlay.png')


if __name__ == '__main__':
    main()
