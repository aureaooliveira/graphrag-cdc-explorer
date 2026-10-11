import { useCallback, useRef, useState } from "react";
import { streamQuery } from "../lib/api";
import type { QueryRequest, QueryStep } from "../types/query";

export type StreamStatus = "idle" | "running" | "completed" | "error";

/** Estado de uma consulta em andamento: etapas, resposta parcial e status. */
export function useQueryStream() {
  const [steps, setSteps] = useState<QueryStep[]>([]);
  const [answer, setAnswer] = useState("");
  const [status, setStatus] = useState<StreamStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const start = useCallback(async (req: QueryRequest) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setSteps([]);
    setAnswer("");
    setError(null);
    setRunId(null);
    setStatus("running");
    let failed = false;
    try {
      await streamQuery(
        req,
        (type, payload) => {
          if (type === "token") {
            setAnswer((a) => a + payload);
            return;
          }
          if (type === "run") setRunId(payload.run_id);
          if (type === "result") setAnswer(payload.response);
          if (type === "error") {
            failed = true;
            setError(payload.message);
          }
          if (type === "done") return;
          setSteps((s) => [...s, { type, payload }]);
        },
        controller.signal,
      );
      setStatus(failed ? "error" : "completed");
    } catch (e: any) {
      if (e?.name === "AbortError") return;
      setError(e?.message ?? String(e));
      setStatus("error");
    }
  }, []);

  /** Para de acompanhar no navegador (a consulta termina e é gravada no backend). */
  const detach = useCallback(() => {
    abortRef.current?.abort();
    setStatus("idle");
  }, []);

  return { steps, answer, status, error, runId, start, detach };
}
