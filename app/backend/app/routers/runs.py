"""Histórico de consultas gravadas no SQLite."""
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import QueryRun
from app.services.run_service import run_to_dict

router = APIRouter(prefix="/api/runs", tags=["Runs"])


@router.get("")
def list_runs(
    method: str | None = None,
    source: str | None = None,
    status: str | None = None,
    evaluation_run_id: int | None = None,
    q: str | None = Query(default=None, description="Trecho da pergunta"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    with SessionLocal() as s:
        stmt = select(QueryRun)
        if method:
            stmt = stmt.where(QueryRun.method == method)
        if source:
            stmt = stmt.where(QueryRun.source == source)
        if status:
            stmt = stmt.where(QueryRun.status == status)
        if evaluation_run_id is not None:
            stmt = stmt.where(QueryRun.evaluation_run_id == evaluation_run_id)
        if q:
            stmt = stmt.where(QueryRun.question.ilike(f"%{q}%"))
        total = s.scalar(select(func.count()).select_from(stmt.subquery()))
        runs = s.scalars(stmt.order_by(QueryRun.created_at.desc()).limit(limit).offset(offset)).all()
        return {"total": total, "items": [run_to_dict(r) for r in runs]}


@router.get("/{run_id}")
def get_run(run_id: str):
    with SessionLocal() as s:
        run = s.get(QueryRun, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Consulta não encontrada")
        return run_to_dict(run, include_steps=True)


@router.delete("/{run_id}", status_code=204)
def delete_run(run_id: str):
    with SessionLocal() as s:
        run = s.get(QueryRun, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Consulta não encontrada")
        s.delete(run)
        s.commit()
