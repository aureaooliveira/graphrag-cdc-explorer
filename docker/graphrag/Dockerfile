FROM python:3.11-slim

# Versão do GraphRAG fixada para garantir a reprodutibilidade dos experimentos.
# pyvis é usado por scripts/visualize_graph.py.
RUN pip install --no-cache-dir graphrag==3.1.0 pyvis==0.3.2

WORKDIR /data
