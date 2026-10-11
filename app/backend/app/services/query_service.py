"""Execução das consultas do GraphRAG com rastreamento das etapas.

Usa a mesma biblioteca (graphrag==3.1.0), o mesmo settings.yaml e o mesmo
índice (data/output) da CLI `graphrag query`, montando os motores de busca do
mesmo jeito que graphrag.api.query. A diferença é que cada etapa é emitida
como um evento, para ser exibida ao vivo e gravada no banco:

  context      contexto recuperado (tabelas de entidades, relações, relatórios,
               trechos) + texto exato inserido no prompt          [local, basic]
  prompt       prompt de sistema final e pergunta enviados ao modelo
  token        pedaços da resposta conforme são gerados (não gravados)
  map_start    lotes de relatórios de comunidade enviados à etapa map  [global]
  map_end      respostas parciais (pontos-chave com nota) de cada lote [global]
  reduce_start estado antes da síntese: pontos-chave (global) ou
               árvore de perguntas de acompanhamento (drift)
  reduce_end   resposta da síntese
  result       resposta final e métricas (chamadas ao LLM, tokens, tempo)

Observação: as funções usadas aqui (factory, indexer_adapters, DataReader)
são internas do GraphRAG; por isso a versão está fixada em 3.1.0.
"""
from __future__ import annotations

import logging
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from graphrag.callbacks.query_callbacks import QueryCallbacks
from graphrag.config.embeddings import (
    community_full_content_embedding,
    entity_description_embedding,
    text_unit_text_embedding,
)
from graphrag.config.load_config import load_config
from graphrag.data_model.data_reader import DataReader
from graphrag.query.factory import (
    get_basic_search_engine,
    get_drift_search_engine,
    get_global_search_engine,
    get_local_search_engine,
)
from graphrag.query.indexer_adapters import (
    read_indexer_communities,
    read_indexer_covariates,
    read_indexer_entities,
    read_indexer_relationships,
    read_indexer_report_embeddings,
    read_indexer_reports,
    read_indexer_text_units,
)
from graphrag.utils.api import get_embedding_store
from graphrag_storage import create_storage
from graphrag_storage.tables.table_provider_factory import create_table_provider

logger = logging.getLogger(__name__)

Emit = Callable[[str, Any], None]
METHODS = ("local", "global", "drift", "basic")


# ---------------------------------------------------------------------------
# Serialização (DataFrames, numpy, objetos do GraphRAG -> JSON)
# ---------------------------------------------------------------------------
def to_jsonable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        return None if math.isnan(obj) or math.isinf(obj) else obj
    if isinstance(obj, pd.DataFrame):
        return [to_jsonable(r) for r in obj.to_dict(orient="records")]
    if isinstance(obj, pd.Series):
        return to_jsonable(obj.to_list())
    if isinstance(obj, np.generic):
        return to_jsonable(obj.item())
    if isinstance(obj, np.ndarray):
        return [to_jsonable(x) for x in obj.tolist()]
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(x) for x in obj]
    if hasattr(obj, "model_dump"):
        return to_jsonable(obj.model_dump())
    if hasattr(obj, "__dict__"):
        return to_jsonable({k: v for k, v in vars(obj).items() if not k.startswith("_")})
    return str(obj)


# ---------------------------------------------------------------------------
# Callbacks do GraphRAG -> eventos
# ---------------------------------------------------------------------------
class TraceCallbacks(QueryCallbacks):
    def __init__(self, emit: Emit, multi_context: bool = False) -> None:
        super().__init__()
        self.emit = emit
        self.context_emitted = False
        # Na DRIFT, cada pergunta de acompanhamento roda uma busca local com
        # contexto próprio: emitimos todos, numerados.
        self.multi_context = multi_context
        self.context_count = 0

    def on_context(self, context: Any) -> None:
        if self.multi_context:
            self.context_count += 1
            self.emit("context", {"records": to_jsonable(context), "index": self.context_count})
            return
        # Na busca local/basic o contexto já foi emitido antes da geração
        # (ver _trace_context_builder); aqui só cobre os demais casos (global).
        if not self.context_emitted:
            self.emit("context", {"records": to_jsonable(context)})
            self.context_emitted = True

    def on_map_response_start(self, map_response_contexts: list[str]) -> None:
        self.emit("map_start", {
            "batches": len(map_response_contexts),
            "contexts": list(map_response_contexts),
        })

    def on_map_response_end(self, map_response_outputs: list) -> None:
        self.emit("map_end", [
            {
                "batch": i,
                "points": to_jsonable(o.response),
                "llm_calls": o.llm_calls,
                "prompt_tokens": o.prompt_tokens,
                "output_tokens": o.output_tokens,
                "completion_time": o.completion_time,
            }
            for i, o in enumerate(map_response_outputs)
        ])

    def on_reduce_response_start(self, reduce_response_context: Any) -> None:
        self.emit("reduce_start", to_jsonable(reduce_response_context))

    def on_reduce_response_end(self, reduce_response_output: str) -> None:
        self.emit("reduce_end", {"response": to_jsonable(reduce_response_output)})

    def on_llm_new_token(self, token: Any) -> None:
        if token:
            self.emit("token", token)


