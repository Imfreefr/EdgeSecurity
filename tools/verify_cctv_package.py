"""Read-only ZIP validation and optional comparison with platform NDJSON export."""
import argparse
import hashlib
import io
import json
from pathlib import Path
from collections import Counter
from zipfile import ZipFile
from PIL import Image

def decoded_pixels(source):
    """Compare decoded RGB, not JPEG containers or thumbnails."""
    with Image.open(source) as im:
        im.load()
        rgb = im.convert('RGB')
        return rgb.size, hashlib.sha256(rgb.tobytes()).hexdigest()


def verify_remote_pixels(archive, records, platform_images, remote_root):
    root = Path(remote_root).resolve()
    by_name = {Path(item['file']).stem: item for item in platform_images}
    if len(by_name) != len(platform_images) or len(by_name) != len(records):
        raise ValueError('Remote image mapping is not one-to-one')
    for record in records:
        item = by_name.get(record['id'])
        if item is None:
            raise ValueError('Missing remote image: '+record['id'])
        # Downloaded exports must preserve the relative file name. Do not
        # interpret URLs as paths or allow an export to escape its root.
        filename = item['file']
        if '://' in filename or Path(filename).is_absolute():
            raise ValueError('Remote file must be a relative downloaded path')
        remote = (root/filename).resolve()
        if not remote.is_relative_to(root):
            raise ValueError('Remote path escapes image directory')
        if decoded_pixels(io.BytesIO(archive.read(record['path']))) != decoded_pixels(remote):
            raise ValueError('Platform decoded pixels differ: '+record['id'])


def compare_boxes(actual,expected,tolerance=1e-5):
    if len(actual)!=len(expected):return False
    remaining=list(expected)
    for box in actual:
        match=next((candidate for candidate in remaining if int(box[0])==int(candidate[0]) and
                    all(abs(a-b)<=tolerance for a,b in zip(box[1:],candidate[1:]))),None)
        if match is None:return False
        remaining.remove(match)
    return not remaining

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('zip')
    parser.add_argument('--platform-export',help='Downloaded NDJSON after assisted upload; read only')
    parser.add_argument('--platform-images',help='Directory of original remote images, matching relative export file paths')
    args=parser.parse_args()
    if args.platform_images and not args.platform_export:
        parser.error('--platform-images requires --platform-export')
    with ZipFile(args.zip) as archive:
        if archive.testzip() is not None:raise ValueError('ZIP corruption')
        records=[json.loads(line) for line in archive.read('manifest.ndjson').decode('utf-8').splitlines() if line]
        stats=json.loads(archive.read('statistics.json'))
        boxes_count=Counter()
        expected_images=set()
        for record in records:
            data=archive.read(record['path'])
            if hashlib.sha256(data).hexdigest()!=record['sha256']:raise ValueError('Hash mismatch')
            with Image.open(io.BytesIO(data)) as im:
                im.load()
                if im.size!=(record['width'],record['height']):raise ValueError('Invalid dimensions')
            labels=archive.read('labels/'+record['split']+'/'+record['id']+'.txt').decode('utf-8')
            actual=[[float(v) for v in line.split()] for line in labels.splitlines() if line]
            if any(len(box)!=5 for box in actual) or not compare_boxes(actual,record['boxes']):
                raise ValueError('Serialized YOLO labels differ from reviewed manifest')
            boxes_count.update(int(box[0]) for box in actual)
            expected_images.add(record['path'])
        actual_images={name for name in archive.namelist() if name.startswith('images/') and name.endswith('.jpg')}
        if actual_images!=expected_images:raise ValueError('Unexpected/missing images in ZIP')
        if len(records)!=stats['images'] or boxes_count!=Counter({int(k):v for k,v in stats['by_class_id'].items()}):
            raise ValueError('Statistics mismatch')
    print('LOCAL ZIP VERIFIED:',len(records),'images;',sum(boxes_count.values()),'boxes; class counts',dict(sorted(boxes_count.items())))
    if not args.platform_export:
        print('PLATFORM: not verified; provide downloaded export with --platform-export')
        return
    platform=[json.loads(line) for line in Path(args.platform_export).read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    dataset=next(x for x in platform if x.get('type')=='dataset')
    classes=dataset.get('class_names',dataset.get('names'))
    if isinstance(classes,list):classes={str(i):name for i,name in enumerate(classes)}
    expected_classes={'0':'pessoa','1':'maquina','2':'operador','3':'objeto'}
    if classes!=expected_classes:raise ValueError('Platform class IDs/names differ: '+str(classes))
    images=[x for x in platform if x.get('type')=='image']
    if len(images)!=len(records):raise ValueError('Platform image count mismatch')
    by_name={Path(x['file']).stem:x for x in images}
    if len(by_name)!=len(images):raise ValueError('Repeated platform filename')
    for record in records:
        uploaded=by_name.get(record['id'])
        if uploaded is None:raise ValueError('Platform filename mapping differs: '+record['id'])
        if uploaded.get('split')!=record['split']:raise ValueError('Platform split differs')
        if (uploaded.get('width'),uploaded.get('height'))!=(record['width'],record['height']):
            raise ValueError('Platform dimensions differ')
        if not compare_boxes(uploaded.get('annotations',{}).get('boxes',[]),record['boxes']):
            raise ValueError('Platform annotations differ: '+record['id'])
    if args.platform_images:
        with ZipFile(args.zip) as archive:
            verify_remote_pixels(archive, records, images, args.platform_images)
        print('PLATFORM METADATA AND DECODED PIXELS VERIFIED for every image.')
    else:
        print('PLATFORM METADATA VERIFIED ONLY. Provide --platform-images to verify decoded pixels; import is not fully verified.')

if __name__=='__main__':main()
