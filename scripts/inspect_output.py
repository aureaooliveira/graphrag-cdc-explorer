"""
inspect_output.py

Inspeciona as tabelas geradas pelo GraphRAG em data/output: colunas, tipos,
quantidade de linhas e um exemplo de registro. Útil para depurar o backend
e para conferir o resultado de uma indexação.

Uso (dentro do container graphrag):
    python /scripts/inspect_output.py              # todas as tabelas
    python /scripts/inspect_output.py entities     # apenas uma tabela
    python /scripts/inspect_output.py --titles     # títulos das entidades e
                                                   # origens das relações
"""
import os
import sys

import pandas as pd

OUTPUT_DIR = os.path.join(os.environ.get("GRAPHRAG_ROOT", "/data"), "output")
TABLES = ["documents", "text_units", "entities", "relationships",
          "communities", "community_reports"]


def inspect_table(name: str) -> None:
    path = os.path.join(OUTPUT_DIR, f"{name}.parquet")
    print(f"--- {name} ({path}) ---")
    try:
        df = pd.read_parquet(path)
    except Exception as e:  # noqa: BLE001
        print(f"Erro ao ler: {e}\n")
        return
    print(f"{len(df)} linha(s)")
    for col in df.columns:
        print(f"  - {col}: {df[col].dtype}")
    print("Primeiro registro:")
    print(df.iloc[0].to_dict() if not df.empty else "(vazio)")
    print()


def print_titles() -> None:
    entities = pd.read_parquet(os.path.join(OUTPUT_DIR, "entities.parquet"))
    print("--- Títulos das entidades (title -> id) ---")
    for _, row in entities.iterrows():
        print(f"  {row.get('title')!r}: {row.get('id')!r}")
    rels = pd.read_parquet(os.path.join(OUTPUT_DIR, "relationships.parquet"))
    print("\n--- Origens das relações ---")
    for s in rels.get("source", []):
        print(f"  {s!r}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--titles" in args:
        print_titles()
    else:
        for table in (args or TABLES):
            inspect_table(table)
