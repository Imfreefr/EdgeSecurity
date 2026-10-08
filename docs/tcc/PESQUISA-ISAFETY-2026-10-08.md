# Pesquisa privada: iSafetyBench

Fontes primárias: [projeto dos autores](https://isafetybench.github.io/), [anotações](https://github.com/iSafetyBench/data), [mídias e declaração de direitos](https://huggingface.co/datasets/raiyaanabdullah/isafety-bench).

O dataset acadêmico descreve clipes de ambientes industriais reais. O cartão declara CC BY-NC-SA 4.0, mas também afirma que os direitos sobre os vídeos originais pertencem aos respectivos titulares. Portanto, não foi presumida autorização sobre toda mídia nem redistribuição pública. A pesquisa local permanece privada e não realiza inferências jurídicas sobre fair use.

## Aquisição verificada

Pasta: `C:\Users\ELIPSE\Downloads\EdgeSecurity-CCTV-v2\research\isafety-2026-10-08`.

As anotações normais e de perigo foram consultadas. O primeiro lote de arquivos da API pública permitiu localizar 24 IDs distintos de vídeos com referência textual a empilhadeiras. Foram baixados doze clipes, um por ID, com limites de tamanho; os tamanhos e SHA-256 foram conferidos contra os registros LFS públicos. Nenhuma autenticação, restrição de acesso ou programa dos autores foi utilizado para baixar ou processar os clipes.

Os arquivos `annotations.json`, `public-tree-first-page.json` e `candidates.ndjson` preservam a rastreabilidade. A consulta da árvore ainda não cobriu páginas adicionais: não se trata de um inventário completo do dataset remoto.

## Triagem visual efetivamente realizada

Os doze quadros centrais foram abertos individualmente. O registro `tools/isafety_midpoint_triage_2026_10_08.json` separa oito candidatos para inspeção integral dos clipes e quatro quadros inadequados. Há candidatos com empilhadeiras e pedestres no mesmo quadro, fábricas, corredores e áreas externas, além de oclusões e baixa resolução.

As exclusões nesta triagem referem-se somente aos quadros centrais examinados, não a outros momentos não vistos. Textos, bordas e marcas editoriais deverão ser avaliados para recorte sem ocultar objetos-alvo.

## Critérios ainda não satisfeitos

IDs distintos do YouTube não provam gravações independentes: compilações podem compartilhar cenas, e algumas podem estar no dataset original. A independência continua não verificada. São necessários revisão integral, comparação de cenas, identificação de eventos relacionados, seleção de quadros não redundantes e anotação individual com as quatro classes do Edge Security.

Nenhum destes clipes/imagens foi aprovado para treino, incluído no teste congelado, importado ou usado em trabalho pago. Os doze downloads não são apresentados como doze novos grupos aprovados. A exigência de pelo menos vinte grupos permanece ativa.

## Segundo lote

A pasta `isafety-2026-10-08-offset-12` preserva outros doze downloads, sem sobrescrever o primeiro lote. O coletor agora permite selecionar um intervalo explícito de até doze arquivos. Foram abertos individualmente os doze quadros centrais: seis ficaram candidatos à inspeção integral e seis quadros foram excluídos da seleção por enquadramento, obstrução editorial ou gravação próxima. As decisões estão em `tools/isafety_second_midpoint_triage_2026_10_08.json`.

O quadro `ZNOHrOs9VMA_trim_1` mostra uma fábrica aparentemente relacionada à de `_XXq1kmmBYY_trim_6`. Essa hipótese requer comparação dos clipes e foi registrada como relação possível, não prova de independência. O quadro `YzLYJ9YqSaE_trim_0` tem círculos cobrindo pessoas: não será utilizado para inferir ocupantes invisíveis. Equipamentos como transpaleteiras no segundo lote não recebem automaticamente a classe de empilhadeira.

Total adquirido nesta pesquisa: **24 clipes de IDs distintos, 24 quadros centrais examinados, 14 candidatos à revisão integral e dez quadros não selecionados**. Isso não representa 24 grupos independentes nem 14 imagens com caixas aprovadas. A origem pode conter compilações e eventos repetidos, e a árvore remota continua limitada à primeira página consultada.

## Inventário remoto completo

Após os dois lotes, a paginação da API foi verificada: duas páginas, sem próxima página ao final. O coletor foi adaptado para seguir apenas URLs HTTPS do mesmo endpoint público, com teto de dez páginas. A operação `--index-only` preservou o inventário em `isafety-2026-10-08-complete-index`, sem baixar mais vídeos.

Esse índice completo identifica **26 IDs de origem** com menção textual a empilhadeira nas anotações e arquivos dentro do limite de tamanho de pesquisa. Portanto, existem dois IDs adicionais ainda não baixados; isso também não prova dois novos grupos independentes. As limitações de primeira página descritas acima permanecem válidas para os lotes históricos, mas não para o novo inventário completo.

## Inspeção dos dois clipes adicionais

Os dois clipes adicionais foram baixados e seus quadros centrais abertos individualmente, em `isafety-2026-10-08-offset-24`. `oeHrto1r-S4_clip0_trim_17` mostra um close muito baixo da roda e da carga; o quadro não atende CCTV elevado. `oyRnP9p0KIs_trim_8` apresenta a marca **For Preview Purposes Only**: foi excluído da seleção para treino, sem remover a marca ou presumir autorização. A decisão explícita está em `tools/isafety_final_midpoint_triage_2026_10_08.json`.

Estado consolidado: 26 clipes adquiridos para inspeção, 26 quadros centrais vistos, 14 candidatos à revisão integral e doze quadros/clipes não selecionados. Nenhuma aprovação de caixas ou grupo independente foi emitida nesta pesquisa.

## Rechecagem da possível fábrica repetida

Os clipes `_XXq1kmmBYY_trim_6` e `ZNOHrOs9VMA_trim_1` foram decodificados sequencialmente: 210 e 480 quadros, respectivamente, coincidindo com as contagens reportadas. Foram preservados início, meio e fim, com hashes, em `isafety-factory-comparison-r1`. Os quadros inicial e final de cada clipe foram examinados individualmente; os quadros centrais já haviam sido vistos.

A suspeita inicial de evento repetido **não foi confirmada**: o primeiro clipe mostra recipientes de bobinas e uma estrutura caindo; o segundo mostra processamento de tubos e uma empilhadeira em chamas. A semelhança do quadro central não basta para afirmar identidade de evento. Isso também não comprova independência em relação a outras compilações ou ao dataset original. A decisão está em `tools/isafety_factory_comparison_2026_10_08.json`; a revisão visual integral e as caixas continuam pendentes.
