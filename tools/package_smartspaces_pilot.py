"""Export one visually reviewed pedestrian crop, not the final dataset."""
import hashlib
import json
import zipfile
from pathlib import Path
from PIL import Image
from prepare_cctv_v2 import ROOT
from build_cctv_review import normalize, check_integrity, CLASSES
from build_collision_supplement import clip_boxes


def main():
    proposal = json.loads(Path(__file__).with_name('smartspaces_pilot_labels.json').read_text(encoding='utf-8'))
    if proposal['status'] != 'approved_visual_review':
        raise ValueError('Visual crop/box review not complete')
    source_records = json.loads((ROOT/'research/smartspaces-real/preview-manifest.json').read_text(encoding='utf-8'))
    source = next(record for record in source_records if record['id'] == proposal['source_id'])
    package = ROOT/'public-smartspaces-pedestrian-pilot-r1'
    archive_path = package.with_suffix('.zip')
    if package.exists() or archive_path.exists():
        raise ValueError('Pilot exists; refusing overwrite')
    identifier = 'public-smartspaces-027-camera5-5s-corridor'
    crop = proposal['crop']
    width, height = crop[2]-crop[0], crop[3]-crop[1]
    boxes = normalize(clip_boxes(proposal['boxes_source_xyxy'], crop), width, height)
    with Image.open(source['path']) as image:
        if list(image.size) != proposal['reference_dimensions']:
            raise ValueError('Geometry changed')
        image = image.crop(crop).convert('RGB')
    image_path = package/f'images/train/{identifier}.jpg'
    label_path = package/f'labels/train/{identifier}.txt'
    image_path.parent.mkdir(parents=True)
    label_path.parent.mkdir(parents=True)
    image.save(image_path, quality=95)
    record = {**source, 'id': identifier, 'path': str(image_path), 'width': width, 'height': height,
              'boxes': boxes, 'split': 'train', 'status': 'approved_visual_review',
              'approved_for_training': False, 'framing': 'elevated_cropped_corridor',
              'confirmed_negative': False, 'is_original': False,
              'group': 'smartspaces-real-unknown-related-events',
              'review_method': proposal['review_method'],
              'review_reason': proposal['reason'],
              'transform': {'type': 'frame_extraction_and_crop', 'xyxy_source': crop,
                            'source_dimensions': proposal['reference_dimensions']}}
    check_integrity([record])
    label_path.write_text(''.join(str(int(box[0]))+' '+' '.join(f'{v:.8f}' for v in box[1:])+'\n'
                                  for box in boxes), encoding='utf-8')
    portable = {**record, 'path': image_path.relative_to(package).as_posix(),
                'sha256': hashlib.sha256(image_path.read_bytes()).hexdigest()}
    (package/'manifest.ndjson').write_text(json.dumps(portable, ensure_ascii=False)+'\n', encoding='utf-8')
    (package/'data.yaml').write_text('path: .\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n'+
                                   ''.join(f'  {key}: {value}\n' for key, value in CLASSES.items()), encoding='utf-8')
    stats = {'status': 'PARTIAL_PEDESTRIAN_PILOT_NOT_FINAL', 'images': 1,
             'by_class_id': {'0': 4, '1': 0, '2': 0, '3': 0},
             'by_split': {'train': 1, 'val': 0, 'test': 0},
             'independence_verified': False, 'training_ready': False,
             'platform_import_verified': False}
    (package/'statistics.json').write_text(json.dumps(stats, indent=2), encoding='utf-8')
    (package/'sources-licenses.json').write_text(json.dumps({
        'author': 'NVIDIA', 'license': 'CC-BY-4.0',
        'license_url': 'https://creativecommons.org/licenses/by/4.0/',
        'source': source['source_dataset'], 'video': source['source_url'],
        'real_scene_evidence': 'Official dataset card explicitly identifies Warehouse_026/027 as real-world test captures.',
        'modifications': 'Frame at 5 seconds, documented crop, manual visible-pedestrian boxes, JPEG encoding.',
        'attribution': 'NVIDIA (2026), Physical AI Smart Spaces; no endorsement implied.'}, indent=2), encoding='utf-8')
    (package/'LEIA-ME.md').write_text(
        '# Piloto parcial — NÃO iniciar treino\n\n'
        'Uma imagem real de CCTV elevada, quatro pedestres; nenhum operador ou '
        'veículo oculto inferido. Não é negativo. Os quatro IDs estão preservados.\n\n'
        'Independência entre eventos/câmeras ainda não confirmada; todas as cenas '
        'reais desta fonte ficam agrupadas conservadoramente. Não cumpre 20 grupos '
        'nem validação/teste. Não houve importação ou treinamento. Originais e '
        'pacotes anteriores preservados.\n\n'
        'NVIDIA (2026), Physical AI Smart Spaces, CC BY 4.0. Origem e modificações '
        'em sources-licenses.json. Sem endosso dos autores.\n', encoding='utf-8')
    with zipfile.ZipFile(archive_path, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(package).as_posix())
    archive_path.with_suffix('.sha256').write_text(hashlib.sha256(archive_path.read_bytes()).hexdigest()+'  '+archive_path.name+'\n', encoding='utf-8')
    print(json.dumps(stats, indent=2))
    print(archive_path)


if __name__ == '__main__':
    main()
