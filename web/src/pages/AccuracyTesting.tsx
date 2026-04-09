import React, { useState } from "react";
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
import LastRunBadge from "@/components/LastRunBadge";
import { runValidation, runAllValidations, discoverIncidents } from "@/api/accuracy";
import { cn } from "@/lib/utils";
import type { DiscoveryResponse } from "@/types";

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

type ValidationScriptKey = (typeof VALIDATION_SCRIPTS)[number]["key"];
type SelectedScript = ValidationScriptKey | "run-all";
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

interface FieldProps {
  label: string;
  error?: string;
  children: React.ReactNode;
}

const Field: React.FC<FieldProps> = ({ label, error, children }) => (
  <div className="flex flex-col gap-1">
    <label className="text-xs font-medium text-muted-foreground">{label}</label>
    {children}
    {error && <p className="text-xs text-destructive">{error}</p>}
  </div>
);

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
// Log level + dry run row (shared between forms)
// ---------------------------------------------------------------------------

interface LogRowProps {
  registerLogLevel: React.InputHTMLAttributes<HTMLSelectElement> &
    React.RefAttributes<HTMLSelectElement>;
  registerDryRun: React.InputHTMLAttributes<HTMLInputElement> &
    React.RefAttributes<HTMLInputElement>;
  disabled: boolean;
  logLevelError?: string;
}

const LogRow: React.FC<LogRowProps> = ({
  registerLogLevel,
  registerDryRun,
  disabled,
  logLevelError,
}) => (
  <div className="flex items-end gap-4">
    <Field label="Log Level" error={logLevelError}>
      <select
        {...registerLogLevel}
        disabled={disabled}
        className={cn(selectCls, "w-40")}
      >
        {LOG_LEVELS.map((l) => (
          <option key={l} value={l}>
            {l}
          </option>
        ))}
      </select>
    </Field>
    <label className="flex items-center gap-2 cursor-pointer text-sm pb-1">
      <input
        type="checkbox"
        {...registerDryRun}
        disabled={disabled}
        className="accent-primary h-4 w-4"
      />
      Dry Run
    </label>
  </div>
);

// ---------------------------------------------------------------------------
// Validation Script Form
// ---------------------------------------------------------------------------

const validationSchema = z.object({
  testingPeriod: z.object({ fiscalYear: z.string(), quarter: z.string() }),
  mode: z.enum(["batch", "single"]),
  // Batch fields
  inputDirectory: z.string().optional(),
  outputDirectory: z.string().optional(),
  templateDirectory: z.string().optional(),
  logOutput: z.string().optional(),
  italianTracker: z.string().optional(),
  mainTracker: z.string().optional(),
  // Single fields
  incidentCode: z.string().optional(),
  inputFile: z.string().optional(),
  templateFile: z.string().optional(),
  outputFile: z.string().optional(),
  // Common
  logLevel: z.string(),
  dryRun: z.boolean(),
});

type ValidationFormValues = z.infer<typeof validationSchema>;

interface ValidationScriptFormProps {
  scriptName: string;
}

