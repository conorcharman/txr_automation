import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useForm, Controller, type Resolver } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import TestingPeriodSelector from "@/components/TestingPeriodSelector";
import ConfigLoader from "@/components/ConfigLoader";
import { PathPickerInput } from "@/components/PathPickerInput";
import SmartPathConfig from "@/components/SmartPathConfig";
import LastRunBadge from "@/components/LastRunBadge";
import Field from "@/components/Field";
import IncidentChecklist from "@/components/IncidentChecklist";
import type { IncidentScriptDef } from "@/components/IncidentChecklist";
import IncidentFileTable from "@/components/IncidentFileTable";
import IncidentPreview from "@/components/IncidentPreview";
import {
  detectConsolidatedIncidents,
  runValidation,
  runIncidents,
  discoverIncidents,
} from "@/api/accuracy";
import { browseDirectory, getFilesystemConfig } from "@/api/filesystem";
import { cn } from "@/lib/utils";
import type {
  DiscoveryResponse,
  IncidentRunConfig,
  IncidentSelection,
  ResolvedPaths,
} from "@/types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"] as const;

const INCIDENT_CODE_RE = /^\d+_\d+$/;

interface DetectedIncidentStat {
  code: string;
  description: string;
  errorsCount: number;
  queriesCount: number;
}

const INCIDENT_SCRIPTS: IncidentScriptDef[] = [
  {
    scriptKey: "buyer_id_validation",
    displayLabel: "Incorrect Buyer ID",
    incidents: [
      { code: "7_35", label: "Incorrect Buyer ID" },
      { code: "7_37", label: "Incorrect Buyer ID" },
      { code: "7_39", label: "Incorrect Buyer ID" },
    ],
  },
  {
    scriptKey: "seller_id_validation",
    displayLabel: "Incorrect Seller ID",
    incidents: [
      { code: "16_19", label: "Incorrect Seller ID" },
      { code: "16_21", label: "Incorrect Seller ID" },
      { code: "16_23", label: "Incorrect Seller ID" },
    ],
  },
  {
    scriptKey: "inconsistent_buyer_id_validation",
    displayLabel: "Inconsistent Buyer ID",
    incidents: [{ code: "7_66", label: "Inconsistent Buyer ID" }],
  },
  {
    scriptKey: "inconsistent_seller_id_validation",
    displayLabel: "Inconsistent Seller ID",
    incidents: [{ code: "16_20", label: "Inconsistent Seller ID" }],
  },
  {
    scriptKey: "validate_ftbdm",
    displayLabel: "Incorrect FT Buyer Decision Maker",
    incidents: [{ code: "12_17", label: "FT Buyer Decision Maker" }],
  },
  {
    scriptKey: "validate_ftsdm",
    displayLabel: "Incorrect FT Seller Decision Maker",
    incidents: [{ code: "21_17", label: "FT Seller Decision Maker" }],
  },
  {
    scriptKey: "incorrect_net_amount_validation",
    displayLabel: "Incorrect Net Amount",
    incidents: [{ code: "35_3", label: "Incorrect Net Amount" }],
  },
  {
    scriptKey: "non_zero_net_quantity",
    displayLabel: "Non-Zero Net Quantity",
    incidents: [{ code: "7_6", label: "Non-Zero Net Quantity" }],
  },
  {
    scriptKey: "non_zero_net_amount",
    displayLabel: "Non-Zero Net Amount",
    incidents: [{ code: "7_42", label: "Non-Zero Net Amount" }],
  },
  {
    scriptKey: "incorrect_time",
    displayLabel: "Incorrect Time",
    incidents: [{ code: "7_30", label: "Incorrect Time" }],
  },
];

type ActiveTab = "validation" | "utilities";

function currentFY(): string {
  return `FY${String(new Date().getFullYear()).slice(-2)}`;
}

function incidentSort(a: string, b: string): number {
  const [aLeft, aRight] = a.split("_").map((n) => Number(n));
  const [bLeft, bRight] = b.split("_").map((n) => Number(n));
  if (aLeft !== bLeft) return aLeft - bLeft;
  return aRight - bRight;
}

function fileNameOnly(path: string): string {
  const parts = path.split(/[\\/]/);
  return parts[parts.length - 1] || path;
}

function buildTemplateIncidentScripts(detectedIncidents: Map<string, string>): IncidentScriptDef[] {
  if (detectedIncidents.size === 0) {
    return INCIDENT_SCRIPTS;
  }

  const scripts: IncidentScriptDef[] = [];
  const knownCodes = new Set<string>();

  for (const script of INCIDENT_SCRIPTS) {
    const matchedIncidents = script.incidents
      .filter((incident) => detectedIncidents.has(incident.code))
      .sort((a, b) => incidentSort(a.code, b.code));
    for (const incident of matchedIncidents) {
      knownCodes.add(incident.code);
    }
    if (matchedIncidents.length > 0) {
      scripts.push({
        scriptKey: script.scriptKey,
        displayLabel: script.displayLabel,
        incidents: matchedIncidents,
      });
    }
  }

  const unknownCodes = Array.from(detectedIncidents.keys())
    .filter((code) => !knownCodes.has(code))
    .sort(incidentSort);

  for (const code of unknownCodes) {
    const description = detectedIncidents.get(code) || "Detected Incident";
    scripts.push({
      scriptKey: `detected_${code}`,
      displayLabel: description,
      incidents: [{ code, label: description }],
    });
  }

  return scripts;
}

function flattenIncidentSelection(scripts: IncidentScriptDef[]): IncidentSelection[] {
  return scripts.flatMap((script) =>
    script.incidents.map((incident) => ({
      scriptKey: script.scriptKey,
      incidentCode: incident.code,
    })),
  );
}

