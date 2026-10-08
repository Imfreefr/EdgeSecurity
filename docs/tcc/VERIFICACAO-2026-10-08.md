# Verificação local — 8 de outubro de 2026

A execução integral não está concluída. O desligamento solicitado só deve ocorrer
depois de verificar todos os requisitos do plano, nunca ao fim de uma etapa parcial.

## Evidência atual

- Os diretórios `C:/Users/ELIPSE/Downloads/EdgeSecurity-CCTV-v2` e
  `C:/Users/ELIPSE/Downloads/EdgeSecurity-dataset-audit` não existem no ambiente
  atual. Não é possível revalidar aqui as imagens, revisões e ZIPs anteriormente
  descritos. Isso não comprova exclusão: os arquivos podem estar em outro ambiente.
- A busca por NDJSON, manifestos de originais e nomes CCTV em Downloads, Desktop,
  Documents, OneDrive, Pictures e Projects não encontrou esses artefatos.
- Os modelos `backend/model/edgev1.pt` e `edgev1.onnx` continuam no projeto.
- `.local/ultralytics-access.json` registra uma verificação anterior de leitura;
  não comprova uma sessão ativa, disponibilidade da chave ou permissão de escrita.
- Os 37 testes de ferramentas passaram com
  `python -m unittest discover -s tools -p 'test_*.py'`. São testes de software,
  não evidência de revisão visual, importação ou treinamento concluídos.
- Não foi executado upload, treinamento pago, publicação, limpeza ou desligamento
  nesta verificação.

## Próxima ação necessária para retomar a revisão

Localizar ou restaurar as duas pastas externas e os exports originais
`edge-security.ndjson` / `edge-security (1).ndjson`. Confirmar a localização real
antes de executar os scripts: eles apontam para os caminhos acima.
Não reconstruir anotações revisadas a partir de memória nem criar manifestos
substitutos que pareçam comprovar o trabalho anterior.

Após recuperar os arquivos, verificar hashes e integridade dos pacotes,
retomar a revisão individual e a busca das 20 cenas independentes licenciadas.
As etapas posteriores continuam pendentes: congelamento e divisão, importação
autenticada verificada, controle de gasto, treino/comparação, demonstração,
evidências do TCC e relatório de código sem exclusões automáticas.

## Recuperação parcial posterior à busca local

Foi possível recriar a pasta externa com os dois vídeos piloto públicos de
NVIDIA PhysicalAI-SmartSpaces, usando `tools/collect_smartspaces_real.py`.
Os vídeos têm 19.598.552 e 16.892.801 bytes; o coletor verificou tamanho e
SHA-256, comparando com o publicador quando o hash estava disponível na API.
Seis quadros foram decodificados. Não são seis cenas independentes.

A imagem de Warehouse_027/Camera_0005 em 5 segundos e sua sobreposição recortada
foram novamente inspecionadas individualmente. As quatro caixas existentes de
pedestres correspondem aos alvos visíveis. O piloto separado foi reconstruído
por `tools/package_smartspaces_pilot.py`, mantendo aprovação de treino falsa e
independência pendente. Isso não recupera o suplemento de 13 imagens nem os
originais. A contagem histórica de 14 imagens não comprova sua disponibilidade
atual: somente este piloto de uma imagem foi recuperado nesta continuação.

### Pesquisa adicional de fontes

