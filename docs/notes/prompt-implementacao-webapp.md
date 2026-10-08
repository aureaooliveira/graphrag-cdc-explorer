# Instruções para Implementação: Visualização do Grafo de Conhecimento (GraphRAG)

## Contexto

Este projeto é uma prova de conceito (PoC) acadêmica de um sistema RAG baseado
em grafo (GraphRAG, da Microsoft) aplicado ao Código de Defesa do Consumidor
(CDC). A etapa de indexação já foi executada com sucesso, gerando um conjunto
de arquivos `.parquet` em `data/output/` contendo o grafo de conhecimento
extraído (entidades, relacionamentos, comunidades e resumos de comunidade).

**Escopo desta tarefa:** implementar uma aplicação web full-stack cuja
**única funcionalidade por enquanto** é exibir esse grafo de conhecimento de
forma interativa, rica em informação e com boa usabilidade. **Não
implemente, ainda, nenhuma funcionalidade de consulta/pergunta em linguagem
natural** (local search, global search, etc.) — isso será tratado em uma
etapa posterior. Foque exclusivamente em ler os dados já indexados e
apresentá-los visualmente.

---

## Stack obrigatória

### Backend
- **Python** com **FastAPI**
- Leitura dos arquivos `.parquet` com **pandas** (e `pyarrow` como engine)
- Sem necessidade de banco de dados adicional nesta etapa — os arquivos
  parquet são a única fonte de dados
- Documentação automática da API deve ficar disponível em `/docs` (padrão do
  FastAPI, não precisa configuração extra)

### Frontend
- **React** com **TypeScript**, criado com **Vite**
- Estilização com **Tailwind CSS** + biblioteca de componentes **shadcn/ui**
  (para elementos de interface como painel lateral, legendas, tooltips,
  controles de filtro)
- Biblioteca de visualização de grafo: utilize **react-force-graph**
  (especificamente `react-force-graph-2d`, que é suficiente e mais leve que a
  versão 3D para este caso de uso). Caso, durante a implementação, você
  identifique limitações de performance ou de customização visual
  relevantes, pode propor a troca por **Cytoscape.js** (via `react-cytoscapejs`),
  mas explique o motivo antes de trocar.

### Orquestração
- O projeto já possui um ambiente Docker configurado (`docker-compose.yml`
  com serviços `ollama` e `graphrag`, e a pasta `data/` montada como volume).
  Adicione um serviço `backend` e um serviço `frontend` a esse
  `docker-compose.yml`, montando a mesma pasta `data/` como volume
  **somente leitura** no serviço `backend`, já que ele só precisa ler os
  arquivos de output.

---

## Fonte de dados: arquivos gerados pelo GraphRAG

Os arquivos relevantes estão em `data/output/*.parquet`. **Antes de escrever
qualquer código de leitura/transformação, inspecione o schema real desses
arquivos** (rodando algo como `pandas.read_parquet(path).columns` e
`.dtypes`, e olhando algumas linhas de exemplo) — **não assuma nomes de
colunas de memória ou de documentação antiga**, pois esse projeto já teve
problemas de incompatibilidade de schema entre versões da biblioteca
GraphRAG durante o desenvolvimento. Os arquivos esperados são:

- **`entities.parquet`** — uma linha por entidade extraída. Deve conter, no
  mínimo, um identificador, um título/nome, um tipo (`type` — ex.:
  `artigo`, `direito`, `obrigacao`, conforme a taxonomia jurídica definida
  no `settings.yaml` do projeto), uma descrição textual, e alguma medida de
  grau/conectividade (`degree`).
- **`relationships.parquet`** — uma linha por relação entre duas entidades.
  Deve conter identificadores de origem e destino (`source`, `target`), uma
  descrição da relação e um peso (`weight`).
- **`communities.parquet`** — o resultado do agrupamento hierárquico de
  comunidades (algoritmo de Leiden). Deve conter um identificador de
  comunidade, um nível hierárquico (`level`) e a lista de entidades
  pertencentes a cada comunidade (`entity_ids`).
- **`community_reports.parquet`** — os resumos textuais gerados pelo LLM
  para cada comunidade, em diferentes níveis hierárquicos. Deve conter
  identificador de comunidade, nível, título/resumo curto e o conteúdo
  completo do relatório.

Trate a leitura desses arquivos de forma defensiva: valide se as colunas
esperadas existem antes de usá-las, e trate o caso de alguma coluna vir como
lista/array (comum em colunas como `entity_ids`) em vez de valor escalar.

---

## Requisitos do Backend

1. **Endpoint `GET /api/graph`**: retorna o grafo completo em um formato
   único, pronto para consumo pelo frontend, estruturado como:
   ```json
   {
     "nodes": [
       {
         "id": "...",
         "label": "...",
         "type": "...",
         "description": "...",
         "degree": 0,
         "communities": [
           { "level": 0, "community_id": "...", "summary": "..." },
           { "level": 1, "community_id": "...", "summary": "..." }
         ]
       }
     ],
     "edges": [
       { "source": "...", "target": "...", "description": "...", "weight": 0 }
     ]
   }
   ```
   Cada nó deve carregar, já pré-processado no backend, a que comunidade
   pertence em **cada nível hierárquico** disponível (uma entidade pode
   pertencer a comunidades diferentes em níveis diferentes), junto com o
   resumo da comunidade correspondente àquele nível — isso é o que vai
   alimentar o tooltip de "resumos em vários níveis" pedido pelo usuário.

2. **Endpoint `GET /api/communities`**: retorna a lista de comunidades com
   seus metadados (id, nível, título, resumo completo, quantidade de
   entidades), útil para popular filtros e legendas no frontend sem precisar
   reprocessar o grafo inteiro no cliente.

