import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import GRAPHRAG_ROOT
from app.db import init_db
from app.routers import graph, index, query, runs
from app.services import state
from app.services.query_service import QueryService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    state.query_service = QueryService(GRAPHRAG_ROOT)
    await index.load_index()
    yield


app = FastAPI(
    title="GraphRAG CDC API",
    description="Grafo de conhecimento do CDC e consultas ao GraphRAG com rastreamento das etapas.",
    version="2.0.0",
    lifespan=lifespan,
)

# Em desenvolvimento o frontend acessa a API pelo proxy do Vite (/api), então
# o CORS só é necessário para acesso direto (ex.: scripts ou outra origem).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graph.router)
app.include_router(query.router)
app.include_router(runs.router)
app.include_router(index.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "query_ready": bool(state.query_service and state.query_service.ready)}


@app.get("/")
async def root():
    return {"message": "GraphRAG CDC API. Documentação em /docs."}
