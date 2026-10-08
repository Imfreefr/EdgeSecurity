# Expansão privada — execução em 08/10/2026

O usuário confirmou uso privado na Ultralytics e do pacote local. Licença aberta
deixou de ser requisito de seleção. Origem continua obrigatória; direitos
desconhecidos permanecem desconhecidos. Não publicar o dataset/ZIP, não contornar
acesso e não incluir fontes com proibição explícita de treinamento pretendido.

## Alterações implementadas

`tools/finalize_tcc_dataset.py` e o preflight de `tools/ultralytics_tcc.py`
aceitam `--usage private` (padrão da CLI) ou `--usage redistributable`.
A função de inspeção mantém o padrão estrito anterior para chamadas legadas.
No fluxo privado, direitos desconhecidos ou ausência de autorização de
redistribuição não bloqueiam seleção. Proibição explícita de treino/cloud ou
permissão de acesso não resolvida continuam bloqueios. O registro original de
direitos não é alterado para fabricar autorização.

O pacote final, quando existir, incluirá `usage-policy.json` com visibilidade
privada exigida, ausência de liberação para distribuição pública e lista dos
grupos cujos direitos não foram verificados. Diversidade, revisão visual,
negativos, agrupamento, teste novo, limite de 1.000 imagens e 50 por grupo
permanecem exigidos. O alias `ground_level_close` também conta na cota de 20%.

Foi corrigida a cópia de imagens para preservar a codificação original e seus
bytes: JPEG como `.jpg`, PNG como `.png`, WebP como `.webp`, sem recompactação.
O export anterior copiaria bytes WebP/PNG sob nomes `.jpg`.

## Material novo efetivamente obtido

Dois vídeos públicos foram baixados com limite de 25 MiB por transferência e
registrados por SHA-256 em `EdgeSecurity-CCTV-v2/private-github-pilots-2026-10-08/`.
Foram extraídos seis quadros completos, todos abertos individualmente:

- Salão branco com câmera elevada: três imagens, uma/duas/uma pessoas.
  As quatro caixas de pedestres foram anotadas manualmente e cada sobreposição
  foi aberta e inspecionada. Manifesto de revisão em
  `EdgeSecurity-CCTV-v2/private-white-hall-reviewed-r1/`.
- Pátio noturno elevado: três imagens com pessoas pequenas, empilhadeiras e
  muitos fardos/cargas. Fontes inspecionadas, anotações completas **pendentes**.
  Nenhum quadro foi tratado como negativo.

O primeiro repositório declara extração de footage CCTV público; sua licença de
software MIT **não foi presumida como licença do vídeo**. Direitos de mídia dos
dois pilotos estão registrados como desconhecidos. Todos os quadros de cada
vídeo permanecem juntos. Origem original, relacionamento de eventos e exposição
ao `edgev1` ainda precisam de confirmação; esses pilotos **não aumentaram a
contagem de grupos independentes verificados**. As três imagens anotadas são
suplemento parcial, não dataset final nem treinamento aprovado.

Fontes públicas consultadas:
- https://github.com/Sanaurrehmanarain/forklift-safety-ai
- https://github.com/YanggaY/Forklift-Safety-Monitoring-System-Using-YOLO-and-OpenCV

Manifestos, vídeos e quadros fonte foram preservados. A revisão e aprovação
manual estão em `tools/private_github_visual_review_2026_10_08.json` e
`tools/private_github_approvals_2026_10_08.json`, vinculadas a hashes de fontes,
manifesto e sobreposições. O export revisado recusa mudanças e sobrescrita.

## Pendências, sem conclusão presumida

- 294 originais ainda precisam de revisão individual; o estado r8 foi preservado.
- Concluir caixas do pátio, ampliar a pesquisa e confirmar pelo menos 20 grupos.
- Congelar pacote final, implementar importação/acompanhamento/treino/exportação
  na API oficial e obter autenticação segura. Atualmente esses comandos de
  mutação ainda estão explicitamente bloqueados.
- Verificar importação, proteger o teto de US$ 24, treinar e comparar; depois
  demonstração, evidências do TCC e relatório Ponytail sem exclusões automáticas.

O preflight privado foi executado sobre o manifesto r8 e retornou `NOT_FINAL`:
retirar o requisito de licença aberta não libera os demais critérios. Nenhuma
imagem foi importada na plataforma; nenhuma execução paga ou publicação iniciou.

Verificação desta etapa: **55 testes passaram**, incluindo direitos desconhecidos
em uso privado, exigência de origem, manutenção dos bloqueios de diversidade e
revisão, preservação do formato/bytes e rejeição de aprovações alteradas. A inspeção
do suplemento real de três imagens confirmou abertura, dimensões, quatro caixas
válidas, ausência de pixels idênticos e ausência de divisão do mesmo grupo entre
conjuntos. Essas verificações não comprovam conclusão da expansão integral.