- O estudo [Multispectral Benchmark Dataset and Baseline for Forklift Collision
  Avoidance](https://www.mdpi.com/1424-8220/22/20/7953) usa câmeras embarcadas na
  empilhadeira. Não atende à expansão exigida de CCTV elevado; nenhum download
  ou nova cena aprovada.
- [SPARL versão 1](https://zenodo.org/records/11280959) declara 16 registros de
  sensores, mas disponibiliza apenas duas gravações representativas anônimas.
  Não transformar a contagem de sensores em grupos de vídeo. Não baixado.
- O estudo [Deep Learning-Based Automated Inspection of Generic Personal
  Protective Equipment](https://www.techscience.com/cmc/v85n2/63829/html) cita
  `tml_safety_v3`, mas fornece uma página genérica de busca do Roboflow, não
  origem, licença de imagens e gravações suficientes para nossa aprovação.
  Permanece apenas uma pista; zero imagens incorporadas.

Nenhuma destas pesquisas resolve as 20 cenas. Nenhum upload ou treino iniciado.

## Recuperação de clipes Mendeley

`tools/collect_public_cctv.py` terminou sem erro e recuperou nove vídeos e seus
quadros centrais: `0_te1`, `0_te10`, `0_te20`, `0_te30`, `3_te1`, `4_te1`,
`4_te10`, `4_te20`, `7_te1`. O manifesto em `review/public-candidates.json`
mantém todos como `pending_visual_review`, sem caixas aprovadas. Os arquivos
estão novamente disponíveis em `external/videos` e `external/frames`.

A [fonte primária Mendeley](https://data.mendeley.com/datasets/xjmtb22pff/1)
foi consultada nesta continuação: declara CC BY 4.0, permissões obtidas para a
coleta e somente duas câmeras. Nove clipes não equivalem a nove novos grupos.

Dois quadros recuperados foram reinspecionados individualmente:

- `3_te1`: empilhadeira à direita, três contêineres de carga à frente,
  trabalhador parcialmente visível junto à prensa no alto à direita.
  O condutor não é visualmente identificável; não inferir sua classe 2.
  Texto IPC aparece no alto à esquerda; recorte e caixas precisam de conferência.
- `4_te1`: um pedestre ao fundo à esquerda, outro em primeiro plano junto à
  prensa; não há empilhadeira visível. As prensas fixas não são classe 1.
  Não tratar a imagem como negativo, pois há pessoas e cargas visíveis.

Nenhuma anotação foi aprovada automaticamente a partir dos JSON antigos.
O suplemento r2 de 13 imagens ainda não foi reconstruído; faltam recuperação
dos clipes adicionais e revisão individual das respectivas caixas. O dataset
original de 340 imagens e seus exports continuam ausentes neste ambiente.

## Reinspeção dos rótulos recuperados

Os nove quadros fonte foram inspecionados individualmente, assim como nove
sobreposições candidatas (oito positivos e o recorte de piso). Isso encontrou
dois problemas que impedem reaproveitar cegamente as anotações anteriores:
`0_te10` contém uma caixa de carga sobre a porta/cabine; foi retirado da seleção,
preservando fonte e JSON antigo. Em `7_te1`, a caixa do contêiner ao fundo foi
limitada à faixa visível à esquerda, sem incluir a janela que o oclui.

Os quadros `3_te1` e `7_te1` perderam a faixa superior de 120 pixels para remover
IPC; caixas foram transformadas/recortadas e as duas novas sobreposições foram
novamente inspecionadas. A cobertura completa de cargas/pallets nos positivos
ainda precisa de revisão; nenhum arquivo de aprovação integral foi emitido e
nenhum pacote positivo de recuperação foi exportado. O negativo recortado foi
reconfirmado visualmente, mas não aumenta a diversidade de cenas.

Registro de decisões: `tools/public_recovery_findings_2026_10_08.json`.
Ferramenta `tools/recover_public_review.py render` mantém estado pendente;
`export` exige aprovação manual separada vinculada aos hashes das imagens e
das sobreposições, além da verificação de integridade. Não executar export sem
completar a revisão das anotações.

O usuário retirou o desligamento do objetivo nesta continuação. Não desligar
o computador como parte deste trabalho.

## Recuperação integral dos dados públicos originais

A pendência de disponibilidade dos originais foi resolvida nesta continuação
pela API oficial, com requisições GET anônimas. O endpoint de export retornou
401, mas a consulta do dataset e a listagem de imagens públicas com
`includeImageUrls=true` e `includeLabels=true` retornaram 200. Nenhuma chave
foi usada e nenhuma operação remota de escrita foi executada.

`tools/recover_originals_public_api.py` recuperou **340 imagens em tamanho
completo e 1.322 caixas**, conferindo abertura, dimensões, bytes declarados,
IDs únicos, ausência de truncamento dos rótulos e contagens. Os metadados do
dataset permaneceram iguais antes e depois da transferência. As URLs assinadas
não foram persistidas ou impressas. Cópia isolada em
`EdgeSecurity-CCTV-v2/original-api-recovery-2026-10-08/`.

Composição recuperada: treino 316, validação 24; classes 0: 399, 1: 389,
2: 158, 3: 376. Os 14 registros sem caixas continuam pendentes, explicitamente
sem confirmação de negativo. Em 38 imagens há coordenadas fora dos limites
estritos (incluindo pequenos excessos compatíveis com arredondamento): valores
preservados, sem clipping automático ou aprovação visual presumida.

A auditoria dos bytes/hash dos pixels decodificados confirmou **324 imagens
únicas e 16 grupos duplicados, todos atravessando treino/validação**. A seleção
e consolidação das caixas desses pares continuam pendentes de nova revisão.
Nenhuma imagem foi excluída da cópia preservada.

Artefatos: `manifest.ndjson`, `recovery-report.json`, `original-inventory.json`.
O inventário inclui os pares, seus rótulos, IDs/nome da plataforma, imagens sem
caixas, problemas geométricos e SHA-256 do manifesto. A ordem dos índices do
export antigo e as correções locais ausentes **não foram recuperadas**; nunca
aplicar decisões antigas somente pelo índice. Confirmar identidade por nome,
ID, pixels e contexto antes de reaproveitá-las.

Os 40 testes de ferramentas passaram após esta recuperação. Não houve
importação, treinamento, comparação, publicação ou cobrança. O próximo trabalho
é a revisão individual destes originais agora acessíveis, a reconstrução das
correções e a obtenção dos 20 grupos licenciados. O dataset final permanece
não aprovado; a auditoria de código segue posterior à conclusão da IA.

Referência oficial: https://docs.ultralytics.com/platform/api

## Conclusão da decisão sobre os 14 originais sem caixas

Todas as 14 imagens sem caixas foram abertas e inspecionadas individualmente
nesta continuação. São nove quadros de `VID-20260825-WA0011` e cinco de
`VID-20260825-WA0010`, com pessoas, empilhadeiras e/ou cargas visíveis. Nenhum
foi considerado negativo.

A decisão registrada é exclusão **da seleção CCTV**, por captura móvel ao nível
do chão e primeiro plano próximo. Isso não afirma que as imagens sejam inúteis
em outros experimentos. O plano permite anotar se aproveitadas ou registrar
exclusão; optou-se por não ampliar com elas o complemento de vistas próximas.
As duas sequências foram agrupadas conservadoramente por mostrarem o mesmo
corredor, trabalhadores, corrente de segurança e empilhadeira. Não contam como
dois ambientes independentes.

`tools/original_unlabeled_review_2026_10_08.json` contém observação específica
para cada quadro. `tools/curate_collision_originals.py --recovered-manifest ...`
vinculou as decisões aos nomes e IDs atuais, verificando SHA-256 dos arquivos,
sem reutilizar índices antigos. A revisão separada
`EdgeSecurity-CCTV-v2/original-review-r4-unlabeled/` contém manifesto dos 340
registros, CSV de 14 decisões, JSON de revisão e estatísticas. Todos os originais
e rótulos publicados foram preservados; zero exclusões físicas ou mutações remotas.

Esta pendência específica foi decidida: 14 exclusões da seleção, zero negativos
confirmados e zero aprovações para treino. **326 originais ainda estão pendentes
de revisão individual completa**, além da consolidação das duplicatas e expansão
licenciada. A revisão das 14 imagens não equivale à conclusão de toda a curadoria.

Os 42 testes passaram, incluindo preservação da entrada, bloqueio quando os bytes
mudam e recusa de sobrescrita de uma revisão existente. Nenhum treino ou cobrança.

## Revisão dos pares exatos recuperados: seleção e caixas

Os 16 quadros `IMG_0457_frame_001` a `016` foram abertos individualmente em
quadro completo. `tools/apply_duplicate_redraw.py` conferiu novamente os bytes,
dimensões e igualdade dos pixels decodificados dos dois membros de cada par.
Foi mantida uma ocorrência canônica de treino por quadro; as 16 ocorrências
duplicadas de validação estão excluídas **da seleção**, com referência à canônica.
Todos os 340 arquivos originais e seus rótulos continuam preservados.

A sequência mostra um pedestre fora de uma empilhadeira com o banco vazio.
Não se inferiu operador. As caixas da máquina incluem os garfos visíveis, não
somente a cabine. O grupo conservador é uma única sessão móvel ao nível do chão;
não conta como nova cena CCTV nem pode entrar em validação/teste final. Eventual
uso no treino ainda depende dos direitos e da cota máxima de 20% de vistas próximas.

Foram redesenhadas propostas para todos os 16 quadros em
`tools/duplicate_redraw_2026_10_08.json`. As sobreposições de `001` a `009` foram
abertas individualmente e conferidas. Em `004`, o limite esquerdo do sapato foi
corrigido após a primeira sobreposição, que foi regenerada e reinspecionada.
As oito outras imagens de sobreposição permaneceram idênticas byte a byte.
As aprovações em `tools/duplicate_overlay_approvals_2026_10_08.json` estão
vinculadas ao hash do manifesto e a cada sobreposição. A aplicação verifica
também os bytes originais e não altera os manifestos de entrada.

Revisão atual isolada: `EdgeSecurity-CCTV-v2/original-review-r6-duplicates-partial/`.
Contém 340 registros: **9 com revisão das anotações concluída**, 7 com propostas
pendentes de inspeção detalhada, 294 ainda sem revisão individual completa,
16 duplicatas excluídas e 14 exclusões de enquadramento previamente decididas.
Assim, **301 ocorrências selecionáveis ainda precisam concluir a revisão**.
Os sete quadros finais têm pessoas pequenas e/ou possíveis pallets ao fundo;
não foram aprovados por extrapolação dos nove primeiros.

Aprovação de anotação não equivale a aprovação para treino: todas as flags
`approved_for_training` permanecem falsas. Não há dataset final, importação,
treino, avaliação ou cobrança nova. Foram adicionados testes de preservação,
recusa de sobrescrita, identidade dos pixels, limites das caixas e rejeição de
aprovações quando manifesto, sobreposição ou imagem original mudam.

Verificação executada: **47 testes de ferramentas passaram**. Uma conferência
adicional confirmou 310 pixels de imagens únicos nas 310 ocorrências ainda
selecionáveis, caixas válidas nos nove quadros aprovados visualmente e o SHA-256
inalterado do manifesto original recuperado. Isso não comprova revisão das
301 imagens restantes nem aprovação final dos grupos/divisões/licenças.

## Conclusão da revisão de anotações dos 16 quadros duplicados

Os sete quadros restantes foram reinspecionados individualmente, com detalhes
extraídos dos originais de 3840×2160. As ampliações confirmaram pessoas distantes
nos quadros `010`, `012`, `013` e `014`. Em `013`, foi adicionada a pessoa que
faltava; somente a parte visível do corpo foi delimitada, pois o pedestre à frente
oculta as pernas. Em `014`, a caixa da pessoa distante foi corrigida para incluir
as pernas visíveis, sem inferir regiões fora do quadro.

Também foram anotados os pallets e recipientes de carga visíveis nos quadros
`013` a `016`. Recipientes armazenados sobre pallets foram tratados como carga;
cada pallet identificável recebeu uma caixa separada. Estantes metálicas fixas,
lixeiras, móveis, EPIs e cones não foram tratados como carga. Tambores totalmente
ocultos não foram inferidos. Essa regra está registrada na aprovação manual.

As sobreposições completas e os detalhes em resolução nativa foram inspecionados.
Essa inspeção levou a corrigir o topo de um tambor que incluía a viga da estante,
o limite esquerdo de outro recipiente, a extensão das tábuas de um pallet e caixas
que incluíam área de cinta/pilar. As versões corrigidas foram novamente abertas.
As caixas dos quadros `001` a `012` e `015` permaneceram idênticas às respectivas
sobreposições já inspecionadas; os hashes das nove primeiras também coincidem
com a aprovação parcial anterior.

Estado atual isolado: `EdgeSecurity-CCTV-v2/original-review-r8-duplicates-reviewed/`.
As aprovações em `tools/duplicate_complete_approvals_2026_10_08.json` vinculam
os 16 quadros ao manifesto e aos hashes das sobreposições finais. As versões
intermediárias e a revisão parcial anterior foram preservadas. O manifesto mantém
as caixas originais no campo `original_boxes` e as corrigidas em `boxes`.

Contagens atuais dos originais: **16 ocorrências canônicas com revisão de caixas
concluída, 294 ainda pendentes, 16 duplicatas excluídas da seleção e 14 exclusões
de enquadramento**. Nos 16 quadros revisados há 20 caixas de pedestre, 16 de
empilhadeira, zero operadores e 11 de carga/pallet. Todos pertencem à mesma sessão
móvel original, não a 16 cenas independentes. A retirada de quase duplicatas,
licença, cota de vistas próximas e agrupamento final continuam pendências distintas.

Verificação executada: 47 testes passaram. A conferência adicional verificou o
SHA-256 dos **340 arquivos originais**, o manifesto original inalterado, 310 imagens
de pixels únicos na seleção, as 47 caixas corrigidas dentro dos limites e zero
aprovações para treino final. SHA-256 do manifesto r8:
`fb62abc198aee99f76eea9099ec93f8aca5530452ed3f6b5876d7aa221a348fb`.

Não houve importação, treinamento, avaliação, publicação ou cobrança. A conclusão
desta sequência não representa conclusão da curadoria integral ou da expansão CCTV.