const ValidationScriptForm: React.FC<ValidationScriptFormProps> = ({ scriptName }) => {
  const navigate = useNavigate();
  const [showTrackers, setShowTrackers] = useState(false);

  const {
    control,
    register,
    handleSubmit,
    watch,
    setValue,
    getValues,
    reset,
    formState: { errors },
  } = useForm<ValidationFormValues>({
    resolver: zodResolver(validationSchema),
    defaultValues: {
      testingPeriod: { fiscalYear: currentFY(), quarter: "Q1" },
      mode: "batch",
      inputDirectory: "",
      outputDirectory: "",
      templateDirectory: "",
      logOutput: "logs",
      italianTracker: "",
      mainTracker: "",
      incidentCode: "",
      inputFile: "",
      templateFile: "",
      outputFile: "",
      logLevel: "INFO",
      dryRun: false,
    },
  });

  const mode = watch("mode");

  const mutation = useMutation({
    mutationFn: runValidation,
    onSuccess: (job) => {
      navigate(`/jobs/${job.id}`);
    },
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const onSubmit = (values: ValidationFormValues) => {
    const req =
      values.mode === "batch"
        ? {
            scriptName,
            testingPeriod: values.testingPeriod,
            mode: "batch" as const,
            batchConfig: {
              inputDirectory: values.inputDirectory ?? "",
              outputDirectory: values.outputDirectory ?? "",
              templateDirectory: values.templateDirectory ?? "",
              logOutput: values.logOutput ?? "logs",
              italianTracker: values.italianTracker || undefined,
              mainTracker: values.mainTracker || undefined,
            },
            logLevel: values.logLevel,
            dryRun: values.dryRun,
          }
        : {
            scriptName,
            testingPeriod: values.testingPeriod,
            mode: "single" as const,
            singleConfig: {
              incidentCode: values.incidentCode ?? "",
              inputFile: values.inputFile ?? "",
              templateFile: values.templateFile ?? "",
              outputFile: values.outputFile ?? "",
            },
            logLevel: values.logLevel,
            dryRun: values.dryRun,
          };

    mutation.mutate(req);
  };

  const handleLoadConfig = (config: Record<string, unknown>) => {
    reset(config as unknown as ValidationFormValues);
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
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

      {/* Mode selector */}
      <div className="flex flex-col gap-1">
        <p className="text-xs font-medium text-muted-foreground">Mode</p>
        <div className="flex gap-4">
          {(["batch", "single"] as const).map((m) => (
            <label key={m} className="flex items-center gap-2 cursor-pointer text-sm">
              <input
                type="radio"
                value={m}
                {...register("mode")}
                disabled={isPending}
                className="accent-primary"
              />
              {m.charAt(0).toUpperCase() + m.slice(1)}
            </label>
          ))}
        </div>
      </div>

      {/* Batch fields */}
      {mode === "batch" && (
        <div className="space-y-3 rounded-lg border border-border p-4">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Batch Config
          </p>
          <Field label="Input Directory" error={errors.inputDirectory?.message}>
            <PathPickerInput
              value={watch("inputDirectory") ?? ""}
              onChange={(v) => setValue("inputDirectory", v)}
              mode="directory"
              placeholder="/path/to/input"
              disabled={isPending}
            />
          </Field>
          <Field label="Output Directory" error={errors.outputDirectory?.message}>
            <PathPickerInput
              value={watch("outputDirectory") ?? ""}
              onChange={(v) => setValue("outputDirectory", v)}
              mode="directory"
              placeholder="/path/to/output"
              disabled={isPending}
            />
          </Field>
          <Field label="Template Directory" error={errors.templateDirectory?.message}>
            <PathPickerInput
              value={watch("templateDirectory") ?? ""}
              onChange={(v) => setValue("templateDirectory", v)}
              mode="directory"
              placeholder="/path/to/templates"
              disabled={isPending}
            />
          </Field>
          <Field label="Log Output" error={errors.logOutput?.message}>
            <PathPickerInput
              value={watch("logOutput") ?? ""}
              onChange={(v) => setValue("logOutput", v)}
              mode="directory"
              placeholder="logs"
              disabled={isPending}
            />
          </Field>

          {/* Collapsible tracker files */}
          <div className="rounded-md border border-border">
            <button
              type="button"
              onClick={() => setShowTrackers(!showTrackers)}
              className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
            >
              Advanced — Tracker Files
              <span className={cn("transition-transform text-[10px]", showTrackers && "rotate-180")}>▾</span>
            </button>
            {showTrackers && (
              <div className="space-y-3 px-3 pb-3 border-t border-border pt-3">
                <Field label="Italian Fiscal Code Tracker">
                  <PathPickerInput
                    value={watch("italianTracker") ?? ""}
                    onChange={(v) => setValue("italianTracker", v)}
                    mode="file"
                    placeholder="/path/to/italian_tracker.csv"
                    disabled={isPending}
                  />
                </Field>
                <Field label="Main ID Cross-Reference Tracker">
                  <PathPickerInput
                    value={watch("mainTracker") ?? ""}
                    onChange={(v) => setValue("mainTracker", v)}
                    mode="file"
                    placeholder="/path/to/main_tracker.csv"
                    disabled={isPending}
                  />
                </Field>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Single fields */}
      {mode === "single" && (
        <div className="space-y-3 rounded-lg border border-border p-4">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Single Config
          </p>
          <Field label="Incident Code" error={errors.incidentCode?.message}>
            <input
              {...register("incidentCode")}
              disabled={isPending}
              className={inputCls}
              placeholder="e.g. 7_39"
            />
          </Field>
          <Field label="Input File" error={errors.inputFile?.message}>
            <PathPickerInput
              value={watch("inputFile") ?? ""}
              onChange={(v) => setValue("inputFile", v)}
              mode="file"
              placeholder="/path/to/input.csv"
              disabled={isPending}
            />
          </Field>
          <Field label="Template File" error={errors.templateFile?.message}>
            <PathPickerInput
              value={watch("templateFile") ?? ""}
              onChange={(v) => setValue("templateFile", v)}
              mode="file"
              placeholder="/path/to/template.csv"
              disabled={isPending}
            />
          </Field>
          <Field label="Output File" error={errors.outputFile?.message}>
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

      <LogRow
        registerLogLevel={register("logLevel")}
        registerDryRun={register("dryRun")}
        disabled={isPending}
        logLevelError={errors.logLevel?.message}
      />

      <ConfigLoader
        scriptName={scriptName}
        currentConfig={getValues() as unknown as Record<string, unknown>}
        onLoad={handleLoadConfig}
      />

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
// Run All Form
// ---------------------------------------------------------------------------

const runAllSchema = z.object({
  testingPeriod: z.object({ fiscalYear: z.string(), quarter: z.string() }),
  inputDirectory: z.string().min(1, "Required"),
  outputDirectory: z.string().min(1, "Required"),
  templateDirectory: z.string().min(1, "Required"),
  logLevel: z.string(),
  dryRun: z.boolean(),
  stopOnError: z.boolean(),
});

type RunAllFormValues = z.infer<typeof runAllSchema>;

const RunAllForm: React.FC = () => {
  const navigate = useNavigate();
  const [selectedTypes, setSelectedTypes] = useState<string[]>(
    VALIDATION_SCRIPTS.map((s) => s.key),
  );
  const [discoveryResult, setDiscoveryResult] = useState<DiscoveryResponse | null>(null);

  const {
    control,
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<RunAllFormValues>({
    resolver: zodResolver(runAllSchema),
    defaultValues: {
      testingPeriod: { fiscalYear: currentFY(), quarter: "Q1" },
      inputDirectory: "",
      outputDirectory: "",
      templateDirectory: "",
      logLevel: "INFO",
      dryRun: false,
      stopOnError: false,
    },
  });

  const inputDirectory = watch("inputDirectory");

  const mutation = useMutation({
    mutationFn: runAllValidations,
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const discoveryMutation = useMutation({
    mutationFn: discoverIncidents,
    onSuccess: (result) => {
      setDiscoveryResult(result);
      // Auto-select types that have found files
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

  const onSubmit = (values: RunAllFormValues) => {
    mutation.mutate({
      testingPeriod: values.testingPeriod,
      validationTypes: selectedTypes,
      inputDirectory: values.inputDirectory,
      outputDirectory: values.outputDirectory,
      templateDirectory: values.templateDirectory,
      logLevel: values.logLevel,
      dryRun: values.dryRun,
      stopOnError: values.stopOnError || undefined,
    });
  };

  const toggleType = (key: string) => {
    setSelectedTypes((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );
  };

  const allSelected = selectedTypes.length === VALIDATION_SCRIPTS.length;
  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
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

      {/* Validation type checklist */}
      <div className="rounded-lg border border-border p-4 space-y-2">
        <div className="flex items-center justify-between mb-1">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Validation Types
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

      <Field label="Input Directory" error={errors.inputDirectory?.message}>
        <PathPickerInput
          value={watch("inputDirectory") ?? ""}
          onChange={(v) => setValue("inputDirectory", v)}
          mode="directory"
          placeholder="/path/to/input"
          disabled={isPending}
        />
      </Field>

      {/* Autodiscovery */}
      <Button
        type="button"
        variant="outline"
        disabled={!inputDirectory || discoveryMutation.isPending}
        onClick={() => discoveryMutation.mutate({ inputDirectory })}
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

      <Field label="Output Directory" error={errors.outputDirectory?.message}>
        <PathPickerInput
          value={watch("outputDirectory") ?? ""}
          onChange={(v) => setValue("outputDirectory", v)}
          mode="directory"
          placeholder="/path/to/output"
          disabled={isPending}
        />
      </Field>
      <Field label="Template Directory" error={errors.templateDirectory?.message}>
        <PathPickerInput
          value={watch("templateDirectory") ?? ""}
          onChange={(v) => setValue("templateDirectory", v)}
          mode="directory"
          placeholder="/path/to/templates"
          disabled={isPending}
        />
      </Field>

      <LogRow
        registerLogLevel={register("logLevel")}
        registerDryRun={register("dryRun")}
        disabled={isPending}
        logLevelError={errors.logLevel?.message}
      />

      <label className="flex items-center gap-2 cursor-pointer text-sm">
        <input
          type="checkbox"
          {...register("stopOnError")}
          disabled={isPending}
          className="accent-primary h-4 w-4"
        />
        Stop on first error
      </label>

      <Button
        type="submit"
        disabled={isPending || selectedTypes.length === 0}
        className="w-full"
      >
        {isPending ? "Running…" : "Run All"}
      </Button>
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
    description: "Generate accuracy testing template files.",
    fields: [
      {
        name: "outputDirectory",
        label: "Output Directory",
        placeholder: "/path/to/output",
        type: "directory",
      },
      {
        name: "templateDirectory",
        label: "Template Directory",
        placeholder: "/path/to/templates",
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

  const {
    control,
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<UtilityFormValues>({
    resolver: zodResolver(utilitySchema),
    defaultValues: {
      testingPeriod: { fiscalYear: currentFY(), quarter: "Q1" },
      inputDirectory: "",
      outputDirectory: "",
      templateDirectory: "",
      outputFile: "",
      logLevel: "INFO",
      dryRun: false,
    },
  });

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
        logOutput: "logs",
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

      <LogRow
        registerLogLevel={register("logLevel")}
        registerDryRun={register("dryRun")}
        disabled={isPending}
        logLevelError={errors.logLevel?.message}
      />

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
  const [selectedScript, setSelectedScript] = useState<SelectedScript>(
    VALIDATION_SCRIPTS[0].key,
  );
  const [selectedUtility, setSelectedUtility] = useState<string>(UTILITY_CONFIGS[0].key);

  const selectedScriptLabel =
    selectedScript === "run-all"
      ? "Run All"
      : (VALIDATION_SCRIPTS.find((s) => s.key === selectedScript)?.label ?? selectedScript);

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
        <div className="flex gap-6 min-h-[600px]">
          {/* Sidebar */}
          <nav className="w-60 shrink-0 space-y-1">
            <button
              type="button"
              onClick={() => setSelectedScript("run-all")}
              className={navItemCls(selectedScript === "run-all")}
            >
              Run All
            </button>
            <div className="border-t border-border my-2" />
            {VALIDATION_SCRIPTS.map((s) => (
              <button
                key={s.key}
                type="button"
                onClick={() => setSelectedScript(s.key)}
                className={navItemCls(selectedScript === s.key)}
              >
                {s.label}
              </button>
            ))}
          </nav>

          {/* Panel */}
          <div className="flex-1 min-w-0 rounded-lg border border-border p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold">{selectedScriptLabel}</h2>
              {selectedScript !== "run-all" && (
                <LastRunBadge scriptName={selectedScript} />
              )}
              {selectedScript === "run-all" && (
                <LastRunBadge scriptName="run_all_validations" />
              )}
            </div>
            {selectedScript === "run-all" ? (
              <RunAllForm />
            ) : (
              <ValidationScriptForm key={selectedScript} scriptName={selectedScript} />
            )}
          </div>
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
