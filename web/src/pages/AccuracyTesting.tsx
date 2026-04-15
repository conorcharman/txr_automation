import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import TestingPeriodSelector from "@/components/TestingPeriodSelector";
import ConfigLoader from "@/components/ConfigLoader";
import { PathPickerInput } from "@/components/PathPickerInput";
import SmartPathConfig from "@/components/SmartPathConfig";
import LastRunBadge from "@/components/LastRunBadge";
import Field from "@/components/Field";
import { runValidation, runAllValidations, discoverIncidents } from "@/api/accuracy";
import { cn } from "@/lib/utils";
import type { DiscoveryResponse, ResolvedPaths } from "@/types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"] as const;

const VALIDATION_SCRIPTS = [
  { key: "buyer_id_validation", label: "Buyer ID Validation" },
  { key: "seller_id_validation", label: "Seller ID Validation" },
  { key: "inconsistent_buyer_id", label: "Inconsistent Buyer ID" },
  { key: "inconsistent_seller_id", label: "Inconsistent Seller ID" },
  { key: "fund_trade_buyer_dm", label: "Fund Trade Buyer DM" },
  { key: "fund_trade_seller_dm", label: "Fund Trade Seller DM" },
  { key: "incorrect_net_amount", label: "Incorrect Net Amount" },
  { key: "non_zero_net_quantity", label: "Non-Zero Net Quantity" },
  { key: "non_zero_net_amount", label: "Non-Zero Net Amount" },
] as const;

type ActiveTab = "validation" | "utilities";

function currentFY(): string {
  return `FY${String(new Date().getFullYear()).slice(-2)}`;
}

// ---------------------------------------------------------------------------
// Shared styles
// ---------------------------------------------------------------------------

const inputCls =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm " +
  "focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50 " +
  "placeholder:text-muted-foreground";

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
      <span className={cn("transition-transform text-[10px]", isOpen && "rotate-180")}>▾</span>
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
// Unified Validation Form
// ---------------------------------------------------------------------------

const unifiedSchema = z.object({
  testingPeriod: z.object({ fiscalYear: z.string(), quarter: z.string() }),
  mode: z.enum(["batch", "single"]),
  // Batch fields (auto-filled by SmartPathConfig)
  inputDirectory: z.string().optional(),
  outputDirectory: z.string().optional(),
  templateDirectory: z.string().optional(),
  // Single fields (only when exactly 1 incident selected + single mode)
  incidentCode: z.string().optional(),
  inputFile: z.string().optional(),
  templateFile: z.string().optional(),
  outputFile: z.string().optional(),
  // Common
  logLevel: z.string(),
  dryRun: z.boolean(),
  stopOnError: z.boolean(),
});

type UnifiedFormValues = z.infer<typeof unifiedSchema>;