class _AwaitedStreamModel:
    """Contorna um bug do GraphRAG 3.1.0 (também presente na 3.2.0).

    BasicSearch.search() chama `self.model.completion_async(..., stream=True)`
    SEM `await` e itera o resultado com `async for`. Como completion_async é
    uma corrotina, a iteração falha, o erro é capturado internamente e a busca
    basic devolve resposta vazia. (A CLI não é afetada porque usa
    stream_search, que tem o `await`.) Este invólucro faz a chamada sem
    `await` devolver um iterador assíncrono, como o código espera.
    """

    def __init__(self, model: Any) -> None:
        self._model = model

    def __getattr__(self, name: str) -> Any:
        return getattr(self._model, name)

    def completion_async(self, **kwargs: Any):
        if not kwargs.get("stream"):
            return self._model.completion_async(**kwargs)

        async def _stream():
            response = await self._model.completion_async(**kwargs)
            async for chunk in response:
                yield chunk

        return _stream()


def _trace_context_builder(engine: Any, cb: TraceCallbacks, system_prompt: str,
                           response_type: str, question: str) -> None:
    """Emite o contexto e o prompt final ASSIM QUE o contexto é montado.

    Nas buscas local e basic o GraphRAG só chama on_context depois de gerar a
    resposta. Envolvemos o build_context desta instância do motor (criada para
    esta consulta) para mostrar o contexto antes da geração e reconstruir o
    prompt exatamente como o GraphRAG o formata (mesmo template e argumentos).
    """
    original = engine.context_builder.build_context

    def traced(*args, **kwargs):
        result = original(*args, **kwargs)
        cb.emit("context", {
            "records": to_jsonable(result.context_records),
            "context_text": result.context_chunks,
        })
        cb.context_emitted = True
        cb.emit("prompt", {
            "system": system_prompt.format(
                context_data=result.context_chunks, response_type=response_type
            ),
            "user": question,
        })
        return result

    engine.context_builder.build_context = traced


