# Configuração das modalidades de busca do GraphRAG 3.1.0

Este documento explica cada opção de configuração das quatro modalidades de busca
(basic, local, global e DRIFT), o que ela faz no código do GraphRAG 3.1.0 e qual o
impacto esperado na **qualidade**, na **complexidade** (número de chamadas ao modelo) e
no **gasto de tokens**. Serve para decidir a configuração da avaliação e para o capítulo
de configuração da monografia.

Os valores padrão foram conferidos em `graphrag/config/defaults.py`, e o uso de cada
opção em `graphrag/query/factory.py` e nos motores de busca
(`graphrag/query/structured_search/*`). Os números medidos vêm do índice v1 (1.373
entidades, 6.885 relações, 369 relatórios de comunidade) e das consultas registradas no
SQLite (`storage/app.db`).

**Status: decisão pendente.** Nenhuma opção de busca foi alterada ainda no
`settings.yaml`; hoje valem os padrões, exceto as temperaturas (fixadas em 1, ver
seção 3 do `implementation-log.md`).

---

## 1. Conceitos que valem para todas as buscas

- **Tokens de entrada** = prompt de sistema (instruções) + contexto recuperado + pergunta.
  Nas buscas do GraphRAG o contexto domina: as instruções têm cerca de 600 a 1.000 tokens,
  e o contexto pode chegar ao limite configurado (12 mil tokens por padrão).
- **Tokens de saída** são mais caros por token, mas aparecem em menor volume. Nos modelos
  de raciocínio (GPT-6), há ainda os tokens de raciocínio, que são cobrados e não
  aparecem nas métricas do GraphRAG (ver item 13.8 do log).
- **Custo de uma consulta ≈ número de chamadas × tokens por chamada.** As buscas basic e
  local fazem uma chamada; a global e a DRIFT fazem dezenas. Por isso as opções que
  controlam o **número de chamadas** pesam muito mais do que as que controlam o tamanho
  do contexto.
- **Orçamento de contexto (`max_context_tokens` / `max_data_tokens`).** O GraphRAG
  preenche o contexto com registros (entidades, relações, relatórios, trechos) até atingir
  o orçamento e descarta o resto. Aumentar o orçamento aumenta os tokens de entrada de
  forma quase linear. Também tende a aumentar a cobertura, mas pode diluir a atenção do
  modelo ("lost in the middle").
- **`community_level`** (parâmetro da consulta, não do `settings.yaml`; padrão 2 na CLI e
  no backend). Define até que nível da hierarquia de comunidades os relatórios são
  considerados. Afeta muito a busca global, um pouco a local e a DRIFT, e não afeta a
  basic.
- **`response_type`** (parâmetro da consulta; padrão "Multiple Paragraphs"). Muda apenas
  o formato pedido ao modelo e, portanto, os tokens de saída.

---

## 2. Busca basic (baseline vetorial)

Fluxo: embedding da pergunta → os `k` trechos mais similares no LanceDB → um único
prompt com os trechos → resposta. **1 chamada.**

| Opção (`basic_search`) | Padrão | O que faz | Impacto |
|---|---|---|---|
| `k` | 10 | Quantos trechos (text units) recuperar por similaridade | Cada trecho tem até ~1.000 tokens no nosso corpus (um artigo). Mais trechos = mais cobertura e mais tokens; menos = risco de não trazer o artigo certo (no teste do art. 54-E, o artigo certo não veio nas primeiras posições) |
| `max_context_tokens` | 12.000 | Teto do contexto | Com `k=10` e artigos curtos, raramente é atingido (consulta real: ~4,5 mil tokens de entrada) |
| `prompt` | padrão | Instruções de geração | Ver seção 6 |
| `completion_model_id` / `embedding_model_id` | — | Modelos | Devem ser **os mesmos** das outras buscas para a comparação ser justa |

Custo medido: 1 chamada, ~4,5 a 5 mil tokens de entrada.

---

## 3. Busca local

Fluxo: embedding da pergunta → entidades com descrição mais similar → expansão pelo
grafo (relações dessas entidades, relatórios das comunidades a que pertencem, trechos
de onde foram extraídas) → um único prompt com tabelas → resposta. **1 chamada.**

O orçamento de contexto é dividido em três partes:

```
max_context_tokens = 12.000
  ├─ community_prop   (0,15) → relatórios de comunidade   ~1.800 tokens
  ├─ text_unit_prop   (0,50) → trechos de texto           ~6.000 tokens
  └─ restante         (0,35) → entidades + relações       ~4.200 tokens
```

