# Pendências após o envio do código — 08/10/2026

## Prioridade: dataset

- Concluir a revisão individual dos 277 originais pendentes. A versão r23 corrigiu
  a orientação de IMG_0303–IMG_0306, mas não aprovou suas caixas.
- Conferir novamente os 29 originais com revisão de caixas e aplicar os critérios
  finais de composição. Nenhum desses registros equivale à aprovação final.
- Concluir a expansão privada com até 1.000 imagens reais, pelo menos 20 grupos
  independentes e máximo de 50 novas imagens por grupo. Os candidatos pesquisados
  não contam como grupos aprovados; o suplemento de 13 imagens de duas câmeras
  continua parcial.
- Revisar todas as caixas nas quatro classes, confirmar negativos, agrupar cenas
  relacionadas e registrar origem/direitos, inclusive direitos desconhecidos.
- Respeitar a cota de vistas próximas (máximo 20%, somente treino), compor 70/15/15
  por grupos e reservar pelo menos três grupos elevados para cada avaliação.
- Congelar teste exclusivamente novo, auditar ausência de vazamento e gerar
  pacote YOLO privado, manifesto, decisões, estatísticas e SHA-256.
- No checkpoint de 12/10/2026, reportar eventual insuficiência de grupos sem
  diminuir a exigência automaticamente.

## Plataforma, treinamento e avaliação

- Substituir as credenciais expostas e obter autenticação segura válida no momento
  da operação. O diálogo de acesso não armazena a chave para uso posterior.
- Completar e validar as operações de importação, acompanhamento de operações,
  treinamento e exportação da automação. A checagem de acesso e a consulta de
  progresso não implementam por si só esse fluxo completo.
- Criar Edge Security CCTV v2 privado, sem sobrescrever o original, importar e
  conferir pixels, dimensões, rótulos e divisões; congelar a versão remota.
- Demonstrar controle financeiro antes de iniciar: teto acumulado US$ 24,
  orçamento operacional US$ 18, reserva US$ 6; incluir falhas/cancelamentos.
- Executar os treinos sequenciais autorizados e comparar com edgev1; escolher
  modelo/limiar pela validação, registrar métricas reais no teste congelado.
- Exportar ONNX FP32 estático 640×640, batch 1, validar saída e integrar localmente
  mantendo recuperação do modelo anterior. Não houve novo treino nem importação.

## Demonstração e câmeras

- Verificar o alinhamento das caixas em orientações e tamanhos diferentes, alertas
  de pedestres e exclusão de operadores do alerta contra a própria empilhadeira.
- Concluir painel de pelo menos quatro câmeras e navegação sem interromper fontes
  ocultas, inclusive produtores de quadros de webcams no navegador.
- Validar integração, acesso/revogação, reconexão, ciclo de remoção/reinclusão e
  processamento independente no serviço local.
- Medir desempenho real progressivamente em 1, 4, 8, 16 e 20–30 fontes, com CPU,
  RAM, GPU quando existente, latência, filas e estabilidade. Testes simulados e
  rastreadores isolados não comprovam desempenho de 30 câmeras físicas.

## TCC e auditoria

- Produzir pesos finais, histórico de custos, tabela/gráficos comparativos, exemplos
  de erros, vídeo, roteiro, instruções de reprodução e texto com resultados reais.
- Apresentar como protótipo de alerta visual, não prevenção certificada de acidentes.
- Depois da IA, aplicar a auditoria Ponytail do repositório inteiro como relatório,
  sem exclusões automáticas.

## O que este envio não contém

Datasets privados, imagens baixadas, ZIPs, ambientes, bancos, credenciais e relatórios
locais de autenticação permanecem fora do GitHub. Os originais e modelos existentes
são preservados. Enviar código para a branch não confirma publicação em produção,
importação do dataset ou conclusão acadêmica.
