# Etapa posterior ao dataset: todas as câmeras processadas

Objetivo atualizado lido integralmente em 08/10/2026: todas as câmeras conectadas devem detectar múltiplas ocorrências das quatro classes, preservando câmera e identidade de origem. A preparação do dataset permanece pendente; a operação multicâmera completa ainda não foi implementada nem validada.

O computador deverá analisar todas as câmeras disponíveis, inicialmente 20–30. O painel exibirá pelo menos quatro por vez, sem controlar a continuidade da análise das demais.

## Arquitetura a implementar depois da preparação do dataset

- Captura independente por câmera, buffers limitados e isolamento de falhas.
- Inferência compartilhada, escalonamento justo e resultados identificados por câmera; não carregar um modelo por câmera.
- Estado de conexão/processamento separado do estado de exibição.
- Paginação altera somente a visualização; não reinicia o modelo nem interrompe câmeras ocultas.
- Reconexão individual, adição/remoção dinâmica e resultados recentes disponíveis ao abrir outra página.

## Evidências obrigatórias

Testar progressivamente 1, 4, 8, 16 e 20 ou mais fontes. Registrar hardware, CPU/GPU, RAM/VRAM, banda, taxa e idade das detecções por câmera, filas, estabilidade e resposta da interface. Distinguir explicitamente vídeos reproduzidos de câmeras físicas.

Comprovar inferência nas câmeras ocultas durante navegação; falha de uma fonte sem interromper as demais; associação correta dos resultados; buffers limitados; ausência de crescimento persistente de memória. Exibir quatro câmeras, isoladamente, não satisfaz o aceite.

## Diagnóstico inicial, ainda parcial

`js/ai-api.js` usa uma conexão com uma câmera selecionada; `js/cameras.js` envia frames da visualização ativa; `/ws/detection` em `backend/app.py` autentica uma câmera por conexão. Isso não demonstra captura contínua das câmeras ocultas. A investigação completa precederá as alterações, preservando permissões por câmera e o contrato das detecções.

## Requisitos acrescentados pelo objetivo atualizado

- Preservar pessoa (ID 0), máquina/empilhadeira (ID 1), operador (ID 2) e objeto/carga (ID 3), conforme as classes efetivamente treinadas. Não transformar pessoa em operador por heurística.
- Permitir múltiplas ocorrências de várias classes no mesmo quadro e manter contagens individuais por câmera.
- Isolar o estado de rastreamento entre câmeras. O detector atual compartilhado usa `model.track(persist=True)`, mas `infer(frame)` não recebe identidade da fonte: o isolamento ainda não está demonstrado e precisará ser corrigido antes do aceite multicâmera.
- Validar as quatro classes em vídeos reais anotados, incluindo associação e estabilidade ao longo dos quadros. Mostrar vídeo ou passar testes com detecções artificiais não comprova capacidade do modelo.

## Base de resultados por câmera implementada

`backend/services/camera_results.py` armazena somente o resultado mais recente de cada par empresa/câmera, com limite de memória de 256 entradas, contagens separadas por classe e cópias defensivas. O WebSocket existente registra o resultado após inferência e autorização, acrescentando `counts` e `processed_at` à resposta sem remover campos anteriores.

Cinco testes unitários verificam contagem de múltiplas classes, isolamento de empresa/câmera, proteção contra mutação, limite de entradas e retenção de resultados de trinta IDs sem qualquer seleção de exibição. Esses testes utilizam detecções de teste: **não comprovam trinta capturas simultâneas nem inferência real, desempenho, rastreamento ou funcionamento do painel**.

Um teste adicional executa o corpo real do handler WebSocket com decodificação e inferência explicitamente simuladas, em duas câmeras autorizadas, verificando resposta e armazenamento com as quatro contagens, sem acesso por outra empresa. A suíte Python de `tests/test_*.py` passou com nove testes unittest e as verificações existentes de autenticação/cadastro executadas durante a descoberta. Nenhuma medição de processamento de trinta vídeos foi realizada nesta etapa.

Ainda faltam captura contínua independente da interface, escalonamento e buffers limitados, isolamento de rastreamento, reconexão, painel com navegação e validação progressiva em fontes reais/reproduzidas identificadas como tais. O armazenamento recente ainda não possui endpoint de consulta próprio; consumidores futuros deverão manter autorização por câmera e empresa.

## Isolamento de rastreamento implementado e verificado parcialmente

O detector agora usa uma única instância YOLO com `predict`, acesso serializado por lock e um contexto ByteTrack distinto para cada par empresa/câmera. Os alocadores de IDs pertencem aos respectivos contextos: criar uma câmera não reinicia IDs de outra. A resposta preserva `track_id` e acrescenta `camera_id` e `track_key` (câmera, geração do contexto e ID). Mudança de dimensões ou remoção explícita cria nova geração, evitando associar coordenadas/identidades antigas a outro fluxo. Contextos têm limite de 256 entradas. Detecções ainda sem rastro confirmado permanecem na resposta com ID nulo.

O WebSocket passa câmera e empresa ao detector e executa inferência com `asyncio.to_thread`, para não bloquear o event loop durante a chamada. Isso não implementa ainda o escalonador justo, a captura contínua independente do painel ou filas globais limitadas.

Verificação realizada em ambiente isolado `.local/multicam-venv`, com Ultralytics 8.4.138 e LAP 0.5.13. `scripts/verify-camera-tracking.py` executa ByteTrack real sobre caixas sintéticas das quatro classes e verifica trinta contextos, estabilidade dos IDs e ausência de reinicialização do alocador por outra câmera. Essas caixas são exclusivamente testes, não imagens incluídas no dataset.

Uma execução adicional carregou `backend/model/edgev1.pt` e analisou o mesmo quadro `_2tSBxyAwLs_trim_52.png` sob os IDs `smoke-a`, `smoke-b` e `smoke-a` novamente. Resultado: uma detecção em cada chamada, nomes de classes `{0: '.pessoa', 1: '.máquina', 2: 'operador', 3: 'objeto'}`, câmeras corretas e chaves sem interseção entre fontes. É uma imagem reproduzida, não duas câmeras físicas, nem avaliação de precisão/recall ou comprovação das quatro classes nesse quadro.

Após a mudança, a suíte `tests/test_*.py` passou com treze testes unittest e verificações existentes de autorização/cadastro. Permanecem pendentes captura e reconexão multicâmera, escalonamento justo, resultados consultáveis com autorização, paginação da visualização e testes progressivos reais de recurso/latência. O objetivo completo não está concluído.
