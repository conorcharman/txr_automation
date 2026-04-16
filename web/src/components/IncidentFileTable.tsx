import React, { useEffect, useCallback, useState } from "react";
import { ChevronDown } from "lucide-react";
import { PathPickerInput } from "@/components/PathPickerInput";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { IncidentRunConfig, IncidentSelection, ResolvedPaths } from "@/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export type FileTableColumn = "input" | "template" | "output";

interface IncidentFileTableProps {
  /** Currently selected incidents. */
  incidents: IncidentSelection[];
  /** Resolved paths from SmartPathConfig (used for auto-fill). */
  resolvedPaths: ResolvedPaths | null;
  /** Fiscal year string, e.g. "FY26". */
  fiscalYear: string;
  /** Quarter string, e.g. "Q1". */
  quarter: string;
  /** Current per-incident file configurations. */
  value: IncidentRunConfig[];
  /** Called when configurations change. */
  onChange: (configs: IncidentRunConfig[]) => void;
  /** Which columns to display. */
  columns: FileTableColumn[];
  /** Disable all inputs. */
  disabled?: boolean;
  /** Show VALUES badge for incidents 7_6 and 7_42 (Extract Generator context). */
  showValuesBadge?: boolean;
  /**
   * Which key from ResolvedPaths to use as the base directory for the output
   * file. Defaults to "output". Use "extracts" for Collate.
   */
  outputDirKey?: keyof ResolvedPaths;
  /**
   * Filename suffix appended after the incident code + period, e.g.
   * "validated.csv" (default) or "extract.csv" (for Collate).
   */
  outputFileSuffix?: string;
  /** Wrap the table in a collapsible section. Defaults to true. */
  collapsible?: boolean;
  /** Initial open state when collapsible. Defaults to false (collapsed). */
  defaultOpen?: boolean;
}

// ---------------------------------------------------------------------------
// Column metadata
// ---------------------------------------------------------------------------

const COLUMN_LABELS: Record<FileTableColumn, string> = {
  input: "Input File",
  template: "Template File",
  output: "Output File",
};

// ---------------------------------------------------------------------------
// Naming convention helpers
// ---------------------------------------------------------------------------

function buildFileName(
  code: string,
  fy: string,
  q: string,
  suffix: string,
): string {
  return `${code}_${fy}_${q}_${suffix}`;
}

function buildTemplateFileName(code: string, fy: string, q: string): string {
  return `${fy} ${q} ${code}.csv`;
}

function deriveDefaults(
  code: string,
  fy: string,
  q: string,
  paths: ResolvedPaths | null,
  outputDirKey: keyof ResolvedPaths = "output",
  outputFileSuffix: string = "validated.csv",
): { inputFile: string; templateFile: string; outputFile: string } {
  const extractsDir = paths?.extracts ?? "";
  const templatesDir = paths?.templates ?? "";
  const outputBase = (paths?.[outputDirKey] as string | undefined) ?? "";

  return {
    inputFile: extractsDir
      ? `${extractsDir}/${buildFileName(code, fy, q, "extract.csv")}`
      : "",
    templateFile: templatesDir
      ? `${templatesDir}/${buildTemplateFileName(code, fy, q)}`
      : "",
    outputFile: outputBase
      ? (outputFileSuffix === "template.csv"
          ? `${outputBase}/${buildTemplateFileName(code, fy, q)}`
          : `${outputBase}/${buildFileName(code, fy, q, outputFileSuffix)}`)
      : "",
  };
}

