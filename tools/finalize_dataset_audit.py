"""Record visual review recommendations; never modify the source dataset."""
import csv
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps
from audit_dataset import load, source

OUT = Path(r'C:\Users\ELIPSE\Downloads\EdgeSecurity-dataset-audit')
records = [r for r in load(r'C:\Users\ELIPSE\Downloads\edge-security (1).ndjson') if r['type'] == 'image']
audit = json.loads((OUT / 'audit.json').read_text(encoding='utf-8'))
exact = {i for group in audit['exact_duplicate_groups'] for i in group}
near = {i for pair in audit['near_duplicate_candidate_pairs'] for i in (pair['a'], pair['b'])}
social = {'VID_20260820_064426_454', 'VID_20260820_065936_069', 'VID_20260820_051738_560'}
rows = []
for i, record in enumerate(records):
    recommendations = []
    group = source(record['file'])
    if i in exact:
        recommendations.append('Copia_identica_entre_train_val;consolidar_anotacoes_e_separar_por_gravacao')
    if i in near:
        recommendations.append('Similaridade_visual_candidata;comparar_antes_de_descartar')
    if group in social:
        recommendations.append('Texto_bordas_embutidos;obter_quadro_original_ou_recortar_e_reanotar')
    if record['file'].startswith('IMG_') and '_frame_' not in record['file']:
        recommendations.append('Foto_lateral_girada;corrigir_orientacao_junto_com_caixas;enquadramento_distante_a_adicionar')
    if group in {'VID-20260825-WA0010', 'VID-20260825-WA0011'}:
        recommendations.append('Camera_na_altura_das_pessoas;usar_como_complemento_ao_CFTV')
    if not record.get('annotations', {}).get('boxes'):
        recommendations.append('Ha_pessoas_ou_maquinas_visiveis_na_folha;revisar_rotulos_ausentes')
    rows.append({'index': i, 'file': record['file'], 'split': record['split'],
                 'recommendation': '|'.join(recommendations) or 'Revisar_variedade_e_qualidade_das_caixas',
                 'action_applied': 'Nenhuma;original_preservado'})
with (OUT / 'recommendations.csv').open('w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
with (OUT / 'near-duplicates.csv').open('w', encoding='utf-8-sig', newline='') as f:
    fields = ['a', 'file_a', 'b', 'file_b', 'distance', 'same_recording', 'cross_split']
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for pair in audit['near_duplicate_candidate_pairs']:
        writer.writerow({**pair, 'file_a': records[pair['a']]['file'], 'file_b': records[pair['b']]['file']})

# Annotated examples of the same pixels with different training/validation labels.
sheet = Image.new('RGB', (1000, 750), '#141820')
draw = ImageDraw.Draw(sheet)
for pos, i in enumerate([38, 317, 73, 320]):
    r = records[i]
    im = Image.open(OUT / 'images' / f'{i:03d}.webp').convert('RGB')
    painter = ImageDraw.Draw(im)
    for cls, x, y, w, h in r.get('annotations', {}).get('boxes', []):
        box = [(x - w / 2) * im.width, (y - h / 2) * im.height, (x + w / 2) * im.width, (y + h / 2) * im.height]
        painter.rectangle(box, outline=['#00ff70', '#ffaa00', '#00cfff', '#dd77ff'][int(cls)], width=5)
        painter.text((box[0], box[1]), str(int(cls)), fill='white', stroke_width=2, stroke_fill='black')
    im.thumbnail((480, 320))
    x, y = (pos % 2) * 500, (pos // 2) * 375
    sheet.paste(im, (x, y + 40))
    draw.text((x + 8, y + 8), f'{i:03d} {r["split"]} {len(r["annotations"]["boxes"])} boxes - {r["file"]}', fill='white')
sheet.save(OUT / 'annotation-conflicts.jpg', quality=95)
print('recommendations', len(rows), 'sideways_photo_review', sum('Foto_lateral_girada' in r['recommendation'] for r in rows), 'social_overlay_review', sum(source(r['file']) in social for r in records))
