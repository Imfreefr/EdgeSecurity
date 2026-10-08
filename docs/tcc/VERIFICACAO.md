# Verificação local — 2026-10-07

História: câmera local → frame → ONNX Worker → classe/caixa → aproximação → UI.
Inferência antiga preservada; não existe ainda um modelo novo treinado.

| Fronteira | Resultado | Evidência |
| --- | --- | --- |
| Build | Passou | `npm run build`, Vite 6.4.3; modelo antigo copiado para dist/assets |
| Worker → modelo real | Passou | `node tests/browser-model.mjs`: resultado real para frame 640×480 |
| Câmera → inferência → overlay → parar | Passou | `node tests/camera-inference.mjs`, webcam simulada, ONNX real, API simulada |
| Operador/pedestre e escala | Passou | Dez casos compartilhados entre JavaScript e Python, incluindo 320/640/1280 de largura |
| Dimensões para cálculo de alerta | Passou | `node tests/ai-pipeline.mjs` verifica propagação de frame_width=1280 |
| Autorização websocket | Passou | Token ausente/inválido e câmera de outra empresa rejeitados; câmera própria aceita |
| Cadastro/estado da câmera | Passou | Testes de seleção/identidade e isolamento de empresas |
| Backend real → banco de alertas | Não verificado nesta entrega | API simulada no teste do navegador; teste de autorização não prova persistência |
| Dataset final | Reprovado corretamente | 13 imagens, apenas 2/20 grupos; val/test vazios |
| Importação na Ultralytics | Pendente | Sem sessão autenticada/conexão disponível |
| Novo treinamento/precisão | Pendente | Nenhuma execução lançada; resultados novos inexistentes |

Outras verificações: cinco testes do finalizador, quatro de orçamento,
cinco de curadoria pontual e oito de integridade/geometria passaram.
O método real de inferência do backend foi testado com tensores simulados:
IDs 0/1/2/3 são preservados e nomes com ponto inicial são normalizados.
As imagens geradas pelos testes do finalizador são fixtures artificiais
temporárias para testar código; não foram adicionadas a qualquer dataset.

Sem publicação, push, alteração do modelo, uso de credencial ou cobrança.

## Fontes investigadas

- Mendeley: CC BY 4.0, somente duas câmeras, aprovado como fonte atual.
  https://data.mendeley.com/datasets/xjmtb22pff/1
- AiSPRY: 99 imagens, licença CC BY 4.0 declarada; download, origem das cenas e
  revisão individual pendentes. Não contar como 99 cenas ou imagens aprovadas.
  https://universe.roboflow.com/aispry-inb32/forklift-monitoring-system
  Três prévias públicas foram baixadas e inspecionadas: uma foto ao nível dos
  olhos, um candidato CCTV de somente 200 pixels de largura e uma captura de
  erro do YouTube/navegador. As três estão fora do treino; a captura de erro não
  é negativo válido. Artefatos em EdgeSecurity-CCTV-v2/research/aispry-previews/.
- LOCO: CC0, mas câmeras em movimento/ao nível dos olhos, não serve para cumprir
  a diversidade de CCTV elevado. Não adicionado ao dataset.
  https://github.com/tum-fml/loco
- NVIDIA AMC NV Warehouse: seis câmeras reais, mas licença primária limita
  finalidade e proíbe redistribuição; excluído da expansão planejada.
  https://developer.download.nvidia.com/licenses/NVIDIA-Sample-Data-License.pdf

Essas buscas ainda não completam cinco dias de investigação nem provam que
fontes adicionais adequadas não existem. O marco continua em 2026-10-12.
