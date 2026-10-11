# Registro de implementação

Este documento reúne, em detalhes, tudo o que foi implementado na prova de conceito
(PoC), as decisões tomadas e os motivos, os problemas encontrados e como foram
resolvidos, e as medições feitas. Ele é a fonte para a redação do relatório final do
TCC e é atualizado a cada nova implementação.

**Como usar:** as seções estão organizadas por tema (corpus, configuração, taxonomia,
indexação, aplicação etc.). A seção 13 consolida os problemas encontrados no GraphRAG
e a seção 14, as medições de custo. O histórico cronológico está no final.

**Ambiente de referência:** GraphRAG 3.1.0 (versão fixada), Python 3.11 nos
containers, Docker Compose no Windows, modelos da OpenAI (`gpt-6.1-sol`,
`gpt-6-luna`, `text-embedding-3-large`).

---

## 1. Ponto de partida (julho/2026)

Estado da PoC antes desta etapa de trabalho:

- **Execução 100% local**: Ollama em container com `llama3.1:8b` (variante
  `llama3.1-8k`, com `num_ctx 8192`) para geração e `nomic-embed-text` para embeddings.
  `concurrent_requests: 1` e `timeout: 1800` s, porque a máquina não tem GPU.
- **Qualidade e tempo**: a indexação levava horas em CPU (cerca de 420 s por chamada ao
  modelo) e a extração do grafo era de baixa qualidade, motivo da migração para modelos
  em nuvem.
- **Entrada**: `input.type: text`. Como o GraphRAG procura arquivos de forma recursiva
  na pasta de entrada, a indexação lia dois documentos: um trecho antigo do CDC
  (`cdc.txt`) e o texto completo bruto (`entrada.txt`), que estava numa subpasta junto
  com o parser.
- **Prompts**: gerados por `graphrag prompt-tune` com o modelo local. O prompt de
  extração usava tipos de entidade em inglês (`law, consumer, business, government,
  product, service`), e não a taxonomia definida no `settings.yaml` (ver seção 7).
- **Aplicação web**: backend FastAPI que apenas lia os arquivos `.parquet` do índice e
  frontend React que exibia o grafo. Consultas só pela linha de comando, no container.

## 2. Migração para modelos em nuvem

### 2.1 Escolha dos modelos por etapa

O corpus é pequeno (130 artigos, cerca de 22 mil tokens), então o custo é dominado
pelo número de chamadas e pelo tamanho dos prompts, não pelo volume de texto. A
estratégia foi usar o modelo mais barato que atende bem cada etapa:

| Etapa | Modelo | Motivo |
|---|---|---|
| Extração de entidades e relações | `gpt-6.1-sol` | Define a qualidade do grafo; etapa mais importante |
| Resumo de descrições de entidades | `gpt-6-luna` | Tarefa simples: fundir descrições de uma mesma entidade |
| Relatórios de comunidade | `gpt-6.1-sol` | Base da busca global |
| Respostas das buscas (local, global, drift, basic) | `gpt-6.1-sol` | Mesmo modelo gerador em todas as modalidades |
| Embeddings | `text-embedding-3-large` (3072 dimensões) | A Anthropic não oferece API de embeddings; custo desprezível |

A OpenAI foi escolhida como provedor padrão porque o GraphRAG foi desenvolvido e
testado pela Microsoft com modelos GPT (comparação mais fiel à ferramenta), porque
basta uma chave de API e porque tem os embeddings mais baratos. Blocos prontos para
Anthropic (Claude) e Google (Gemini) ficaram em `config/model_providers.yaml`. A
configuração local original foi preservada em `config/settings.ollama.yaml`, idêntica
à de nuvem exceto pelos modelos, para permitir comparação.

### 2.2 Teste prévio dos modelos

Criado `scripts/test_models.py`, que faz chamadas mínimas (custo de centavos) para
conferir chave e nomes dos modelos antes de indexar. Ele lê os modelos do
`settings.yaml` e testa cada um de duas formas: chamada simples (como na indexação) e
com a temperatura configurada para a busca DRIFT.

Problemas encontrados:

- Os modelos GPT-6 não aceitam o parâmetro `max_tokens` (exigem
  `max_completion_tokens`). O erro estava no script de teste; o GraphRAG 3.x já usa
  `max_completion_tokens`.
- A biblioteca LiteLLM usada pelo GraphRAG (1.86.2 no container) não conhece os
  modelos GPT-6 e, por isso, não sabe que são modelos de raciocínio: repassa
  `temperature` e outros parâmetros sem filtrar (`drop_params` não tem efeito para
  modelos desconhecidos).
- Os modelos GPT-6 só aceitam `temperature=1` (ver seção 3).

### 2.3 Custo estimado × custo real

A estimativa inicial para uma indexação completa era de US$ 3 a 6. O custo real
estimado pelos tokens registrados ficou entre US$ 16 e 24 (seção 8). A diferença veio
principalmente dos tokens de saída: a extração ficou muito mais detalhada do que o
previsto (6.885 relações) e os tokens de saída são os mais caros. Lição para o
relatório: o custo do GraphRAG é dominado pela extração do grafo e pelos tokens
gerados, e estimativas baseadas só no tamanho do corpus subestimam o custo.

## 3. Temperatura dos modelos

