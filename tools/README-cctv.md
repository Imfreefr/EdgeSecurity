# Curadoria local CCTV — implementação parcial

## Revisão focada em colisões (r2)

Executar, preservando as prévias anteriores:

```powershell
python tools/curate_collision_originals.py
python tools/collect_collision_candidates.py
python tools/build_collision_supplement.py
python tools/test_collision_curation.py
python tools/verify_cctv_package.py "C:/Users/ELIPSE/Downloads/EdgeSecurity-CCTV-v2/EdgeSecurity-CCTV-colisao-r2-PARCIAL.zip"
```

Correção local pontual de pessoa fora da máquina (classe 2 → 0), sem aprovar
a anotação incompleta do ocupante; 14 quadros com alvos não anotados excluídos
da seleção e explicitamente não negativos; 1 operador ambíguo separado.
O suplemento r2 tem 13 imagens/71 caixas (10 anteriores + 3 novas), duas
câmeras e nenhum val/test. NÃO está pronto para treinamento. Cinco candidatos
novos permanecem pendentes. Ver collision-review/ para rastreabilidade.

Saída: `C:/Users/ELIPSE/Downloads/EdgeSecurity-CCTV-v2`.
Originais e produção permanecem intactos. Não executa treinamento ou upload.

Dependências já utilizadas no ambiente: Python, Pillow, requests e OpenCV.

Ordem de execução, a partir da raiz do repositório:

```powershell
python tools/prepare_cctv_v2.py
python tools/collect_public_cctv.py
python tools/render_cctv_pairs.py
python tools/render_cctv_ambiguous.py
python tools/consolidate_cctv_exact.py
python tools/build_cctv_review.py
python tools/package_cctv_preview.py
python tools/test_cctv_review.py
python tools/verify_cctv_package.py "C:/Users/ELIPSE/Downloads/EdgeSecurity-CCTV-v2/EdgeSecurity-CCTV-v2-PREVIA-PRIVADA.zip"
```

Os primeiros scripts dependem do cache da auditoria em
`C:/Users/ELIPSE/Downloads/EdgeSecurity-dataset-audit`, dos exports originais e
de rede para coleta das fontes públicas. Os scripts de empacotamento não
apagam arquivos: usar uma pasta de saída nova para uma revisão de composição
que remova itens, para não carregar resíduos de uma versão anterior.

As decisões manuais estão em `cctv_exact_labels.json`, `cctv_public_labels.json`
e `cctv_pair_decisions.json`. Não equivalem a aprovação de todo o dataset:
somente os dois lotes revisados entram na prévia. Nenhum rótulo pendente é
promovido automaticamente. Cada câmera/sessão fica inteira no mesmo conjunto.

Entrega atual: 26 imagens/82 caixas, todas em train, sem val/test. A prévia NÃO
é adequada para treinamento/comparação nem cumpre a meta de 20 cenas. O original
rotacionado precisa de revisão semântica: por exemplo, estar sentado na máquina
ou ajustando o calçado não basta para receber classe operador conduzindo.

Após eventual importação assistida em dataset privado de prévia:

```powershell
python tools/verify_cctv_package.py "C:/Users/ELIPSE/Downloads/EdgeSecurity-CCTV-v2/EdgeSecurity-CCTV-v2-PREVIA-PRIVADA.zip" --platform-export "CAMINHO_DO_EXPORT.ndjson"
```

Compara nomes, dimensões, classes, caixas e splits do export com o pacote.
Não comprova igualdade dos pixels remotos; não solicita nem envia credenciais.
