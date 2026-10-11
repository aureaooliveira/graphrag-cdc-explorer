"""Consultas ao GraphRAG.

POST /api/query            -> fluxo SSE com as etapas (padrão)
POST /api/query?stream=false -> espera terminar e devolve o registro completo
"""
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.db import SessionLocal
from app.models import QueryRun
from app.schemas.query import QueryRequest
from app.services import state
from app.services.run_service import run_to_dict, start_query

router = APIRouter(prefix="/api", tags=["Query"])


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@router.post("/query")
async def query(req: QueryRequest, stream: bool = True):
    if state.query_service is None or not state.query_service.ready:
        detail = state.query_service.load_error if state.query_service else "serviço não iniciado"
        raise HTTPException(status_code=503, detail=f"Índice indisponível para consultas: {detail}")

    job = start_query(**req.model_dump())

    if not stream:
        await job.task
        with SessionLocal() as s:
            run = s.get(QueryRun, job.run_id)
            return run_to_dict(run, include_steps=True)

    async def events():
        while True:
            item = await job.queue.get()
            if item is None:
                yield _sse("done", {"run_id": job.run_id})
                break
            event_type, payload = item
            yield _sse(event_type, payload)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
