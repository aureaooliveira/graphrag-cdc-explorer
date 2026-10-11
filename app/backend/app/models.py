"""Tabelas do SQLite.

index_versions   identificação de cada índice do GraphRAG usado nas consultas
query_runs       cada consulta (pergunta, modalidade, resposta, métricas)
query_steps      passo a passo de cada consulta (contexto, map/reduce, prompt...)
questions        conjunto de perguntas de teste da avaliação
evaluation_runs  cada rodada de avaliação (modalidades x repetições)
assessments      notas atribuídas manualmente às respostas
"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IndexVersion(Base):
    __tablename__ = "index_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    registered_at: Mapped[datetime] = mapped_column(default=utcnow)
    indexed_at: Mapped[datetime | None]
    graphrag_version: Mapped[str | None] = mapped_column(String(32))
    settings_sha256: Mapped[str | None] = mapped_column(String(64))
    prompts_sha256: Mapped[str | None] = mapped_column(String(64))
    models: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    stats: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    label: Mapped[str | None] = mapped_column(String(64))  # ex.: "v0.1.0"


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str | None] = mapped_column(String(32), unique=True)  # ex.: "Q07"
    text: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(64))
    expected_articles: Mapped[list[str] | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    methods: Mapped[list[str]] = mapped_column(JSON)
    repetitions: Mapped[int] = mapped_column(Integer, default=1)
    index_version_id: Mapped[int | None] = mapped_column(ForeignKey("index_versions.id"))
    notes: Mapped[str | None] = mapped_column(Text)


class QueryRun(Base):
    __tablename__ = "query_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # uuid
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    finished_at: Mapped[datetime | None]
    question: Mapped[str] = mapped_column(Text)
    method: Mapped[str] = mapped_column(String(16), index=True)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(16), default="ui", index=True)  # ui | evaluation | api
    status: Mapped[str] = mapped_column(String(16), default="running")  # running | completed | error

    index_version_id: Mapped[int | None] = mapped_column(ForeignKey("index_versions.id"))
    evaluation_run_id: Mapped[int | None] = mapped_column(ForeignKey("evaluation_runs.id"), index=True)
    question_id: Mapped[int | None] = mapped_column(ForeignKey("questions.id"))
    repetition: Mapped[int | None] = mapped_column(Integer)

    response: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    completion_time: Mapped[float | None] = mapped_column(Float)
    llm_calls: Mapped[int | None] = mapped_column(Integer)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    usage_by_category: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    steps: Mapped[list["QueryStep"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="QueryStep.seq"
    )
    assessments: Mapped[list["Assessment"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class QueryStep(Base):
    __tablename__ = "query_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("query_runs.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[Any] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    run: Mapped[QueryRun] = relationship(back_populates="steps")


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("query_runs.id", ondelete="CASCADE"), index=True)
    criterion: Mapped[str] = mapped_column(String(64))  # ex.: correcao, completude, fundamentacao
    score: Mapped[float] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    run: Mapped[QueryRun] = relationship(back_populates="assessments")
