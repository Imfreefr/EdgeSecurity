# Execução atual — 7 de outubro de 2026

## Estado verificado

O plano completo permanece **incompleto**. O preflight local encontrou 13
imagens de dois grupos, sem validação/teste. Não houve importação, novo treino,
comparação de modelos ou alteração do modelo publicado. Gasto novo: US$ 0.
O usuário executou a janela local e o registro `.local/ultralytics-access.json`
confirmou leitura autenticada de conta/datasets/faturamento. Permissão de escrita
não foi verificada. A chave foi usada apenas em memória nessa verificação e não
ficou disponível para execuções posteriores. Sua revogação não foi confirmada.

## Avanço desta execução

- `tools/ultralytics_tcc.py preflight` audita manifestos sem rede/credenciais.
- `check-access` verifica leituras de conta, faturamento e datasets pelo contrato
  OpenAPI oficial, sem imprimir tokens ou respostas completas.
- `status` faz uma consulta de progresso; **não é um monitor financeiro**.
- `import`, `train` e `export` estão explicitamente bloqueados, não implementados
  como operações remotas. Não usar esses comandos como evidência de integração
  concluída. Faltam fluxo mutável retomável e controle financeiro verificável.
- `verify_cctv_package.py --platform-images` compara os pixels RGB decodificados
  de todas as imagens baixadas com o ZIP, além dos metadados e caixas existentes.
  Conversões com perdas serão reprovadas, não toleradas silenciosamente.
- Testes usam imagens artificiais somente como fixtures de software; nenhuma
  delas é incluída no dataset.

## Fonte adicional encontrada, ainda não aprovada

**Warehouse — Addverb Technologies**

- Origem: https://universe.roboflow.com/addverb-technologies/warehouse-ijyxt
- A página do publicador declara 8.301 imagens e licença CC BY 4.0.
- Licença: https://creativecommons.org/licenses/by/4.0/
- Classes anunciadas incluem forklift, person e pallet, além de quatro classes
  que não devem ser importadas automaticamente para nossos IDs.
- A descrição da origem/gravações não está publicada na página consultada.
- Faltam acesso aos arquivos, inspeção do enquadramento, verificação de imagens
  reais, anotações e agrupamento independente. **Zero imagens aprovadas desta
  fonte.** Não constitui 20 cenas nem prova de diversidade.

Contagem comprovada permanece dois grupos do suplemento. Espelhos e projetos
que reutilizam o dataset Mendeley não contam como novas fontes independentes.
Datasets sintéticos encontrados na busca foram descartados para esta expansão.

## Próximos requisitos

1. Concluir a revisão visual e reunir pelo menos 20 grupos licenciados; congelar
   pacote que passe todos os critérios. Não importar o suplemento como versão final.
2. O proprietário deve revogar a chave exposta em Settings → API Keys e criar
   uma nova. API keys não podem criar/revogar chaves pela API.
3. Disponibilizar a nova chave **somente no ambiente local do processo**; nunca
   enviar pelo chat, gravar no repositório ou passar na linha de comando.
4. Implementar/testar upload retomável, reconciliação das imagens importadas,
   snapshot e vínculo dos treinos; comprovar controle de cobrança antes de iniciar.
5. Treinar, avaliar e demonstrar; só depois elaborar o relatório de código sem uso.

Referências oficiais:
https://docs.ultralytics.com/platform/api
https://platform.ultralytics.com/openapi.json
https://docs.ultralytics.com/platform/account/api-keys

## Comandos disponíveis

```powershell
python tools/ultralytics_tcc.py preflight --manifest "C:/Users/ELIPSE/Downloads/EdgeSecurity-CCTV-v2/public-collision-supplement-r2/manifest.ndjson" --registry tools/tcc_scene_registry.json
python tools/ultralytics_tcc.py check-access --owner felipe-souza-nascimento
python tools/verify_cctv_package.py "ZIP_FINAL" --platform-export "EXPORT.ndjson" --platform-images "PASTA_IMAGENS_BAIXADAS"
```

