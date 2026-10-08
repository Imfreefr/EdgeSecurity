# Dataset: prioridade de execução

A pedido do usuário, a curadoria e a expansão têm prioridade sobre a implementação
de múltiplas câmeras e a auditoria do código. Alterações existentes são preservadas.

## Estado conferido em 08/10/2026

O manifesto r22 conserva 340 originais: 29 com revisão de caixas concluída,
277 pendentes, 16 ocorrências idênticas excluídas da seleção, duas quase duplicatas
confirmadas, duas exclusões editoriais e 14 exclusões de enquadramento.
Revisão de caixas não significa aprovação do dataset final.

Foi gerada uma versão separada `original-review-r23-yard-rotations`, no diretório
local `EdgeSecurity-CCTV-v2`, com quatro correções de orientação:
IMG_0303, IMG_0304, IMG_0305 e IMG_0306. Imagens e coordenadas válidas foram
rotacionadas conjuntamente. Rótulos inválidos, se encontrados, ficam preservados
na origem e exigem redesenho, nunca confirmação de negativo.

Os quatro quadros foram inspecionados individualmente: vistas próximas da mesma
sessão, com empilhadeira, condutor identificável e pessoas externas. Não são quatro
novos grupos e não foram aprovados para treinamento. Os originais não foram apagados.
O registro geométrico vincula a nova versão ao SHA-256 do manifesto r22.
Os quatro testes de transformação passaram.

## Próxima sequência

1. Revisar as caixas dessas quatro imagens corrigidas e registrar as sobreposições.
2. Continuar a revisão individual dos demais originais.
3. Revisar candidatos reais de CCTV, comprovar agrupamento e buscar a diversidade
   de pelo menos 20 grupos, sem completar quantidade com quadros redundantes.
4. Somente após os critérios de qualidade, congelar os conjuntos e preparar
   importação privada; importação e treinamento continuam pendentes.

Não houve upload, treinamento pago ou aprovação de uma expansão de 1.000 imagens.