# ---------------------------------------------------------------------------
# Serviço
# ---------------------------------------------------------------------------
class QueryService:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.config = None
        self.tables: dict[str, pd.DataFrame | None] = {}
        self.prompts: dict[str, str] = {}
        self.ready = False
        self.load_error: str | None = None

    def _read_prompt(self, rel: str | None, name: str) -> str:
        """Lê o prompt configurado. Ao contrário do GraphRAG, falha se não achar
        o arquivo (o GraphRAG cai silenciosamente no prompt padrão em inglês)."""
        if not rel:
            raise ValueError(f"Prompt '{name}' não configurado no settings.yaml")
        path = Path(rel)
        if not path.is_absolute():
            path = self.root / path
        if not path.exists():
            raise FileNotFoundError(f"Prompt '{name}' não encontrado: {path}")
        return path.read_text(encoding="utf-8")

    async def load(self) -> None:
        """Carrega configuração, tabelas do índice e prompts (na inicialização
        e ao recarregar o índice)."""
        try:
            config = load_config(root_dir=self.root)
            storage = create_storage(config.output_storage)
            provider = create_table_provider(config.table_provider, storage=storage)
            reader = DataReader(provider)
            tables: dict[str, pd.DataFrame | None] = {}
            for name in ("entities", "communities", "community_reports",
                         "text_units", "relationships"):
                tables[name] = await getattr(reader, name)()
            tables["covariates"] = (
                await reader.covariates() if await provider.has("covariates") else None
            )
            self.prompts = {
                "local": self._read_prompt(config.local_search.prompt, "local_search"),
                "global_map": self._read_prompt(config.global_search.map_prompt, "global_map"),
                "global_reduce": self._read_prompt(config.global_search.reduce_prompt, "global_reduce"),
                "global_knowledge": self._read_prompt(config.global_search.knowledge_prompt, "global_knowledge"),
                "drift": self._read_prompt(config.drift_search.prompt, "drift"),
                "drift_reduce": self._read_prompt(config.drift_search.reduce_prompt, "drift_reduce"),
                "basic": self._read_prompt(config.basic_search.prompt, "basic"),
            }
            self.config, self.tables = config, tables
            self.ready, self.load_error = True, None
            logger.info("Índice carregado: %s entidades", len(tables["entities"]))
        except Exception as e:  # noqa: BLE001
            self.ready, self.load_error = False, f"{type(e).__name__}: {e}"
            logger.exception("Falha ao carregar o índice para consultas")

    def stats(self) -> dict:
        t = self.tables
        return {name: (len(df) if df is not None else 0) for name, df in t.items()}

    async def run(self, question: str, method: str, emit: Emit, *,
                  community_level: int, response_type: str,
                  dynamic_community_selection: bool = False) -> dict:
        """Executa a consulta emitindo as etapas. Retorna o resultado final."""
        if not self.ready:
            raise RuntimeError(f"Índice não carregado: {self.load_error}")
        if method not in METHODS:
            raise ValueError(f"Modalidade inválida: {method}")

        config, t = self.config, self.tables
        cb = TraceCallbacks(emit, multi_context=(method == "drift"))

        if method == "local":
            engine = get_local_search_engine(
                config=config,
                reports=read_indexer_reports(t["community_reports"], t["communities"], community_level),
                text_units=read_indexer_text_units(t["text_units"]),
                entities=read_indexer_entities(t["entities"], t["communities"], community_level),
                relationships=read_indexer_relationships(t["relationships"]),
                covariates={"claims": read_indexer_covariates(t["covariates"])
                            if t["covariates"] is not None else []},
                description_embedding_store=get_embedding_store(
                    config.vector_store, entity_description_embedding),
                response_type=response_type,
                system_prompt=self.prompts["local"],
                callbacks=[cb],
            )
            _trace_context_builder(engine, cb, self.prompts["local"], response_type, question)

        elif method == "basic":
            engine = get_basic_search_engine(
                config=config,
                text_units=read_indexer_text_units(t["text_units"]),
                text_unit_embeddings=get_embedding_store(config.vector_store, text_unit_text_embedding),
                response_type=response_type,
                system_prompt=self.prompts["basic"],
                callbacks=[cb],
            )
            engine.model = _AwaitedStreamModel(engine.model)
            _trace_context_builder(engine, cb, self.prompts["basic"], response_type, question)

        elif method == "global":
            engine = get_global_search_engine(
                config,
                reports=read_indexer_reports(
                    t["community_reports"], t["communities"], community_level=community_level,
                    dynamic_community_selection=dynamic_community_selection),
                entities=read_indexer_entities(t["entities"], t["communities"], community_level=community_level),
                communities=read_indexer_communities(t["communities"], t["community_reports"]),
                response_type=response_type,
                dynamic_community_selection=dynamic_community_selection,
                map_system_prompt=self.prompts["global_map"],
                reduce_system_prompt=self.prompts["global_reduce"],
                general_knowledge_inclusion_prompt=self.prompts["global_knowledge"],
                callbacks=[cb],
            )

        else:  # drift
            reports = read_indexer_reports(t["community_reports"], t["communities"], community_level)
            read_indexer_report_embeddings(
                reports, get_embedding_store(config.vector_store, community_full_content_embedding))
            engine = get_drift_search_engine(
                config=config,
                reports=reports,
                text_units=read_indexer_text_units(t["text_units"]),
                entities=read_indexer_entities(t["entities"], t["communities"], community_level),
                relationships=read_indexer_relationships(t["relationships"]),
                description_embedding_store=get_embedding_store(
                    config.vector_store, entity_description_embedding),
                local_system_prompt=self.prompts["drift"],
                reduce_system_prompt=self.prompts["drift_reduce"],
                response_type=response_type,
                callbacks=[cb],
            )

        result = await engine.search(question)

        if method == "global":
            emit("prompt", {
                "system": self.prompts["global_reduce"].format(
                    report_data=result.reduce_context_text,
                    response_type=response_type,
                    max_length=engine.reduce_max_length,
                ),
                "user": question,
                "note": "Prompt da etapa reduce. Os prompts da etapa map são o template "
                        "global_search_map_system_prompt.txt aplicado a cada lote (ver map_start).",
            })

        response = to_jsonable(result.response)
        if isinstance(response, (dict, list)):
            response = str(response)
        if not response:
            # O GraphRAG captura exceções na geração e devolve resposta vazia.
            raise RuntimeError("O GraphRAG retornou resposta vazia (erro na chamada ao modelo; "
                               "veja os logs do backend).")

        final = {
            "response": response,
            "completion_time": result.completion_time,
            "llm_calls": result.llm_calls,
            "prompt_tokens": result.prompt_tokens,
            "output_tokens": result.output_tokens,
            "usage_by_category": {
                "llm_calls": to_jsonable(result.llm_calls_categories),
                "prompt_tokens": to_jsonable(result.prompt_tokens_categories),
                "output_tokens": to_jsonable(result.output_tokens_categories),
            },
        }
        emit("result", final)
        return final