O primeiro comando retorna código 2 para o suplemento atual, como esperado.
O segundo exige credencial nova e não altera a conta. O terceiro exige export e
imagens realmente baixados da plataforma, com caminhos relativos correspondentes.

## Continuação: revisão r3 e pesquisa de fontes

- Dez quadros inspecionados individualmente: cinco originais e os cinco candidatos
  pendentes da câmera B. Isso não representa conclusão da revisão dos 340 originais.
- Removidas, em revisão separada, quatro caixas de cones indevidamente classificadas
  como carga em `IMG_0495.jpg`. A imagem permanece pendente de geometria/licença.
- `IMG_0421.jpg` excluída da seleção pela visão extremamente próxima da cabine.
- Os quadros `7_te5` e `7_te8` foram comparados: o pedestre distante aparece somente
  no primeiro. A variação útil foi preservada, não tratada como redundância confirmada.
- No quadro `3_te8`, trabalhadores junto a prensas fixas são pedestres, não operadores
  de empilhadeira. O título do clipe não pode substituir a inspeção visual dos alvos.
- Decisões e versão corrigida em `EdgeSecurity-CCTV-v2/collision-review-r3/`.
  Nenhum arquivo original, ZIP anterior ou dataset remoto foi sobrescrito.
- Registro de fontes atualizado: SPARL3 (CC BY 4.0 verificado pela API Zenodo),
  Addverb/tir_project (arquivos e agrupamento pendentes), DaRA (CC BY-NC 4.0,
  compatibilidade de uso ainda não aprovada). Não contar essas fontes como grupos
  aprovados antes da revisão. SPARL3 permanece em pesquisa, fora do pacote.

Referências de novas fontes:
https://zenodo.org/records/16636916
https://zenodo.org/records/10468175
https://universe.roboflow.com/iheb/tir_project

## Resultado dos pilotos baixados

- SPARL3: Experiment1.zip (1.289.311.312 bytes) conferido contra MD5 do publicador;
  vídeo de 493 segundos abriu. Cinco quadros compostos inspecionados individualmente.
  Eles misturam POV/visão próxima/ao nível do chão e pixelizam trabalhadores;
  nenhum foi incluído na expansão de CCTV elevada. Materiais permanecem em pesquisa.
- NVIDIA Physical AI Smart Spaces: baixar apenas cenas reais explicitamente
  declaradas pelo publicador, `Warehouse_026` e `Warehouse_027`. Todas as demais
  cenas sintéticas foram excluídas. Dois vídeos piloto e seis quadros decodificados
  e visualmente inspecionados; licença CC BY 4.0 da fonte oficial. Essa licença é
  de outra publicação, não o EULA incompatível do AMC NV Warehouse.
- Uma imagem recortada de corredor de Warehouse_027 foi anotada manualmente com
  quatro pedestres (classe 0), conferida na sobreposição transformada e exportada
  como `public-smartspaces-pedestrian-pilot-r1.zip`. Não é negativo; nenhuma
  empilhadeira ou operador oculto foi inferido. Caixas do lado cortado foram
  recortadas/conferidas junto com a imagem. JSON registra quadro/tempo/crop/hash.
- O piloto permanece separado do suplemento de 13 imagens. Portanto existem
  **14 imagens com revisão visual em dois pacotes públicos parciais**, mas apenas
  dois grupos originais verificados; o novo grupo/evento ainda tem independência
  pendente. Não existem 20 grupos aprovados, validação/teste ou versão final.
- Nenhum upload, treinamento ou cobrança. Relatório de código sem uso continua
  posterior à conclusão da IA, conforme a ordem solicitada.

Fontes do novo piloto:
https://huggingface.co/datasets/nvidia/PhysicalAI-SmartSpaces/blob/main/README.md
https://creativecommons.org/licenses/by/4.0/
