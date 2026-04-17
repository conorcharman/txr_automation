import React, { useCallback, useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";

import { PathPickerInput } from "@/components/PathPickerInput";
import { resolvePaths } from "@/api/filesystem";
import { cn } from "@/lib/utils";
import type { ResolvedPaths } from "@/types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface SmartPathConfigProps {
  /** Current fiscal year, e.g. "FY26". */
  fiscalYear: string;
  /** Current quarter, e.g. "Q1". */
  quarter: string;
  /**
   * Module sub-directory inserted between the quarter and stage dirs.
   * Use "accuracy_testing" or "replay" to keep the two separate.
   */
  module?: string;
  /**
   * Which stage directories to show in the summary and override panels.
   * Defaults to all five stages when omitted.
   */
  visibleStages?: readonly ("kaizen" | "extracts" | "templates" | "output" | "logs")[];
  /** Called when resolved paths change. */
  onChange: (paths: ResolvedPaths) => void;
  /** Disable all inputs. */
  disabled?: boolean;
}

// ---------------------------------------------------------------------------
// Field wrapper (matches pattern used in form pages)
// ---------------------------------------------------------------------------

const Label: React.FC<{ text: string; value: string }> = ({ text, value }) => (
  <div className="flex items-center justify-between gap-2">
    <span className="text-xs font-medium text-muted-foreground">{text}</span>
    <span className="truncate text-xs text-foreground/80 font-mono">{value}</span>
  </div>
);

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const SmartPathConfig: React.FC<SmartPathConfigProps> = ({
  fiscalYear,
  quarter,
  module,
  visibleStages,
  onChange,
  disabled = false,
}) => {
  const stages = visibleStages ?? (["kaizen", "extracts", "templates", "output", "logs"] as const);
  const [overridesOpen, setOverridesOpen] = useState(false);
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [resolved, setResolved] = useState<ResolvedPaths | null>(null);

  const mutation = useMutation({
    mutationFn: resolvePaths,
    onSuccess: (data) => {
      setResolved(data);
      onChange(data);
    },
  });

  // Resolve paths whenever FY/Q/module changes (and on mount).
  useEffect(() => {
    if (!fiscalYear || !quarter) return;
    mutation.mutate({
      fiscalYear,
      quarter,
      module: module ?? null,
      overrides: Object.keys(overrides).length > 0 ? overrides : null,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fiscalYear, quarter, module]);

  const handleOverrideChange = useCallback(
    (stage: string, value: string) => {
      const next = { ...overrides, [stage]: value };
      if (!value) delete next[stage];
      setOverrides(next);
    },
    [overrides],
  );

  const applyOverrides = useCallback(() => {
    if (!fiscalYear || !quarter) return;
    mutation.mutate({
      fiscalYear,
      quarter,
      module: module ?? null,
      overrides: Object.keys(overrides).length > 0 ? overrides : null,
    });
  }, [fiscalYear, quarter, module, overrides, mutation]);

  if (!fiscalYear || !quarter) return null;

  return (
    <div className="rounded-md border border-border">
      {/* Header: resolved paths summary */}
      <div className="px-3 py-2 space-y-1">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          Directories
        </p>
        {mutation.isPending && (
          <p className="text-xs text-muted-foreground">Resolving paths…</p>
        )}
        {mutation.isError && (
          <p className="text-xs text-destructive">
            {mutation.error instanceof Error
              ? mutation.error.message
              : "Failed to resolve paths"}
          </p>
        )}
        {resolved && (
          <div className="space-y-0.5">
            {stages.map((stage) => (
              <Label
                key={stage}
                text={stage.charAt(0).toUpperCase() + stage.slice(1)}
                value={overrides[stage] || resolved[stage]}
              />
            ))}
          </div>
        )}
      </div>

      {/* Collapsible override section */}
      <div className="border-t border-border">
        <button
          type="button"
          onClick={() => setOverridesOpen(!overridesOpen)}
          className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
        >
          Override Paths
          <ChevronDown
            className={cn(
              "h-3 w-3 transition-transform",
              overridesOpen && "rotate-180",
            )}
          />
        </button>
        {overridesOpen && (
          <div className="space-y-3 px-3 pb-3">
            {stages.map(
              (stage) => (
                <div key={stage} className="flex flex-col gap-1">
                  <label className="text-xs font-medium text-muted-foreground capitalize">
                    {stage}
                  </label>
                  <PathPickerInput
                    value={overrides[stage] ?? ""}
                    onChange={(v) => handleOverrideChange(stage, v)}
                    mode="directory"
                    placeholder={resolved?.[stage] ?? ""}
                    disabled={disabled}
                  />
                </div>
              ),
            )}
            <button
              type="button"
              onClick={applyOverrides}
              disabled={disabled || mutation.isPending}
              className="text-xs text-primary hover:underline disabled:opacity-50"
            >
              Apply overrides
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default SmartPathConfig;