// ---------------------------------------------------------------------------
// Shared styles
// ---------------------------------------------------------------------------

const selectCls =
  "h-9 rounded-md border border-input bg-background px-3 text-sm " +
  "focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50";

// ---------------------------------------------------------------------------
// Field wrapper
// ---------------------------------------------------------------------------



// ---------------------------------------------------------------------------
// Sidebar nav item
// ---------------------------------------------------------------------------

function navItemCls(active: boolean): string {
  return cn(
    "w-full text-left px-3 py-2 rounded-md text-sm transition-colors",
    active
      ? "bg-primary/10 text-primary font-medium"
      : "text-muted-foreground hover:bg-muted hover:text-foreground",
  );
}

// ---------------------------------------------------------------------------
// Advanced collapsible (log level + dry run + optional ConfigLoader slot)
// ---------------------------------------------------------------------------

interface AdvancedSectionProps {
  isOpen: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}

const AdvancedSection: React.FC<AdvancedSectionProps> = ({ isOpen, onToggle, children }) => (
  <div className="rounded-md border border-border">
    <button
      type="button"
      onClick={onToggle}
      className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
    >
      Advanced
      <span className={cn("transition-transform text-[10px]", isOpen && "rotate-180")}>â–¾</span>
    </button>
    {isOpen && (
      <div className="space-y-3 px-3 pb-3 border-t border-border pt-3">{children}</div>
    )}
  </div>
);

// ---------------------------------------------------------------------------
// localStorage helpers
// ---------------------------------------------------------------------------

function loadCache<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(`txr_form_${key}`);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

// ---------------------------------------------------------------------------
// Unified Validation Form (incident-level)
// ---------------------------------------------------------------------------

/** All incidents from INCIDENT_SCRIPTS, used as the default selection. */
const ALL_INCIDENTS: IncidentSelection[] = INCIDENT_SCRIPTS.flatMap((s) =>
  s.incidents.map((i) => ({ scriptKey: s.scriptKey, incidentCode: i.code })),
);

const unifiedSchema = z.object({
  testingPeriod: z.object({ fiscalYear: z.string(), quarter: z.string() }),
  logLevel: z.string(),
  dryRun: z.boolean(),
  stopOnError: z.boolean(),
});

type UnifiedFormValues = z.infer<typeof unifiedSchema>;

