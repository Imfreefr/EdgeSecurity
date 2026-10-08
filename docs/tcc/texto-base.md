# Texto-base para o TCC — preencher somente com evidências

## Objetivo

Desenvolver e avaliar um protótipo de visão computacional para detectar
pedestres e empilhadeiras em imagens de câmeras elevadas, exibindo alertas
de aproximação visual. O sistema não substitui medidas de segurança do trabalho.

## Metodologia

Descrever fontes e permissões, critérios de enquadramento, distribuição das
quatro classes, correção de orientação/recortes, revisão manual e deduplicação.
Documentar agrupamento por câmera/evento e divisão treino/validação/teste.
Anexar a versão/hash do dataset congelado e os parâmetros de cada execução.
Explicar que seleção de modelo/limiar utiliza apenas validação; teste contém
cenas novas em relação ao `edgev1` e permanece separado do desenvolvimento.

## Implementação

A inferência no navegador utiliza ONNX Runtime Web. Caixas retornam ao espaço
do vídeo após letterbox. A aproximação é calculada entre pedestres e
empilhadeiras, com limiares em uma largura de referência de 640 pixels.
Operadores continuam visíveis, mas não são classificados como pedestres no
alerta. Essa heurística não estima metros, profundidade ou tempo até colisão.

## Resultados — PENDENTES

Não existem resultados novos de treinamento ou comparação nesta entrega.
Preencher a tabela somente após avaliar o modelo antigo e os candidatos no
teste congelado. Incluir erros, falsos alertas, latência e custo real; resultados
desfavoráveis também devem ser apresentados. Não reutilizar métricas antigas
de validação contaminada como resultado do novo protocolo.

## Limitações

Até agora, o suplemento aprovado representa somente duas câmeras externas,
sem gravações do ambiente real de implantação. Generalização local e melhoria
de precisão ainda não foram demonstradas. Oclusões, pessoas pequenas, reflexos
e perspectiva podem afetar detecções e alertas. Sobreposição de caixas não prova
colisão física. Os testes automatizados verificam lógica/integridade, não segurança.

## Trabalhos futuros

Avaliação em câmeras reais autorizadas, calibração geométrica, análise temporal,
associação robusta de operador/veículo e validação de alarmes com profissionais
de segurança. Ampliar fontes somente com direitos compatíveis.

## Roteiro da apresentação

1. Problema: exposição de pedestres a empilhadeiras; objetivo do protótipo.
2. Dataset: fontes, exemplos, classes, revisão e separação por cenas.
3. Experimentos: configuração, comparação justa, custos e limitações.
4. Demonstração: detecção, aproximação, operador e uma falha real.
5. Conclusão: o que foi demonstrado, o que não foi e próximos passos.