const UnifiedValidationForm: React.FC = () => {
  const navigate = useNavigate();
  const [selectedTypes, setSelectedTypes] = useState<string[]>(
    VALIDATION_SCRIPTS.map((s) => s.key),
  );
  const [discoveryResult, setDiscoveryResult] = useState<DiscoveryResponse | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const {
    control,
    register,
    handleSubmit,
    watch,
    setValue,
    getValues,
    reset,
    formState: { errors },
  } = useForm<UnifiedFormValues>({
    resolver: zodResolver(unifiedSchema),
    defaultValues: loadCache("accuracy_validation_unified", {
      testingPeriod: { fiscalYear: currentFY(), quarter: "Q1" },
      mode: "batch" as const,
      inputDirectory: "",
      outputDirectory: "",
      templateDirectory: "",
      incidentCode: "",
      inputFile: "",
      templateFile: "",
      outputFile: "",
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
  const mode = watch("mode");
  const inputDirectory = watch("inputDirectory");
  const outputDirectory = watch("outputDirectory");

  // Auto-switch to batch when >1 incident selected.
  useEffect(() => {
    if (selectedTypes.length > 1 && mode === "single") {
      setValue("mode", "batch");
    }
  }, [selectedTypes.length, mode, setValue]);

  // Auto-fill incident code when single mode + exactly 1 incident.
  useEffect(() => {
    if (mode === "single" && selectedTypes.length === 1) {
      const incidentLabel = VALIDATION_SCRIPTS.find((s) => s.key === selectedTypes[0])?.label ?? "";
      setValue("incidentCode", incidentLabel);
    }
  }, [mode, selectedTypes, setValue]);

  const singleModeAllowed = selectedTypes.length === 1;

  const handlePathsResolved = useCallback(
    (paths: ResolvedPaths) => {
      setValue("inputDirectory", paths.extracts);
      setValue("outputDirectory", paths.output);
      setValue("templateDirectory", paths.templates);
    },
    [setValue],
  );

  const outputFilenamePreview = useMemo(() => {
    const { fiscalYear, quarter } = testingPeriod;
    const today = new Date();
    const dateStr = today.toISOString().slice(0, 10).replace(/-/g, "");
    return `${fiscalYear}_${quarter}_all_validations_${dateStr}.csv`;
  }, [testingPeriod]);

  const mutation = useMutation({
    mutationFn: (args: { isBatch: boolean; values: UnifiedFormValues }) => {
      if (args.isBatch) {
        return runAllValidations({
          testingPeriod: args.values.testingPeriod,
          validationTypes: selectedTypes,
          selectedScripts: selectedTypes,
          inputDirectory: args.values.inputDirectory ?? "",
          outputDirectory: args.values.outputDirectory ?? "",
          templateDirectory: args.values.templateDirectory ?? "",
          logOutput: ((): string => { try { return localStorage.getItem("txr_global_log_output") || "logs"; } catch { return "logs"; } })(),
          logLevel: args.values.logLevel,
          dryRun: args.values.dryRun,
          stopOnError: args.values.stopOnError || undefined,
        });
      }
      // Single incident + single mode
      return runValidation({
        scriptName: selectedTypes[0],
        testingPeriod: args.values.testingPeriod,
        mode: "single",
        singleConfig: {
          incidentCode: args.values.incidentCode ?? "",
          inputFile: args.values.inputFile ?? "",
          templateFile: args.values.templateFile ?? "",
          outputFile: args.values.outputFile ?? "",
        },
        logLevel: args.values.logLevel,
        dryRun: args.values.dryRun,
      });
    },
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const discoveryMutation = useMutation({
    mutationFn: discoverIncidents,
    onSuccess: (result) => {
      setDiscoveryResult(result);
      const foundTypes = result.results
        .filter((r) => r.foundFiles.length > 0)
        .map((r) => r.scriptName);
      if (foundTypes.length > 0) {
        setSelectedTypes(foundTypes);
      }
      toast.success(`Found ${result.totalFound} file(s) across ${foundTypes.length} script(s)`);
    },
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Discovery failed");
    },
  });

  const onSubmit = (values: UnifiedFormValues) => {
    const isBatch = values.mode === "batch" || selectedTypes.length > 1;
    mutation.mutate({ isBatch, values });
  };

  const toggleType = (key: string) => {
    setSelectedTypes((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );
  };

  const allSelected = selectedTypes.length === VALIDATION_SCRIPTS.length;
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
        onChange={handlePathsResolved}
        disabled={isPending}
      />

      {/* Validation type checklist */}
      <div className="rounded-lg border border-border p-4 space-y-2">
        <div className="flex items-center justify-between mb-1">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Validation Scripts
          </p>
          <button
            type="button"
            onClick={() =>
              setSelectedTypes(
                allSelected ? [] : VALIDATION_SCRIPTS.map((s) => s.key),
              )
            }
            className="text-xs text-primary hover:underline"
          >
            {allSelected ? "Deselect All" : "Select All"}
          </button>
        </div>
        {VALIDATION_SCRIPTS.map((s) => (
          <label key={s.key} className="flex items-center gap-2 cursor-pointer text-sm">
            <input
              type="checkbox"
              checked={selectedTypes.includes(s.key)}
              onChange={() => toggleType(s.key)}
              disabled={isPending}
              className="accent-primary h-4 w-4"
            />
            {s.label}
          </label>
        ))}
      </div>

      {/* Discover Files */}
      <Button
        type="button"
        variant="outline"
        disabled={!inputDirectory || discoveryMutation.isPending}
        onClick={() => discoveryMutation.mutate({ inputDirectory: inputDirectory ?? "" })}
        className="w-full"
      >
        {discoveryMutation.isPending ? "Scanning…" : "Discover Files"}
      </Button>

      {discoveryResult && (
        <div className="rounded-lg border border-border p-4 space-y-2 text-sm">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Discovery Results — {discoveryResult.totalFound} file(s) found
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
                {VALIDATION_SCRIPTS.find((s) => s.key === r.scriptName)?.label ?? r.scriptName}
              </span>
              <span className="ml-auto text-xs text-muted-foreground">
                {r.foundFiles.length} file(s)
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Mode selector */}
      <div className="flex flex-col gap-1">
        <p className="text-xs font-medium text-muted-foreground">Mode</p>
        <div className="flex gap-4">
          {(["batch", "single"] as const).map((m) => (
            <label
              key={m}
              className={cn(
                "flex items-center gap-2 cursor-pointer text-sm",
                m === "single" && !singleModeAllowed && "opacity-50 cursor-not-allowed",
              )}
            >
              <input
                type="radio"
                value={m}
                {...register("mode")}
                disabled={isPending || (m === "single" && !singleModeAllowed)}
                className="accent-primary"
              />
              {m.charAt(0).toUpperCase() + m.slice(1)}
            </label>
          ))}
        </div>
        {!singleModeAllowed && (
          <p className="text-[11px] text-muted-foreground">
            Single mode is only available when exactly one validation script is selected.
          </p>
        )}
      </div>

      {/* Batch fields */}
      {(mode === "batch" || selectedTypes.length > 1) && (
        <div className="space-y-3 rounded-lg border border-border p-4">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Batch Config
          </p>
          <Field label="Input Directory" hint="Directory containing per-incident extract CSVs." error={errors.inputDirectory?.message}>
            <PathPickerInput
              value={watch("inputDirectory") ?? ""}
              onChange={(v) => setValue("inputDirectory", v)}
              mode="directory"
              placeholder="/path/to/input"
              disabled={isPending}
            />
          </Field>
          <Field label="Output Directory" hint="Directory for validated output CSVs." error={errors.outputDirectory?.message}>
            <PathPickerInput
              value={watch("outputDirectory") ?? ""}
              onChange={(v) => setValue("outputDirectory", v)}
              mode="directory"
              placeholder="/path/to/output"
              disabled={isPending}
            />
          </Field>
          <Field label="Template Directory" hint="Directory containing Kaizen template CSVs." error={errors.templateDirectory?.message}>
            <PathPickerInput
              value={watch("templateDirectory") ?? ""}
              onChange={(v) => setValue("templateDirectory", v)}
              mode="directory"
              placeholder="/path/to/templates"
              disabled={isPending}
            />
          </Field>

          {outputDirectory && (
            <p className="text-xs text-muted-foreground">
              Output file:{" "}
              <code className="font-mono bg-muted px-1 py-0.5 rounded">{outputFilenamePreview}</code>
            </p>
          )}
        </div>
      )}

      {/* Single fields */}
      {mode === "single" && singleModeAllowed && (
        <div className="space-y-3 rounded-lg border border-border p-4">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Single Config
          </p>
          <Field label="Incident Code" hint="Incident code to validate, e.g. 7_39." error={errors.incidentCode?.message}>
            <input
              {...register("incidentCode")}
              disabled={isPending}
              className={inputCls}
              placeholder="e.g. 7_39"
            />
          </Field>
          <Field label="Input File" hint="Path to the extract CSV file for this incident." error={errors.inputFile?.message}>
            <PathPickerInput
              value={watch("inputFile") ?? ""}
              onChange={(v) => setValue("inputFile", v)}
              mode="file"
              placeholder="/path/to/input.csv"
              disabled={isPending}
            />
          </Field>
          <Field label="Template File" hint="Path to the Kaizen template CSV file." error={errors.templateFile?.message}>
            <PathPickerInput
              value={watch("templateFile") ?? ""}
              onChange={(v) => setValue("templateFile", v)}
              mode="file"
              placeholder="/path/to/template.csv"
              disabled={isPending}
            />
          </Field>
          <Field label="Output File" hint="Path for the validation results output file." error={errors.outputFile?.message}>
            <PathPickerInput
              value={watch("outputFile") ?? ""}
              onChange={(v) => setValue("outputFile", v)}
              mode="file"
              placeholder="/path/to/output.csv"
              disabled={isPending}
            />
          </Field>
        </div>
      )}

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
        disabled={isPending || selectedTypes.length === 0}
        className="w-full"
      >
        {isPending ? "Running…" : selectedTypes.length > 1 ? "Run Selected" : "Run"}
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
// Utility Script Form
// ---------------------------------------------------------------------------

interface UtilityFieldConfig {
  name: "inputDirectory" | "outputDirectory" | "templateDirectory" | "outputFile";
  label: string;
  placeholder: string;
  type: "file" | "directory";
}

interface UtilityConfig {
  key: string;
  label: string;
  description: string;
  fields: UtilityFieldConfig[];
  needsPeriod: boolean;
}

const UTILITY_CONFIGS: UtilityConfig[] = [
  {
    key: "sql_extract_generator",
    label: "SQL Extract Generator",
    description: "Generate SQL extract scripts for a given testing period.",
    fields: [
      { name: "outputDirectory", label: "Output Directory", placeholder: "/path/to/output", type: "directory" },
    ],
    needsPeriod: true,
  },
  {
    key: "accuracy_template_generator",
    label: "Accuracy Template Generator",
    description: "Generate accuracy testing template files. The input directory must contain consolidated_errors.csv and/or consolidated_queries.csv.",
    fields: [
      {
        name: "inputDirectory",
        label: "Input Directory",
        placeholder: "/path/to/consolidated",
        type: "directory",
      },
      {
        name: "outputDirectory",
        label: "Output Directory",
        placeholder: "/path/to/output",
        type: "directory",
      },
    ],
    needsPeriod: true,
  },
  {
    key: "collate_csv_extracts",
    label: "Collate CSV Extracts",
    description: "Collate CSV extract files from an input directory into a single output file.",
    fields: [
      {
        name: "inputDirectory",
        label: "Input Directory",
        placeholder: "/path/to/input",
        type: "directory",
      },
      {
        name: "outputFile",
        label: "Output File",
        placeholder: "/path/to/output.csv",
        type: "file",
      },
    ],
    needsPeriod: false,
  },
  {
    key: "data_push",
    label: "Data Push",
    description: "Push data files from an input directory to downstream destinations.",
    fields: [
      {
        name: "inputDirectory",
        label: "Input Directory",
        placeholder: "/path/to/input",
        type: "directory",
      },
    ],
    needsPeriod: false,
  },
];

const utilitySchema = z.object({
  testingPeriod: z.object({ fiscalYear: z.string(), quarter: z.string() }),
  inputDirectory: z.string().optional(),
  outputDirectory: z.string().optional(),
  templateDirectory: z.string().optional(),
  outputFile: z.string().optional(),
  logLevel: z.string(),
  dryRun: z.boolean(),
});

type UtilityFormValues = z.infer<typeof utilitySchema>;

interface UtilityScriptFormProps {
  config: UtilityConfig;
}

const UtilityScriptForm: React.FC<UtilityScriptFormProps> = ({ config }) => {
  const navigate = useNavigate();
  const [showAdvanced, setShowAdvanced] = useState(false);

  const cacheKey = `accuracy_utility_${config.key}`;

  const {
    control,
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<UtilityFormValues>({
    resolver: zodResolver(utilitySchema),
    defaultValues: loadCache(cacheKey, {
      testingPeriod: { fiscalYear: currentFY(), quarter: "Q1" },
      inputDirectory: "",
      outputDirectory: "",
      templateDirectory: "",
      outputFile: "",
      logLevel: "INFO",
      dryRun: false,
    }),
  });

  useEffect(() => {
    const sub = watch((values) => {
      try { localStorage.setItem(`txr_form_${cacheKey}`, JSON.stringify(values)); } catch { /* ignore */ }
    });
    return () => sub.unsubscribe();
  }, [watch, cacheKey]);

  const mutation = useMutation({
    mutationFn: runValidation,
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const onSubmit = (values: UtilityFormValues) => {
    mutation.mutate({
      scriptName: config.key,
      testingPeriod: values.testingPeriod,
      mode: "batch",
      batchConfig: {
        inputDirectory: values.inputDirectory ?? "",
        outputDirectory: values.outputDirectory ?? "",
        templateDirectory: values.templateDirectory ?? "",
        logOutput: ((): string => { try { return localStorage.getItem("txr_global_log_output") || "logs"; } catch { return "logs"; } })(),
      },
      logLevel: values.logLevel,
      dryRun: values.dryRun,
    });
  };

  const isPending = mutation.isPending;
  const fieldErrors: Partial<Record<UtilityFieldConfig["name"], { message?: string }>> = errors;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
      <p className="text-sm text-muted-foreground">{config.description}</p>

      {config.needsPeriod && (
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
      )}

      {config.fields.map((f) => (
        <Field key={f.name} label={f.label} error={fieldErrors[f.name]?.message}>
          <PathPickerInput
            value={watch(f.name) ?? ""}
            onChange={(v) => setValue(f.name, v)}
            mode={f.type}
            placeholder={f.placeholder}
            disabled={isPending}
          />
        </Field>
      ))}

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
        {isPending ? "Running…" : "Run"}
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
// Main AccuracyTesting page
// ---------------------------------------------------------------------------

const AccuracyTesting: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ActiveTab>("validation");
  const [selectedUtility, setSelectedUtility] = useState<string>(UTILITY_CONFIGS[0].key);

  const selectedUtilityConfig =
    UTILITY_CONFIGS.find((u) => u.key === selectedUtility) ?? UTILITY_CONFIGS[0];

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
            {UTILITY_CONFIGS.map((u) => (
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
              <h2 className="text-lg font-semibold">{selectedUtilityConfig.label}</h2>
              <LastRunBadge scriptName={selectedUtilityConfig.key} />
            </div>
            <UtilityScriptForm key={selectedUtility} config={selectedUtilityConfig} />
          </div>
        </div>
      )}
    </div>
  );
};

export default AccuracyTesting;
