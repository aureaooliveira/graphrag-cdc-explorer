import React, { useMemo, useState } from "react";

interface DriftNode {
  id: number;
  query: string;
  answer?: string | null;
  score?: number | null;
}
interface DriftState {
  nodes: DriftNode[];
  edges: { source: number; target: number }[];
}

const NodeItem: React.FC<{ node: DriftNode; children: Map<number, DriftNode[]>; depth: number; path?: Set<number> }> = ({
  node,
  children,
  depth,
  path = new Set(),
}) => {
  const [open, setOpen] = useState(depth === 0);
  // proteção extra contra ciclos
  const kids = (children.get(node.id) ?? []).filter((k) => !path.has(k.id) && k.id !== node.id);
  const nextPath = new Set(path).add(node.id);
  return (
    <li className="space-y-1">
      <button className="flex w-full gap-2 rounded px-1 py-1 text-left text-xs hover:bg-accent" onClick={() => setOpen((o) => !o)}>
        <span className="shrink-0 font-mono text-muted-foreground">{depth === 0 ? "pergunta" : `nível ${depth}`}</span>
        {node.score !== null && node.score !== undefined && (
          <span className="shrink-0 rounded bg-muted px-1 font-mono">{node.score}</span>
        )}
        <span className="font-medium">{node.query}</span>
      </button>
      {open && node.answer && (
        <div className="ml-4 whitespace-pre-wrap border-l-2 pl-3 text-xs text-muted-foreground">{node.answer}</div>
      )}
      {kids.length > 0 && (
        <ul className="ml-4 space-y-1 border-l pl-2">
          {kids.map((k) => (
            <NodeItem key={k.id} node={k} children={children} depth={depth + 1} path={nextPath} />
          ))}
        </ul>
      )}
    </li>
  );
};

/** Árvore de raciocínio da DRIFT: pergunta inicial e perguntas de acompanhamento. */
export const DriftTree: React.FC<{ state: DriftState }> = ({ state }) => {
  const { roots, children } = useMemo(() => {
    const byId = new Map(state.nodes.map((n) => [n.id, n]));
    const children = new Map<number, DriftNode[]>();
    const hasParent = new Set<number>();
    // O grafo de estado da DRIFT pode ter arestas repetidas e laços (nó
    // apontando para si mesmo): ignoramos ambos para montar uma árvore.
    const seen = new Set<string>();
    for (const e of state.edges) {
      const child = byId.get(e.target);
      const key = `${e.source}->${e.target}`;
      if (!child || e.source === e.target || seen.has(key) || hasParent.has(e.target)) continue;
      seen.add(key);
      hasParent.add(e.target);
      children.set(e.source, [...(children.get(e.source) ?? []), child]);
    }
    return { roots: state.nodes.filter((n) => !hasParent.has(n.id)), children };
  }, [state]);
  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">
        {state.nodes.length} pergunta(s) respondida(s). Clique para ver a resposta parcial de cada uma.
      </p>
      <ul className="max-h-[480px] space-y-1 overflow-auto">
        {roots.map((r) => (
          <NodeItem key={r.id} node={r} children={children} depth={0} />
        ))}
      </ul>
    </div>
  );
};
