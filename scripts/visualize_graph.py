"""
Gera uma visualizacao HTML interativa do grafo produzido pelo GraphRAG.

Uso (dentro do container graphrag):
    python /scripts/visualize_graph.py

Le os parquets de output do GraphRAG (entities, relationships, communities)
e produz /data/output/graph.html, que pode ser aberto direto no navegador
do Windows (a pasta ./data esta montada como volume).
"""

import pandas as pd
import networkx as nx
from pyvis.network import Network
import os

OUTPUT_DIR = os.path.join(os.environ.get("GRAPHRAG_ROOT", "/data"), "output")

# Paleta de cores para colorir por comunidade (repete se houver mais
# comunidades do que cores)
PALETTE = [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
    "#911eb4", "#46f0f0", "#f032e6", "#bcf60c", "#fabebe",
    "#008080", "#e6beff", "#9a6324", "#800000", "#aaffc3",
]

def load_parquet(name):
    path = os.path.join(OUTPUT_DIR, f"{name}.parquet")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Nao encontrei {path}. Rode 'graphrag index' primeiro.")
    return pd.read_parquet(path)


def main():
    print("Carregando entidades...")
    entities = load_parquet("entities")

    print("Carregando relacionamentos...")
    relationships = load_parquet("relationships")

    communities = None
    try:
        print("Carregando comunidades...")
        communities = load_parquet("communities")
    except FileNotFoundError:
        print("Sem arquivo de comunidades, seguindo sem colorir por comunidade.")

    # Mapear entity id/title -> community (se disponivel)
    entity_to_community = {}
    if communities is not None:
        for _, row in communities.iterrows():
            comm_id = row.get("community")
            entity_ids = row.get("entity_ids")
            if entity_ids is None:
                entity_ids = []
            for eid in entity_ids:
                entity_to_community[eid] = comm_id

    G = nx.Graph()

    print(f"Adicionando {len(entities)} entidades ao grafo...")
    for _, row in entities.iterrows():
        eid = row.get("id")
        title = row.get("title", eid)
        etype = row.get("type", "desconhecido")
        description = str(row.get("description", ""))[:300]
        degree = row.get("degree", 1) or 1

        community = entity_to_community.get(eid)
        color = PALETTE[community % len(PALETTE)] if community is not None else "#97c2fc"

        G.add_node(
            title,
            label=title,
            title=f"<b>{title}</b><br>Tipo: {etype}<br>{description}",
            color=color,
            size=10 + min(degree, 20) * 2,
        )

    print(f"Adicionando {len(relationships)} relacoes ao grafo...")
    for _, row in relationships.iterrows():
        source = row.get("source")
        target = row.get("target")
        description = str(row.get("description", ""))[:200]
        weight = row.get("weight", 1) or 1

        if source in G.nodes and target in G.nodes:
            G.add_edge(source, target, title=description, value=weight)

    print("Gerando visualizacao interativa...")
    net = Network(
        height="900px",
        width="100%",
        bgcolor="#111111",
        font_color="white",
        notebook=False,
        cdn_resources="in_line",
    )
    net.from_nx(G)

    # Fisica mais estavel para grafos medios
    net.set_options("""
    {
      "physics": {
        "solver": "forceAtlas2Based",
        "forceAtlas2Based": {
          "gravitationalConstant": -60,
          "springLength": 120,
          "springConstant": 0.03
        },
        "stabilization": { "iterations": 200 }
      },
      "interaction": { "hover": true, "tooltipDelay": 100 }
    }
    """)

    out_path = os.path.join(OUTPUT_DIR, "graph.html")
    net.write_html(out_path, open_browser=False)
    print(f"\nPronto! Abra o arquivo no seu Windows em: .\\data\\output\\graph.html")
    print(f"(dentro do container: {out_path})")


if __name__ == "__main__":
    main()