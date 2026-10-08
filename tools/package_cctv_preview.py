"""Package only reviewed lots; clearly marked private preview, not final v2."""
import json
import shutil
import hashlib
import zipfile
from collections import Counter
from pathlib import Path
from prepare_cctv_v2 import ROOT
from build_cctv_review import check_integrity

def main():
    preview=ROOT/'private-preview'
    for sub in ['images/train','labels/train']:(preview/sub).mkdir(parents=True,exist_ok=True)
    records=[]
    for lot in ['original-reviewed-complement','public-reviewed-supplement']:
        package=ROOT/lot
        for line in (package/'manifest.ndjson').read_text(encoding='utf-8').splitlines():
            record=json.loads(line)
            source=Path(record['path'])
            if not source.is_absolute():source=package/source
            dest=preview/'images/train'/(record['id']+'.jpg')
            shutil.copy2(source,dest)
            shutil.copy2(package/'labels/train'/(record['id']+'.txt'),preview/'labels/train'/(record['id']+'.txt'))
            records.append({**record,'path':str(dest),'split':'train'})
    integrity=check_integrity(records)
    shutil.copy2(ROOT/'public-reviewed-supplement/data.yaml',preview/'data.yaml')
    shutil.copy2(ROOT/'public-reviewed-supplement/sources-licenses.csv',preview/'sources-licenses.csv')
    portable=[{**x,'path':'images/train/'+x['id']+'.jpg',
               'sha256':hashlib.sha256(Path(x['path']).read_bytes()).hexdigest()} for x in records]
    (preview/'manifest.ndjson').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in portable),encoding='utf-8')
    counts=Counter(int(b[0]) for x in records for b in x['boxes'])
    statistics={'status':'PRIVATE_PREVIEW_NOT_FINAL','images':len(records),
                'by_class_id':{str(i):counts[i] for i in range(4)},
                'by_camera':dict(Counter(x['group'] for x in records)),
                'by_framing':dict(Counter(x.get('framing','unknown') for x in records)),
                'by_split':{'train':len(records),'val':0,'test':0},
                'integrity':integrity,'final_split_approved':False,'platform_import_verified':False}
    (preview/'statistics.json').write_text(json.dumps(statistics,ensure_ascii=False,indent=2),encoding='utf-8')
    notice='''# PRÉVIA PRIVADA — NÃO É O DATASET V2 FINAL

26 imagens revisadas: 16 originais consolidadas (enquadramento próximo) e
10 novas imagens reais (9 quadros de CCTV + 1 recorte negativo).
Somente 3 grupos de sessão/câmera. Não cumpre 20 cenas independentes.
Todas as imagens estão em train para não introduzir vazamento: a divisão
70/15/15 NÃO está feita. Não treinar/comparar modelos com esta prévia.
Restante da curadoria original e expansão ainda pendentes: ver RELATORIO.md
na pasta superior. Manter o dataset Edge Security atual intacto.

Importação opcional apenas para inspeção: criar dataset PRIVADO separado
“Edge Security CCTV v2 — prévia”, tarefa Detect, e importar este ZIP YOLO.
Conferir 26 imagens, 4 IDs e contagens de statistics.json; exportar NDJSON
para verificação posterior. A importação não foi feita nem verificada pelo agente.

IDs preservados: 0 pessoa; 1 maquina/empilhadeira; 2 operador; 3 objeto/carga.
manifest.ndjson é rastreabilidade local, não um export importável com URLs.

Direitos dos originais: material fornecido pelo usuário, sem verificação de
licença para redistribuição pública. NÃO publicar este pacote misto.
Novos quadros: Önal, Oğuzhan; Dandıl, Emre (2024), Video Dataset for Safe
and Unsafe Behaviours, Mendeley Data, V1, doi:10.17632/xjmtb22pff.1, CC BY 4.0.
https://data.mendeley.com/datasets/xjmtb22pff/1
https://creativecommons.org/licenses/by/4.0/
Alterações: extração, recortes e caixas YOLO manuais; sem endosso dos autores.
Nenhuma imagem sintética, treinamento pago ou alteração do modelo publicado.
'''
    (preview/'LEIA-ME.md').write_text(notice,encoding='utf-8')
    destination=ROOT/'EdgeSecurity-CCTV-v2-PREVIA-PRIVADA.zip'
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(preview.rglob('*')):
            if path.is_file():archive.write(path,path.relative_to(preview).as_posix())
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:raise ValueError('ZIP corruption')
        images=[x for x in archive.namelist() if x.startswith('images/') and x.endswith('.jpg')]
        if len(images)!=len(records):raise ValueError('ZIP image count mismatch')
    (ROOT/'preview.sha256').write_text(hashlib.sha256(destination.read_bytes()).hexdigest()+'  '+destination.name+'\n',encoding='utf-8')
    (ROOT/'preview-statistics.json').write_text(json.dumps(statistics,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(statistics,ensure_ascii=False,indent=2))
    print(destination)

if __name__=='__main__':main()
