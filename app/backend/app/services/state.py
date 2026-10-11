"""Estado compartilhado do backend (preenchido na inicialização)."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.query_service import QueryService

query_service: "QueryService | None" = None
index_version_id: int | None = None
