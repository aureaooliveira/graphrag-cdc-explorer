from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.routers import graph
from app.services.graph_loader import graph_loader

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load data on startup
    graph_loader.load_data()
    yield
    # Cleanup on shutdown (if needed)
    pass

app = FastAPI(
    title="GraphRAG Visualizer API",
    description="API for accessing GraphRAG knowledge graph data.",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graph.router)

@app.get("/")
async def root():
    return {"message": "Welcome to the GraphRAG API. Visit /docs for the documentation."}
