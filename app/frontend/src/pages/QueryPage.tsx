import React, { useState } from "react";
import { Play, Square, Info } from "lucide-react";
import { Button } from "../components/ui/button";
import { RunView } from "../components/query/RunView";
import { useQueryStream } from "../hooks/useQueryStream";
import { METHOD_INFO, type QueryMethod } from "../types/query";
import { cn } from "@/lib/utils";

const EXAMPLES = [
  "O que diz o art. 49 do CDC sobre o direito de arrependimento?",
  "Quais são os direitos básicos do consumidor?",
  "Quem pode propor ações coletivas em defesa do consumidor?",
  "O que acontece com o art. 54-E do CDC?",
];

const RESPONSE_TYPES = ["Multiple Paragraphs", "Single Paragraph", "List of 3-7 Points", "Single Sentence"];

export const QueryPage: React.FC<{ onOpenGraph?: () => void }> = ({ onOpenGraph }) => {
  const [question, setQuestion] = useState("");
  const [method, setMethod] = useState<QueryMethod>("local");
  const [communityLevel, setCommunityLevel] = useState(2);
  const [responseType, setResponseType] = useState(RESPONSE_TYPES[0]);
  const [submitted, setSubmitted] = useState<{ method: QueryMethod } | null>(null);
  const { steps, answer, status, error, start, detach } = useQueryStream();
  const running = status === "running";

  const submit = () => {
    if (!question.trim() || running) return;
    setSubmitted({ method });
    start({ question: question.trim(), method, community_level: communityLevel, response_type: responseType });
  };

  return (
    <div className="mx-auto grid h-full max-w-7xl gap-6 overflow-hidden p-4 lg:grid-cols-[380px_1fr]">
      {/* Formulário */}
      <div className="space-y-4 overflow-y-auto pr-1">
        <div>
          <label className="mb-1 block text-xs font-semibold uppercase text-muted-foreground">Pergunta</label>
          <textarea
            className="min-h-[110px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            placeholder="Faça uma pergunta sobre o Código de Defesa do Consumidor..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) submit();
            }}
          />
          <div className="mt-1 flex flex-wrap gap-1">
            {EXAMPLES.map((ex) => (
              <button key={ex} className="rounded border bg-muted px-1.5 py-0.5 text-[11px] hover:bg-accent" onClick={() => setQuestion(ex)}>
                {ex.length > 42 ? ex.slice(0, 42) + "…" : ex}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs font-semibold uppercase text-muted-foreground">Modalidade de busca</label>
          <div className="grid grid-cols-2 gap-1.5">
            {(Object.keys(METHOD_INFO) as QueryMethod[]).map((m) => (
              <button
                key={m}
                onClick={() => setMethod(m)}
                className={cn(
                  "rounded-md border px-2 py-1.5 text-sm",
                  method === m ? "bg-primary text-primary-foreground" : "bg-muted hover:bg-accent",
                )}
              >
                {METHOD_INFO[m].label}
              </button>
            ))}
          </div>
          <p className="mt-2 flex gap-1.5 text-xs text-muted-foreground">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {METHOD_INFO[method].description}
          </p>
        </div>

        {method !== "basic" && (
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase text-muted-foreground">Nível de comunidade</label>
            <select
              className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
              value={communityLevel}
              onChange={(e) => setCommunityLevel(Number(e.target.value))}
            >
              {[0, 1, 2, 3].map((l) => (
                <option key={l} value={l}>
                  Nível {l}
                  {l === 0 ? " (comunidades mais amplas)" : l === 3 ? " (mais específicas)" : ""}
                  {l === 2 ? " · padrão da CLI" : ""}
                </option>
              ))}
            </select>
            {method === "global" && (
              <p className="mt-1 text-xs text-amber-700">
                A busca global faz uma chamada ao modelo por lote de relatórios. Neste índice: nível 0 ≈ 7 chamadas, nível 1 ≈
                30, nível 2 ≈ 68 (centenas de milhares de tokens).
              </p>
            )}
          </div>
        )}

        <div>
          <label className="mb-1 block text-xs font-semibold uppercase text-muted-foreground">Formato da resposta</label>
          <select
            className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm"
            value={responseType}
            onChange={(e) => setResponseType(e.target.value)}
          >
            {RESPONSE_TYPES.map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </div>

        <div className="flex gap-2">
          <Button className="flex-1" onClick={submit} disabled={!question.trim() || running}>
            <Play className="mr-1 h-4 w-4" /> {running ? "Consultando..." : "Consultar"}
          </Button>
          {running && (
            <Button variant="outline" onClick={detach} title="Para de acompanhar; a consulta termina e fica no histórico">
              <Square className="h-4 w-4" />
            </Button>
          )}
        </div>
        <p className="text-[11px] text-muted-foreground">
          Ctrl+Enter para consultar. Toda consulta é gravada no histórico com o contexto, o prompt e as métricas.
        </p>
      </div>

      {/* Linha do tempo */}
      <div className="overflow-y-auto pb-8">
        {submitted ? (
          <RunView method={submitted.method} steps={steps} answer={answer} running={running} error={error} onOpenGraph={onOpenGraph} />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            Faça uma pergunta para ver, passo a passo, o que o GraphRAG recupera e envia ao modelo.
          </div>
        )}
      </div>
    </div>
  );
};
