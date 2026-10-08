# Avaliação

Pasta reservada para a etapa de avaliação comparativa descrita no anteprojeto
(`docs/proposal/anteprojeto-aureaoliveira.pdf`, seções 1.3 e 2.3).

Estrutura prevista:

```
evaluation/
├── questions.csv        # conjunto de perguntas de teste sobre o CDC
├── run_queries.py       # executa cada pergunta nas modalidades local, global, drift e basic
└── results/             # respostas obtidas (uma execução por arquivo)
```

Protocolo:

- Todas as consultas usam o **mesmo índice congelado** (mesma pasta `data/output`).
- A busca **basic** (RAG vetorial) é o baseline: mesmo corpus, mesmo modelo de
  embeddings e mesmo modelo gerador das demais modalidades.
- Como os modelos usados só aceitam `temperature=1`, cada pergunta é executada
  **mais de uma vez** por modalidade, para avaliar também a consistência das respostas.