- **Comportamento do GraphRAG 3.x**: somente a busca DRIFT define temperatura própria
  (`local_search_temperature` e `reduce_temperature`, padrão 0). As buscas local,
  global e basic não definem temperatura e usam o padrão do provedor (1).
- **Origem**: é uma herança da versão 2.x, em que **todos** os modelos tinham
  `temperature: 0` por padrão (`LanguageModelDefaults`, conferido no código da 2.7.2).
  Na 3.x a configuração de modelo passou a usar `call_args` genérico, sem temperatura
  padrão, mas os campos próprios da DRIFT permaneceram com 0. Resultado: inconsistência
  entre modalidades.
- **Restrição**: os modelos GPT-6 (de raciocínio) só aceitam `temperature=1`; com 0, a
  API retorna `Unsupported value: 'temperature' does not support 0`.
- **Decisão**: temperatura fixada explicitamente em 1 no `call_args` dos dois modelos e
  nos dois campos da DRIFT. Assim, todas as etapas e todas as modalidades usam a mesma
  temperatura e ela não é uma variável de confusão na comparação com o baseline (a
  busca basic usa o mesmo corpus, embeddings e modelo gerador; a única diferença deve
  ser a estrutura de grafo).
- **Consequência metodológica**: com temperatura 1 as respostas variam entre
  execuções. Por isso a avaliação usará (a) um índice congelado, igual para todas as
  modalidades, e (b) repetições de cada pergunta, para medir também a consistência.
- **Detalhe de implementação**: quando a DRIFT passa `temperature` na chamada e ela
  também está no `call_args`, o GraphRAG junta os dois dicionários e o valor da chamada
  prevalece (conferido em `graphrag_llm/completion/lite_llm_completion.py`); não há
  conflito.

## 4. Preparação do corpus

Arquivos: `corpus/raw/cdc_planalto.txt` (texto bruto do planalto.gov.br) →
`corpus/parser/legislation_parser.py` → `data/input/cdc.json`.

O parser segue a técnica legislativa da LC nº 95/1998 (Parte > Livro > Título >
Capítulo > Seção > Subseção > Artigo) e gera **um registro por artigo**, com a
hierarquia (número e nome de cada nível) e o texto completo (caput, parágrafos,
incisos e alíneas). Ele foi escrito para ser reaproveitável em outras leis federais.

### 4.1 Problemas corrigidos

| Problema | Causa | Correção |
|---|---|---|
| Ids repetidos (`art_54` para os arts. 54, 54-A a 54-G; também 42-A e 104-A a 104-C) | A expressão regular do artigo descartava o sufixo de letra | O número inclui o sufixo (`54-A`) e o id é `cdc_art_54-A`. O prefixo da sigla evita colisões entre leis. O script falha se houver id repetido |
| Cabeçalho "Art. 11º", "Art. 54º -C." | O cabeçalho era remontado sempre com ordinal | Regra da LC 95/1998: ordinal até o nono ("Art. 9º"), cardinal a partir do décimo ("Art. 10.", "Art. 54-A.") |
| Capítulo VI-A lido como "VI" com nome "-A"; nome real perdido | A regra dos níveis não aceitava sufixo de letra | Os níveis aceitam sufixo (`VI-A`) e o nome é lido da linha seguinte |
| Campo `revogado_ou_vetado` marcava o artigo inteiro quando só um parágrafo era vetado (ex.: arts. 6, 37) | Busca de "(Vetado)" em todo o texto | Campo substituído (ver 4.2) |

### 4.2 Dispositivos vetados e revogados

Decisão: **manter** todo o texto vetado ou revogado no corpus, porque o registro do
veto também é informação jurídica (por exemplo, o art. 54-E, vetado na Lei nº
14.181/2021). Cada artigo recebe:

- `situacao`: `vigente`, `vetado` ou `revogado`, referente ao artigo como um todo;
- `dispositivos_vetados_ou_revogados`: rótulos dos parágrafos, incisos ou alíneas
  vetados dentro de um artigo vigente (ex.: art. 51: `["V", "XIX", "§ 3º"]`).

Números do CDC: 130 artigos; 12 inteiramente vetados (arts. 11, 15, 16, 45, 54-E, 62,
85, 86, 89, 96, 108 e 109); 30 dispositivos vetados dentro de 21 artigos vigentes. A
opção `--remover-vetados` gera a versão sem eles (118 artigos), para comparação.

A consulta de teste "O que acontece com o art. 54-E do CDC?" (busca basic, seção 15)
respondeu corretamente que o artigo foi vetado, o que só é possível porque o texto
vetado foi mantido.

### 4.3 Campos do JSON

Os nomes internos do parser e os campos do JSON (`titulo_nome`, `situacao` etc.)
ficaram em português de propósito: eles aparecem para o modelo no início de cada
trecho (seção 5.2) e, em português, combinam com o texto da lei.

## 5. Configuração do GraphRAG (`data/settings.yaml`)

### 5.1 Entrada

- `input.type: json`, `id_column: id`, `title_column: id`, `text_column: text`.
- O padrão de arquivos do GraphRAG para JSON (`.*\.json$`) é usado; o texto bruto e o
  parser saíram da pasta `data/input`.

### 5.2 Segmentação (chunking)

