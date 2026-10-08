"""Build traceable partial curation artifacts, never certify pending labels.

The supplement is importable but NOT the final v2 dataset. All supplement images
stay in train until the merged, camera-grouped split has been reviewed.
"""
import csv
import hashlib
import json
import math
import shutil
import zipfile
from collections import Counter
from pathlib import Path

from PIL import Image
from prepare_cctv_v2 import ROOT, AUDIT, sheet

CLASSES = {0: 'pessoa', 1: 'maquina', 2: 'operador', 3: 'objeto'}


def normalize(boxes, width, height):
    result = []
    for cls, left, top, right, bottom in boxes:
        if not (0 <= left < right <= width and 0 <= top < bottom <= height):
            raise ValueError(f'Invalid pixel box: {boxes}')
        result.append([cls, (left+right)/2/width, (top+bottom)/2/height,
                       (right-left)/width, (bottom-top)/height])
    return result


def validate_record(record):
    if record.get('status') != 'approved_visual_review':
        raise ValueError('Unreviewed record cannot be exported: '+record['id'])
    with Image.open(record['path']) as im:
        im.load()
        if im.size != (record['width'], record['height']):
            raise ValueError('Dimension mismatch: '+record['id'])
    if not record['boxes'] and not record.get('confirmed_negative'):
        raise ValueError('Empty labels require explicit negative confirmation')
    for cls, x, y, w, h in record['boxes']:
        if cls not in CLASSES or not all(math.isfinite(v) for v in (x,y,w,h)):
            raise ValueError('Invalid class/coordinate')
        if not (0 < w <= 1 and 0 < h <= 1 and x-w/2 >= -1e-8 and
                y-h/2 >= -1e-8 and x+w/2 <= 1+1e-8 and y+h/2 <= 1+1e-8):
            raise ValueError('Box outside image: '+record['id'])


def check_integrity(records):
    hashes, names, groups = set(), set(), {}
    for record in records:
        validate_record(record)
        if record['id'] in names:
            raise ValueError('Duplicate name')
        names.add(record['id'])
        with Image.open(record['path']) as im:
            digest = hashlib.sha256(str(im.size).encode()+im.convert('RGB').tobytes()).hexdigest()
        if digest in hashes:
            raise ValueError('Identical decoded pixels')
        hashes.add(digest)
        if groups.setdefault(record['group'],record['split']) != record['split']:
            raise ValueError('Camera/scene leakage')
    return {'images_open':True, 'boxes_valid':True, 'no_identical_pixels':True,
            'no_camera_group_leakage':True, 'reviewed_records':len(records)}


