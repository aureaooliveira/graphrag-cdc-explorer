import React, { useState } from "react";
import { ChevronDown, ChevronRight, CheckCircle2, Loader2, Circle } from "lucide-react";
import { cn } from "@/lib/utils";

export type SectionState = "pending" | "running" | "done";

interface SectionProps {
  step: number;
  title: string;
  subtitle?: React.ReactNode;
  state: SectionState;
  defaultOpen?: boolean;
  children?: React.ReactNode;
}

/** Bloco recolhível de uma etapa da linha do tempo da consulta. */
export const Section: React.FC<SectionProps> = ({ step, title, subtitle, state, defaultOpen = false, children }) => {
  const [open, setOpen] = useState(defaultOpen);
  const Icon = state === "done" ? CheckCircle2 : state === "running" ? Loader2 : Circle;
  return (
    <div className="rounded-lg border bg-card">
      <button
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
        onClick={() => setOpen((o) => !o)}
        disabled={state === "pending"}
      >
        <Icon
          className={cn(
            "h-5 w-5 shrink-0",
            state === "done" && "text-emerald-600",
            state === "running" && "animate-spin text-primary",
            state === "pending" && "text-muted-foreground/40",
          )}
        />
        <div className="min-w-0 flex-1">
          <div className={cn("text-sm font-semibold", state === "pending" && "text-muted-foreground")}>
            {step}. {title}
          </div>
          {subtitle && <div className="truncate text-xs text-muted-foreground">{subtitle}</div>}
        </div>
        {state !== "pending" &&
          (open ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />)}
      </button>
      {open && state !== "pending" && <div className="border-t px-4 py-3">{children}</div>}
    </div>
  );
};