- `size: 1200` tokens, `overlap: 100`. O maior artigo tem cerca de 900 tokens, então
  **cada artigo é um único chunk** e nenhum chunk mistura artigos.
- `prepend_metadata: [lei_sigla, titulo_nome, capitulo_nome, secao_nome, situacao]`:
  cada chunk começa com a localização do artigo na lei e sua situação, por exemplo:

  ```
  lei_sigla: CDC.
  titulo_nome: Dos Direitos do Consumidor.
  capitulo_nome: Disposições Gerais.
  situacao: vigente.
  Art. 2º Consumidor é toda pessoa física ou jurídica...
  ```

### 5.3 Erros de configuração encontrados e corrigidos

| Erro | Efeito | Correção |
|---|---|---|
| `db_uri: output\lancedb` (barra invertida do Windows) | Dentro do container Linux criou uma pasta chamada literalmente `output\lancedb` (que ainda foi parar no git) | `db_uri: output/lancedb` |
| Prompt `drift_search_reduce_prompt.txt` inexistente (o arquivo é `drift_reduce_prompt.txt`) | A busca DRIFT usaria o prompt padrão em inglês sem avisar (ver 13.4) | Nome corrigido |
| Cifrão no padrão de arquivos (`".*\\.json$"`) | O GraphRAG substitui variáveis de ambiente no arquivo **inteiro**, inclusive em comentários; o cifrão gerou `ValueError: Invalid placeholder` e impediria a indexação | Linha removida (o padrão do GraphRAG já é esse) |
| Blocos comentados de Claude e Gemini com `${ANTHROPIC_API_KEY}` e `${GEMINI_API_KEY}` | Mesmo comentados, são substituídos; como essas variáveis não existem no `.env`, o carregamento falharia com `KeyError` | Blocos movidos para `config/model_providers.yaml`; aviso no topo do `settings.yaml` |
| Modelos sem `default_completion_model` | O `graphrag prompt-tune` oficial procura um modelo com esse id fixo e falharia | Contornado pelo script próprio de prompt-tune (seção 7) |

### 5.4 Chaves de API

Ficam em `data/.env` (lido automaticamente pelo GraphRAG a partir da pasta `--root`),
fora do git. Modelo em `config/.env.example`.

## 6. Taxonomia de entidades

### 6.1 Antes

`[artigo, direito, obrigacao, sancao, orgao_fiscalizador, relacao_consumo, fornecedor,
consumidor]`. Problemas: faltavam conceitos centrais (produto, serviço, contrato,
práticas abusivas, crimes, ações coletivas); `orgao_fiscalizador` não cobria Ministério
Público, Defensoria, Judiciário e associações; `relacao_consumo` é um conceito, não uma
categoria; `sancao` misturava sanções administrativas e crimes; `artigo` não captava
remissões a outras normas.

### 6.2 Depois (14 tipos)

| Grupo | Tipo | Abrange |
|---|---|---|
| Sujeitos | `consumidor` | consumidor e equiparados; consumidor superendividado |
| | `fornecedor` | fabricante, produtor, construtor, importador, comerciante, prestador, fornecedor de crédito |
| | `orgao_entidade` | Procon, SNDC, Ministério Público, Defensoria, entes federativos, Judiciário, associações |
| Objeto | `produto` | bens móveis/imóveis, duráveis/não duráveis, perigosos, peças de reposição |
| | `servico` | serviços em geral, inclusive bancários, de crédito, securitários e públicos |
| | `contrato` | contratos de consumo e de adesão, cláusulas, garantias, crédito, compra a prazo |
| Normativo | `direito` | direitos do consumidor |
| | `obrigacao` | deveres do fornecedor e do poder público |
| | `pratica_abusiva` | práticas abusivas, publicidade enganosa/abusiva, cobrança vexatória, cláusulas abusivas |
| | `instituto_juridico` | princípios (vulnerabilidade, boa-fé...) e conceitos (relação de consumo, responsabilidade objetiva, fato e vício, decadência e prescrição, inversão do ônus da prova, superendividamento) |
| Consequências e tutela | `sancao_administrativa` | multa, apreensão, cassação, interdição, contrapropaganda |
| | `infracao_penal` | crimes contra as relações de consumo e penas |
| | `instrumento_processual` | ações coletivas, ação civil pública, interesses difusos/coletivos/individuais homogêneos, coisa julgada |
| Remissões | `dispositivo_legal` | artigos do CDC e de outras normas citadas |

`principio` foi proposto como tipo próprio e, por decisão da autora, incorporado a
`instituto_juridico`.

### 6.3 Decisões de projeto

- **Quantidade de tipos**: tipos demais fragmentam o grafo e deixam o modelo indeciso;
  14 cobrem os seis títulos do CDC com pouca sobreposição.
- **Prazo não é tipo**: "30 dias" aparece com sentidos diferentes (decadência de vícios,
  prazo para sanar o vício). Como o GraphRAG funde entidades com o mesmo nome, sentidos
  diferentes seriam misturados. O prazo vai na descrição do instituto, direito ou
  obrigação.
- **Definições no prompt**: o GraphRAG só coloca os nomes dos tipos no prompt; o script
  de prompt-tune acrescenta uma definição de cada tipo (seção 7).