| Opção (`local_search`) | Padrão | O que faz | Impacto |
|---|---|---|---|
| `top_k_entities` | 10 | Quantas entidades são "mapeadas" a partir da pergunta (por similaridade das descrições) | É a porta de entrada no grafo: valores maiores trazem mais vizinhança e mais tokens (até o teto). Valores baixos focam a resposta |
| `top_k_relationships` | 10 | Quantas relações por entidade mapeada entram no contexto | Mais relações = mais conexões entre artigos (o diferencial do grafo), mas também mais ruído |
| `text_unit_prop` | 0,5 | Fração do orçamento para trechos de texto originais | Garante o texto literal da lei. Se for alta demais, sobra pouco espaço para entidades e relações |
| `community_prop` | 0,15 | Fração para relatórios de comunidade | **Atenção:** os relatórios deste índice têm de ~1.300 a ~4.900 tokens (mediana ~2.300). Com 1.800 tokens de orçamento, cabe no máximo um relatório pequeno, e muitas vezes nenhum |
| `max_context_tokens` | 12.000 | Teto do contexto | Medido: ~9 a 10 mil tokens de entrada por consulta |
| `conversation_history_max_turns` | 5 | Histórico de conversa no contexto | Não usado na aplicação (cada consulta é independente) |
| `prompt` | padrão | Instruções | Ver seção 6 |

**Restrição:** `text_unit_prop + community_prop ≤ 1`. O que sobra vai para entidades e
relações. Se a soma for 1, **nenhuma entidade ou relação entra no contexto** (é o que
acontece hoje na DRIFT, seção 5).

Custo medido: 1 chamada, ~10 mil tokens de entrada (art. 49: 10.154).

---

## 4. Busca global

Fluxo (map-reduce):

1. Seleciona os relatórios de comunidade até o nível `community_level`.
2. **Map:** embaralha os relatórios e os divide em lotes de até `max_context_tokens`
   (12 mil). Cada lote vira **uma chamada** que devolve pontos-chave com uma nota de
   relevância (0 a 100).
3. **Reduce:** os melhores pontos (até `data_max_tokens`) vão para uma chamada final de
   síntese.

**Chamadas ≈ ⌈tokens de todos os relatórios do nível ÷ 12 mil⌉ + 1.**

| Opção (`global_search`) | Padrão | O que faz | Impacto |
|---|---|---|---|
| `community_level` (consulta) | 2 | Nível máximo da hierarquia de comunidades | **É o que mais pesa.** Medido neste índice: nível 0 → 7 chamadas e 71 mil tokens; nível 1 → 30 e 336 mil; nível 2 → 68 e 775 mil; nível 3 → 82 e 944 mil. Níveis baixos usam poucas comunidades amplas (visão geral); níveis altos, muitas comunidades específicas (mais detalhe e muito mais custo) |
| `max_context_tokens` | 12.000 | Tamanho de cada lote do map | Lotes maiores = menos chamadas com mais tokens cada (o total de tokens de entrada quase não muda). Um lote muito grande prejudica a atenção do modelo |
| `data_max_tokens` | 12.000 | Teto de pontos-chave enviados ao reduce | Define o tamanho da chamada final |
| `map_max_length` | 1.000 palavras | Tamanho pedido para a resposta de cada lote | Afeta os tokens de saída × número de lotes |
| `reduce_max_length` | 2.000 palavras | Tamanho pedido para a resposta final | Tokens de saída da síntese |
| `map_prompt`, `reduce_prompt`, `knowledge_prompt` | padrão | Instruções do map, do reduce e do uso de conhecimento geral | O backend usa `allow_general_knowledge=False` (como a CLI) |
| `dynamic_community_selection` (consulta) | falso | Em vez de usar um nível fixo, percorre a hierarquia a partir da raiz e pergunta ao modelo se cada relatório é relevante | Faz **chamadas extras de classificação**, uma por relatório visitado, normalmente com um modelo barato. Pode reduzir o map, mas o custo total depende da pergunta |
| `dynamic_search_threshold` | 1 | Nota mínima para um relatório ser considerado relevante | Mais alto = poda mais |
| `dynamic_search_keep_parent` | falso | Manter o relatório-pai quando os filhos são relevantes | Mais contexto e mais tokens |
| `dynamic_search_num_repeats` | 1 | Repetições da classificação (média) | Multiplica as chamadas de classificação |
| `dynamic_search_use_summary` | falso | Classificar pelo resumo em vez do relatório completo | Classificação mais barata |
| `dynamic_search_max_level` | 2 | Profundidade máxima da descida | Limita as chamadas |

Observação: o embaralhamento dos lotes (`shuffle_data=True`, fixo no código) é mais uma
fonte de variação entre execuções, além da temperatura.

---

## 5. Busca DRIFT

### 5.1 Como funciona no código da 3.1.0

1. **Expansão da pergunta (HyDE):** o modelo escreve uma resposta hipotética no formato
   de um relatório de comunidade **sorteado** como modelo, e o embedding dessa resposta é
   usado na busca. *1 chamada* (`build_context`).
