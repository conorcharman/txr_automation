import React, { useMemo, useState } from "react";

import type { XsdColumnEntry } from "@/types";
import { cn } from "@/lib/utils";

interface SchemaPreviewPanelProps {
  columns: XsdColumnEntry[];
  warnings?: string[];
  errors?: string[];
  unsupportedConstructs?: string[];
  stats?: Record<string, number>;
}

const tableHeadCls = "px-3 py-2 text-left text-xs font-medium text-muted-foreground";
const tableCellCls = "px-3 py-2 align-top text-sm";

function renderConstraints(value: XsdColumnEntry["constraints"]): string {
  const entries = Object.entries(value ?? {});
  if (entries.length === 0) {
    return "-";
  }

  return entries
    .map(([key, raw]) => {
      const serialised = Array.isArray(raw) ? raw.join("|") : raw;
      return `${key}: ${serialised}`;
    })
    .join("; ");
}

const SchemaPreviewPanel: React.FC<SchemaPreviewPanelProps> = ({
  columns,
  warnings = [],
  errors = [],
  unsupportedConstructs = [],
  stats = {},
}) => {
  const [expanded, setExpanded] = useState(false);

  const rows = useMemo(
    () =>
      columns.map((col) => ({
        ...col,
        depth: Math.max(0, col.path.split("_").length - 1),
      })),
    [columns],
  );

  return (
    <div className="rounded-lg border border-border">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
      >
        <span>{columns.length} fields detected</span>
        <span className={cn("transition-transform", expanded && "rotate-180")}>▾</span>
      </button>

      {expanded && (
        <div className="space-y-3 border-t border-border px-4 pb-4 pt-3">
          {Object.keys(stats).length > 0 && (
            <div className="rounded-md border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
              {Object.entries(stats).map(([key, value]) => (
                <p key={key}>{`${key}: ${value}`}</p>
              ))}
            </div>
          )}

          {errors.length > 0 && (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              {errors.map((error) => (
                <p key={error}>{error}</p>
              ))}
            </div>
          )}

          {warnings.length > 0 && (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900/40 dark:bg-amber-900/10 dark:text-amber-200">
              {warnings.map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          )}

          {unsupportedConstructs.length > 0 && (
            <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900/40 dark:bg-amber-900/10 dark:text-amber-200">
              <p className="font-medium">Unsupported constructs</p>
              <p>{unsupportedConstructs.join(", ")}</p>
            </div>
          )}

          <div className="max-h-80 overflow-auto rounded-md border border-border">
            <table className="min-w-full border-collapse">
              <thead>
                <tr className="border-b border-border bg-muted/40">
                  <th className={tableHeadCls}>Column Path</th>
                  <th className={tableHeadCls}>Type</th>
                  <th className={tableHeadCls}>Min</th>
                  <th className={tableHeadCls}>Max</th>
                  <th className={tableHeadCls}>Constraints</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.path} className="border-b border-border/70 last:border-b-0">
                    <td className={tableCellCls}>
                      <span style={{ paddingLeft: `${row.depth * 12}px` }}>{row.path}</span>
                    </td>
                    <td className={tableCellCls}>{row.typeName || "-"}</td>
                    <td className={tableCellCls}>{row.minOccurs}</td>
                    <td className={tableCellCls}>{row.maxOccurs}</td>
                    <td className={tableCellCls}>{renderConstraints(row.constraints)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default SchemaPreviewPanel;