- **Regras de nomeação** (também inseridas no prompt): nomes em maiúsculas, no
  singular, sem artigo inicial; termos do próprio CDC, sem sinônimos; artigos como
  `ART. 54-A DO CDC` (artigo como unidade; parágrafos e incisos na descrição); outras
  normas como `LEI Nº 7.347/1985`; prazos na descrição; artigos vetados viram entidade
  com o veto registrado na descrição. Objetivo: evitar nós duplicados ("ART. 6",
  "ARTIGO 6º") e fusões indevidas.

## 7. Geração dos prompts de indexação (prompt-tuning)

### 7.1 Problemas do `graphrag prompt-tune` oficial (3.1.0)

1. **Não aceita taxonomia.** Com `--discover-entity-types` (padrão), o modelo
   "descobre" os tipos e eles são gravados fixos no `extract_graph.txt`, ignorando os
   `entity_types` do `settings.yaml` (foi o que aconteceu no índice local antigo: tipos
   em inglês). Com `--no-discover-entity-types`, o prompt sai sem tipo nenhum.
2. **Exige um modelo com id fixo** `default_completion_model`.
3. **Sorteia os trechos de exemplo** (`--selection-method random`), o que não é
   reprodutível.
4. **Bug: todos os exemplos saem do mesmo artigo.** A função
   `generate_entity_relationship_examples` reaproveita o mesmo
   `CompletionMessagesBuilder` em todas as chamadas, e o `build()` devolve a mesma
   lista. Como as chamadas só são executadas depois (`asyncio.gather`), cada uma recebe
   **todos** os textos e o modelo responde sempre sobre o último. Na primeira execução,
   os textos de entrada dos exemplos eram dos arts. 6, 12, 51 e 56, mas as quatro
   respostas eram a extração do art. 82. Confirmado com um teste mínimo
   (`[4, 4, 4]` mensagens por chamada em vez de `[2, 2, 2]`).

### 7.2 Solução: `scripts/prompt_tune.py`

Executa as mesmas etapas e funções do prompt-tune oficial
(`graphrag.api.prompt_tune.generate_indexing_prompts`), com estas diferenças:

- usa a taxonomia do `settings.yaml` e falha se a lista do script
  (`ENTITY_TYPE_DEFINITIONS`) divergir dela;
- insere no `extract_graph.txt`, antes da seção de exemplos, as definições dos tipos e
  as regras de nomeação; as mesmas orientações entram como mensagem de sistema na
  geração dos exemplos;
- domínio e idioma fixos: "legislação consumerista brasileira (Código de Defesa do
  Consumidor, Lei nº 8.078/1990)" e "português do Brasil";
- gera cada exemplo numa conversa nova (contorno do bug 7.1.4);
- monta os trechos de exemplo exatamente como na indexação (mesmo chunker e mesmo
  `prepend_metadata`);
- normaliza os exemplos (nomes em maiúsculas; tipos com erro de digitação corrigidos,
  como `instrument_processual`) e avisa se um exemplo não cita o próprio artigo;
- grava os metadados da geração em `data/prompts/prompt_tune_metadata.json` (modelo,
  versão, persona, papel do relator, critérios de relevância, artigos usados, avisos).

### 7.3 Escolha dos artigos de exemplo

- **Primeira tentativa** (arts. 6, 12, 51, 56, 82): exemplos corretos, mas os arts. 6 e
  51 geraram exemplos com 50 entidades e 113 relações e 37 entidades e 72 relações; o
  prompt de extração ficou com cerca de 27 mil tokens por chamada.
- **Versão final**: artigos curtos que juntos cobrem quase toda a taxonomia, em ordem
  de prioridade: 49 (direito de arrependimento), 12 (responsabilidade pelo fato), 42
  (cobrança de dívidas), 82 (legitimados), 66 (crime), 56 (sanções). Entram no prompt
  enquanto couberem em 12 mil tokens, com mínimo de 3. Resultado: arts. 49, 12 e 42,
  prompt de **11.709 tokens**. Os tipos sem exemplo (órgãos, instrumentos processuais,
  sanções, crimes) são guiados apenas pelas definições.
- Contexto para o papel do relator de comunidades: os exemplos mais os arts. 2, 4, 6,
  51, 18, 26, 39, 54-A, 54-E e 106.

## 8. Indexação v1 (08/10/2026)

- Duração: cerca de 26 minutos (04:17 a 04:43 UTC), sem erros e sem novas tentativas.
- Fluxo: `load_input_documents` → `create_base_text_units` (130) →
  `create_final_documents` → `extract_graph` (com 1 *gleaning*) → resumo de descrições
  (8.270 descrições) → `create_communities` → `create_final_text_units` →
  `create_community_reports` → `generate_text_embeddings` (400 textos).

### 8.1 Resultado

| Item | Valor |
|---|---|
| Documentos / text units | 130 / 130 |
| Entidades | 1.373 (todas dentro dos 14 tipos) |
| Relações | 6.885 |
| Comunidades / relatórios | 369 / 369 (níveis 0 a 3: 17 / 89 / 185 / 78) |
| Artigos do CDC como entidades | os 130, no padrão `ART. 54-E DO CDC` |
| Relações descartadas pelo GraphRAG | 288 (citavam entidades inexistentes; cerca de 4%) |

