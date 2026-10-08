# Edge Security — pacote de conclusão do TCC

## Estado real

Veja também [EXECUCAO-ATUAL.md](EXECUCAO-ATUAL.md) para os comandos de preflight,
acesso somente leitura e comparação dos pixels importados. Importação e treino
automatizados ainda não estão implementados como operações remotas.

O plano completo ainda NÃO foi concluído. O suplemento atual possui 13 imagens,
71 caixas e duas câmeras. Não houve importação, treino novo, comparação de
precisão ou substituição do modelo publicado. O custo de novas execuções nesta
implementação é US$ 0. A chave exposta anteriormente não foi utilizada.

## Implementado localmente

- Operador permanece identificado, mas não é pedestre no cálculo de aproximação.
- Navegador e backend normalizam as faixas em uma largura de referência de
  640 pixels. Os campos de distância originais permanecem em pixels do frame;
  `gap_reference_pixels` explicita o valor utilizado para classificar o alerta.
- A resposta do backend informa dimensões reais do frame para alinhar caixas.
- As mensagens não afirmam colisão nem distâncias físicas calibradas.
- Finalizador bloqueia fontes sem direitos/grupos verificados, imagens sem
  revisão, duplicatas, ausência de negativos, divisão inadequada e menos de
  20 grupos novos. Não altera os manifestos de entrada.
- Parâmetros de treino e registro de gastos estão preparados, não executados.

## Dataset e importação

Revisar imagens individualmente e preparar manifestos com o contrato existente:
`id`, `path`, dimensões, `group`, `split`, `boxes`, `framing`,
`status=approved_visual_review` e `confirmed_negative` quando vazio.
As caixas são YOLO normalizadas `[classe,x,y,largura,altura]`.
Novos quadros devem ter enquadramento `elevated_*`. Grupos de cenas devem estar
no registro `tools/tcc_scene_registry.json` com evidência de independência,
origem/licença, permissões de treino/redistribuição e exposição ao `edgev1`.
Nunca inventar grupos diferentes para trechos da mesma câmera/evento.

Verificação atual, somente leitura (esperado: NOT_FINAL):

```powershell
python tools/finalize_tcc_dataset.py --manifest "C:/Users/ELIPSE/Downloads/EdgeSecurity-CCTV-v2/public-collision-supplement-r2/manifest.ndjson" --registry tools/tcc_scene_registry.json
```

Quando todos os registros estiverem aprovados, acrescentar manifestos usando
`--manifest` repetidamente; usar `--assign-splits` para a divisão determinística
por grupo, semente 42. O algoritmo reserva três grupos novos com pessoas e
empilhadeiras para cada holdout; se os tamanhos não permitirem aproximar
70/15/15, reprova e exige revisar a composição, não divide câmeras.
Acrescentar `--output "PASTA_NOVA"` apenas após os critérios passarem.
O export final é imutável: pasta/ZIP existente não será sobrescrito.

Importar ZIP em **Edge Security CCTV v2**, Detect, privado. Conferir os quatro
IDs e todos os conjuntos; baixar o export NDJSON e comparar:

```powershell
python tools/verify_cctv_package.py "ZIP_FINAL" --platform-export "EXPORT.ndjson"
```

Essa comparação prova metadados/caixas, NÃO identidade dos pixels remotos.
Conferir visualmente os uploads e baixar imagens para comparar os pixels
antes de declarar importação plenamente verificada. Criar versão congelada.

Formatos oficiais: https://docs.ultralytics.com/platform/data/

## Treino e controle de custos

Usar `training-recipes.json`, uma execução por vez. Selecionar a GPU pelo menor
custo estimado total, registrando preço/hora, estimativa e início. Confirmar
capacidade de observar custos e cancelar, incluindo possíveis cobranças
pendentes. Não habilitar recarga automática, comprar créditos ou usar
anotação paga. Parar novos gastos ao atingir US$ 18, mantendo US$ 6 de reserva;
o teto total autorizado continua US$ 24. Se não houver um controle seguro
de exposição à cobrança, não lançar trabalhos pagos.

Atualizar `training-ledger.json` com `name`, `status`, `estimated_usd`,
`actual_usd`, `billing_settled`, horários e referência da execução. Registrar
também falhas/cancelamentos. Guardar credenciais fora do repositório e dos logs.

O comando abaixo apenas verifica pré-condições; não inicia nada:

```powershell
python tools/check_tcc_budget.py --ledger docs/tcc/training-ledger.json --estimate-usd "ESTIMATIVA_REAL" --final-dataset-verified --monitoring-available
```

As flags são confirmações factuais, não substituem a auditoria. Estimativa
não é teto de cobrança. Não definir `time` na UI como garantia: a plataforma
pode ignorar esse parâmetro no editor cloud.
Referência: https://docs.ultralytics.com/platform/train/cloud-training/

## Avaliação e demonstração

Congelar teste antes dos treinamentos; somente novas cenas, nunca imagens ou
sequências relacionadas ao treino do modelo antigo. Selecionar na validação,
priorizando recall de pessoas, depois empilhadeiras, com latência como desempate.
Avaliar limiares 0.20, 0.30, 0.40 e 0.50 em validação e registrar falsos positivos;
não alegar ótimo global ou garantia operacional. Teste é avaliação final única.
Registrar precisão, recall, mAP50, mAP50–95 e matriz de confusão por classe;
destacar tamanho dos objetos e oclusões. Sem resultados, usar PENDENTE, nunca zero
ou números de outra base como se fossem novos experimentos.

Exportar o melhor modelo em FP32 e conferir o contrato ONNX do navegador.
Integrar só na demonstração local; manter o arquivo `edgev1` e hashes intactos.
Publicação em produção não está autorizada por este roteiro.

Testes de regressão:

```powershell
node tests/risk-engine.mjs
node tests/ai-pipeline.mjs
python -m unittest discover -s tests -p test_risk_engine.py
python -m unittest discover -s tests -p test_detector_classes.py
python tools/test_tcc_dataset.py
python tools/test_tcc_budget.py
python tools/test_collision_curation.py
python tools/test_cctv_review.py
```

Para os testes reais de navegador, servir localmente o projeto, incluindo o
modelo existente; executar `tests/browser-model.mjs` e `tests/camera-inference.mjs`.
As respostas de contas/API nesses testes são simuladas no navegador, para não
criar dados de produção. Isso verifica inferência/renderização, mas não comprova
persistência de alertas no backend real ou o desempenho do futuro modelo.

## Entrega para a banca

Utilizar `texto-base.md` e `resultados.csv`. Incluir fontes, dataset final,
pesos, configurações, custos, gráficos, matriz de confusão e exemplos de falhas.
Gravar vídeo com pessoa/empilhadeira detectadas, operador sem falso alerta,
situação vazia e oclusão/falha; explicar os limites de pixels e perspectiva.
Sem calibração, não apresentar valores em metros ou prevenção garantida.

O cronograma de quatro semanas é referência. A investigação de fontes começou
em 2026-10-07; o marco de cinco dias é 2026-10-12, sem contagem fictícia de dias.
Não há monitoramento autônomo agendado. Se a diversidade continuar insuficiente
nesse marco, solicitar decisão de escopo e preservar o status parcial.
