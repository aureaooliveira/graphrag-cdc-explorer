"""Identificação da versão do índice do GraphRAG.

Cada consulta guarda qual índice a respondeu. A "impressão digital" do índice
combina o conteúdo das tabelas principais com o settings.yaml e os prompts:
se qualquer um deles mudar (reindexação, novo prompt-tune), nasce uma nova
versão e as consultas antigas continuam associadas à versão anterior.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import GRAPHRAG_ROOT, OUTPUT_DIR
from app.models import IndexVersion

FINGERPRINT_TABLES = ["entities", "relationships", "communities", "community_reports", "text_units"]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _sha256_dir(path: Path, pattern: str = "*.txt") -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    for p in sorted(path.glob(pattern)):
        h.update(p.name.encode())
        h.update(_sha256_file(p).encode())
    return h.hexdigest()


def _models_from_settings(settings_path: Path) -> dict:
    """Lê os modelos do settings.yaml (sem resolver variáveis de ambiente)."""
    try:
        cfg = yaml.safe_load(settings_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    models = {}
    for section in ("completion_models", "embedding_models"):
        for name, m in (cfg.get(section) or {}).items():
            models[name] = f"{m.get('model_provider')}/{m.get('model')}"
    return models


def compute_fingerprint() -> dict:
    """Calcula a impressão digital e os metadados do índice atual."""
    h = hashlib.sha256()
    for table in FINGERPRINT_TABLES:
        p = OUTPUT_DIR / f"{table}.parquet"
        if p.exists():
            h.update(table.encode())
            h.update(_sha256_file(p).encode())
    settings_path = GRAPHRAG_ROOT / "settings.yaml"
    settings_sha = _sha256_file(settings_path) if settings_path.exists() else None
    prompts_sha = _sha256_dir(GRAPHRAG_ROOT / "prompts")
    h.update((settings_sha or "").encode())
    h.update((prompts_sha or "").encode())

    stats_path = OUTPUT_DIR / "stats.json"
    indexed_at = None
    if stats_path.exists():
        indexed_at = datetime.fromtimestamp(stats_path.stat().st_mtime, tz=timezone.utc)

    try:
        graphrag_version = version("graphrag")
    except PackageNotFoundError:
        graphrag_version = None

    return {
        "fingerprint": h.hexdigest(),
        "indexed_at": indexed_at,
        "graphrag_version": graphrag_version,
        "settings_sha256": settings_sha,
        "prompts_sha256": prompts_sha,
        "models": _models_from_settings(settings_path),
    }


def register_current_index(session: Session, stats: dict | None = None) -> IndexVersion:
    """Registra (ou reaproveita) a versão do índice atual no banco."""
    info = compute_fingerprint()
    current = session.scalar(
        select(IndexVersion).where(IndexVersion.fingerprint == info["fingerprint"])
    )
    if current is None:
        current = IndexVersion(**info, stats=stats)
        session.add(current)
    elif stats:
        current.stats = stats
    session.commit()
    return current


def index_version_to_dict(iv: IndexVersion | None) -> dict | None:
    if iv is None:
        return None
    return {
        "id": iv.id,
        "fingerprint": iv.fingerprint,
        "label": iv.label,
        "registered_at": iv.registered_at.isoformat() if iv.registered_at else None,
        "indexed_at": iv.indexed_at.isoformat() if iv.indexed_at else None,
        "graphrag_version": iv.graphrag_version,
        "settings_sha256": iv.settings_sha256,
        "prompts_sha256": iv.prompts_sha256,
        "models": iv.models,
        "stats": iv.stats,
    }


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