Distribuição por tipo: instituto_juridico 313, obrigacao 228, dispositivo_legal 177,
direito 128, instrumento_processual 114, orgao_entidade 83, pratica_abusiva 80,
contrato 57, fornecedor 50, produto 44, infracao_penal 31, consumidor 30,
sancao_administrativa 23, servico 15. Entidades mais conectadas: CONSUMIDOR (grau
597), FORNECEDOR (272), PRODUTO (262), SERVIÇO (218).

Verificações de qualidade: nenhum nome em minúsculas; artigos de outras leis também
padronizados ("ART. 16 DA LEI Nº 7.347/1985", "ART. 44 DO CÓDIGO PENAL"); a entidade do
art. 54-E registra que o dispositivo foi vetado e incluído pela Lei nº 14.181/2021;
prazos não viraram entidades soltas.

### 8.2 Uso de tokens

| Modelo | Chamadas | Tokens de entrada | Tokens de saída |
|---|---|---|---|
| `gpt-6.1-sol` | 630 | 4.303.693 | 1.471.243 |
| `gpt-6-luna` | 406 | 188.741 | 157.098 |
| `text-embedding-3-large` | 220 | 1.032.518 | — |

Custo estimado pelos preços de tabela: US$ 16 a 24 (o valor real deve ser conferido no
painel da OpenAI). O cache (`data/cache`, 256 MB) guarda as respostas do modelo:
reindexar com o mesmo prompt e configuração reaproveita as respostas e custa
praticamente zero. **O cache não deve ser apagado.**

## 9. Publicação do índice (release v0.1.0)

- Pacote gerado em `releases/` (fora do git): `graphrag-cdc-index-v0.1.0.zip` (77 MB,
  1.323 arquivos: `data/output`, `data/cache`, `data/logs` e cópias de `settings.yaml`,
  `prompts/` e `cdc.json`, com os caminhos originais), checksum SHA-256, `MANIFEST`
  (commit, modelos, estatísticas, tokens, hashes da configuração e dos prompts) e
  notas da release.
- Convenções: tag com versionamento semântico (`v0.1.0`; `v1.0.0` reservado para o
  índice congelado da avaliação final), título "versão — frase curta", notas com
  resumo, estatísticas, configuração, assets e instruções de restauração; marcada como
  *latest release*, não *pre-release*.
- Restauração: `git checkout v0.1.0` e extrair o zip na raiz do repositório.
- Nenhuma chave de API é incluída (verificado por busca de padrões de chave).

## 10. Organização do repositório

- Estrutura: `app/` (backend e frontend), `config/`, `corpus/` (texto bruto e parser),
  `data/` (raiz do GraphRAG, estrutura padrão mantida), `docker/graphrag/`, `docs/`,
  `evaluation/`, `scripts/`, `storage/` (SQLite, fora do git). Detalhes no README.
- Convenção: código e pastas em inglês; documentação em português.
- `.gitignore` completo: segredos (`.env`), artefatos do GraphRAG (`data/output`,
  `data/cache`, `data/logs`), banco (`storage/`), pacotes de release, LaTeX (só o PDF
  do anteprojeto é versionado), Python, Node, editores e sistema operacional.
- `.gitattributes`: fins de linha normalizados (LF no repositório). As "modificações"
  em `data/prompts` que apareciam no git eram só diferença de fim de linha.
- Removidos: ambiente virtual vazio, pasta `output\lancedb` criada por engano,
  arquivos de template do Vite não usados, scripts de depuração (unificados em
  `scripts/inspect_output.py`).
- Versão do GraphRAG fixada (`graphrag==3.1.0`) no container de indexação e no backend,
  para reprodutibilidade.

## 11. Problemas de ambiente da aplicação

- **Página em branco após o rebuild**: o `package.json` pedia Tailwind CSS 4, mas o
  código foi escrito para o Tailwind 3 (`tailwind.config.js`, diretivas `@tailwind`,
  plugin do PostCSS). O CSS falhava com erro 500 e derrubava o app. Correção: Tailwind
  fixado em `^3.4.17`.
- **A correção não surtia efeito no container**: sem `.dockerignore`, o `COPY . .` do
  Dockerfile copiava a pasta `node_modules` da máquina (com o Tailwind 4) por cima da
  instalação limpa da imagem. Correção: `.dockerignore` no frontend e no backend.
- **Erros de TypeScript pré-existentes** (`baseUrl` obsoleto, variáveis não usadas)
  corrigidos; `tsc -b` passa sem erros.

## 12. Aplicação: consultas com passo a passo e histórico (11/10/2026)

### 12.1 Arquitetura

- O **índice é único** (`data/output`), gerado pelo container `graphrag`. O backend lê
  os mesmos arquivos, com a mesma versão do GraphRAG e o mesmo `settings.yaml`: uma
  consulta pela interface é equivalente à mesma consulta pela CLI.
- O container `graphrag` não é um servidor; é usado sob demanda (indexação,
  prompt-tune, consultas pela CLI).
- O frontend acessa o backend pelo proxy do Vite (`/api` → `backend:8000`), o que
  coloca frontend e API na mesma origem (sem CORS) e permite o fluxo SSE.
- Diagramas, rotas e tabelas em `docs/architecture.md`.

### 12.2 Backend (`app/backend/app`)

