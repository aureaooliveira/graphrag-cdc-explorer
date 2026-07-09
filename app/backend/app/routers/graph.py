from fastapi import APIRouter
from app.schemas.graph import GraphResponse, CommunityResponse, MetaResponse
from app.services.graph_loader import graph_loader

router = APIRouter(prefix="/api", tags=["Graph"])

@router.get("/graph", response_model=GraphResponse)
async def get_graph():
    return graph_loader.graph_data

@router.get("/communities", response_model=CommunityResponse)
async def get_communities():
    return {"communities": graph_loader.communities_data}

@router.get("/meta", response_model=MetaResponse)
async def get_meta():
    return graph_loader.meta_data
