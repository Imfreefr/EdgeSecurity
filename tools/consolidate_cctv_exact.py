"""Consolidate reviewed identical pairs in a separate local supplementary lot."""
import json
import shutil
from pathlib import Path
from PIL import Image
from prepare_cctv_v2 import ROOT, AUDIT, sheet
from build_cctv_review import normalize, check_integrity

def main():
    decisions=json.loads(Path(__file__).with_name('cctv_exact_labels.json').read_text(encoding='utf-8'))
    original=json.loads((ROOT/'review/originals.json').read_text(encoding='utf-8'))
    audit=json.loads((AUDIT/'audit.json').read_text(encoding='utf-8'))
    pairs={min(pair):pair for pair in audit['exact_duplicate_groups']}
    package=ROOT/'original-reviewed-complement'
    for sub in ['images/train','labels/train']:(package/sub).mkdir(parents=True,exist_ok=True)
    records=[]
    for key,boxes in decisions['images'].items():
        index=int(key)
        item=original[index]
        with Image.open(item['path']) as im:width,height=im.size
        destination=package/'images/train'/(item['id']+'.jpg')
        shutil.copy2(item['path'],destination)
        normalized=normalize(boxes,*decisions['reference_dimensions'])
        record={**item,'path':str(destination),'width':width,'height':height,'boxes':normalized,
                'status':'approved_visual_review','confirmed_negative':False,'split':'train',
                'group':'original-IMG_0457-session','framing':'close_eye_level_supplement',
                'original_indices':pairs[index],'review_method':decisions['method'],
                'rights':'User-provided material; public redistribution rights not verified',
                'final_v2_inclusion':'pending_final_composition'}
        records.append(record)
        (package/'labels/train'/(item['id']+'.txt')).write_text(
            ''.join(str(int(b[0]))+' '+' '.join(f'{v:.8f}' for v in b[1:])+'\n' for b in normalized),encoding='utf-8')
    integrity=check_integrity(records)
    (package/'data.yaml').write_text('path: .\ntrain: images/train\nnames:\n  0: pessoa\n  1: maquina\n  2: operador\n  3: objeto\n',encoding='utf-8')
    (package/'manifest.ndjson').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in records),encoding='utf-8')
    (ROOT/'review/exact-consolidated.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    (package/'LEIA-ME.md').write_text(
        '# Complemento original revisado — não é o CCTV v2 final\n\n'
        '16 imagens únicas dos 16 pares idênticos; caixas redesenhadas manualmente.\n'
        'Enquadramento próximo/na altura das pessoas: não contar como câmeras altas.\n'
        'Manter a sessão inteira no mesmo conjunto. Inclusão final ainda pendente.\n'
        'Original e anotações alternativas preservados. Uso privado; direitos de\n'
        'redistribuição pública do material fornecido pelo usuário não verificados.\n',encoding='utf-8')
    sheet(records,ROOT/'review/sheets/exact-consolidated.jpg')
    print(json.dumps(integrity))

if __name__=='__main__':main()
