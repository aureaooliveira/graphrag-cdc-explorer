# Pendências do texto

Tópicos a desenvolver na documentação do TCC:

- Detalhes do funcionamento do GraphRAG
- Prompt-tuning (`graphrag prompt-tune`)
- Comunidades e níveis de comunidade (algoritmo de Leiden)
- Grau das entidades
- Temperatura dos modelos: na versão 3.x do GraphRAG só a busca DRIFT define
  temperatura própria (padrão 0, herdado da 2.x, em que todos os modelos usavam 0);
  com modelos de raciocínio (GPT-6), só `temperature=1` é aceita, então ela foi
  fixada em 1 para todas as modalidades e as perguntas de avaliação são repetidas
  para medir a variabilidade das respostas.
- Bug do prompt-tune no GraphRAG 3.1.0: `generate_entity_relationship_examples`
  reaproveita o mesmo `CompletionMessagesBuilder` para todas as chamadas; cada chamada
  recebe todos os artigos de exemplo e o modelo responde sempre sobre o último, então
  todos os exemplos do `extract_graph.txt` saem iguais (na 1ª execução, todos eram do
  art. 82). Contornado em `scripts/prompt_tune.py` (uma conversa por exemplo). Vale
  citar no TCC e, opcionalmente, reportar no repositório do GraphRAG.