| Módulo | Responsabilidade |
|---|---|
| `config.py` | Caminhos (`GRAPHRAG_ROOT=/data`, `STORAGE_DIR=/storage`) e parâmetros padrão (nível de comunidade 2 e "Multiple Paragraphs", iguais aos da CLI) |
| `db.py`, `models.py` | SQLite com SQLAlchemy 2 (modo WAL); tabelas `index_versions`, `query_runs`, `query_steps`, `questions`, `evaluation_runs`, `assessments` |
| `services/query_service.py` | Carrega configuração, tabelas (via `DataReader`, como a CLI) e prompts; monta os motores de busca como `graphrag.api.query`; emite as etapas como eventos |
| `services/run_service.py` | Cria o registro da consulta, executa em segundo plano, grava cada etapa e repassa os eventos ao navegador. A gravação ocorre na tarefa, não na conexão: se o navegador fechar, a consulta termina e fica registrada |
| `services/index_service.py` | Impressão digital do índice: SHA-256 das tabelas principais + `settings.yaml` + prompts. Se qualquer um mudar, nasce uma nova versão; cada consulta guarda qual versão a respondeu |
| `routers/` | `/api/query`, `/api/runs`, `/api/index`, `/api/graph`... |

**Eventos de uma consulta** (SSE e tabela `query_steps`): `run`, `context` (tabelas
recuperadas e texto exato inserido no prompt), `prompt` (mensagem de sistema final e
pergunta), `map_start`/`map_end` (lotes e pontos-chave da busca global),
`reduce_start`/`reduce_end` (síntese; na DRIFT, a árvore de perguntas de
acompanhamento), `token` (resposta sendo gerada; não gravado), `result` (resposta,
chamadas, tokens por etapa, tempo), `error`, `done`.

**Por que o backend usa `search()` e não `stream_search()`**: o `search()` devolve o
`SearchResult` completo (contexto, chamadas ao modelo e tokens por etapa, tempo), que
é o que se exibe e se grava. A resposta continua aparecendo aos poucos porque o
`search()` também notifica cada pedaço gerado (`on_llm_new_token`).

**Contexto antes da resposta**: nas buscas local e basic, o GraphRAG só notifica o
contexto depois de gerar a resposta. O backend envolve o `build_context` da instância
do motor criada para a consulta, para emitir o contexto e reconstruir o prompt final
(mesmo template e mesmos argumentos usados pelo GraphRAG) antes da geração.

**Prompt exibido por modalidade**: local e basic, o prompt único; global, o prompt da
síntese (reduce) — o da etapa map é o template aplicado a cada lote; DRIFT, a árvore de
perguntas e respostas parciais.

### 12.3 Frontend (`app/frontend/src`)

- Abas **Grafo** (tela original), **Consultas** e **Histórico**; cabeçalho com a
  versão do índice em uso.
- **Consultas**: pergunta, modalidade (com descrição de cada uma), nível de comunidade
  (com aviso de custo na busca global) e formato da resposta. Linha do tempo de etapas
  recolhíveis: contexto em abas (entidades, relações, relatórios, trechos, texto
  enviado), pontos-chave da etapa map ordenados por nota (com o lote de origem), árvore
  da DRIFT, prompt com botão de copiar, resposta com marcação simples e métricas por
  etapa.
- **Histórico**: lista com filtros (modalidade, origem, texto) e abertura de cada
  consulta com o passo a passo gravado; exclusão.
- O estado da DRIFT pode ter arestas repetidas e laços (nó apontando para si mesmo);
  sem tratamento, a árvore entrava em recursão infinita e travava a página. A árvore
  ignora laços e arestas repetidas.

### 12.4 Destaque do contexto no grafo (11/10/2026)

Objetivo: mostrar visualmente **qual parte do grafo** cada consulta usou como
contexto, para apoiar a análise qualitativa (por que uma resposta saiu mais ou menos
completa) e a comparação com o baseline.

**Onde aparece**

- Na linha do tempo de cada consulta (ao vivo e no histórico), uma etapa nova,
  "Subgrafo usado como contexto", com um grafo interativo só com as entidades e
  relações envolvidas, colorido por tipo, com legenda e detalhes ao clicar em um nó.
- Botão **"Ver no grafo completo"**: abre a aba Grafo com essas entidades e relações
  destacadas (as demais ficam esmaecidas, as relações destacadas em vermelho), um
  aviso no topo descrevendo o destaque e o enquadramento automático nos nós
  destacados. O destaque é removido pelo botão do aviso.

**Como o destaque é calculado** (`app/frontend/src/lib/highlight.ts`), por modalidade:

| Modalidade | Entidades destacadas | Relações destacadas |
|---|---|---|
| local / drift | As da tabela de entidades do contexto, localizadas no grafo pelo título (o contexto usa o título da entidade, que é o rótulo do nó), mais as entidades que só aparecem como extremidade das relações do contexto | As da tabela de relações do contexto |
| basic | Entidades **extraídas dos trechos** recuperados pela busca vetorial. A busca basic não usa o grafo; o destaque mostra o que o grafo sabe sobre os mesmos trechos — útil para a comparação | Relações do grafo entre essas entidades |
| global | Entidades das comunidades cujos relatórios foram **citados** (`[Data: Reports (...)]`) nos pontos-chave com nota > 0 da etapa map e na resposta final | Relações do grafo entre essas entidades |