def write_csv(path, rows):
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def stage_originals():
    originals=json.loads((ROOT/'review/originals.json').read_text(encoding='utf-8'))
    audit=json.loads((AUDIT/'audit.json').read_text(encoding='utf-8'))
    consolidated_path=ROOT/'review/exact-consolidated.json'
    consolidated=({item['index']:item for item in json.loads(consolidated_path.read_text(encoding='utf-8'))}
                  if consolidated_path.exists() else {})
    canonical={}
    conflicts=[]
    for pair in audit['exact_duplicate_groups']:
        keep=min(pair)
        for index in pair: canonical[index]=keep
        conflicts.append({'canonical_index':keep,'members':pair,
                          'status':'consolidated_visual_review' if keep in consolidated else 'pending_label_consolidation',
                          'reason':'Manual redrawing; one occurrence, alternatives preserved' if keep in consolidated else
                                   'Identical pixels, conflicting labels; alternatives preserved, not unioned'})
    rows=[]
    staged=[]
    for item in originals:
        index=item['index']
        duplicate=index in canonical and canonical[index]!=index
        eyes_level=item['group'] in {'VID-20260825-WA0010','VID-20260825-WA0011'}
        status='duplicate_reference_only' if duplicate else ('quarantine_viewpoint' if eyes_level else 'pending_label_review')
        reason=('Identical pixels; labels retained as an alternative for consolidation' if duplicate else
                'Eye-level shop footage, not elevated CCTV; visible targets, not a negative' if eyes_level else
                'Rotation prepared; semantic and box review pending' if item['rotation_ccw'] else
                'Box/crop/origin review pending')
        if index in consolidated:
            status='reviewed_close_view_complement'
            reason='Exact-pair labels manually consolidated; one copy retained in a separate close-view supplementary lot'
        group=('original-indoor-forklift-session' if item['rotation_ccw'] else item['group'])
        updated={**item,'status':status,'camera_group':group,'canonical_index':canonical.get(index,index)}
        staged.append(updated)
        rows.append({'index':index,'original_file':item['file'],'review_file':item['path'],
                     'rotation_ccw':item['rotation_ccw'],'camera_group':group,'action':status,
                     'canonical_index':canonical.get(index,index),'reason':reason,
                     'labels_empty':not bool(item['boxes']),'original_preserved':True})
    (ROOT/'review/original-decisions.json').write_text(json.dumps(staged,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'review/exact-label-conflicts.json').write_text(json.dumps(conflicts,ensure_ascii=False,indent=2),encoding='utf-8')
    write_csv(ROOT/'changes-originals.csv',rows)
    pair_decisions=json.loads(Path(__file__).with_name('cctv_pair_decisions.json').read_text(encoding='utf-8'))
    ambiguous=set(pair_decisions['ambiguous_pair_indices'])
    near=[]
    for number,pair in enumerate(audit['near_duplicate_candidate_pairs']):
        uncertain=number in ambiguous
        enlarged=pair_decisions.get('enlarged_decisions',{}).get(str(number))
        near.append({**pair,'pair_index':number,
                     'review_status':'pending_enlarged_comparison' if uncertain else 'visual_comparison_complete',
                     'decision':enlarged['decision'] if enlarged else ('retain_uncertain' if uncertain else 'retain_visible_variation'),
                     'reason':enlarged['reason'] if enlarged else pair_decisions['enlarged_visible_variation'].get(str(number),
                              pair_decisions['ambiguous_reason'] if uncertain else pair_decisions['remaining_reason']),
                     'sheet':f'review/ambiguous-enlarged/pair-{number:03d}.jpg' if enlarged else
                             f'review/sheets/near-pairs-{number//12+1:02d}.jpg'})
    write_csv(ROOT/'near-duplicate-review.csv',near)
    return originals, rows, conflicts, near


def public_records():
    candidates=json.loads((ROOT/'review/public-candidates.json').read_text(encoding='utf-8'))
    decisions=json.loads(Path(__file__).with_name('cctv_public_labels.json').read_text(encoding='utf-8'))
    result=[]
    for item in candidates:
        stem=Path(item['video']).stem
        if stem not in decisions['images']:continue
        with Image.open(item['path']) as im:width,height=im.size
        camera_b=stem in {'3_te1','7_te1'}
        # Camera A's left side contains heavily occluded press workers. Retain
        # the wide corridor, avoiding uncertain labels, while keeping the view
        # elevated. This is a documented crop, not a new independent scene.
        region=[0,0,width,height] if camera_b else [600,0,width,height]
        reviewed_boxes=[]
        for cls,left,top,right,bottom in decisions['images'][stem]:
            left=max(left,region[0]);top=max(top,region[1])
            right=min(right,region[2]);bottom=min(bottom,region[3])
            if right>left and bottom>top:
                reviewed_boxes.append([cls,left-region[0],top-region[1],right-region[0],bottom-region[1]])
        destination=ROOT/'external/frames'/('reviewed-'+stem+'.jpg')
        with Image.open(item['path']) as im:im.crop(region).save(destination,quality=95)
        cropped_width,cropped_height=region[2]-region[0],region[3]-region[1]
        result.append({**item,'path':str(destination),'width':cropped_width,'height':cropped_height,
                       'boxes':normalize(reviewed_boxes,cropped_width,cropped_height),
                       'authors':'Oğuzhan Önal; Emre Dandıl',
                       'group':'public-factory-camera-B' if camera_b else 'public-factory-camera-A',
                       'split':'train','framing':'elevated_distant','confirmed_negative':False,
                       'status':'approved_visual_review','review_method':'manual_boxes_after_visual_inspection',
                       'transform':{'type':'frame_extraction_and_crop','xyxy_source':region,'source_dimensions':[width,height]}})
    for crop in decisions['negative_crops']:
        parent=next(x for x in result if Path(x['video']).stem==crop['source'])
        destination=ROOT/'external/frames'/(crop['id']+'.jpg')
        source_path=next(x['path'] for x in candidates if Path(x['video']).stem==crop['source'])
        with Image.open(source_path) as im:im.crop(crop['crop']).save(destination,quality=95)
        result.append({**parent,'id':crop['id'],'path':str(destination),
                       'width':crop['crop'][2]-crop['crop'][0],'height':crop['crop'][3]-crop['crop'][1],
                       'boxes':[],'confirmed_negative':True,
                       'framing':'elevated_floor_crop',
                       'transform':{'type':'crop','xyxy_source':crop['crop'],'same_source_as':parent['id']},
                       'review_reason':crop['reason']})
    return result


def main():
    originals,changes,conflicts,near=stage_originals()
    records=public_records()
    integrity=check_integrity(records)
    package=ROOT/'public-reviewed-supplement'
    package.mkdir(exist_ok=True)
    for sub in ['images/train','labels/train']:(package/sub).mkdir(parents=True,exist_ok=True)
    manifests=[]
    for item in records:
        filename=item['id']+'.jpg'
        dest=package/'images/train'/filename
        shutil.copy2(item['path'],dest)
        labels=package/'labels/train'/(item['id']+'.txt')
        labels.write_text(''.join(' '.join([str(int(box[0]))]+[f'{v:.8f}' for v in box[1:]])+'\n'
                                  for box in item['boxes']),encoding='utf-8')
        manifests.append({**item,'path':str(dest.relative_to(package)).replace('\\','/'),
                          'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
    yaml='path: .\ntrain: images/train\n# Supplement only: merged val/test split NOT finalized.\nnames:\n'+''.join(f'  {key}: {name}\n' for key,name in CLASSES.items())
    (package/'data.yaml').write_text(yaml,encoding='utf-8')
    (package/'manifest.ndjson').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in manifests),encoding='utf-8')
    sources=[{'source':'Video Dataset for Safe and Unsafe Behaviours','authors':'Oğuzhan Önal; Emre Dandıl',
              'version':'1','doi':'10.17632/xjmtb22pff.1','url':'https://data.mendeley.com/datasets/xjmtb22pff/1',
              'license':'CC-BY-4.0','license_url':'https://creativecommons.org/licenses/by/4.0/',
              'download_mirror':'https://huggingface.co/datasets/Voxel51/Safe_and_Unsafe_Behaviours',
              'modifications':'Frames extracted; manual YOLO boxes; one crop; no synthetic imagery',
              'verified_date':'2026-10-07','independent_cameras':2}]
    write_csv(package/'sources-licenses.csv',sources)
    counts=Counter(int(box[0]) for item in records for box in item['boxes'])
    statistics={'status':'PARTIAL_NOT_FINAL_V2','original_images':len(originals),
                'original_candidates_after_exact_pixel_dedup':len(originals)-sum(len(x['members'])-1 for x in conflicts),
                'exact_conflicts_pending':sum(x['status']=='pending_label_consolidation' for x in conflicts),
                'exact_pairs_consolidated':sum(x['status']=='consolidated_visual_review' for x in conflicts),
                'near_pairs_visual_triage':len(near),
                'near_pairs_confirmed_variation':sum(x['decision']=='retain_visible_variation' for x in near),
                'near_pairs_retained_conservatively':sum(x['decision']=='retain_conservative' for x in near),
                'near_pairs_pending':sum(x['review_status']=='pending_enlarged_comparison' for x in near),
                'rotated_review_copies':sum(bool(x['rotation_ccw']) for x in originals),
                'originals_quarantined_viewpoint':sum(x['action']=='quarantine_viewpoint' for x in changes),
                'originals_visual_label_review_complete':sum(x['status']=='consolidated_visual_review' for x in conflicts),
                'originals_final_v2_inclusion_approved':0,'new_reviewed_images':len(records),
                'new_unique_recordings':len({x['video'] for x in records}),
                'new_independent_camera_groups':len({x['group'] for x in records}),
                'new_negative_crops':sum(x['confirmed_negative'] for x in records),
                'by_class':{CLASSES[k]:counts[k] for k in CLASSES},
                'by_split':dict(Counter(x['split'] for x in records)),
                'by_camera':dict(Counter(x['group'] for x in records)),
                'by_framing':dict(Counter(x['framing'] for x in records)),
                'by_source':{'Mendeley xjmtb22pff v1':len(records)},
                'validation':integrity,'platform_import_verified':False,
                'completion_gate':{'curation_complete':False,'three_way_split_complete':False,
                                   'twenty_independent_scenes':False,'final_import_verified':False}}
    (ROOT/'report.json').write_text(json.dumps(statistics,ensure_ascii=False,indent=2),encoding='utf-8')
    notice='''# Entrega parcial — não é o dataset CCTV v2 final

Este ZIP contém SOMENTE o suplemento público revisado. Não contém o dataset
original, nem conclui sua curadoria. Não treinar nem comparar modelos usando
este suplemento isolado: val/test ainda precisam ser definidos no conjunto
combinado. Todos os arquivos estão em train para não dividir a mesma câmera.

IDs: 0 pessoa fora da empilhadeira; 1 empilhadeira (não prensa industrial fixa);
2 operador visualmente identificável conduzindo; 3 carga, caixa ou pallet.
Rótulos do vídeo original eram de comportamento, NÃO caixas de detecção.
As caixas YOLO deste pacote foram criadas após inspeção visual dos quadros.
Um negativo é recorte de piso real, não uma nova gravação independente.

Atribuição: Önal, Oğuzhan; Dandıl, Emre (2024), Video Dataset for Safe and
Unsafe Behaviours, Mendeley Data, V1, doi:10.17632/xjmtb22pff.1, CC BY 4.0.
https://data.mendeley.com/datasets/xjmtb22pff/1
https://creativecommons.org/licenses/by/4.0/
Alterações: extração de quadros, anotação de caixas e um recorte. Sem imagens
sintéticas. Não há endosso dos autores ao Edge Security.

manifest.ndjson é manifesto de rastreabilidade LOCAL, não um export NDJSON da
plataforma com URLs hospedadas. Para importar, use o ZIP YOLO, não o manifesto.
'''
    (package/'LEIA-ME.md').write_text(notice,encoding='utf-8')
    sheet(records,ROOT/'review/sheets/public-reviewed.jpg')
    zip_path=ROOT/'EdgeSecurity-CCTV-public-supplement-PARCIAL.zip'
    with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package.rglob('*')):
            if path.is_file():archive.write(path,path.relative_to(package).as_posix())
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:raise ValueError('Corrupt ZIP')
    (ROOT/'supplement.sha256').write_text(hashlib.sha256(zip_path.read_bytes()).hexdigest()+'  '+zip_path.name+'\n',encoding='utf-8')
    report=f'''# Edge Security CCTV v2 — estado parcial

Original preservado. {len(originals)} cópias preparadas, {statistics['rotated_review_copies']} rotacionadas com suas caixas.
{len(conflicts)} pares idênticos com rótulos conflitantes: {statistics['exact_pairs_consolidated']} consolidados por
redesenho manual das caixas; alternativas preservadas, sem união automática.
São fotos próximas, mantidas em original-reviewed-complement/ como complemento,
não aprovadas ainda para a composição final de CFTV. {len(near)} pares próximos tiveram
triagem visual: {statistics['near_pairs_confirmed_variation']} preservados por variação visível,
{statistics['near_pairs_retained_conservatively']} preservados por decisão conservadora, sem comprovação suficiente de redundância,
{statistics['near_pairs_pending']} ainda pendentes de comparação ampliada.
Nenhum foi removido só por similaridade.
As 14 imagens sem rótulos não foram declaradas negativas: há alvos visíveis.
{statistics['originals_quarantined_viewpoint']} quadros de supermercado separados por enquadramento na altura das pessoas.

## Suplemento público

{len(records)} imagens anotadas/revisadas: 9 quadros reais de 9 clipes e 1 recorte negativo.
Somente 2 grupos de câmera independentes. Origem CC BY 4.0 confirmada na fonte
primária, com atribuição incluída. Não se cumpriu a meta de 20 cenas independentes.
Distribuição de caixas: {json.dumps(statistics['by_class'],ensure_ascii=False)}.
Conjuntos: train={len(records)}, val=0, test=0; divisão definitiva NÃO concluída.
ZIP validado, imagens decodificadas, caixas válidas, sem pixels idênticos.
Uma foto vazia de caixas/pallets, mas com pessoas, NÃO é um negativo.

## Pendências para concluir o plano

- Conferir a participação das 16 imagens originais consolidadas na composição final.
- Revisar/corrigir as caixas dos originais e recortes de textos/bordas.
- Encontrar fontes adicionais adequadas para diversidade real de câmeras/cenas.
- Dividir o conjunto combinado por grupo em aproximadamente 70/15/15.
- Exportar o ZIP FINAL v2 somente após essas etapas.
- Importar assistidamente e comparar a plataforma com o manifesto local.

## Importação assistida

O ZIP suplementar é tecnicamente importável no formato YOLO aceito pela
Ultralytics (https://docs.ultralytics.com/platform/data). Para inspecioná-lo
agora, criar um dataset PRIVADO separado chamado “Edge Security CCTV v2 — prévia”,
tarefa Detect; nunca sobrescrever Edge Security. Conferir 10 imagens, 4 IDs de
classe e os números de caixas em report.json. Não iniciar treinamento pago.
Para a versão final usar “Edge Security CCTV v2” após concluir as pendências.
Não tive acesso à sessão autenticada; não foi feita nem verificada importação.

Arquivos: changes-originals.csv (340 decisões/estados), near-duplicate-review.csv,
review/exact-label-conflicts.json, review/original-decisions.json, report.json,
public-reviewed-supplement/ e EdgeSecurity-CCTV-public-supplement-PARCIAL.zip.

## Prévia combinada privada

Também foi preparado EdgeSecurity-CCTV-v2-PREVIA-PRIVADA.zip: 26 imagens revisadas
(16 originais suplementares + 10 novas), com YOLO, data.yaml, manifesto e estatísticas.
Consultar preview-statistics.json para as contagens combinadas. São apenas 3 grupos,
todos em train; NÃO é a divisão final 70/15/15. A licença de redistribuição dos
originais não foi verificada: não publicar esse pacote misto nem o dataset da prévia.
O suplemento tem apenas uma anotação de operador e não deve ser tratado como
expansão suficiente/equilibrada para treinamento das quatro classes.
'''
    report+='''
Após importação assistida, baixar o NDJSON da plataforma e comparar com:
`python tools/verify_cctv_package.py "C:/Users/ELIPSE/Downloads/EdgeSecurity-CCTV-v2/EdgeSecurity-CCTV-v2-PREVIA-PRIVADA.zip" --platform-export "CAMINHO_DO_EXPORT.ndjson"`
Essa comparação verifica metadados e caixas, não os hashes dos pixels remotos.
Não fornecer credenciais ou tokens; o comando lê o export local e não faz upload.
'''
    (ROOT/'RELATORIO.md').write_text(report,encoding='utf-8')
    print(json.dumps(statistics,ensure_ascii=False,indent=2))
    print('Supplement:',zip_path)


if __name__=='__main__':main()
