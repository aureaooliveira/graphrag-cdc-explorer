import { useState, useEffect } from "react";
import { GraphData, CommunityInfo, MetaData } from "../types/graph";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export function useGraphData() {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [communities, setCommunities] = useState<CommunityInfo[]>([]);
  const [meta, setMeta] = useState<MetaData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        const [graphRes, commRes, metaRes] = await Promise.all([
          fetch(`${API_URL}/api/graph`),
          fetch(`${API_URL}/api/communities`),
          fetch(`${API_URL}/api/meta`)
        ]);

        if (!graphRes.ok || !commRes.ok || !metaRes.ok) {
          throw new Error("Failed to fetch data from API.");
        }

        const graphJson = await graphRes.json();
        const commJson = await commRes.json();
        const metaJson = await metaRes.json();

        setGraphData(graphJson);
        setCommunities(commJson.communities);
        setMeta(metaJson);
      } catch (err: any) {
        setError(err.message || "Unknown error occurred.");
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, []);

  return { graphData, communities, meta, loading, error };
}