Na DRIFT é usado o contexto da primeira busca local (o GraphRAG não expõe por
callback o contexto de cada pergunta de acompanhamento).

**Alterações no backend**: cada nó do grafo (`/api/graph`) passou a trazer
`text_units`, os ids curtos dos trechos de onde a entidade foi extraída — os mesmos ids
que aparecem no contexto das buscas e nas citações das respostas ("Sources (49)"). O
mapeamento uuid → id curto vem de `text_units.parquet`. Verificado: a entidade
`ART. 54-E DO CDC` aponta para o trecho 59, o mesmo citado pela busca basic na
pergunta sobre o art. 54-E. Também foi verificado que o id dos relatórios de
comunidade exibido no contexto é o número da comunidade (`community` =
`human_readable_id` em `communities.parquet` e `community_reports.parquet`).

**Alterações no frontend**:

- `context/GraphDataContext.tsx`: o grafo é carregado uma única vez e compartilhado
  pelas telas, junto com o destaque ativo.
- As três telas ficam montadas e só são escondidas ao trocar de aba; antes, ir ao
  grafo descartava a consulta em andamento.
- O Histórico recarrega a lista ao ser aberto.
- `GraphView`: esmaecimento dos nós não destacados, relações destacadas, rótulos dos
  nós destacados com menos zoom e enquadramento automático. Os rótulos do grafo
  passaram a ser escuros (eram brancos sobre fundo branco).
- `components/query/ContextGraph.tsx`: subgrafo com no máximo 250 entidades (as mais
  conectadas, se houver mais); rótulos só com zoom ou em subgrafos pequenos, para não
  sobrepor.

**Testes** (índice real, modelo simulado, navegador automatizado): busca local — 40
entidades (20 da tabela de entidades e 20 extremidades de relações) e 31 relações;
basic — 216 entidades extraídas de 10 trechos; global — 138 entidades da comunidade
citada; ida e volta entre as abas mantendo a consulta; nenhum erro no console.

**Verificação na aplicação real** (11/10/2026, após o rebuild do backend): `/api/graph`
devolve `text_units` para as 1373 entidades. No Histórico, a consulta real da busca
local sobre o art. 49 exibe o subgrafo com 26 entidades (20 da tabela de entidades e
6 extremidades de relações) e 9 relações, coerente com o contexto registrado (20
entidades, 9 relações). "Ver no grafo completo" abre a aba Grafo com o aviso
"Destacando: Contexto da consulta", o enquadramento nos nós destacados (ART. 49, 18,
19, 20, 24, 26, 35, 39 DO CDC, PRODUTO, SERVIÇO, CONTRATO...) e as relações em
vermelho. Nenhum erro da aplicação no console.

**Leitura para o relatório**: o contraste é informativo. Na local, o contexto é um
conjunto pequeno de entidades e relações selecionadas a partir da pergunta; na basic, os
trechos recuperados por similaridade "tocam" uma região grande do grafo (centenas de
entidades), mas o modelo recebe só o texto; na global, o contexto é definido por
comunidades inteiras.

## 13. Problemas encontrados no GraphRAG 3.1.0 (consolidado)

| # | Problema | Onde | Efeito | Tratamento |
|---|---|---|---|---|
| 13.1 | `BasicSearch.search()` chama `completion_async(stream=True)` **sem `await`** e itera o resultado com `async for` | `query/structured_search/basic_search/search.py` | O erro é capturado internamente e a busca basic **sempre devolve resposta vazia**, sem aviso. A CLI não é afetada porque usa `stream_search()`, que tem o `await`. Também presente na 3.2.0 | Invólucro do modelo (`_AwaitedStreamModel` em `query_service.py`) que faz a chamada sem `await` devolver um iterador assíncrono. Só vale para a basic; não altera a biblioteca; mesmo prompt, mesmos trechos e mesmo modelo da CLI |
| 13.2 | Prompt-tune reaproveita a lista de mensagens entre chamadas | `prompt_tune/generator/entity_relationship.py` | Todos os exemplos de extração saem do último artigo | Script próprio com uma conversa por exemplo (seção 7) |
| 13.3 | Prompt-tune não aceita taxonomia | `api/prompt_tune.py` | Tipos descobertos são gravados fixos no prompt; `entity_types` do settings é ignorado | Script próprio (seção 7) |
| 13.4 | `load_search_prompt` resolve o caminho em relação ao diretório atual e, se não achar o arquivo, usa o prompt padrão em inglês **sem avisar** | `utils/api.py` | Uma consulta pode rodar com o prompt errado silenciosamente | O backend resolve os caminhos a partir de `data/` e falha se o arquivo não existir |
| 13.5 | Substituição de variáveis de ambiente no `settings.yaml` inteiro, inclusive comentários | `graphrag_common/config/load_config.py` | Cifrão em comentário ou referência a variável inexistente derruba o carregamento | Regra documentada no topo do `settings.yaml` |
| 13.6 | Na 3.x só a DRIFT define temperatura (padrão 0, herança da 2.x) | `config/defaults.py` | Inconsistência entre modalidades; com modelos de raciocínio, erro de parâmetro | Temperatura 1 explícita em tudo (seção 3) |
| 13.7 | Contexto das buscas local/basic notificado só depois da resposta | `local_search/search.py`, `basic_search/search.py` | Não é possível mostrar o contexto antes da geração usando só os callbacks | `build_context` envolvido na instância do motor (seção 12.2) |
| 13.8 | Métricas de tokens são contadas pelo tokenizer sobre o texto | buscas | Não incluem tokens de raciocínio dos modelos GPT-6; subestimam o custo real | Usar o painel do provedor para custo; registrar a ressalva no relatório |
| 13.9 | LiteLLM do container não conhece os modelos GPT-6 | `litellm` 1.86.2 | `drop_params` não filtra parâmetros não suportados | Parâmetros compatíveis definidos explicitamente |

