"""Prepare isolated review assets; no upload, training, or production changes."""
import hashlib
import json
from pathlib import Path
import requests
from PIL import Image, ImageDraw
from audit_dataset import load, source

ROOT = Path(r'C:\Users\ELIPSE\Downloads\EdgeSecurity-CCTV-v2')
AUDIT = Path(r'C:\Users\ELIPSE\Downloads\EdgeSecurity-dataset-audit')
HF = 'https://huggingface.co/datasets/Voxel51/Safe_and_Unsafe_Behaviours/resolve/main/'


def sheet(items, path, columns=4):
    canvas = Image.new('RGB', (columns * 320, ((len(items) + columns - 1) // columns) * 230), '#141820')
    draw = ImageDraw.Draw(canvas)
    for pos, item in enumerate(items):
        image = Image.open(item['path']).convert('RGB')
        painter = ImageDraw.Draw(image)
        for cls, x, y, w, h in item.get('boxes', []):
            box = [(x-w/2)*image.width, (y-h/2)*image.height, (x+w/2)*image.width, (y+h/2)*image.height]
            painter.rectangle(box, outline=['#00ff70','#ffaa00','#00cfff','#dd77ff'][int(cls)], width=max(2, image.width//300))
            painter.text((box[0],box[1]), str(int(cls)), fill='white', stroke_width=1, stroke_fill='black')
        image.thumbnail((310, 200))
        x,y=(pos%columns)*320,(pos//columns)*230
        canvas.paste(image,(x+(320-image.width)//2,y))
        draw.text((x+3,y+202),item['id'],fill='white')
    canvas.save(path,quality=94)


def main():
    for sub in ['review/originals','review/sheets','external/videos','external/frames','provenance']:
        (ROOT/sub).mkdir(parents=True,exist_ok=True)
    records=[r for r in load(r'C:\Users\ELIPSE\Downloads\edge-security (1).ndjson') if r['type']=='image']
    originals=[]
    for i,r in enumerate(records):
        im=Image.open(AUDIT/'images'/f'{i:03d}.webp').convert('RGB')
        boxes=r.get('annotations',{}).get('boxes',[])
        rotation=0
        if r['file'].startswith('IMG_') and '_frame_' not in r['file']:
            im=im.transpose(Image.Transpose.ROTATE_90)
            boxes=[[c,y,1-x,h,w] for c,x,y,w,h in boxes]
            rotation=90
        path=ROOT/'review/originals'/f'original-{i:03d}.jpg'
        im.save(path,quality=95)
        originals.append({'id':f'original-{i:03d}','index':i,'file':r['file'],'original_split':r['split'],
                          'path':str(path),'group':source(r['file']),'rotation_ccw':rotation,'boxes':boxes,
                          'sha256':hashlib.sha256((AUDIT/'images'/f'{i:03d}.webp').read_bytes()).hexdigest(),
                          'status':'pending_visual_review'})
    (ROOT/'review/originals.json').write_text(json.dumps(originals,ensure_ascii=False,indent=2),encoding='utf-8')
    for start in range(0,len(originals),24):
        sheet(originals[start:start+24],ROOT/'review/sheets'/f'original-{start//24+1:02d}.jpg')
    for name in ['README.md','samples.json','metadata.json','fiftyone.yml']:
        path=ROOT/'provenance'/('safe-unsafe-'+name)
        if not path.exists():
            response=requests.get(HF+name,timeout=60);response.raise_for_status();path.write_bytes(response.content)
    samples=json.loads((ROOT/'provenance/safe-unsafe-samples.json').read_text(encoding='utf-8'))
    print('originals prepared',len(originals),'rotated',sum(bool(x['rotation_ccw']) for x in originals))
    print('sample metadata type',type(samples).__name__)
    if isinstance(samples,dict):
        print('metadata keys',list(samples))
        samples=samples.get('samples',[])
    print('samples',len(samples))
    for sample in samples[:2]:
        print(json.dumps({k:v for k,v in sample.items() if k in ['filepath','metadata','ground_truth','tags']},ensure_ascii=False))


if __name__=='__main__':
    main()