3. **Endpoint `GET /api/meta`**: retorna metadados úteis sobre o grafo
   indexado — contagem total de entidades, de relacionamentos, lista de
   tipos de entidade distintos (`type`) presentes, quantidade de níveis de
   comunidade disponíveis. Isso alimenta a legenda de cores e os filtros da
   interface.

4. Estruture o código do backend com separação clara entre: (a) camada de
   leitura/carregamento dos parquets, (b) camada de transformação para o
   formato de grafo, e (c) camada de rotas HTTP. Use um cache em memória
   simples para os dados carregados (os parquets não mudam durante a
   execução da aplicação, não há necessidade de reler o disco a cada
   requisição).

---

## Requisitos do Frontend

### Visualização principal do grafo

- Renderize o grafo completo (nós e arestas) usando `react-force-graph-2d`,
  ocupando a maior parte da tela.
- **Cor dos nós por tipo de entidade (`type`)**: gere uma paleta de cores
  consistente (uma cor por tipo distinto), e exiba uma **legenda fixa**
  (usando componentes shadcn/ui) mapeando cor → tipo de entidade.
- **Tamanho dos nós proporcional ao grau (`degree`)**: entidades mais
  conectadas devem aparecer visualmente maiores, facilitando a
  identificação de entidades centrais no grafo (ex.: artigos muito
  referenciados).
- **Identificação visual de comunidades**: implemente um seletor (dropdown
  ou toggle) que permita ao usuário alternar entre "colorir por tipo de
  entidade" e "colorir por comunidade" (nesse segundo modo, escolha o nível
  hierárquico de comunidade via outro seletor, já que o GraphRAG gera
  comunidades em múltiplos níveis). Ao colorir por comunidade, use uma
  paleta distinta o suficiente para diferenciar visualmente os
  agrupamentos, e considere desenhar um agrupamento visual leve (ex.:
  aproximar espacialmente nós da mesma comunidade, se a biblioteca de force
  graph permitir customizar a força de atração por grupo).

### Tooltips e painel de detalhes

- Ao passar o mouse sobre um **nó**, exiba um tooltip com: nome da
  entidade, tipo, descrição completa, grau de conectividade.
- Ao passar o mouse sobre uma **aresta**, exiba um tooltip com a descrição
  da relação e o peso.
- Ao **clicar** em um nó, abra um painel lateral (usando um componente
  shadcn/ui, como `Sheet` ou `Drawer`) mostrando informações estendidas:
  todos os dados da entidade, todas as relações diretas daquele nó, e — o
  ponto pedido explicitamente para fins acadêmicos — **os resumos de
  comunidade em cada nível hierárquico** ao qual aquela entidade pertence,
  permitindo ver como a granularidade do agrupamento muda entre níveis.

### Filtros e controles de usabilidade

- Filtro por tipo de entidade (multi-select, permitindo mostrar/ocultar
  tipos específicos no grafo).
- Filtro por comunidade/nível hierárquico.
- Campo de busca textual que destaque (e centralize a visualização em) uma
  entidade pelo nome.
- Controles de zoom/pan (nativos da biblioteca de force graph) e um botão
  de "resetar visualização".
- Indicador de carregamento (loading state) enquanto os dados são buscados
  do backend, e tratamento visível de erro caso a API falhe.

### Considerações de performance

- Caso o grafo completo do CDC tenha um volume grande de nós/arestas,
  avalie a necessidade de renderização otimizada (a própria
  `react-force-graph-2d` usa canvas e lida bem com grafos de tamanho médio,
  mas teste com o dado real gerado pela indexação e ajuste parâmetros de
  física da simulação — como `cooldownTicks` ou `d3AlphaDecay` — se a
  performance ficar comprometida).

---

## Estrutura de pastas sugerida

```
app/
├── backend/
│   ├── app/
│   │   ├── main.py              # instancia o FastAPI e inclui as rotas
│   │   ├── routers/
│   │   │   └── graph.py         # endpoints /api/graph, /api/communities, /api/meta
│   │   ├── services/
│   │   │   └── graph_loader.py  # leitura dos parquets e cache em memória
│   │   └── schemas/
│   │       └── graph.py         # modelos Pydantic de resposta
│   ├── requirements.txt
│   └── Dockerfile
└── frontend/
    ├── src/
    │   ├── components/
    │   │   ├── GraphView.tsx
    │   │   ├── Legend.tsx
    │   │   ├── FiltersPanel.tsx
    │   │   └── EntityDetailsPanel.tsx
    │   ├── hooks/
    │   │   └── useGraphData.ts
    │   ├── types/
    │   │   └── graph.ts
    │   └── App.tsx
    ├── package.json
    └── Dockerfile
```

---

## Critérios de aceite desta etapa

- [ ] O grafo completo do CDC indexado é exibido corretamente, com todos os
      nós e arestas visíveis e navegáveis.
- [ ] É possível identificar visualmente o tipo de cada entidade por cor,
      com legenda correspondente.
- [ ] É possível alternar a visualização para colorir por comunidade,
      escolhendo o nível hierárquico.
- [ ] Ao interagir (hover/clique) com um nó, as informações da entidade e os
      resumos de comunidade em múltiplos níveis são exibidos claramente.
- [ ] Existem filtros funcionais por tipo de entidade e por comunidade.
- [ ] A aplicação sobe corretamente via `docker compose up`, consumindo os
      dados reais gerados pela indexação em `data/output/`.
- [ ] Nenhuma funcionalidade de consulta/pergunta em linguagem natural foi
      implementada nesta etapa — isso fica para uma tarefa futura.