Os itens 13.1 e 13.2 merecem destaque no relatório: sem o contorno de 13.1, quem usa a
biblioteca diretamente teria um baseline que sempre "responde" vazio, o que distorceria
qualquer comparação com o GraphRAG.

## 14. Custo por modalidade de busca (medido neste índice)

Medições com o índice real e modelo simulado (contagem do próprio GraphRAG; seção
13.8). Os tokens de entrada da busca global vêm do contexto real (lotes de relatórios),
então são representativos. Na DRIFT, o número de chamadas depende de quantas perguntas
de acompanhamento o modelo gera, e o modelo simulado gerou poucas: com o modelo real o
valor tende a ser maior. As buscas local e basic foram confirmadas com o modelo real
(seção 15).

| Modalidade | Chamadas ao modelo | Tokens de entrada (aprox.) |
|---|---|---|
| basic | 1 | 4,5 a 5 mil |
| local | 1 | 9 a 10 mil |
| drift (nível 2) | 8 | 67 mil |
| global, nível 0 | 7 | 71 mil |
| global, nível 1 | 30 | 336 mil |
| global, nível 2 (padrão da CLI) | 68 | 775 mil |
| global, nível 3 | 82 | 944 mil |

A busca global faz uma chamada por lote de relatórios de comunidade (até 12 mil tokens
por lote). No nível 2, cada consulta global deve custar mais de US$ 1. **Decisão
pendente**: fixar o nível de comunidade da busca global para a avaliação (sugestão:
0 ou 1, com justificativa de custo no relatório). A seleção dinâmica de comunidades
(`dynamic_community_selection`) faz chamadas extras para classificar a relevância dos
relatórios.

## 15. Testes e validação

- **Teste com modelos simulados**: índice real e modelos `mock` do GraphRAG (com
  suporte a streaming acrescentado só no teste), exercitando as quatro modalidades, o
  fluxo SSE, a gravação no SQLite, o histórico e a interface (navegador automatizado,
  capturas de tela). Foi assim que se encontraram os problemas 13.1 e o laço da árvore
  DRIFT.
- **Consulta real, busca local** (11/10/2026): "O que diz o art. 49 do CDC sobre o
  direito de arrependimento?" — 1 chamada, 10.154 tokens de entrada, 205 de saída.
  Contexto: 20 entidades, 9 relações, 17 trechos. Resposta correta em português (prazo
  de 7 dias, contratação fora do estabelecimento, devolução imediata e atualizada dos
  valores), citando `[Data: Sources (49)]`.
- **Consulta real, busca basic** (11/10/2026), validando o contorno 13.1: "O que
  acontece com o art. 54-E do CDC?" — 1 chamada, 4.452 tokens de entrada, 123 de saída,
  6,6 s. Contexto: 10 trechos recuperados por similaridade (os primeiros eram dos arts.
  34 e 52, não do 54-E). Resposta correta: o artigo foi vetado, aparece apenas como
  "Art. 54-E. (VETADO)", está associado à Lei nº 14.181/2021 e ao capítulo do
  superendividamento; o modelo ressalvou que os dados não informam a redação proposta
  nem os motivos do veto. Observação útil para a comparação: a busca vetorial trouxe o
  artigo certo, mas não nas primeiras posições.
- **Destaque do contexto no grafo, dados reais** (11/10/2026): ver o fim da seção
  12.4 — subgrafo da consulta local do art. 49 (26 entidades, 9 relações) e destaque
  no grafo completo funcionando.

## 16. Pendências e próximos passos

- Definir o nível de comunidade da busca global para a avaliação (seção 14).
- Avaliação: conjunto de perguntas (`evaluation/questions.csv`), script
  `evaluation/run_queries.py` usando a mesma API (`source = "evaluation"`), exportação
  para `evaluation/results/`, notas manuais (`assessments`).
- Publicar o índice congelado da avaliação como release `v1.0.0`.

## 17. Histórico cronológico

| Data | Etapa |
|---|---|
| 07/2026 | Primeira versão: execução local (Ollama), indexação de teste, visualizador do grafo |
| 07/10/2026 | Configuração para modelos em nuvem; correções do parser (ids, vetados, Capítulo VI-A); análise da temperatura; reorganização do repositório |
| 08/10/2026 | Nova taxonomia; script de prompt-tune; indexação v1 com `gpt-6.1-sol`; pacote da release v0.1.0; correção do frontend (Tailwind e `.dockerignore`) |
| 11/10/2026 | Backend de consultas com etapas (SSE) e SQLite; telas de Consultas e Histórico; documentação da arquitetura; testes reais das buscas local e basic |
| 11/10/2026 | Destaque do contexto no grafo (subgrafo por consulta e destaque no grafo completo) |
