"""Orquestra uma consulta: cria o registro, executa no GraphRAG, grava cada
etapa no SQLite e repassa os eventos para quem estiver ouvindo (SSE).

A gravação acontece na tarefa da consulta, não na conexão HTTP: se o
navegador fechar no meio, a consulta termina e fica registrada do mesmo jeito.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config import DEFAULT_COMMUNITY_LEVEL, DEFAULT_RESPONSE_TYPE
from app.db import SessionLocal
from app.models import QueryRun, QueryStep
from app.services import state
from app.services.query_service import to_jsonable

logger = logging.getLogger(__name__)

# Eventos repassados ao vivo mas não gravados (a resposta completa já fica
# gravada no evento "result").
NOT_PERSISTED = {"token"}


class QueryJob:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.queue: asyncio.Queue = asyncio.Queue()
        self.task: asyncio.Task | None = None
        self._seq = 0

    def emit(self, event_type: str, payload: Any) -> None:
        payload = to_jsonable(payload)
        if event_type not in NOT_PERSISTED:
            self._seq += 1
            with SessionLocal() as s:
                s.add(QueryStep(run_id=self.run_id, seq=self._seq, type=event_type, payload=payload))
                s.commit()
        self.queue.put_nowait((event_type, payload))


def start_query(*, question: str, method: str, community_level: int | None = None,
                response_type: str | None = None, dynamic_community_selection: bool = False,
                source: str = "ui", evaluation_run_id: int | None = None,
                question_id: int | None = None, repetition: int | None = None) -> QueryJob:
    """Cria o registro da consulta e dispara a execução em segundo plano."""
    params = {
        "community_level": community_level if community_level is not None else DEFAULT_COMMUNITY_LEVEL,
        "response_type": response_type or DEFAULT_RESPONSE_TYPE,
        "dynamic_community_selection": dynamic_community_selection,
    }
    run_id = str(uuid.uuid4())
    with SessionLocal() as s:
        s.add(QueryRun(
            id=run_id, question=question, method=method, params=params, source=source,
            status="running", index_version_id=state.index_version_id,
            evaluation_run_id=evaluation_run_id, question_id=question_id, repetition=repetition,
        ))
        s.commit()

    job = QueryJob(run_id)
    job.emit("run", {"run_id": run_id, "question": question, "method": method,
                     "params": params, "index_version_id": state.index_version_id})

    async def worker() -> None:
        status, final, error = "completed", None, None
        try:
            final = await state.query_service.run(
                question, method, job.emit,
                community_level=params["community_level"],
                response_type=params["response_type"],
                dynamic_community_selection=dynamic_community_selection,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("Erro na consulta %s", run_id)
            status, error = "error", f"{type(e).__name__}: {e}"
            job.emit("error", {"message": error})
        finally:
            with SessionLocal() as s:
                run = s.get(QueryRun, run_id)
                run.status = status
                run.finished_at = datetime.now(timezone.utc)
                run.error = error
                if final:
                    run.response = final["response"]
                    run.completion_time = final["completion_time"]
                    run.llm_calls = final["llm_calls"]
                    run.prompt_tokens = final["prompt_tokens"]
                    run.output_tokens = final["output_tokens"]
                    run.usage_by_category = final["usage_by_category"]
                s.commit()
            job.queue.put_nowait(None)  # fim do fluxo

    job.task = asyncio.create_task(worker())
    return job


def run_to_dict(run: QueryRun, include_steps: bool = False) -> dict:
    d = {
        "id": run.id,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "question": run.question,
        "method": run.method,
        "params": run.params,
        "source": run.source,
        "status": run.status,
        "index_version_id": run.index_version_id,
        "evaluation_run_id": run.evaluation_run_id,
        "question_id": run.question_id,
        "repetition": run.repetition,
        "response": run.response,
        "error": run.error,
        "completion_time": run.completion_time,
        "llm_calls": run.llm_calls,
        "prompt_tokens": run.prompt_tokens,
        "output_tokens": run.output_tokens,
        "usage_by_category": run.usage_by_category,
    }
    if include_steps:
        d["steps"] = [{"seq": st.seq, "type": st.type, "payload": st.payload,
                       "created_at": st.created_at.isoformat() if st.created_at else None}
                      for st in run.steps]
    return d
