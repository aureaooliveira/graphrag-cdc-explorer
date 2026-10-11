import React from "react";

/** Renderização simples de markdown (títulos, listas, negrito) da resposta. */
function inline(text: string, key: string): React.ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? (
      <strong key={`${key}-${i}`}>{part.slice(2, -2)}</strong>
    ) : (
      <React.Fragment key={`${key}-${i}`}>{part}</React.Fragment>
    ),
  );
}

export const Answer: React.FC<{ text: string; streaming?: boolean }> = ({ text, streaming }) => {
  const lines = text.split("\n");
  return (
    <div className="space-y-2 text-sm leading-relaxed">
      {lines.map((line, i) => {
        const key = String(i);
        if (/^#{1,6}\s/.test(line)) {
          return (
            <p key={key} className="pt-2 font-semibold">
              {inline(line.replace(/^#{1,6}\s/, ""), key)}
            </p>
          );
        }
        if (/^\s*[-*]\s/.test(line)) {
          return (
            <p key={key} className="pl-4 -indent-3">
              • {inline(line.replace(/^\s*[-*]\s/, ""), key)}
            </p>
          );
        }
        if (!line.trim()) return null;
        return <p key={key}>{inline(line, key)}</p>;
      })}
      {streaming && <span className="inline-block h-4 w-1.5 animate-pulse bg-primary align-middle" />}
    </div>
  );
};
