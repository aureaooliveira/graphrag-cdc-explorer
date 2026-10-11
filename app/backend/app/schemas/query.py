from typing import Literal

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    method: Literal["local", "global", "drift", "basic"] = "local"
    community_level: int | None = Field(default=None, ge=0, description="Padrão: 2 (igual à CLI)")
    response_type: str | None = Field(default=None, description="Padrão: Multiple Paragraphs")
    dynamic_community_selection: bool = False
    source: Literal["ui", "evaluation", "api"] = "ui"
    evaluation_run_id: int | None = None
    question_id: int | None = None
    repetition: int | None = None
