# Frontend — visualizador do grafo

Aplicação React + TypeScript (Vite) que exibe de forma interativa o grafo de
conhecimento gerado pelo GraphRAG, consumindo a API do backend
(`VITE_API_URL`, padrão `http://localhost:8000`).

- `src/components/GraphView.tsx` — renderização do grafo (react-force-graph-2d)
- `src/components/FiltersPanel.tsx` — filtros por tipo de entidade e comunidade
- `src/components/EntityDetailsPanel.tsx` — detalhes da entidade selecionada
- `src/components/Legend.tsx` — legenda de cores
- `src/hooks/useGraphData.ts` — carregamento dos dados da API

Execução: o serviço `frontend` do `docker-compose.yml` sobe o servidor de
desenvolvimento em `http://localhost:5173`. Veja o README da raiz do projeto.
