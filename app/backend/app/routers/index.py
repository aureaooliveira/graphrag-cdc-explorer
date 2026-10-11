"""Versão do índice em uso e recarga após reindexação."""
from fastapi import APIRouter

from app.db import SessionLocal
from app.models import IndexVersion
from app.services import state
from app.services.graph_loader import graph_loader
from app.services.index_service import index_version_to_dict, register_current_index

router = APIRouter(prefix="/api/index", tags=["Index"])


def current_index() -> dict:
    with SessionLocal() as s:
        iv = s.get(IndexVersion, state.index_version_id) if state.index_version_id else None
        return {
            "index_version": index_version_to_dict(iv),
            "query_ready": bool(state.query_service and state.query_service.ready),
            "query_error": state.query_service.load_error if state.query_service else None,
        }


async def load_index() -> None:
    """Carrega o índice (grafo + consultas) e registra sua versão."""
    graph_loader.reload()
    await state.query_service.load()
    with SessionLocal() as s:
        iv = register_current_index(s, stats=state.query_service.stats() if state.query_service.ready else None)
        state.index_version_id = iv.id


@router.get("")
def get_index():
    return current_index()


@router.post("/reload")
async def reload_index():
    """Use depois de reindexar (graphrag index) ou de trocar os prompts."""
    await load_index()
    return current_index()