// Incidents that require VALUES mode in Extract Generator.
const VALUES_MODE_CODES = new Set(["7_6", "7_42"]);

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const IncidentFileTable: React.FC<IncidentFileTableProps> = ({
  incidents,
  resolvedPaths,
  fiscalYear,
  quarter,
  value,
  onChange,
  columns,
  disabled = false,
  showValuesBadge = false,
  outputDirKey = "output",
  outputFileSuffix = "validated.csv",
  collapsible = true,
  defaultOpen = false,
}) => {
  const [open, setOpen] = useState(defaultOpen);

  // Auto-populate when incidents or resolvedPaths change.
  useEffect(() => {
    if (incidents.length === 0) {
      if (value.length > 0) onChange([]);
      return;
    }

    const next = incidents.map((inc) => {
      const existing = value.find(
        (v) => v.scriptName === inc.scriptKey && v.incidentCode === inc.incidentCode,
      );
      const defaults = deriveDefaults(
        inc.incidentCode,
        fiscalYear,
        quarter,
        resolvedPaths,
        outputDirKey,
        outputFileSuffix,
      );

      return {
        scriptName: inc.scriptKey,
        incidentCode: inc.incidentCode,
        inputFile: existing?.inputFile || defaults.inputFile,
        templateFile: existing?.templateFile || defaults.templateFile,
        outputFile: existing?.outputFile || defaults.outputFile,
      };
    });

    // Only update if something actually changed to avoid infinite loops.
    const serialised = JSON.stringify(next);
    const currentSerialised = JSON.stringify(
      incidents.map((inc) =>
        value.find(
          (v) => v.scriptName === inc.scriptKey && v.incidentCode === inc.incidentCode,
        ) ?? {
          scriptName: inc.scriptKey,
          incidentCode: inc.incidentCode,
          inputFile: "",
          templateFile: "",
          outputFile: "",
        },
      ),
    );
    if (serialised !== currentSerialised) {
      onChange(next);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [incidents, resolvedPaths, fiscalYear, quarter, outputDirKey, outputFileSuffix]);

  const updateField = useCallback(
    (
      scriptName: string,
      incidentCode: string,
      field: "inputFile" | "templateFile" | "outputFile",
      newValue: string,
    ) => {
      onChange(
        value.map((c) =>
          c.scriptName === scriptName && c.incidentCode === incidentCode
            ? { ...c, [field]: newValue }
            : c,
        ),
      );
    },
    [value, onChange],
  );

  const fieldMap: Record<FileTableColumn, "inputFile" | "templateFile" | "outputFile"> = {
    input: "inputFile",
    template: "templateFile",
    output: "outputFile",
  };

  if (incidents.length === 0) {
    return (
      <p className="text-xs text-muted-foreground italic">
        No incidents selected.
      </p>
    );
  }

  const table = (
    <div className={cn("overflow-x-auto", collapsible && "border-t border-border")}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/50">
            <th className="px-3 py-2 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide whitespace-nowrap">
              Incident
            </th>
            {columns.map((col) => (
              <th
                key={col}
                className="px-3 py-2 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide whitespace-nowrap"
              >
                {COLUMN_LABELS[col]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {incidents.map((inc) => {
            const config = value.find(
              (v) => v.scriptName === inc.scriptKey && v.incidentCode === inc.incidentCode,
            );

            return (
              <tr
                key={`${inc.scriptKey}-${inc.incidentCode}`}
                className="border-b border-border last:border-0"
              >
                <td className="px-3 py-2 whitespace-nowrap">
                  <span className="font-mono text-xs">{inc.incidentCode}</span>
                  {showValuesBadge && VALUES_MODE_CODES.has(inc.incidentCode) && (
                    <Badge variant="secondary" className="ml-2 text-[10px]">
                      VALUES format (auto)
                    </Badge>
                  )}
                </td>
                {columns.map((col) => (
                  <td key={col} className="px-3 py-2">
                    <PathPickerInput
                      value={config?.[fieldMap[col]] ?? ""}
                      onChange={(v) =>
                        updateField(inc.scriptKey, inc.incidentCode, fieldMap[col], v)
                      }
                      mode="file"
                      placeholder={`${inc.incidentCode} ${COLUMN_LABELS[col].toLowerCase()}`}
                      disabled={disabled}
                    />
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );

  if (!collapsible) {
    return <div className="rounded-lg border border-border overflow-x-auto">{table}</div>;
  }

  return (
    <div className="rounded-md border border-border">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
      >
        <span>
          File Paths
          <span className="ml-1.5 text-foreground/60">
            ({incidents.length} incident{incidents.length !== 1 ? "s" : ""})
          </span>
        </span>
        <ChevronDown
          className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")}
        />
      </button>
      {open && table}
    </div>
  );
};

export default IncidentFileTable;
