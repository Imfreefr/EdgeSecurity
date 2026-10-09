# OpenCode — integração pelo Codex

Branch: `feature/opencode-dataset-pipeline`. Sem merge/push. r82–r84 e
não-commitados da principal intactos. Nada aqui escreve em manifestos oficiais.

## Arquivos (todos novos, `tools/` + este doc)

- `opencode_pipeline.py` — núcleo: `preannotate_batch` (reusa `preannotate_local`,
  modelo `backend/model/edgev1.pt`), `import_images` (fonte/licença/grupo, teto 50/grupo),
  `find_duplicates_scalable` (SHA exato + aHash por bucket de dimensões + cache),
  `save_checkpoint`/`compact_report` (reusa `save_dataset_checkpoint`),
  `export_approved` (YOLO + `classes.txt`), `plan_acquisition`/`assign_splits`/`validate_acquisition`
  (splits 70/15/15 seed 42, guarda do teste congelado), `save_decision`/`load_working_state`,
  `build_dupe_worklist`/`cluster_dupe_pairs`/`save_dupe_decision` (tiers exact/near/similar,
  clusters, decisões persistentes), `flag_ambiguous_boxes` (IoU, UI),
  `validate_source`/`score_group_priority`/`acquisition_gates` (gates fonte/licença, sem downloads).
- `opencode_review_server.py` — UI local stdlib: `/` (setas navegam, +/- zoom, 0-3 classe,
  Del remove, Enter salva; filtro pendentes/decididas/todas; ⚠ ambíguas em vermelho;
  barra de progresso) e `/dupes` (lado a lado com tier/score/origem, aprovar/rejeitar,
  decididos somem); decisões em `<outdir>/decisions/` + `review-manifest.ndjson`
  e `<outdir>/dupe-decisions/` (cópias de trabalho).
- `opencode_dupes.py` — CLI que gera `dupes.json` a partir de cópia de manifesto.
- `test_opencode_pipeline.py` — 19 testes, fixtures sintéticas.
- `opencode_validate_p1.py` / `opencode_validate_dupes.py` / `opencode_validate_cargo.py` —
  validações manuais em cópias isoladas (caminhos locais fixos).

## Revisar e integrar

```powershell
git checkout feature/opencode-dataset-pipeline
git diff v6.4.3-vercel...HEAD --stat   # só arquivos opencode_*
.\.venv\Scripts\python -m unittest test_opencode_pipeline -v  # em tools/
.\.venv\Scripts\python tools/opencode_validate_p1.py          # lote 20, ~20 s
.\.venv\Scripts\python tools/opencode_validate_dupes.py       # lado a lado, ~10 s
.\.venv\Scripts\python tools/opencode_validate_cargo.py       # classe 3, ~15 s
# UI completa (revisão + duplicatas):
copy "<dataset>\original-review-r84-0331-reviewed\manifest.ndjson" C:\Temp\oc-manifest.ndjson
.\.venv\Scripts\python tools/opencode_dupes.py --manifest C:\Temp\oc-manifest.ndjson --outdir C:\Temp\oc-dupes
.\.venv\Scripts\python tools/opencode_review_server.py --manifest C:\Temp\oc-manifest.ndjson --outdir C:\Temp\oc-review --dupes C:\Temp\oc-dupes\dupes.json --port 8787
git checkout v6.4.3-vercel
git merge --no-ff feature/opencode-dataset-pipeline           # manual, quando quiser
```

## Resultados verificáveis (09/10/2026, CPU local)

- Unitários: 19/19 OK.
- Lote 20 real isolado (P1, revalidado): pré-anotação ~19 s, 0 inválidas;
  round-trip YOLO↔pixels erro ≤ 8,4e-17 (50 caixas); fila 20; bytes 3/3 idênticos;
  aprovação individual + adição + zero-detecção via API OK; restart retomou 2/2 decisões.
- Duplicatas (12 cópias): 14 pares em 2 clusters (tiers near/similar + scores);
  API lista 14, decisão persiste, decidido some (13 restam); erros 400; nada excluído.
- Classe 3 (6 cópias IMG_0492–0497): modelo emitiu classe 3 em 5/6 (0497 = miss do modelo,
  proposta cobre); UI exibiu 29 caixas classe 3; edição + save + export OK (8 linhas `3 `).
- Escala (340 imgs r84, só leitura): 33 s 1ª passada (17.326 comparações, 40.304
  puladas entre buckets, 16 exatas = as 16 conhecidas, 692 próximas candidatas,
  nada descartado); 2ª passada com cache 0,02 s. Projeção 1.340: ~2 min 1ª vez, instantâneo depois.
- r84 oficial intacto (`657f31a2…`), teste congelado intocado, nenhum download feito.
- Tela branca corrigida: `open` global colidia com `window.open` (LegacyUnforgeable) e o
  clique abria o id como URL (404). Renomeado p/ `openImg` + `onerror` com mensagem +
  zoom inicial ajustado (fit). Regressão em 21/21 testes; servidor 8787 reiniciado.

## Pendente de validação humana

- Inspeção visual das overlays (ferramenta validada, não anotação).
- Confirmar na UI `/dupes` os pares (começar pelos 2 clusters do piloto).
- Autorização de fonte/licença antes de baixar as 1.000 (`acquisition_gates` bloqueia:
  `download_allowed` sempre False até decisão explícita fora do código).
