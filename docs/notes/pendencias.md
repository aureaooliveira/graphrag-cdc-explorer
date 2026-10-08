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
