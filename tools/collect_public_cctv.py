"""Collect selected CC-BY-4.0 real CCTV clips as review candidates."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import cv2
import requests
from prepare_cctv_v2 import ROOT, HF, sheet

def collect(filename):
    path=ROOT/'external/videos'/filename
    if not path.exists():
        response=requests.get(HF+'data/'+filename,timeout=90)
        response.raise_for_status()
        path.write_bytes(response.content)
    cap=cv2.VideoCapture(str(path))
    count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps=cap.get(cv2.CAP_PROP_FPS)
    selected=[]
    # One frame per clip initially; subsequent sampling needs visual review.
    frame_number=max(0,count//2)
    cap.set(cv2.CAP_PROP_POS_FRAMES,frame_number)
    ok,frame=cap.read()
    cap.release()
    if not ok: raise ValueError('Cannot decode '+filename)
    destination=ROOT/'external/frames'/(path.stem+'.jpg')
    cv2.imwrite(str(destination),frame,[cv2.IMWRITE_JPEG_QUALITY,95])
    return {'id':'public-'+path.stem,'path':str(destination),'video':filename,'frame':frame_number,
            'timestamp_seconds':round(frame_number/fps,3),'boxes':[], 'status':'pending_visual_review',
            'source_url':HF+'data/'+filename,'license':'CC-BY-4.0',
            'authors':'Oğuzhan Önal; Emre Dandıl',
            'source_dataset':'https://data.mendeley.com/datasets/xjmtb22pff/1',
            'group':'pending_camera_identification'}

def main():
    for directory in ['external/videos','external/frames','provenance','review/sheets']:
        (ROOT/directory).mkdir(parents=True,exist_ok=True)
    response=requests.get('https://huggingface.co/api/datasets/Voxel51/Safe_and_Unsafe_Behaviours/tree/main/data?limit=1000',timeout=60)
    response.raise_for_status()
    available={Path(x['path']).name for x in response.json() if x['type']=='file'}
    requested=[f'{cls}_te{i}.mp4' for cls in [0,3,4,7] for i in [1,10,20,30,40]]
    files=[x for x in requested if x in available]
    records=list(ThreadPoolExecutor(max_workers=5).map(collect,files))
    (ROOT/'review/public-candidates.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    sheet(records,ROOT/'review/sheets/public-candidates.jpg')
    print('public real CCTV candidates',len(records))
    print('missing requested clips',[x for x in requested if x not in available])

if __name__=='__main__':main()
