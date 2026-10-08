# Meta de execução: Dataset → Múltiplas câmeras → Auditoria

Ordem confirmada pelo usuário em 08/10/2026. A próxima etapa só recebe prioridade
de execução quando os critérios da anterior forem comprovados, ou mediante nova
decisão explícita. Não apagar originais, substituir modelos nem publicar produção.

## 1. Dataset e conclusão da IA — prioridade atual

### Trabalho imediato

1. Revisar caixas dos quatro originais com orientação corrigida na r23.
2. Continuar os 277 originais pendentes e conferir os 29 já revisados.
3. Selecionar e anotar até 1.000 novas imagens reais de CCTV, com pelo menos
   20 grupos independentes e no máximo 50 imagens novas por grupo.
4. Auditar todos os rótulos, negativos, duplicatas, direitos/origens e agrupamentos.
5. Dividir por grupos (70/15/15, semente 42), congelar teste novo, gerar pacote privado.
6. Importar com acesso autenticado, reconciliar o conteúdo e congelar a versão remota.
7. Treinar dentro do teto acumulado de US$ 24, somente com controle comprovado
   de exposição financeira; comparar com edgev1 e registrar resultados reais.
8. Exportar modelo escolhido, verificar demonstração local e reunir evidências do TCC.

### Critérios de saída

Todas as imagens finais e caixas têm revisão visual rastreável; classes 0 pedestre,
1 empilhadeira, 2 operador identificável e 3 carga. Negativos explicitamente confirmados.
Vistas próximas limitadas a 20%, somente treino; avaliação elevada com pelo menos
três grupos independentes em validação e três em teste. Nenhum vazamento de pixels
ou grupos entre conjuntos; teste exclusivamente novo. Pacote e importação conferidos;
métricas, custos, pesos e demonstração registrados. Ganho de precisão não é presumido.

Se a diversidade não for viável no checkpoint de 12/10/2026, registrar a lacuna e
pedir decisão de escopo. Não preencher quantidade com redundância nem reduzir critérios.

## 2. Múltiplas câmeras — depois da IA

Preservar o núcleo local já implementado; seus testes não concluem esta etapa.

1. Validar integração, autorização/revogação e ciclo de adição/remoção/reconexão.
2. Concluir painel de pelo menos quatro câmeras, navegação e captura de webcams
   independente de quais câmeras estejam visíveis.
3. Confirmar inferência contínua de fontes ocultas, resultados e rastreamento separados
   por câmera/empresa, buffers limitados e escalonamento justo com modelo compartilhado.
4. Medir progressivamente 1, 4, 8, 16 e 20–30 fontes: CPU, RAM, GPU quando disponível,
   latência, filas, falhas, reconexões e deteções das quatro classes.
5. Documentar limites do computador e da demonstração sem apresentar replays ou
   testes simulados como comprovação de câmeras físicas independentes.

### Critério de saída

Fluxo completo demonstrado, mudanças de painel não interrompem processamento,
falha de uma fonte não paralisa outras, recursos e limites medidos e reproduzíveis.

## 3. Auditoria — por último

Aplicar Ponytail ao repositório inteiro, incluindo entradas HTML, scripts clássicos,
assets, build, rotas, inicializadores, ferramentas, testes, documentação e dependências.
Entregar relatório priorizado com localização, evidência, classificação, confiança,
risco, ação sugerida e teste necessário. Não excluir arquivos nesta etapa.
Limpeza posterior depende de aprovação; preservar datasets, modelos e rastreabilidade.

## Acompanhamento

Registrar cada avanço com artefato, verificação e pendência. A lista detalhada de
bloqueios e entregas está em [PENDENCIAS-ENTREGA.md](PENDENCIAS-ENTREGA.md).
O dataset é parcial; não houve nova importação ou treinamento. Os commits enviados
registram ferramentas e implementação, não aprovação do dataset ou implantação.
