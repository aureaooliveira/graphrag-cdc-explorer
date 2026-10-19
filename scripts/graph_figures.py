# Gera as figuras de análise do grafo usadas na monografia (cap. 6) a partir do índice.
# Uso: python scripts/graph_figures.py data/output docs/paper/figuras   (requer networkx e matplotlib)
import sys, math, pandas as pd, networkx as nx, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
root, out = sys.argv[1], sys.argv[2]
C = {"CONSUMIDOR":"#1f77b4","FORNECEDOR":"#d62728","ORGAO_ENTIDADE":"#9467bd","PRODUTO":"#ff7f0e","SERVICO":"#e6b800","CONTRATO":"#8c564b","DIREITO":"#2ca02c","OBRIGACAO":"#e377c2","PRATICA_ABUSIVA":"#bcbd22","INSTITUTO_JURIDICO":"#17becf","SANCAO_ADMINISTRATIVA":"#393b79","INFRACAO_PENAL":"#843c39","INSTRUMENTO_PROCESSUAL":"#637939","DISPOSITIVO_LEGAL":"#9e9e9e"}
e = pd.read_parquet(f"{root}/entities.parquet"); r = pd.read_parquet(f"{root}/relationships.parquet")
typ = dict(zip(e.title, e.type)); deg = dict(zip(e.title, e.degree))
plt.rcParams.update({"font.family":"DejaVu Sans"})

# 1. especialização por tipo
fig, axes = plt.subplots(2, 2, figsize=(14, 12))
for ax, (T, title) in zip(axes.flat, [("CONSUMIDOR","Tipo consumidor"),("FORNECEDOR","Tipo fornecedor"),("PRODUTO","Tipo produto"),("SERVICO","Tipo serviço")]):
    names = set(e[e.type==T].title)
    G = nx.Graph(); G.add_nodes_from(names)
    for _, x in r[r.source.isin(names) & r.target.isin(names)].iterrows(): G.add_edge(x.source, x.target)
    hub = max(names, key=lambda n: deg[n])
    comp = nx.node_connected_component(G, hub); H = G.subgraph(comp)
    pos = nx.spring_layout(H, k=1.6/math.sqrt(len(H)), seed=7, iterations=300)
    sizes = [30 + 6*deg[n] if n != hub else 1400 for n in H]
    nx.draw_networkx_edges(H, pos, ax=ax, edge_color="#bbbbbb", width=0.8)
    nx.draw_networkx_nodes(H, pos, ax=ax, node_size=sizes, node_color=C[T], alpha=0.85, linewidths=0)
    for n,(x,y) in pos.items():
        if n == hub:
            ax.text(x, y - 0.11, n, fontsize=10, ha="center", va="top", color="#111", fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85), zorder=5)
        else:
            ax.text(x, y + 0.045, n, fontsize=6.5, ha="center", va="bottom", color="#222")
    others = len(names) - len(H)
    ax.set_title(f"{title}: {len(H)} de {len(names)} entidades conectadas ao nó geral" + (f" ({others} fora)" if others else ""), fontsize=11)
    ax.axis("off")
plt.tight_layout(); plt.savefig(f"{out}/fig-grafo-especializacao.png", dpi=200); plt.close()

# 2. maiores graus
top = e.sort_values("degree", ascending=False).head(15)[::-1]
fig, ax = plt.subplots(figsize=(9, 5.5))
ax.barh(top.title, top.degree, color=[C.get(t,"#888") for t in top.type])
for i,(d) in enumerate(top.degree): ax.text(d+5, i, str(d), va="center", fontsize=8)
ax.set_xlabel("Grau (número de relações)"); ax.spines[["top","right"]].set_visible(False)
from matplotlib.patches import Patch
used = list(dict.fromkeys(top.type[::-1]))
ax.legend(handles=[Patch(color=C[t], label=t.lower()) for t in used], fontsize=8, loc="lower right", frameon=False)
plt.tight_layout(); plt.savefig(f"{out}/fig-grafo-graus.png", dpi=200); plt.close()

# 3. ego de DIREITO DE ARREPENDIMENTO
c = "DIREITO DE ARREPENDIMENTO"
x = r[(r.source==c)|(r.target==c)]
G = nx.Graph()
for _, row in x.iterrows(): G.add_edge(row.source, row.target, w=row.weight)
pos = nx.spring_layout(G, seed=3, k=0.9)
pos[c] = (0,0)
fig, ax = plt.subplots(figsize=(11, 8))
nx.draw_networkx_edges(G, pos, ax=ax, edge_color="#999", width=[1+0.12*G[u][v]["w"] for u,v in G.edges()])
nx.draw_networkx_edge_labels(G, pos, ax=ax, edge_labels={(u,v): f'{G[u][v]["w"]:.0f}' for u,v in G.edges()}, font_size=7, rotate=False, bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
nx.draw_networkx_nodes(G, pos, ax=ax, node_color=[C.get(typ.get(n),"#888") for n in G], node_size=[1200 if n==c else 200+2*deg.get(n,1) for n in G], linewidths=[3 if n in ("ART. 49 DO CDC","ART. 54-F DO CDC") else 0 for n in G], edgecolors="black")
for n,(px,py) in pos.items():
    ax.text(px, py-0.09, n, fontsize=8, ha="center", va="top", fontweight="bold" if n in (c,"ART. 49 DO CDC","ART. 54-F DO CDC") else "normal")
used = list(dict.fromkeys(typ.get(n) for n in G))
ax.legend(handles=[Patch(color=C[t], label=t.lower()) for t in used if t], fontsize=8, loc="lower left", frameon=False)
ax.axis("off"); ax.margins(0.12)
plt.tight_layout(); plt.savefig(f"{out}/fig-grafo-ego-arrependimento.png", dpi=200); plt.close()
print("ok")
