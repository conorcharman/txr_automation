import React, { useCallback, useMemo, useState } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { IncidentSelection } from "@/types";

// ---------------------------------------------------------------------------
// Shared incident data shape (matches INCIDENT_SCRIPTS in AccuracyTesting)
// ---------------------------------------------------------------------------

export interface IncidentScriptDef {
  scriptKey: string;
  displayLabel: string;
  incidents: { code: string; label: string }[];
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface IncidentChecklistProps {
  /** Available scripts with their incident codes. */
  scripts: IncidentScriptDef[];
  /** Currently selected incidents. */
  selected: IncidentSelection[];
  /** Called when the selection changes. */
  onChange: (selected: IncidentSelection[]) => void;
  /** Disable all controls. */
  disabled?: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function hasSelection(
  selected: IncidentSelection[],
  scriptKey: string,
  code: string,
): boolean {
  return selected.some((s) => s.scriptKey === scriptKey && s.incidentCode === code);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const IncidentChecklist: React.FC<IncidentChecklistProps> = ({
  scripts,
  selected,
  onChange,
  disabled = false,
}) => {
  // Multi-incident scripts start expanded; single-incident scripts don't need this.
  const initialExpanded = useMemo(
    () => new Set(scripts.filter((s) => s.incidents.length > 1).map((s) => s.scriptKey)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );
  const [expanded, setExpanded] = useState<Set<string>>(initialExpanded);

  const allIncidents = useMemo(
    () =>
      scripts.flatMap((s) =>
        s.incidents.map((i) => ({ scriptKey: s.scriptKey, incidentCode: i.code })),
      ),
    [scripts],
  );

  const allSelected = selected.length === allIncidents.length && allIncidents.length > 0;

  const toggleAll = useCallback(() => {
    onChange(allSelected ? [] : allIncidents);
  }, [allSelected, allIncidents, onChange]);

  const toggleExpanded = useCallback((scriptKey: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(scriptKey)) {
        next.delete(scriptKey);
      } else {
        next.add(scriptKey);
      }
      return next;
    });
  }, []);

  const toggleParent = useCallback(
    (script: IncidentScriptDef) => {
      const childCodes = script.incidents.map((i) => i.code);
      const allChildrenSelected = childCodes.every((code) =>
        hasSelection(selected, script.scriptKey, code),
      );
      if (allChildrenSelected) {
        onChange(
          selected.filter(
            (s) =>
              !(s.scriptKey === script.scriptKey && childCodes.includes(s.incidentCode)),
          ),
        );
      } else {
        const existing = selected.filter(
          (s) =>
            !(s.scriptKey === script.scriptKey && childCodes.includes(s.incidentCode)),
        );
        onChange([
          ...existing,
          ...childCodes.map((code) => ({ scriptKey: script.scriptKey, incidentCode: code })),
        ]);
      }
    },
    [selected, onChange],
  );

  const toggleChild = useCallback(
    (scriptKey: string, code: string) => {
      const exists = hasSelection(selected, scriptKey, code);
      if (exists) {
        onChange(selected.filter((s) => !(s.scriptKey === scriptKey && s.incidentCode === code)));
      } else {
        onChange([...selected, { scriptKey, incidentCode: code }]);
      }
    },
    [selected, onChange],
  );

  return (
    <div className="rounded-lg border border-border p-4 space-y-1">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          Incidents
        </p>
        <button
          type="button"
          onClick={toggleAll}
          disabled={disabled}
          className="text-xs text-primary hover:underline disabled:opacity-50"
        >
          {allSelected ? "Deselect All" : "Select All"}
        </button>
      </div>

      {scripts.map((script) => {
        const isMulti = script.incidents.length > 1;
        const childCodes = script.incidents.map((i) => i.code);
        const selectedCount = childCodes.filter((code) =>
          hasSelection(selected, script.scriptKey, code),
        ).length;
        const allChildrenSelected = selectedCount === childCodes.length;
        const someChildrenSelected = selectedCount > 0 && !allChildrenSelected;
        const isExpanded = expanded.has(script.scriptKey);

        if (!isMulti) {
          // Single-incident: flat row — no expand/collapse.
          const code = childCodes[0];
          return (
            <label
              key={script.scriptKey}
              className={cn(
                "flex items-center gap-2 py-1 cursor-pointer text-sm",
                disabled && "opacity-50 cursor-not-allowed",
              )}
            >
              <input
                type="checkbox"
                checked={hasSelection(selected, script.scriptKey, code)}
                onChange={() => toggleChild(script.scriptKey, code)}
                disabled={disabled}
                className="accent-primary h-4 w-4"
              />
              <span className="font-medium">{script.displayLabel}</span>
              <span className="text-xs text-muted-foreground font-mono">{code}</span>
            </label>
          );
        }

        // Multi-incident: collapsible parent + code-only children.
        return (
          <div key={script.scriptKey}>
            <div className="flex items-center gap-2 py-1">
              <input
                type="checkbox"
                ref={(el) => {
                  if (el) el.indeterminate = someChildrenSelected;
                }}
                checked={allChildrenSelected}
                onChange={() => toggleParent(script)}
                disabled={disabled}
                className="accent-primary h-4 w-4 cursor-pointer"
              />
              <button
                type="button"
                onClick={() => toggleExpanded(script.scriptKey)}
                disabled={disabled}
                className="flex flex-1 items-center gap-2 text-left text-sm font-medium disabled:opacity-50"
              >
                <span>{script.displayLabel}</span>
                <span className="text-xs text-muted-foreground font-mono font-normal">
                  {childCodes.join(", ")}
                </span>
                <ChevronDown
                  className={cn(
                    "ml-auto h-3.5 w-3.5 text-muted-foreground transition-transform shrink-0",
                    isExpanded && "rotate-180",
                  )}
                />
              </button>
            </div>

            {isExpanded && (
              <div className="ml-6 space-y-0.5 pb-1">
                {script.incidents.map((incident) => (
                  <label
                    key={incident.code}
                    className={cn(
                      "flex items-center gap-2 py-0.5 cursor-pointer text-sm",
                      disabled && "opacity-50 cursor-not-allowed",
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={hasSelection(selected, script.scriptKey, incident.code)}
                      onChange={() => toggleChild(script.scriptKey, incident.code)}
                      disabled={disabled}
                      className="accent-primary h-3.5 w-3.5"
                    />
                    <span className="font-mono text-xs">{incident.code}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default IncidentChecklist;
