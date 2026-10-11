import React, { useMemo } from "react";
import { AlertCircle } from "lucide-react";
import type { QueryMethod, QueryStep } from "../../types/query";
import { Section, type SectionState } from "./Section";
import { ContextView } from "./ContextView";
import { PromptView } from "./PromptView";
import { MapView } from "./MapView";
import { DriftTree } from "./DriftTree";
import { Answer } from "./Answer";
import { ContextGraph } from "./ContextGraph";
import { useGraph } from "../../context/GraphDataContext";
import { computeContextHighlight } from "@/lib/highlight";

interface RunViewProps {
  method: QueryMethod;
  steps: QueryStep[];
  answer: string;
  running: boolean;
  error?: string | null;
  /** chamado ao pedir "Ver no grafo completo" (a tela troca para a aba Grafo) */
  onOpenGraph?: () => void;
}

const fmt = (n?: number | null) => (n ?? 0).toLocaleString("pt-BR");

/** Linha do tempo das etapas de uma consulta (ao vivo ou do histórico). */
export const RunView: React.FC<RunViewProps> = ({ method, steps, answer, running, error, onOpenGraph }) => {
  const { graphData, setHighlight } = useGraph();
  const find = (type: string) => steps.find((s) => s.type === type)?.payload;
  const all = (type: string) => steps.filter((s) => s.type === type).map((s) => s.payload);

  const context = find("context");
  const contexts = all("context");
  const prompt = find("prompt");
  const mapStart = find("map_start");
  const mapEnd = find("map_end");
  const reduceStart = find("reduce_start");
  const result = find("result");

  // Destaque no grafo: calculado quando há contexto (local, basic, drift) ou,
  // na global, quando a consulta termina (usa as citações dos pontos e da resposta).
  const highlight = useMemo(() => {
    if (!graphData) return null;
    if (method === "global" && !result) return null;
    if (method !== "global" && !context) return null;
    return computeContextHighlight(method, steps, answer || result?.response || "", graphData);
  }, [graphData, method, steps, answer, result, context]);

  // Estado de cada etapa: concluída se o evento chegou; "em andamento" se é a
  // primeira etapa ainda sem evento enquanto a consulta roda.
  const sections: { title: string; done: boolean; subtitle?: React.ReactNode; body: React.ReactNode }[] = [];

  if (method === "global") {
    sections.push({
      title: "Map: pontos-chave de cada lote de relatórios",
      done: !!mapEnd,
      subtitle: mapStart ? `${mapStart.batches} lote(s) enviados ao modelo em paralelo` : undefined,
      body: mapEnd && <MapView batches={mapEnd} contexts={mapStart?.contexts} />,
    });
    sections.push({
      title: "Relatórios de comunidade considerados",
      done: !!context,
      subtitle: context?.records?.reports ? `${context.records.reports.length} relatório(s)` : undefined,
      body: context && <ContextView records={context.records} />,
    });
  } else {
    sections.push({
      title: method === "drift" ? "Contexto da busca inicial" : "Recuperação de contexto",
      done: !!context,
      subtitle: context?.records
        ? Object.entries(context.records)
            .filter(([, v]) => Array.isArray(v) && (v as unknown[]).length)
            .map(([k, v]) => `${(v as unknown[]).length} ${k}`)
            .join(" · ")
        : undefined,
      body: context && (
        <div className="space-y-4">
          {contexts.length > 1 && (
            <p className="text-xs text-muted-foreground">
              {contexts.length} buscas locais foram feitas; abaixo, a primeira.
            </p>
          )}
          <ContextView records={context.records} contextText={context.context_text} />
        </div>
      ),
    });
  }

  sections.push({
    title: "Subgrafo usado como contexto",
    done: !!highlight || (!!result && !highlight),
    subtitle: highlight
      ? `${highlight.nodeIds.size} entidade(s) · ${highlight.linkCount} relação(ões)`
      : result
        ? "Nenhuma entidade do grafo associada a este contexto"
        : undefined,
    body: highlight && graphData && (
      <ContextGraph
        graph={graphData}
        highlight={highlight}
        onOpenFullGraph={() => {
          setHighlight(highlight);
          onOpenGraph?.();
        }}
      />
    ),
  });

  if (method === "drift") {
    sections.push({
      title: "Raciocínio DRIFT: perguntas de acompanhamento",
      done: !!reduceStart,
      subtitle: reduceStart?.nodes ? `${reduceStart.nodes.length} pergunta(s)` : undefined,
      body: reduceStart?.nodes && <DriftTree state={reduceStart} />,
    });
  } else {
    sections.push({
      title: method === "global" ? "Prompt da síntese (reduce)" : "Prompt enviado ao modelo",
      done: !!prompt,
      subtitle: prompt ? `~${fmt(Math.round(prompt.system.length / 4))} tokens de contexto e instruções` : undefined,
      body: prompt && <PromptView system={prompt.system} user={prompt.user} note={prompt.note} />,
    });
  }

  sections.push({
    title: "Resposta",
    done: !!result,
    body: <Answer text={answer || result?.response || ""} streaming={running && !result} />,
  });

  sections.push({
    title: "Métricas",
    done: !!result,
    subtitle: result
      ? `${fmt(result.llm_calls)} chamada(s) ao modelo · ${fmt(result.prompt_tokens)} tokens de entrada · ${fmt(result.output_tokens)} de saída · ${result.completion_time?.toFixed(1)} s`
      : undefined,
    body: result && (
      <table className="text-xs">
        <thead>
          <tr className="text-left text-muted-foreground">
            <th className="pr-6">Etapa</th>
            <th className="pr-6">Chamadas</th>
            <th className="pr-6">Tokens de entrada</th>
            <th>Tokens de saída</th>
          </tr>
        </thead>
        <tbody>
          {Object.keys(result.usage_by_category?.llm_calls ?? {}).map((k) => (
            <tr key={k}>
              <td className="pr-6 font-mono">{k}</td>
              <td className="pr-6">{fmt(result.usage_by_category.llm_calls[k])}</td>
              <td className="pr-6">{fmt(result.usage_by_category.prompt_tokens?.[k])}</td>
              <td>{fmt(result.usage_by_category.output_tokens?.[k])}</td>
            </tr>
          ))}
        </tbody>
      </table>
    ),
  });

  const firstPending = sections.findIndex((s) => !s.done);
  const state = (i: number): SectionState =>
    sections[i].done ? "done" : running && i === firstPending ? "running" : "pending";

  // A resposta aparece enquanto é gerada (tokens), antes do evento "result".
  const answerIdx = sections.findIndex((s) => s.title === "Resposta");

  return (
    <div className="space-y-2">
      {error && (
        <div className="flex gap-2 rounded-lg border border-destructive bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}
      {sections.map((s, i) => (
        <Section
          key={`${s.title}-${s.done}`}
          step={i + 1}
          title={s.title}
          subtitle={s.subtitle}
          state={i === answerIdx && answer && !s.done ? "running" : state(i)}
          defaultOpen={i === answerIdx}
        >
          {s.body}
        </Section>
      ))}
    </div>
  );
};