2. **Seleção de relatórios:** os `drift_k_followups` relatórios mais similares à
   resposta hipotética (respeitando `community_level`).
3. **Primer:** os relatórios selecionados são divididos em `primer_folds` grupos; cada
   grupo vira uma chamada que devolve uma resposta parcial, uma nota e **perguntas de
   acompanhamento**. *`primer_folds` chamadas.*
4. **Laço de aprofundamento**, repetido `n_depth` vezes: das perguntas ainda não
   respondidas, pega até `drift_k_followups` e responde cada uma com uma **busca local**
   completa. Cada resposta traz novas perguntas, que entram na fila. *Até
   `drift_k_followups` chamadas por rodada.*
   - **Detalhe importante:** a escolha das perguntas da rodada é **aleatória**. O código
     chama `rank_incomplete_actions()` sem função de pontuação, e nesse caso a lista é
     embaralhada (`random.shuffle`). As notas das perguntas não são usadas para priorizar.
5. **Reduce:** todas as respostas parciais vão para uma chamada final de síntese.
   *1 chamada.*

**Chamadas ≈ 1 + `primer_folds` + `n_depth` × `drift_k_followups` + 1.**
Com os padrões: 1 + 5 + 3 × 20 + 1 = **67** (exatamente o medido na consulta real).

A árvore guarda também as perguntas geradas e nunca respondidas. Na consulta real foram
502 nós, dos quais só 61 foram respondidos. Isso é o funcionamento normal do algoritmo,
e não uma falha ou falta de tokens.

### 5.2 Consulta real medida (12/10/2026)

"Quais são os direitos básicos do consumidor?", nível 2, padrões da DRIFT:

| Etapa | Chamadas | Tokens de entrada | Tokens de saída |
|---|---|---|---|
| build_context (HyDE) | 1 | 1.828 | 1.128 |
| primer | 5 | 56.359 | 3.820 |
| action (buscas locais) | 60 | 417.306 | 57.222 |
| reduce | 1 | 49.153 | 755 |
| **Total** | **67** | **524.646** | **62.925** |

Tempo: 221 s. A resposta final está completa e correta (art. 6º, com remissões aos arts.
18, 20, 24, 30, 49...).

### 5.3 Problema encontrado: as buscas locais da DRIFT não usam o grafo

Com os padrões, `local_search_text_unit_prop = 0,9` e `local_search_community_prop = 0,1`,
sobra **0%** do orçamento para entidades e relações (1 − 0,9 − 0,1 = 0). Além disso, os
10% para relatórios (1.200 tokens) são menores que **qualquer** relatório deste índice
(o menor tem ~1.300 tokens), então nenhum relatório entra. Resultado medido: nas 60
buscas locais, **0 entidades, 0 relações e 0 relatórios**, só trechos de texto (1.189
trechos no total, com muitas repetições).

Ou seja, com os padrões, a DRIFT usa o grafo apenas na etapa inicial (relatórios de
comunidade do primer). O aprofundamento é, na prática, uma sequência de **buscas
vetoriais por trechos**, ou seja, uma basic iterada. Isso precisa ser corrigido ou
explicitado no relatório, porque afeta diretamente a comparação DRIFT × basic.

### 5.4 Opções

| Opção (`drift_search`) | Padrão | O que faz | Impacto |
|---|---|---|---|
| `drift_k_followups` | 20 | **Dois usos:** quantos relatórios entram no primer **e** quantas perguntas são respondidas por rodada | **Principal alavanca de custo**: as chamadas crescem linearmente (`n_depth ×` esse valor). Valores menores deixam a busca mais barata e mais focada, mas exploram menos |
| `n_depth` | 3 | Número de rodadas de aprofundamento | Multiplica as chamadas. A rodada 1 responde perguntas do primer; as rodadas seguintes, perguntas derivadas (cada vez mais específicas e mais distantes da original) |
| `primer_folds` | 5 | Em quantos grupos os relatórios do primer são divididos | Mais grupos = mais chamadas menores no primer e mais perguntas iniciais. Impacto pequeno no custo (o total de relatórios é o mesmo) |
| `local_search_text_unit_prop` | 0,9 | Fração do contexto de cada busca local para trechos | Ver 5.3. Com 0,5, metade do espaço vai para trechos |
| `local_search_community_prop` | 0,1 | Fração para relatórios | Ver 5.3. Abaixo de ~0,2 (2.400 tokens), quase nenhum relatório deste índice cabe |
| `local_search_top_k_mapped_entities` | 10 | Entidades mapeadas em cada busca local | Igual à local |
| `local_search_top_k_relationships` | 10 | Relações por entidade | Igual à local |
| `local_search_max_data_tokens` | 12.000 | Teto do contexto de cada busca local | Multiplicado pelo número de ações: é o que faz a etapa "action" custar ~417 mil tokens |
| `local_search_temperature` | 0 → **1** | Temperatura das buscas locais | Fixada em 1 (GPT-6) |
| `reduce_temperature` | 0 → **1** | Temperatura da síntese | Fixada em 1 |
| `local_search_top_p`, `local_search_n` | 1, 1 | Amostragem | Sem motivo para alterar |
| `local_search_llm_max_gen_completion_tokens`, `reduce_max_completion_tokens` | — | Limite de tokens gerados | Podem limitar o custo de saída, mas nos modelos de raciocínio o limite inclui o raciocínio e pode **cortar respostas**. Não recomendado |
| `primer_llm_max_tokens`, `data_max_tokens`, `reduce_max_tokens`, `concurrency` | — | — | Existem na configuração, mas **não são lidos** pelo código da DRIFT na 3.1.0 (conferido por busca no código) |

