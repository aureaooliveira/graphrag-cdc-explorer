"""Configuração do backend (caminhos e banco), via variáveis de ambiente."""
import os
from pathlib import Path

# Raiz do GraphRAG: settings.yaml, prompts/, .env e output/ (índice).
GRAPHRAG_ROOT = Path(os.environ.get("GRAPHRAG_ROOT", "/data"))
OUTPUT_DIR = GRAPHRAG_ROOT / "output"

# Onde fica o banco SQLite com o histórico de consultas e avaliações.
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", "/storage"))
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{STORAGE_DIR / 'app.db'}")

# Parâmetros padrão das consultas (os mesmos da CLI `graphrag query`).
DEFAULT_COMMUNITY_LEVEL = 2
DEFAULT_RESPONSE_TYPE = "Multiple Paragraphs"
