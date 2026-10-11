import React, { useState } from "react";
import { Copy, Check } from "lucide-react";
import { Button } from "../ui/button";

interface PromptViewProps {
  system: string;
  user: string;
  note?: string;
}

/** Mostra o prompt de sistema e a mensagem do usuário exatamente como enviados. */
export const PromptView: React.FC<PromptViewProps> = ({ system, user, note }) => {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(`[system]\n${system}\n\n[user]\n${user}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div className="space-y-3">
      {note && <p className="text-xs text-muted-foreground">{note}</p>}
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase text-muted-foreground">
          Mensagem de sistema · {system.length.toLocaleString("pt-BR")} caracteres (~
          {Math.round(system.length / 4).toLocaleString("pt-BR")} tokens)
        </span>
        <Button variant="outline" size="sm" onClick={copy}>
          {copied ? <Check className="mr-1 h-3 w-3" /> : <Copy className="mr-1 h-3 w-3" />}
          {copied ? "Copiado" : "Copiar"}
        </Button>
      </div>
      <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap rounded border bg-muted/40 p-3 text-xs">{system}</pre>
      <div className="text-xs font-semibold uppercase text-muted-foreground">Mensagem do usuário</div>
      <pre className="whitespace-pre-wrap rounded border bg-muted/40 p-3 text-xs">{user}</pre>
    </div>
  );
};
