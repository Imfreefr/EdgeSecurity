# OpenCode — integração pelo Codex

Branch: `feature/opencode-dataset-pipeline`. Sem merge/push. r82–r84 e
não-commitados da principal intactos. Nada aqui escreve em manifestos oficiais.

## Arquivos (todos novos, `tools/` + este doc)

- `opencode_pipeline.py` — núcleo: `preannotate_batch` (reusa `preannotate_local`,
  modelo `backend/model/edgev1.pt`), `import_images` (fonte/licença/grupo, teto 50/grupo),
  `find_duplicates_scalable` (SHA exato + aHash por bucket de dimensões + cache),
  `save_checkpoint`/`compact_report` (reusa `save_dataset_checkpoint`),
  `export_approved` (YOLO + `classes.txt`), `plan_acquisition`/`assign_splits`/`validate_acquisition`
  (splits 70/15/15 seed 42, guarda do teste congelado), `save_decision`/`load_working_state`.
- `opencode_review_server.py` — UI local stdlib (`/api/queue`, `/img`, `/api/decide`);
  decisões em `<outdir>/decisions/` + `review-manifest.ndjson` (cópia de trabalho).
- `test_opencode_pipeline.py` — 14 testes, fixtures sintéticas.
- `opencode_validate_p1.py` — validação manual do lote de 20 (caminhos locais fixos).

## Revisar e integrar

```powershell
git checkout feature/opencode-dataset-pipeline
git diff v6.4.3-vercel...HEAD --stat   # só os 5 arquivos acima
.\.venv\Scripts\python -m unittest test_opencode_pipeline -v  # em tools/
.\.venv\Scripts\python tools/opencode_validate_p1.py          # lote 20, ~20 s
git checkout v6.4.3-vercel
git merge --no-ff feature/opencode-dataset-pipeline           # manual, quando quiser
```

## Resultados verificáveis (09/10/2026, CPU local)

- Unitários: 14/14 OK (0,17 s).
- Lote 20 real isolado: pré-anotação 18,8 s, 0 inválidas, 10 flags overlap;
  round-trip YOLO↔pixels erro ≤ 8,4e-17 (50 caixas); fila 20; bytes 3/3 idênticos;
  aprovação individual + adição + zero-detecção via API OK; restart retomou 2/2 decisões.
- Escala (340 imgs r84, só leitura): 33 s 1ª passada (17.326 comparações, 40.304
  puladas entre buckets, 16 exatas = as 16 conhecidas, 692 próximas candidatas,
  nada descartado); 2ª passada com cache 0,02 s. Projeção 1.340: ~2 min 1ª vez, instantâneo depois.
- r84 oficial intacto (`657f31a2…`), teste congelado intocado.

## Pendente de validação humana

- Inspeção visual das overlays (nenhum teste substitui; P1 validou ferramenta, não anotação).
- Confirmar as 692 próximas candidatas uma a uma antes de qualquer exclusão.
- Autorização de fonte/licença antes de baixar as 1.000 novas; grupos val/teste ≥3
  só verificáveis com os grupos reais (`validate_acquisition`).
- Classe 3 (carga) não apareceu no lote de 20 — cobrir em lote com paletes.
