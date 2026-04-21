import React, { useState } from "react";
import { cn } from "@/lib/utils";
import type { IncidentRunConfig } from "@/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface IncidentPreviewProps {
  /** Per-incident file configurations to preview. */
  configs: IncidentRunConfig[];
  /** Fiscal year, e.g. "FY26". */
  fiscalYear: string;
  /** Quarter, e.g. "Q1". */
  quarter: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Extract just the filename from a full path for compact display. */
function basename(path: string): string {
  if (!path) return "—";
  const parts = path.replace(/\\/g, "/").split("/");
  return parts[parts.length - 1] || path;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const IncidentPreview: React.FC<IncidentPreviewProps> = ({
  configs,
  fiscalYear: _fiscalYear,
  quarter: _quarter,
}) => {
  const [open, setOpen] = useState(false);

  if (configs.length === 0) return null;

  return (
    <div className="rounded-md border border-border">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
      >
        <span>
          Preview Selected{" "}
          <span className="text-foreground/70">
            ({configs.length} incident{configs.length !== 1 ? "s" : ""})
          </span>
        </span>
        <span className={cn("transition-transform text-[10px]", open && "rotate-180")}>
          ▾
        </span>
      </button>

      {open && (
        <div className="border-t border-border overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-muted/50">
                <th className="px-3 py-1.5 text-left font-semibold text-muted-foreground uppercase tracking-wide">
                  Incident
                </th>
                <th className="px-3 py-1.5 text-left font-semibold text-muted-foreground uppercase tracking-wide">
                  Input
                </th>
                <th className="px-3 py-1.5 text-left font-semibold text-muted-foreground uppercase tracking-wide">
                  Template
                </th>
                <th className="px-3 py-1.5 text-left font-semibold text-muted-foreground uppercase tracking-wide">
                  Output
                </th>
              </tr>
            </thead>
            <tbody>
              {configs.map((c) => (
                <tr
                  key={`${c.scriptName}-${c.incidentCode}`}
                  className="border-t border-border"
                >
                  <td className="px-3 py-1.5 font-mono whitespace-nowrap">
                    {c.incidentCode}
                  </td>
                  <td className="px-3 py-1.5 truncate max-w-[200px]" title={c.inputFile}>
                    {basename(c.inputFile)}
                  </td>
                  <td className="px-3 py-1.5 truncate max-w-[200px]" title={c.templateFile}>
                    {basename(c.templateFile)}
                  </td>
                  <td className="px-3 py-1.5 truncate max-w-[200px]" title={c.outputFile}>
                    {basename(c.outputFile)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default IncidentPreview;
