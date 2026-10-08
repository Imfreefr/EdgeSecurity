# Triagem privada do arquivo público SelimSavas

Fonte: https://github.com/SelimSavas/forklift-and-people-detection-with-YOLOv5

O arquivo disponibilizado pelo autor foi baixado para pesquisa privada. Direitos das imagens permanecem desconhecidos; a publicação do repositório não comprova autorização sobre todas as mídias. A descrição indica uma coleção de ImageNet, Roboflow e Kaggle. Não foram inferidos grupos independentes a partir dos nomes dos arquivos.

## Evidências locais

Pasta: `C:\Users\ELIPSE\Downloads\EdgeSecurity-CCTV-v2\research\public-selim-forklift-2026-10-08`.

- Arquivo: `dataforkliftv19.zip`, 384.739.531 bytes.
- SHA-256: `9ce7812da42ad116d11457f03ca8e39d9638ead39c4576d74c3784b240673820`.
- Inventário técnico atual: `inventory-r2.ndjson`.
- 2.968 imagens examinadas tecnicamente; 2.927 imagens únicas por dimensões e pixels RGB decodificados; 41 ocorrências duplicadas.
- Nenhuma imagem falhou na decodificação. Uma apresentou aviso `Truncated File Read`: `dataforkliftv10/valid/images/n03384352_2757.JPEG`. Isso impede tratá-la como plenamente validada sem exame adicional.
- A inspeção lê somente imagens em memória. Nenhum script ou caminho arbitrário do ZIP é extraído ou executado.

## Revisão visual

Doze imagens amostradas foram abertas individualmente. As decisões estão em `tools/selim_sample_triage_2026_10_08.json`: três candidatas para revisão de anotações e origem; nove excluídas da seleção de expansão CCTV por enquadramento próximo/baixo ou transformações inadequadas. Essas exclusões não apagam o arquivo original nem afirmam que as imagens seriam inúteis para outros projetos.

As três candidatas são `candidate-00000.png`, `candidate-00270.png` e `candidate-01618.jpeg`. As duas primeiras mostram pedestres, sem empilhadeira; a terceira mostra uma empilhadeira em vista elevada. Nenhuma recebeu aprovação de caixas, autorização para treinamento, atribuição a teste ou confirmação de grupo independente.

## Limites e próxima seleção

O inventário não constitui revisão visual de todas as imagens nem verificação de todos os rótulos. As divisões do ZIP de origem não serão preservadas automaticamente. Ainda é necessário investigar relações de cena, selecionar outras vistas elevadas, revisar todas as caixas das imagens aproveitadas e formar a divisão por grupos.

Resultados deste material até aqui: **zero imagens novas aprovadas; zero grupos novos verificados**. Os requisitos de até 1.000 imagens novas e pelo menos 20 grupos continuam pendentes. Nenhuma importação ou execução paga foi iniciada.

## Atualização: revisão de duas candidatas

As imagens `candidate-00000` e `candidate-00270` receberam desenho manual e inspeção individual das sobreposições em `pedestrian-proposals-r2`. Foram conferidas três caixas de pedestre (classe 0): uma na primeira imagem e duas na segunda, incluindo a pessoa parcialmente visível na borda direita. A primeira proposta foi corrigida para incluir o pé inteiro; a revisão anterior permanece preservada.

As aprovações visuais são vinculadas aos hashes de imagem, manifesto e sobreposição nos arquivos `tools/selim_*_visual_approval_2026_10_08.json`. Os manifestos revisados ficam nas pastas `pedestrian-reviewed-candidate-00000-r1` e `pedestrian-reviewed-candidate-00270-r1` da pasta de pesquisa. Ambas continuam **pendentes dos critérios finais**, com `approved_for_training=false`, divisão provisória somente treino e relação com o dataset antigo desconhecida. O grupo misto conservador foi mantido.

Estado atualizado deste arquivo: **duas imagens com caixas revisadas, três caixas de pedestre, zero grupos novos verificados e zero imagens liberadas para treino**. A candidata com empilhadeira permanece pendente de revisão e esclarecimento da pessoa na traseira.
