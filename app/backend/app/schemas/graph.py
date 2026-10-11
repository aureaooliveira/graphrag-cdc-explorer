from pydantic import BaseModel
from typing import List, Optional

class CommunityLevel(BaseModel):
    level: int
    community_id: str
    summary: str

class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    description: str
    degree: int
    communities: List[CommunityLevel]
    text_units: List[str] = []  # ids curtos dos trechos de onde a entidade foi extraída

class GraphEdge(BaseModel):
    source: str
    target: str
    description: str
    weight: float

class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]

class CommunityInfo(BaseModel):
    id: str
    level: int
    title: str
    summary: str
    full_content: str
    entity_count: int

class CommunityResponse(BaseModel):
    communities: List[CommunityInfo]

class MetaResponse(BaseModel):
    total_nodes: int
    total_edges: int
    entity_types: List[str]
    community_levels: List[int]
