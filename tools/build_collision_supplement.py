"""Create a separate, quality-gated expansion without overwriting any earlier package."""
import hashlib
import json
import shutil
import zipfile
from collections import Counter
from pathlib import Path
from PIL import Image
from prepare_cctv_v2 import ROOT, sheet
from build_cctv_review import normalize, check_integrity


def clip_boxes(boxes, crop):
    result = []
    for cls, left, top, right, bottom in boxes:
        left, top = max(left, crop[0]), max(top, crop[1])
        right, bottom = min(right, crop[2]), min(bottom, crop[3])
        if left < right and top < bottom:
            result.append([cls, left-crop[0], top-crop[1], right-crop[0], bottom-crop[1]])
    return result


def main():
    revision = ROOT / 'collision-review'
    decisions = json.loads(Path(__file__).with_name('collision_extra_labels.json').read_text(encoding='utf-8'))
    candidates = json.loads((revision / 'candidates.json').read_text(encoding='utf-8'))
    package = ROOT / 'public-collision-supplement-r2'
    for directory in ('images/train', 'labels/train'):
        (package / directory).mkdir(parents=True, exist_ok=True)
    records = []
    previous = ROOT / 'public-reviewed-supplement'
    for line in (previous / 'manifest.ndjson').read_text(encoding='utf-8').splitlines():
        record = json.loads(line)
        record['path'] = str(previous / record['path'])
        records.append(record)
    for candidate in candidates:
        stem = Path(candidate['video']).stem
        decision = decisions['images'].get(stem)
        if decision is None:
            continue
        crop = decision['crop']
        width, height = crop[2]-crop[0], crop[3]-crop[1]
        path = revision / ('reviewed-'+stem+'.jpg')
        with Image.open(candidate['path']) as image:
            if list(image.size) != decisions['reference_dimensions']:
                raise ValueError('Unexpected source dimensions')
            image.crop(crop).save(path, quality=95)
        records.append({**candidate, 'path': str(path), 'width': width, 'height': height,
                        'boxes': normalize(clip_boxes(decision['boxes'], crop), width, height),
                        'group': 'public-factory-camera-B', 'split': 'train',
                        'framing': 'elevated_distant_cropped_corridor',
                        'confirmed_negative': False, 'status': 'approved_visual_review',
                        'review_method': decisions['method'], 'review_reason': decision['reason'],
                        'transform': {'type': 'frame_extraction_and_crop',
                                      'xyxy_source': crop, 'source_dimensions': [1920, 1080]}})
    integrity = check_integrity(records)
    counts = Counter(int(box[0]) for record in records for box in record['boxes'])
    portable = []
    for record in records:
        destination = package / 'images/train' / (record['id']+'.jpg')
        shutil.copy2(record['path'], destination)
        (package / 'labels/train' / (record['id']+'.txt')).write_text(
            ''.join(str(int(box[0]))+' '+' '.join(f'{value:.8f}' for value in box[1:])+'\n'
                    for box in record['boxes']), encoding='utf-8')
        portable.append({**record, 'path': 'images/train/'+destination.name,
                         'sha256': hashlib.sha256(destination.read_bytes()).hexdigest()})
    shutil.copy2(previous / 'data.yaml', package / 'data.yaml')
    shutil.copy2(previous / 'sources-licenses.csv', package / 'sources-licenses.csv')
    (package / 'manifest.ndjson').write_text(
        ''.join(json.dumps(record, ensure_ascii=False)+'\n' for record in portable), encoding='utf-8')
    statistics = {'status': 'PARTIAL_COLLISION_SUPPLEMENT_NOT_TRAINING_READY',
                  'images': len(records), 'newly_reviewed_images': len(decisions['images']),
                  'extra_candidates_pending': len(candidates)-len(decisions['images']),
                  'by_class_id': {str(cls): counts[cls] for cls in range(4)},
                  'by_camera': dict(Counter(record['group'] for record in records)),
                  'by_split': {'train': len(records), 'val': 0, 'test': 0},
                  'independent_camera_groups': len({record['group'] for record in records}),
                  'integrity': integrity, 'training_ready': False,
                  'platform_import_verified': False,
                  'blockers': ['Original individual box review unfinished',
                               'Fewer than 20 independent camera/scene groups',
                               'Camera-grouped validation and test not finalized',
                               'Platform import not performed or verified']}
    (package / 'statistics.json').write_text(json.dumps(statistics, indent=2), encoding='utf-8')
    notice = '''# Suplemento público CCTV r2 — PARCIAL, não iniciar treino

13 imagens revisadas: 10 da primeira entrega e 3 novas, com empilhadeiras,
operadores visíveis e trabalhadores em câmera elevada. Quatro IDs preservados.
Há apenas duas câmeras independentes. Treino=13, validação=0, teste=0.
Não é o dataset completo Edge Security CCTV v2 nem resolve todas as pendências.
Os 14 originais com alvos sem rótulos não foram incluídos. Nenhum original foi apagado.

Fonte: Önal, Oğuzhan; Dandıl, Emre (2024), Video Dataset for Safe and Unsafe
Behaviours, Mendeley Data, V1, DOI:10.17632/xjmtb22pff.1, CC BY 4.0.
https://data.mendeley.com/datasets/xjmtb22pff/1
https://creativecommons.org/licenses/by/4.0/
Espelho: https://huggingface.co/datasets/Voxel51/Safe_and_Unsafe_Behaviours
Modificações: extração de quadros, recortes de corredores/piso, caixas YOLO manuais.
Sem imagens sintéticas e sem endosso dos autores. Sem upload ou treinamento.
Manifesto NDJSON é rastreabilidade local; importar o ZIP YOLO para inspeção.
'''
    (package / 'LEIA-ME.md').write_text(notice, encoding='utf-8')
    sheet(records[-3:], revision / 'extra-approved.jpg', columns=3)
    destination = ROOT / 'EdgeSecurity-CCTV-colisao-r2-PARCIAL.zip'
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        # Whitelist only current manifests' files, never stale images from a rerun.
        for record in portable:
            for path in (record['path'], 'labels/train/'+record['id']+'.txt'):
                archive.write(package / path, path)
        for name in ('data.yaml', 'manifest.ndjson', 'sources-licenses.csv', 'statistics.json', 'LEIA-ME.md'):
            archive.write(package / name, name)
        archive.write(revision / 'decisions.csv', 'original-review-decisions.csv')
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError('Corrupt ZIP')
    (revision / 'supplement-statistics.json').write_text(json.dumps(statistics, indent=2), encoding='utf-8')
    print(json.dumps(statistics, ensure_ascii=False))
    print(destination)


if __name__ == '__main__':
    main()
