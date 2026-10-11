import os
from typing import Any, Dict, List

import pandas as pd

from app.config import OUTPUT_DIR

DATA_DIR = str(OUTPUT_DIR)

class GraphLoader:
    def __init__(self):
        self.graph_data: Dict[str, Any] = {"nodes": [], "edges": []}
        self.communities_data: List[Dict[str, Any]] = []
        self.meta_data: Dict[str, Any] = {}
        self.loaded = False

    def reload(self):
        """Descarta os dados em memória e lê o índice de novo."""
        self.graph_data = {"nodes": [], "edges": []}
        self.communities_data = []
        self.meta_data = {}
        self.loaded = False
        self.load_data()

    def load_data(self):
        if self.loaded:
            return

        print("Loading parquet files from", DATA_DIR)
        
        try:
            entities_df = pd.read_parquet(os.path.join(DATA_DIR, "entities.parquet"))
            relationships_df = pd.read_parquet(os.path.join(DATA_DIR, "relationships.parquet"))
            communities_df = pd.read_parquet(os.path.join(DATA_DIR, "communities.parquet"))
            reports_df = pd.read_parquet(os.path.join(DATA_DIR, "community_reports.parquet"))
            text_units_df = pd.read_parquet(
                os.path.join(DATA_DIR, "text_units.parquet"), columns=["id", "human_readable_id"]
            )
        except Exception as e:
            print(f"Error loading parquets: {e}")
            # If files don't exist yet, we just initialize empty
            return

        # Build community dictionary: (community, level) -> report data
        reports_dict = {}
        for _, row in reports_df.iterrows():
            key = (row["community"], row["level"])
            reports_dict[key] = {
                "title": row.get("title", ""),
                "summary": row.get("summary", ""),
                "full_content": row.get("full_content", "")
            }

        # Build community info response and entity to communities mapping
        entity_to_communities = {} # entity_id -> list of CommunityLevel
        communities_info_list = []
        community_levels = set()
        
        for _, row in communities_df.iterrows():
            comm_id = str(row["community"])
            level = int(row["level"])
            community_levels.add(level)
            
            report = reports_dict.get((row["community"], level), {})
            
            # For the /api/communities endpoint
            entity_ids = row.get("entity_ids", [])
            if isinstance(entity_ids, (list, tuple)):
                entity_count = len(entity_ids)
            else:
                entity_count = len(list(entity_ids)) if entity_ids is not None else 0
                
            communities_info_list.append({
                "id": comm_id,
                "level": level,
                "title": report.get("title") or row.get("title", ""),
                "summary": report.get("summary", ""),
                "full_content": report.get("full_content", ""),
                "entity_count": entity_count
            })
            
            # Map entities to this community
            if entity_ids is not None:
                for ent_id in entity_ids:
                    if ent_id not in entity_to_communities:
                        entity_to_communities[ent_id] = []
                    
                    entity_to_communities[ent_id].append({
                        "level": level,
                        "community_id": comm_id,
                        "summary": report.get("summary", "")
                    })

        self.communities_data = communities_info_list

        # Mapa uuid do trecho -> id curto (o mesmo exibido no contexto das buscas,
        # ex.: "Sources (49)"), para ligar trechos recuperados às entidades.
        text_unit_hid = {
            str(row["id"]): str(row["human_readable_id"]) for _, row in text_units_df.iterrows()
        }

        # Process Entities (Nodes)
        nodes = []
        entity_types = set()
        title_to_id = {}
        for _, row in entities_df.iterrows():
            ent_id = str(row["id"])
            ent_title = str(row.get("title", ent_id))
            ent_type = str(row.get("type", "unknown"))
            entity_types.add(ent_type)
            title_to_id[ent_title] = ent_id
            
            nodes.append({
                "id": ent_id,
                "label": ent_title,
                "type": ent_type,
                "description": str(row.get("description", "")),
                "degree": int(row.get("degree", 0)),
                "communities": entity_to_communities.get(ent_id, []),
                "text_units": [
                    text_unit_hid[str(tu)]
                    for tu in (row.get("text_unit_ids") if row.get("text_unit_ids") is not None else [])
                    if str(tu) in text_unit_hid
                ],
            })
            
        self.graph_data["nodes"] = nodes

        # Process Relationships (Edges)
        edges = []
        for _, row in relationships_df.iterrows():
            src_title = str(row["source"])
            tgt_title = str(row["target"])
            
            # Map title back to id, fallback to title if not found
            src_id = title_to_id.get(src_title, src_title)
            tgt_id = title_to_id.get(tgt_title, tgt_title)
            
            edges.append({
                "source": src_id,
                "target": tgt_id,
                "description": str(row.get("description", "")),
                "weight": float(row.get("weight", 1.0))
            })
            
        self.graph_data["edges"] = edges

        # Process Meta
        self.meta_data = {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_types": sorted(list(entity_types)),
            "community_levels": sorted(list(community_levels))
        }

        self.loaded = True

graph_loader = GraphLoader()