### 5.5 Cenários (estimativa a partir da consulta real)

Estimativa: ~7 mil tokens de entrada por ação, ~11 mil por chamada do primer, e um
reduce proporcional ao número de respostas.

| Cenário | `k_followups` | `n_depth` | Chamadas | Tokens de entrada (aprox.) | Comentário |
|---|---|---|---|---|---|
| Padrão (atual) | 20 | 3 | 67 | ~525 mil (medido) | Mais caro que a global no nível 1 |
| Moderado | 10 | 2 | 1+5+20+1 = 27 | ~200 mil | Bom equilíbrio |
| Econômico | 5 | 2 | 1+5+10+1 = 17 | ~110 mil | Comparável à global no nível 0–1 |
| Mínimo | 5 | 1 | 1+5+5+1 = 12 | ~75 mil | Quase uma local enriquecida pelo primer |

Mudar as proporções de contexto (5.3) **não muda o número de chamadas** e muda pouco os
tokens: o orçamento por busca local continua 12 mil. Muda **o que** entra no contexto
(entidades e relações no lugar de parte dos trechos).

### 5.6 Recomendação para a decisão

1. **Corrigir as proporções** para a DRIFT usar o grafo nas buscas locais, com os mesmos
   valores da busca local: `local_search_text_unit_prop: 0.5` e
   `local_search_community_prop: 0.15`. Custo extra: praticamente zero. Ressalva: com
   0,15 ainda caberão poucos relatórios (ver 5.3); se quiser relatórios nas buscas
   locais, use 0,25.
2. **Reduzir a exploração** para a avaliação, por exemplo `drift_k_followups: 10` e
   `n_depth: 2` (~27 chamadas). Justificativa para o relatório: custo; e as rodadas
   profundas geram perguntas cada vez mais afastadas da pergunta original.
3. **Registrar no relatório** a seleção aleatória das perguntas (5.1) como fonte de
   variação, junto com a temperatura e o embaralhamento da global.

As mesmas proporções devem valer em toda a avaliação; mudá-las depois exige repetir as
consultas DRIFT.

---

## 6. Prompts das buscas

Arquivos em `data/prompts/` (os de busca continuam os padrões do GraphRAG, em inglês,
pedindo citações no formato `[Data: Sources (...)]`):

| Prompt | Usado por | Variáveis |
|---|---|---|
| `basic_search_system_prompt.txt` | basic | `{context_data}`, `{response_type}` |
| `local_search_system_prompt.txt` | local | idem |
| `global_search_map_system_prompt.txt` | global (map) | `{context_data}`, `{max_length}` |
| `global_search_reduce_system_prompt.txt` | global (reduce) | `{report_data}`, `{response_type}`, `{max_length}` |
| `global_search_knowledge_system_prompt.txt` | global (se conhecimento geral permitido) | — |
| `drift_search_system_prompt.txt` | DRIFT (buscas locais) | `{context_data}`, `{response_type}`, `{global_query}`, `{followups}` |
| `drift_reduce_prompt.txt` | DRIFT (reduce) | `{context_data}`, `{response_type}` |
| `question_gen_system_prompt.txt` | geração de perguntas (não usado) | `{context_data}`, `{question_count}` |

Alterar um prompt de busca não exige reindexar, mas muda a impressão digital do índice
no backend (nova `index_version`). Prompts maiores somam tokens a **cada** chamada; na
global e na DRIFT isso é multiplicado pelo número de chamadas.

---

## 7. Resumo: o que mais pesa no custo

| Modalidade | Alavanca principal | Medido (padrões) |
|---|---|---|
| basic | `k` | 1 chamada, ~5 mil tokens |
| local | `max_context_tokens` | 1 chamada, ~10 mil tokens |
| global | `community_level` | nível 0: 7 chamadas, 71 mil tokens; nível 2: 68 chamadas, 775 mil tokens |
| DRIFT | `drift_k_followups × n_depth` | 67 chamadas, 525 mil tokens |
