"""Enlarged comparison previews; crops do not modify/export dataset images."""
import json
from pathlib import Path
from PIL import Image, ImageDraw
from prepare_cctv_v2 import ROOT, AUDIT

def main():
    originals=json.loads((ROOT/'review/originals.json').read_text(encoding='utf-8'))
    pairs=json.loads((AUDIT/'audit.json').read_text(encoding='utf-8'))['near_duplicate_candidate_pairs']
    decisions=json.loads(Path(__file__).with_name('cctv_pair_decisions.json').read_text(encoding='utf-8'))
    destination=ROOT/'review/ambiguous-enlarged'
    destination.mkdir(exist_ok=True)
    indices=decisions.get('enlarged_pair_indices',decisions['ambiguous_pair_indices'])
    for number in indices:
        canvas=Image.new('RGB',(1280,880),'#141820')
        draw=ImageDraw.Draw(canvas)
        for side in (0,1):
            index=pairs[number]['a' if side==0 else 'b']
            item=originals[index]
            with Image.open(item['path']) as original:
                im=original.convert('RGB')
            region=None
            if item['group']=='VID_20260820_064426_454':region=(0,692,1080,1522)
            if item['group']=='VID_20260820_051738_560':region=(0,724,1080,1335)
            if region:im=im.crop(region)
            im.thumbnail((630,810))
            canvas.paste(im,(side*640+(640-im.width)//2,40))
            draw.text((side*640+10,10),f'Pair {number} / original {index} / preview crop {region}',fill='white')
        canvas.save(destination/f'pair-{number:03d}.jpg',quality=97)
    print('Enlarged previews:',len(indices))

if __name__=='__main__':main()