const UnifiedValidationForm: React.FC = () => {
  const navigate = useNavigate();
  const [selectedIncidents, setSelectedIncidents] = useState<IncidentSelection[]>(ALL_INCIDENTS);
  const [incidentConfigs, setIncidentConfigs] = useState<IncidentRunConfig[]>([]);
  const [resolvedPaths, setResolvedPaths] = useState<ResolvedPaths | null>(null);
  const [discoveryResult, setDiscoveryResult] = useState<DiscoveryResponse | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const { data: fsConfig } = useQuery({
    queryKey: ["filesystem-config"],
    queryFn: getFilesystemConfig,
    staleTime: Infinity,
  });
  const defaultLogsDir = `${fsConfig?.dataRoot ?? "/app/data"}/logs`;

  const {
    control,
    register,
    handleSubmit,
    watch,
    getValues,
    reset,
    formState: { errors },
  } = useForm<UnifiedFormValues>({
    resolver: zodResolver(unifiedSchema),
    defaultValues: loadCache("accuracy_validation_unified", {
      testingPeriod: { fiscalYear: currentFY(), quarter: "Q1" },
      logLevel: "INFO",
      dryRun: false,
      stopOnError: false,
    }),
  });

  useEffect(() => {
    const sub = watch((values) => {
      try { localStorage.setItem("txr_form_accuracy_validation_unified", JSON.stringify(values)); } catch { /* ignore */ }
    });
    return () => sub.unsubscribe();
  }, [watch]);

  const testingPeriod = watch("testingPeriod");

  const handlePathsResolved = useCallback(
    (paths: ResolvedPaths) => {
      setResolvedPaths(paths);
    },
    [],
  );

  const mutation = useMutation({
    mutationFn: (values: UnifiedFormValues) =>
      runIncidents({
        testingPeriod: values.testingPeriod,
        incidents: incidentConfigs.map((c) => ({
          scriptName: c.scriptName,
          incidentCode: c.incidentCode,
          inputFile: c.inputFile,
          templateFile: c.templateFile,
          outputFile: c.outputFile,
        })),
        logLevel: values.logLevel,
        dryRun: values.dryRun,
        stopOnError: values.stopOnError,
      }),
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const discoveryMutation = useMutation({
    mutationFn: discoverIncidents,
    onSuccess: (result) => {
      setDiscoveryResult(result);
      // Match discovered files to incident configs by code.
      const foundFilesByCode = new Map<string, string>();
      for (const r of result.results) {
        for (const code of r.codes) {
          const match = r.foundFiles.find((f) => f.includes(code));
          if (match) foundFilesByCode.set(code, match);
        }
      }
      if (foundFilesByCode.size > 0) {
        setIncidentConfigs((prev) =>
          prev.map((c) => {
            const found = foundFilesByCode.get(c.incidentCode);
            return found ? { ...c, inputFile: found } : c;
          }),
        );
      }
      toast.success(`Found ${result.totalFound} file(s)`);
    },
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Discovery failed");
    },
  });

  const onSubmit = (values: UnifiedFormValues) => {
    mutation.mutate(values);
  };

  const isPending = mutation.isPending;

  const handleLoadConfig = (config: Record<string, unknown>) => {
    reset(config as unknown as UnifiedFormValues);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-2xl">
      {/* Testing Period */}
      <div>
        <p className="text-xs font-medium text-muted-foreground mb-2">Testing Period</p>
        <Controller
          name="testingPeriod"
          control={control}
          render={({ field }) => (
            <TestingPeriodSelector
              value={field.value}
              onChange={field.onChange}
              disabled={isPending}
            />
          )}
        />
      </div>

      {/* Smart Path Config */}
      <SmartPathConfig
        fiscalYear={testingPeriod.fiscalYear}
        quarter={testingPeriod.quarter}
        module="accuracy_testing"
        onChange={handlePathsResolved}
        disabled={isPending}
      />

      {/* Incident Checklist */}
      <IncidentChecklist
        scripts={INCIDENT_SCRIPTS}
        selected={selectedIncidents}
        onChange={setSelectedIncidents}
        disabled={isPending}
      />

      {/* Discover Files */}
      <Button
        type="button"
        variant="outline"
        disabled={!resolvedPaths?.extracts || discoveryMutation.isPending}
        onClick={() =>
          discoveryMutation.mutate({ inputDirectory: resolvedPaths?.extracts ?? "" })
        }
        className="w-full"
      >
        {discoveryMutation.isPending ? "Scanningâ€¦" : "Discover Files"}
      </Button>

      {discoveryResult && (
        <div className="rounded-lg border border-border p-4 space-y-2 text-sm">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Discovery Results â€” {discoveryResult.totalFound} file(s) found
          </p>
          {discoveryResult.results.map((r) => (
            <div key={r.scriptName} className="flex items-center gap-2">
              <span
                className={cn(
                  "h-2 w-2 rounded-full shrink-0",
                  r.foundFiles.length > 0 ? "bg-green-500" : "bg-orange-400",
                )}
              />
              <span className="truncate">
                {INCIDENT_SCRIPTS.find((s) => s.scriptKey === r.scriptName)?.displayLabel ?? r.scriptName}
              </span>
              <span className="ml-auto text-xs text-muted-foreground">
                {r.foundFiles.length} file(s)
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Incident File Table */}
      <IncidentFileTable
        incidents={selectedIncidents}
        resolvedPaths={resolvedPaths}
        fiscalYear={testingPeriod.fiscalYear}
        quarter={testingPeriod.quarter}
        value={incidentConfigs}
        onChange={setIncidentConfigs}
        columns={["input", "template", "output"]}
        disabled={isPending}
      />

      {/* Preview Selected */}
      <IncidentPreview
        configs={incidentConfigs}
        fiscalYear={testingPeriod.fiscalYear}
        quarter={testingPeriod.quarter}
      />

      {/* Stop on error */}
      <label className="flex items-center gap-2 cursor-pointer text-sm">
        <input
          type="checkbox"
          {...register("stopOnError")}
          disabled={isPending}
          className="accent-primary h-4 w-4"
        />
        Stop on first error
      </label>

      <AdvancedSection isOpen={showAdvanced} onToggle={() => setShowAdvanced(!showAdvanced)}>
        <div className="flex flex-wrap gap-4 items-end">
          <Field label="Log Level" hint="Logging verbosity level." error={errors.logLevel?.message}>
            <select {...register("logLevel")} disabled={isPending} className={cn(selectCls, "w-40")}>
              {LOG_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
          </Field>
          <label className="flex items-center gap-2 cursor-pointer text-sm pb-1">
            <input type="checkbox" {...register("dryRun")} disabled={isPending} className="accent-primary h-4 w-4" />
            Dry Run
          </label>
        </div>
        <ConfigLoader
          scriptName="unified_validation"
          currentConfig={getValues() as unknown as Record<string, unknown>}
          onLoad={handleLoadConfig}
        />
      </AdvancedSection>

      <Button
        type="submit"
        disabled={isPending || selectedIncidents.length === 0}
        className="w-full"
      >
        {isPending ? "Runningâ€¦" : selectedIncidents.length > 1 ? "Run Selected" : "Run"}
      </Button>

      {mutation.isError && (
        <p className="text-sm text-destructive">
          {mutation.error instanceof Error
            ? mutation.error.message
            : "An error occurred"}
        </p>
      )}
    </form>
  );
};

// ---------------------------------------------------------------------------
// Utility sidebar config (display only â€” each form is a distinct component)
// ---------------------------------------------------------------------------

interface UtilityNavItem {
  key: string;
  label: string;
}

const UTILITY_NAV: UtilityNavItem[] = [
  { key: "accuracy_template_generator", label: "Template Generator" },
  { key: "sql_extract_generator", label: "Extract Generator" },
  { key: "collate_csv_extracts", label: "Collate CSV Extracts" },
  { key: "data_push", label: "Data Push" },
];

// ---------------------------------------------------------------------------
// Shared utility form schema (testing period + log level + dry run)
// ---------------------------------------------------------------------------

const utilityBaseSchema = z.object({
  testingPeriod: z.object({ fiscalYear: z.string(), quarter: z.string() }),
  logLevel: z.string(),
  dryRun: z.boolean(),
});

type UtilityBaseValues = z.infer<typeof utilityBaseSchema>;

// ---------------------------------------------------------------------------
// Template Generator Form
// ---------------------------------------------------------------------------

const TemplateGeneratorForm: React.FC = () => {
  const navigate = useNavigate();
  const [templateIncidentScripts, setTemplateIncidentScripts] = useState<IncidentScriptDef[]>(INCIDENT_SCRIPTS);
  const [selectedIncidents, setSelectedIncidents] = useState<IncidentSelection[]>(ALL_INCIDENTS);
  const [incidentConfigs, setIncidentConfigs] = useState<IncidentRunConfig[]>([]);
  const [resolvedPaths, setResolvedPaths] = useState<ResolvedPaths | null>(null);
  const [kaizenFiles, setKaizenFiles] = useState<{ errors: string; queries: string } | null>(null);
  const [detectedIncidentCount, setDetectedIncidentCount] = useState<number>(0);
  const [detectedIncidentStats, setDetectedIncidentStats] = useState<DetectedIncidentStat[]>([]);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const { control, register, handleSubmit, watch, formState: { errors } } = useForm<UtilityBaseValues>({
    resolver: zodResolver(utilityBaseSchema),
    defaultValues: loadCache("accuracy_utility_template_gen", {
      testingPeriod: { fiscalYear: currentFY(), quarter: "Q1" },
      logLevel: "INFO",
      dryRun: false,
    }),
  });

  useEffect(() => {
    const sub = watch((values) => {
      try { localStorage.setItem("txr_form_accuracy_utility_template_gen", JSON.stringify(values)); } catch { /* ignore */ }
    });
    return () => sub.unsubscribe();
  }, [watch]);

  const testingPeriod = watch("testingPeriod");

  // Auto-discover consolidated CSVs from kaizen dir whenever paths resolve.
  const handlePathsResolved = useCallback((paths: ResolvedPaths) => {
    setResolvedPaths(paths);
    if (!paths.kaizen) return;
    browseDirectory(paths.kaizen)
      .then((res) => {
        const files = res.entries.filter((e) => !e.isDir).map((e) => e.path);
        const errorsFile = files.find((f) => /(consolidated[._ ]errors[._ ]data|consolidated_errors)/i.test(f)) ?? "";
        const queriesFile = files.find((f) => /(consolidated[._ ]queries[._ ]data|consolidated_queries)/i.test(f)) ?? "";
        setKaizenFiles({ errors: errorsFile, queries: queriesFile });
      })
      .catch(() => setKaizenFiles(null));
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function detectIncidents(): Promise<void> {
      if (!kaizenFiles) {
        setDetectedIncidentStats([]);
        return;
      }

      const response = await detectConsolidatedIncidents({
        errorsFile: kaizenFiles.errors || null,
        queriesFile: kaizenFiles.queries || null,
      }).catch(() => null);

      if (response === null) {
        setDetectedIncidentCount(0);
        setDetectedIncidentStats([]);
        setTemplateIncidentScripts(INCIDENT_SCRIPTS);
        setSelectedIncidents(ALL_INCIDENTS);
        return;
      }

      const incidentMap = new Map<string, string>();
      const stats = response.incidents.map((incident) => ({
        code: incident.code,
        description: incident.description,
        errorsCount: incident.errorsCount,
        queriesCount: incident.queriesCount,
      }));
      for (const stat of stats) {
        if (INCIDENT_CODE_RE.test(stat.code)) {
          incidentMap.set(stat.code, stat.description || "");
        }
      }

      if (cancelled) {
        return;
      }

      const nextScripts = buildTemplateIncidentScripts(incidentMap);
      setTemplateIncidentScripts(nextScripts);
      setDetectedIncidentCount(response.totalIncidents);
      setDetectedIncidentStats(stats.sort((a, b) => incidentSort(a.code, b.code)));
      setSelectedIncidents(flattenIncidentSelection(nextScripts));
    }

    void detectIncidents();
    return () => {
      cancelled = true;
    };
  }, [kaizenFiles]);

  const mutation = useMutation({
    mutationFn: runValidation,
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const onSubmit = (values: UtilityBaseValues) => {
    mutation.mutate({
      scriptName: "accuracy_template_generator",
      testingPeriod: values.testingPeriod,
      mode: "batch",
      batchConfig: {
        inputDirectory: resolvedPaths?.kaizen ?? "",
        outputDirectory: resolvedPaths?.templates ?? "",
        templateDirectory: "",
        incidentCodes: selectedIncidents.map((incident) => incident.incidentCode),
        logOutput: resolvedPaths?.logs || defaultLogsDir,
      },
      logLevel: values.logLevel,
      dryRun: values.dryRun,
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-2xl">
      <p className="text-sm text-muted-foreground">
        Generate accuracy testing template files for selected incidents.
      </p>

      {/* Testing Period */}
      <div>
        <p className="text-xs font-medium text-muted-foreground mb-2">Testing Period</p>
        <Controller
          name="testingPeriod"
          control={control}
          render={({ field }) => (
            <TestingPeriodSelector value={field.value} onChange={field.onChange} disabled={isPending} />
          )}
        />
      </div>

      {/* Smart Path Config â€” includes Kaizen dir */}
      <SmartPathConfig
        fiscalYear={testingPeriod.fiscalYear}
        quarter={testingPeriod.quarter}
        module="accuracy_testing"
        onChange={handlePathsResolved}
        disabled={isPending}
      />

      {/* Auto-discovered consolidated CSVs from Kaizen dir */}
      {kaizenFiles !== null && (
        <div className="rounded-md border border-border px-3 py-3 space-y-2">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Consolidated Source Files (Kaizen)
          </p>
          <div className="space-y-1 text-xs font-mono">
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "h-2 w-2 rounded-full shrink-0",
                  kaizenFiles.errors ? "bg-green-500" : "bg-orange-400",
                )}
              />
              <span className="text-muted-foreground shrink-0">Errors</span>
              <span className="truncate text-foreground/80">
                {kaizenFiles.errors || "not found"}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "h-2 w-2 rounded-full shrink-0",
                  kaizenFiles.queries ? "bg-green-500" : "bg-orange-400",
                )}
              />
              <span className="text-muted-foreground shrink-0">Queries</span>
              <span className="truncate text-foreground/80">
                {kaizenFiles.queries || "not found"}
              </span>
            </div>
          </div>
          {detectedIncidentCount > 0 && (
            <div className="space-y-2">
              <p className="text-[11px] text-muted-foreground">
                Detected {detectedIncidentCount} incident code(s) from consolidated files.
              </p>
              {detectedIncidentStats.length > 0 && (
                <div className="rounded-md border border-border/80 bg-muted/20 px-2 py-2 space-y-1.5">
                  <div className="grid grid-cols-[auto_1fr_auto_auto_auto] gap-2 text-[10px] uppercase tracking-wide text-muted-foreground font-semibold">
                    <span>Code</span>
                    <span>Description</span>
                    <span className="text-right">Errors</span>
                    <span className="text-right">Queries</span>
                    <span className="text-right">Total</span>
                  </div>
                  {detectedIncidentStats.map((stat) => {
                    const total = stat.errorsCount + stat.queriesCount;
                    const sources: string[] = [];
                    if (stat.errorsCount > 0 && kaizenFiles.errors) {
                      sources.push(`Errors: ${fileNameOnly(kaizenFiles.errors)}`);
                    }
                    if (stat.queriesCount > 0 && kaizenFiles.queries) {
                      sources.push(`Queries: ${fileNameOnly(kaizenFiles.queries)}`);
                    }
                    return (
                      <div key={stat.code} className="space-y-0.5">
                        <div className="grid grid-cols-[auto_1fr_auto_auto_auto] gap-2 text-xs items-center">
                          <span className="font-mono text-foreground">{stat.code}</span>
                          <span className="truncate text-foreground/80">{stat.description || "Detected Incident"}</span>
                          <span className="text-right font-mono text-foreground/80">{stat.errorsCount}</span>
                          <span className="text-right font-mono text-foreground/80">{stat.queriesCount}</span>
                          <span className="text-right font-mono text-foreground">{total}</span>
                        </div>
                        {sources.length > 0 && (
                          <p className="text-[10px] text-muted-foreground truncate">{sources.join(" | ")}</p>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Incident Checklist */}
      <IncidentChecklist
        scripts={templateIncidentScripts}
        selected={selectedIncidents}
        onChange={setSelectedIncidents}
        disabled={isPending}
      />

      {/* Incident File Table â€” output only, collapsible */}
      <IncidentFileTable
        incidents={selectedIncidents}
        resolvedPaths={resolvedPaths}
        fiscalYear={testingPeriod.fiscalYear}
        quarter={testingPeriod.quarter}
        value={incidentConfigs}
        onChange={setIncidentConfigs}
        columns={["output"]}
        outputDirKey="templates"
        outputFileSuffix="template.csv"
        disabled={isPending}
      />

      {/* Preview */}
      <IncidentPreview
        configs={incidentConfigs}
        fiscalYear={testingPeriod.fiscalYear}
        quarter={testingPeriod.quarter}
      />

      <AdvancedSection isOpen={showAdvanced} onToggle={() => setShowAdvanced(!showAdvanced)}>
        <div className="flex flex-wrap gap-4 items-end">
          <Field label="Log Level" hint="Logging verbosity level." error={errors.logLevel?.message}>
            <select {...register("logLevel")} disabled={isPending} className={cn(selectCls, "w-40")}>
              {LOG_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
          </Field>
          <label className="flex items-center gap-2 cursor-pointer text-sm pb-1">
            <input type="checkbox" {...register("dryRun")} disabled={isPending} className="accent-primary h-4 w-4" />
            Dry Run
          </label>
        </div>
      </AdvancedSection>

      <Button type="submit" disabled={isPending || selectedIncidents.length === 0} className="w-full">
        {isPending ? "Runningâ€¦" : "Run"}
      </Button>
    </form>
  );
};

// ---------------------------------------------------------------------------
// Extract Generator Form
// ---------------------------------------------------------------------------

const extractGenSchema = z.object({
  testingPeriod: z.object({ fiscalYear: z.string(), quarter: z.string() }),
  logLevel: z.string(),
  dryRun: z.boolean(),
  batchSize: z.coerce.number().int().min(1),
  column: z.string().optional(),
  outputFormat: z.enum(["sql", "dtf", "both"]),
  dtfTemplate: z.string().optional(),
  sqlOutputDir: z.string().optional(),
  dtfOutputDir: z.string().optional(),
  csvOutputDir: z.string().optional(),
});

type ExtractGenValues = z.infer<typeof extractGenSchema>;

/** Build the three extract output subdirectory paths from a base extracts dir. */
function buildExtractDirs(extractsBase: string): { sql: string; dtf: string; csv: string } {
  const base = extractsBase.replace(/\/+$/, "");
  return { sql: `${base}/sql`, dtf: `${base}/dtf`, csv: `${base}/csv` };
}

const ExtractGeneratorForm: React.FC = () => {
  const navigate = useNavigate();
  const [selectedIncidents, setSelectedIncidents] = useState<IncidentSelection[]>(ALL_INCIDENTS);
  const [incidentConfigs, setIncidentConfigs] = useState<IncidentRunConfig[]>([]);
  const [resolvedPaths, setResolvedPaths] = useState<ResolvedPaths | null>(null);
  const [derivedDirs, setDerivedDirs] = useState<{ sql: string; dtf: string; csv: string } | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const { control, register, handleSubmit, watch, setValue, formState: { errors } } = useForm<ExtractGenValues>({
    resolver: zodResolver(extractGenSchema) as Resolver<ExtractGenValues>,
    defaultValues: loadCache("accuracy_utility_extract_gen", {
      testingPeriod: { fiscalYear: currentFY(), quarter: "Q1" },
      logLevel: "INFO",
      dryRun: false,
      batchSize: 900,
      column: "",
      outputFormat: "both" as const,
      dtfTemplate: "",
      sqlOutputDir: "",
      dtfOutputDir: "",
      csvOutputDir: "",
    }),
  });

  useEffect(() => {
    const sub = watch((values) => {
      try { localStorage.setItem("txr_form_accuracy_utility_extract_gen", JSON.stringify(values)); } catch { /* ignore */ }
    });
    return () => sub.unsubscribe();
  }, [watch]);

  const testingPeriod = watch("testingPeriod");

  // Auto-fill sql/dtf/csv output dirs from SmartPathConfig extracts dir.
  const handlePathsResolved = useCallback(
    (paths: ResolvedPaths) => {
      setResolvedPaths(paths);
      if (paths.extracts) {
        const dirs = buildExtractDirs(paths.extracts);
        setDerivedDirs(dirs);
        if (!watch("sqlOutputDir")) setValue("sqlOutputDir", dirs.sql);
        if (!watch("dtfOutputDir")) setValue("dtfOutputDir", dirs.dtf);
        if (!watch("csvOutputDir")) setValue("csvOutputDir", dirs.csv);
      }
    },
    [setValue, watch],
  );

  const mutation = useMutation({
    mutationFn: runValidation,
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const onSubmit = (values: ExtractGenValues) => {
    mutation.mutate({
      scriptName: "sql_extract_generator",
      testingPeriod: values.testingPeriod,
      mode: "batch",
      batchConfig: {
        inputDirectory: resolvedPaths?.extracts ?? "",
        outputDirectory: values.sqlOutputDir ?? derivedDirs?.sql ?? "",
        templateDirectory: "",
        logOutput: resolvedPaths?.logs || defaultLogsDir,
      },
      logLevel: values.logLevel,
      dryRun: values.dryRun,
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-2xl">
      <p className="text-sm text-muted-foreground">
        Generate SQL/DTF extract scripts for selected incidents.
      </p>

      {/* Testing Period */}
      <div>
        <p className="text-xs font-medium text-muted-foreground mb-2">Testing Period</p>
        <Controller
          name="testingPeriod"
          control={control}
          render={({ field }) => (
            <TestingPeriodSelector value={field.value} onChange={field.onChange} disabled={isPending} />
          )}
        />
      </div>

      {/* Smart Path Config */}
      <SmartPathConfig
        fiscalYear={testingPeriod.fiscalYear}
        quarter={testingPeriod.quarter}
        module="accuracy_testing"
        onChange={handlePathsResolved}
        disabled={isPending}
      />

      {/* Derived extract output subdirectories */}
      {derivedDirs && (
        <div className="rounded-md border border-border px-3 py-3 space-y-2">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Extract Output Directories
          </p>
          <div className="space-y-0.5">
            {(["sql", "dtf", "csv"] as const).map((fmt) => (
              <div key={fmt} className="flex items-center justify-between gap-2">
                <span className="text-xs font-medium text-muted-foreground uppercase w-8 shrink-0">
                  {fmt}
                </span>
                <span className="truncate text-xs text-foreground/80 font-mono">
                  {watch(`${fmt}OutputDir` as keyof ExtractGenValues) as string || derivedDirs[fmt]}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Incident Checklist */}
      <IncidentChecklist
        scripts={INCIDENT_SCRIPTS}
        selected={selectedIncidents}
        onChange={setSelectedIncidents}
        disabled={isPending}
      />

      {/* Incident File Table â€” input only, collapsible */}
      <IncidentFileTable
        incidents={selectedIncidents}
        resolvedPaths={resolvedPaths}
        fiscalYear={testingPeriod.fiscalYear}
        quarter={testingPeriod.quarter}
        value={incidentConfigs}
        onChange={setIncidentConfigs}
        columns={["input"]}
        disabled={isPending}
        showValuesBadge
      />

      <AdvancedSection isOpen={showAdvanced} onToggle={() => setShowAdvanced(!showAdvanced)}>
        <div className="flex flex-wrap gap-4 items-end">
          <Field label="Batch Size" hint="Max transaction refs per SQL file." error={errors.batchSize?.message}>
            <input
              type="number"
              {...register("batchSize", { valueAsNumber: true })}
              disabled={isPending}
              className={cn(selectCls, "w-28")}
            />
          </Field>
          <Field label="Column" hint="Transaction ref column name (optional)." error={errors.column?.message}>
            <input
              type="text"
              {...register("column")}
              disabled={isPending}
              className={cn(selectCls, "w-44")}
              placeholder="auto-detect"
            />
          </Field>
          <Field label="Output Format" error={errors.outputFormat?.message}>
            <select {...register("outputFormat")} disabled={isPending} className={cn(selectCls, "w-32")}>
              <option value="both">Both</option>
              <option value="sql">SQL only</option>
              <option value="dtf">DTF only</option>
            </select>
          </Field>
          <Field label="DTF Template" hint="Path to DTF template file." error={errors.dtfTemplate?.message}>
            <PathPickerInput
              value={watch("dtfTemplate") ?? ""}
              onChange={(v) => setValue("dtfTemplate", v)}
              mode="file"
              placeholder="optional"
              disabled={isPending}
            />
          </Field>
          <Field label="SQL Output Dir" hint="Override auto-derived sql/ subdirectory." error={errors.sqlOutputDir?.message}>
            <PathPickerInput
              value={watch("sqlOutputDir") ?? ""}
              onChange={(v) => setValue("sqlOutputDir", v)}
              mode="directory"
              placeholder={derivedDirs?.sql ?? "auto"}
              disabled={isPending}
            />
          </Field>
          <Field label="DTF Output Dir" hint="Override auto-derived dtf/ subdirectory." error={errors.dtfOutputDir?.message}>
            <PathPickerInput
              value={watch("dtfOutputDir") ?? ""}
              onChange={(v) => setValue("dtfOutputDir", v)}
              mode="directory"
              placeholder={derivedDirs?.dtf ?? "auto"}
              disabled={isPending}
            />
          </Field>
          <Field label="CSV Output Dir" hint="System i output path (embedded in DTF)." error={errors.csvOutputDir?.message}>
            <PathPickerInput
              value={watch("csvOutputDir") ?? ""}
              onChange={(v) => setValue("csvOutputDir", v)}
              mode="directory"
              placeholder={derivedDirs?.csv ?? "auto"}
              disabled={isPending}
            />
          </Field>
          <Field label="Log Level" hint="Logging verbosity level." error={errors.logLevel?.message}>
            <select {...register("logLevel")} disabled={isPending} className={cn(selectCls, "w-40")}>
              {LOG_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
          </Field>
          <label className="flex items-center gap-2 cursor-pointer text-sm pb-1">
            <input type="checkbox" {...register("dryRun")} disabled={isPending} className="accent-primary h-4 w-4" />
            Dry Run
          </label>
        </div>
      </AdvancedSection>

      <Button type="submit" disabled={isPending} className="w-full">
        {isPending ? "Runningâ€¦" : "Run"}
      </Button>
    </form>
  );
};

// ---------------------------------------------------------------------------
// Collate CSV Extracts Form
// ---------------------------------------------------------------------------

const CollateExtractsForm: React.FC = () => {
  const navigate = useNavigate();
  const [incidentConfigs, setIncidentConfigs] = useState<IncidentRunConfig[]>([]);
  const [resolvedPaths, setResolvedPaths] = useState<ResolvedPaths | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const { control, register, handleSubmit, watch, formState: { errors } } = useForm<UtilityBaseValues>({
    resolver: zodResolver(utilityBaseSchema),
    defaultValues: loadCache("accuracy_utility_collate", {
      testingPeriod: { fiscalYear: currentFY(), quarter: "Q1" },
      logLevel: "INFO",
      dryRun: false,
    }),
  });

  useEffect(() => {
    const sub = watch((values) => {
      try { localStorage.setItem("txr_form_accuracy_utility_collate", JSON.stringify(values)); } catch { /* ignore */ }
    });
    return () => sub.unsubscribe();
  }, [watch]);

  const testingPeriod = watch("testingPeriod");

  const mutation = useMutation({
    mutationFn: runValidation,
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const onSubmit = (values: UtilityBaseValues) => {
    mutation.mutate({
      scriptName: "collate_csv_extracts",
      testingPeriod: values.testingPeriod,
      mode: "batch",
      batchConfig: {
        inputDirectory: resolvedPaths?.extracts ?? "",
        outputDirectory: resolvedPaths?.extracts ?? "",
        templateDirectory: "",
        logOutput: resolvedPaths?.logs || defaultLogsDir,
      },
      logLevel: values.logLevel,
      dryRun: values.dryRun,
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-2xl">
      <p className="text-sm text-muted-foreground">
        Collate split CSV extract files per incident. Auto-discovers split files by incident code.
      </p>

      {/* Testing Period */}
      <div>
        <p className="text-xs font-medium text-muted-foreground mb-2">Testing Period</p>
        <Controller
          name="testingPeriod"
          control={control}
          render={({ field }) => (
            <TestingPeriodSelector value={field.value} onChange={field.onChange} disabled={isPending} />
          )}
        />
      </div>

      {/* Smart Path Config */}
      <SmartPathConfig
        fiscalYear={testingPeriod.fiscalYear}
        quarter={testingPeriod.quarter}
        module="accuracy_testing"
        onChange={setResolvedPaths}
        disabled={isPending}
      />

      {/* Incident File Table â€” output only, collated files go back to Extracts */}
      <IncidentFileTable
        incidents={ALL_INCIDENTS}
        resolvedPaths={resolvedPaths}
        fiscalYear={testingPeriod.fiscalYear}
        quarter={testingPeriod.quarter}
        value={incidentConfigs}
        onChange={setIncidentConfigs}
        columns={["output"]}
        outputDirKey="extracts"
        outputFileSuffix="extract.csv"
        disabled={isPending}
      />

      <AdvancedSection isOpen={showAdvanced} onToggle={() => setShowAdvanced(!showAdvanced)}>
        <div className="flex flex-wrap gap-4 items-end">
          <Field label="Log Level" hint="Logging verbosity level." error={errors.logLevel?.message}>
            <select {...register("logLevel")} disabled={isPending} className={cn(selectCls, "w-40")}>
              {LOG_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
          </Field>
          <label className="flex items-center gap-2 cursor-pointer text-sm pb-1">
            <input type="checkbox" {...register("dryRun")} disabled={isPending} className="accent-primary h-4 w-4" />
            Dry Run
          </label>
        </div>
      </AdvancedSection>

      <Button type="submit" disabled={isPending} className="w-full">
        {isPending ? "Runningâ€¦" : "Run"}
      </Button>
    </form>
  );
};

// ---------------------------------------------------------------------------
// Data Push Form
// ---------------------------------------------------------------------------

const DataPushForm: React.FC = () => {
  const navigate = useNavigate();
  const [selectedIncidents, setSelectedIncidents] = useState<IncidentSelection[]>(ALL_INCIDENTS);
  const [incidentConfigs, setIncidentConfigs] = useState<IncidentRunConfig[]>([]);
  const [resolvedPaths, setResolvedPaths] = useState<ResolvedPaths | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const { control, register, handleSubmit, watch, formState: { errors } } = useForm<UtilityBaseValues>({
    resolver: zodResolver(utilityBaseSchema),
    defaultValues: loadCache("accuracy_utility_data_push", {
      testingPeriod: { fiscalYear: currentFY(), quarter: "Q1" },
      logLevel: "INFO",
      dryRun: false,
    }),
  });

  useEffect(() => {
    const sub = watch((values) => {
      try { localStorage.setItem("txr_form_accuracy_utility_data_push", JSON.stringify(values)); } catch { /* ignore */ }
    });
    return () => sub.unsubscribe();
  }, [watch]);

  const testingPeriod = watch("testingPeriod");

  const mutation = useMutation({
    mutationFn: runValidation,
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const onSubmit = (values: UtilityBaseValues) => {
    if (!resolvedPaths?.output || !resolvedPaths?.templates) {
      toast.error("Paths have not resolved yet â€” please wait for the Directories section to load.");
      return;
    }
    mutation.mutate({
      scriptName: "data_push",
      testingPeriod: values.testingPeriod,
      mode: "batch",
      batchConfig: {
        inputDirectory: resolvedPaths.output,
        outputDirectory: resolvedPaths.templates,
        templateDirectory: "",
        logOutput: resolvedPaths?.logs || defaultLogsDir,
      },
      logLevel: values.logLevel,
      dryRun: values.dryRun,
    });
  };

  const isPending = mutation.isPending;
  const pathsReady = !!(resolvedPaths?.output && resolvedPaths?.templates);

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-2xl">
      <p className="text-sm text-muted-foreground">
        Push validated data back into template files for selected incidents.
      </p>

      {/* Testing Period */}
      <div>
        <p className="text-xs font-medium text-muted-foreground mb-2">Testing Period</p>
        <Controller
          name="testingPeriod"
          control={control}
          render={({ field }) => (
            <TestingPeriodSelector value={field.value} onChange={field.onChange} disabled={isPending} />
          )}
        />
      </div>

      {/* Smart Path Config */}
      <SmartPathConfig
        fiscalYear={testingPeriod.fiscalYear}
        quarter={testingPeriod.quarter}
        module="accuracy_testing"
        onChange={setResolvedPaths}
        disabled={isPending}
      />

      {/* Incident Checklist */}
      <IncidentChecklist
        scripts={INCIDENT_SCRIPTS}
        selected={selectedIncidents}
        onChange={setSelectedIncidents}
        disabled={isPending}
      />

      {/* Incident File Table â€” input (validated CSV) + output (template overwritten) */}
      <IncidentFileTable
        incidents={selectedIncidents}
        resolvedPaths={resolvedPaths}
        fiscalYear={testingPeriod.fiscalYear}
        quarter={testingPeriod.quarter}
        value={incidentConfigs}
        onChange={setIncidentConfigs}
        columns={["input", "output"]}
        disabled={isPending}
      />

      <AdvancedSection isOpen={showAdvanced} onToggle={() => setShowAdvanced(!showAdvanced)}>
        <div className="flex flex-wrap gap-4 items-end">
          <Field label="Log Level" hint="Logging verbosity level." error={errors.logLevel?.message}>
            <select {...register("logLevel")} disabled={isPending} className={cn(selectCls, "w-40")}>
              {LOG_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
          </Field>
          <label className="flex items-center gap-2 cursor-pointer text-sm pb-1">
            <input type="checkbox" {...register("dryRun")} disabled={isPending} className="accent-primary h-4 w-4" />
            Dry Run
          </label>
        </div>
      </AdvancedSection>

      <Button type="submit" disabled={isPending || !pathsReady} className="w-full">
        {isPending ? "Runningâ€¦" : !pathsReady ? "Waiting for pathsâ€¦" : "Run"}
      </Button>
    </form>
  );
};

// ---------------------------------------------------------------------------
// Main AccuracyTesting page
// ---------------------------------------------------------------------------

const UTILITY_FORM_MAP: Record<string, React.FC> = {
  accuracy_template_generator: TemplateGeneratorForm,
  sql_extract_generator: ExtractGeneratorForm,
  collate_csv_extracts: CollateExtractsForm,
  data_push: DataPushForm,
};

const AccuracyTesting: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ActiveTab>("validation");
  const [selectedUtility, setSelectedUtility] = useState<string>(UTILITY_NAV[0].key);

  const selectedNav = UTILITY_NAV.find((u) => u.key === selectedUtility) ?? UTILITY_NAV[0];
  const UtilityForm = UTILITY_FORM_MAP[selectedNav.key];

  return (
    <div className="space-y-6">
      {/* Page heading */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Accuracy Testing</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Run validation scripts and utilities for accuracy testing.
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-border">
        {(["validation", "utilities"] as const).map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={cn(
              "px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors",
              activeTab === tab
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {tab === "validation" ? "Validation Scripts" : "Utilities"}
          </button>
        ))}
      </div>

      {/* Validation Scripts tab */}
      {activeTab === "validation" && (
        <div className="rounded-lg border border-border p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold">Validation Scripts</h2>
            <LastRunBadge scriptName="run_all_validations" />
          </div>
          <UnifiedValidationForm />
        </div>
      )}

      {/* Utilities tab */}
      {activeTab === "utilities" && (
        <div className="flex gap-6 min-h-[400px]">
          {/* Sidebar */}
          <nav className="w-60 shrink-0 space-y-1">
            {UTILITY_NAV.map((u) => (
              <button
                key={u.key}
                type="button"
                onClick={() => setSelectedUtility(u.key)}
                className={navItemCls(selectedUtility === u.key)}
              >
                {u.label}
              </button>
            ))}
          </nav>

          {/* Panel */}
          <div className="flex-1 min-w-0 rounded-lg border border-border p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold">{selectedNav.label}</h2>
              <LastRunBadge scriptName={selectedNav.key} />
            </div>
            {UtilityForm && <UtilityForm key={selectedUtility} />}
          </div>
        </div>
      )}
    </div>
  );
};

export default AccuracyTesting;

