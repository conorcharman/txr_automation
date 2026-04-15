import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { PathPickerInput } from "@/components/PathPickerInput";
import CsvFormatHint from "@/components/CsvFormatHint";
import LastRunBadge from "@/components/LastRunBadge";
import Field from "@/components/Field";
import { firdsRefresh, firdsCheck, firdsBackfill, firdsLookup } from "@/api/firds";
import { cn } from "@/lib/utils";
import type { FirdsLookupResponse } from "@/types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"] as const;

type FirdsSection = "refresh" | "check" | "backfill";

const SECTIONS: Array<{ key: FirdsSection; label: string }> = [
  { key: "refresh", label: "Refresh Database" },
  { key: "check", label: "Check Reportability" },
  { key: "backfill", label: "Backfill Data" },
];

// ---------------------------------------------------------------------------
// Shared styles
// ---------------------------------------------------------------------------

const inputCls =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm " +
  "focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50 " +
  "placeholder:text-muted-foreground";

const selectCls =
  "h-9 w-40 rounded-md border border-input bg-background px-3 text-sm " +
  "focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50";

// ---------------------------------------------------------------------------
// Shared sub-components
// ---------------------------------------------------------------------------



function navItemCls(active: boolean): string {
  return cn(
    "w-full text-left px-3 py-2 rounded-md text-sm transition-colors",
    active
      ? "bg-primary/10 text-primary font-medium"
      : "text-muted-foreground hover:bg-muted hover:text-foreground",
  );
}

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

function loadCache<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(`txr_form_${key}`);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

// ---------------------------------------------------------------------------
// Refresh Form
// ---------------------------------------------------------------------------

const refreshSchema = z.object({
  refreshType: z.enum(["full", "delta", "auto"]),
  logLevel: z.string(),
});

type RefreshFormValues = z.infer<typeof refreshSchema>;

const RefreshForm: React.FC = () => {
  const navigate = useNavigate();
  const [showAdvanced, setShowAdvanced] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<RefreshFormValues>({
    resolver: zodResolver(refreshSchema),
    defaultValues: loadCache("firds_refresh", {
      refreshType: "auto" as const,
      logLevel: "INFO",
    }),
  });

  useEffect(() => {
    const sub = watch((values) => {
      try { localStorage.setItem("txr_form_firds_refresh", JSON.stringify(values)); } catch { /* ignore */ }
    });
    return () => sub.unsubscribe();
  }, [watch]);

  const mutation = useMutation({
    mutationFn: firdsRefresh,
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const onSubmit = (values: RefreshFormValues) => {
    mutation.mutate({
      refreshType: values.refreshType,
      logLevel: values.logLevel,
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Refresh the local FIRDS database from the FCA FIRDS API.
      </p>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-muted-foreground" title="Type of cache refresh. Auto selects the best method; Full downloads the complete FIRDS dataset; Delta applies incremental updates.">Refresh Type</label>
        <div className="flex gap-4">
          {(["auto", "full", "delta"] as const).map((val) => (
            <label key={val} className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="radio"
                value={val}
                disabled={isPending}
                {...register("refreshType")}
              />
              {val.charAt(0).toUpperCase() + val.slice(1)}
            </label>
          ))}
        </div>
        {errors.refreshType && (
          <p className="text-xs text-destructive">{errors.refreshType.message}</p>
        )}
      </div>

      <AdvancedSection isOpen={showAdvanced} onToggle={() => setShowAdvanced(!showAdvanced)}>
        <Field label="Log Level" hint="Logging verbosity level." error={errors.logLevel?.message}>
          <select {...register("logLevel")} disabled={isPending} className={selectCls}>
            {LOG_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </Field>
      </AdvancedSection>

      <Button type="submit" disabled={isPending} className="w-full">
        {isPending ? "Running…" : "Run Refresh"}
      </Button>

      {mutation.isError && (
        <p className="text-sm text-destructive">
          {mutation.error instanceof Error ? mutation.error.message : "An error occurred"}
        </p>
      )}
    </form>
  );
};

// ---------------------------------------------------------------------------
// Check Reportability Form
// ---------------------------------------------------------------------------

const checkSchema = z
  .object({
    mode: z.enum(["single", "batch"]),
    isin: z.string().optional(),
    date: z.string().optional(),
    mic: z.string().optional(),
    inputFile: z.string().optional(),
    outputFile: z.string().optional(),
    logLevel: z.string(),
  })
  .superRefine((data, ctx) => {
    if (data.mode === "single") {
      if (!data.isin) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Required", path: ["isin"] });
      }
      if (!data.date) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Required for single check", path: ["date"] });
      }
    }
    if (data.mode === "batch") {
      if (!data.inputFile) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Required", path: ["inputFile"] });
      }
      if (!data.outputFile) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Required", path: ["outputFile"] });
      }
    }
  });

type CheckFormValues = z.infer<typeof checkSchema>;

const CheckForm: React.FC = () => {
  const navigate = useNavigate();
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [lookupResult, setLookupResult] = useState<FirdsLookupResponse | null>(null);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<CheckFormValues>({
    resolver: zodResolver(checkSchema),
    defaultValues: loadCache("firds_check", {
      mode: "single" as const,
      isin: "",
      date: "",
      mic: "",
      inputFile: "",
      outputFile: "",
      logLevel: "INFO",
    }),
  });

  useEffect(() => {
    const sub = watch((values) => {
      try { localStorage.setItem("txr_form_firds_check", JSON.stringify(values)); } catch { /* ignore */ }
    });
    return () => sub.unsubscribe();
  }, [watch]);

  const mode = watch("mode");

  const batchMutation = useMutation({
    mutationFn: firdsCheck,
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const lookupMutation = useMutation({
    mutationFn: (vals: { isin: string; date: string; mic?: string }) =>
      firdsLookup(vals.isin, vals.date, vals.mic),
    onSuccess: (result) => setLookupResult(result),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Lookup failed");
    },
  });

  const onSubmit = (values: CheckFormValues) => {
    if (values.mode === "single") {
      setLookupResult(null);
      lookupMutation.mutate({
        isin: values.isin ?? "",
        date: values.date ?? "",
        mic: values.mic || undefined,
      });
    } else {
      batchMutation.mutate({
        mode: values.mode,
        inputFile: values.inputFile || undefined,
        outputFile: values.outputFile || undefined,
        logLevel: values.logLevel,
      });
    }
  };

  const isPending = batchMutation.isPending || lookupMutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Check whether one or more ISINs are reportable under FIRDS.
      </p>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-muted-foreground" title="Single: check one ISIN interactively. Batch: process a CSV file of ISINs.">Mode</label>
        <div className="flex gap-4">
          {(["single", "batch"] as const).map((val) => (
            <label key={val} className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="radio"
                value={val}
                disabled={isPending}
                {...register("mode")}
              />
              {val.charAt(0).toUpperCase() + val.slice(1)}
            </label>
          ))}
        </div>
      </div>

      {mode === "single" && (
        <>
          <Field label="ISIN" hint="12-character International Securities Identification Number." error={errors.isin?.message}>
            <input
              {...register("isin")}
              disabled={isPending}
              className={inputCls}
              placeholder="e.g. GB00B3FLWH99"
            />
          </Field>
          <Field label="Trade Date" hint="Date of the trade to check reportability for." error={errors.date?.message}>
            <input
              type="date"
              {...register("date")}
              disabled={isPending}
              className={inputCls}
            />
          </Field>
          <Field label="MIC (optional)" hint="Market Identifier Code to narrow venue matching, e.g. XLON." error={errors.mic?.message}>
            <input
              {...register("mic")}
              disabled={isPending}
              className={inputCls}
              placeholder="e.g. XLON"
            />
          </Field>
        </>
      )}

      {mode === "batch" && (
        <>
          <CsvFormatHint
            columns={[
              {
                name: "isin",
                required: true,
                description: "ISIN code for the instrument.",
                example: "GB00B3FLWH99",
              },
              {
                name: "trade_date",
                required: false,
                description: "Trade date in YYYY-MM-DD or DD/MM/YYYY format. If absent, the date is extracted from the filename (pattern DD-MM-YYYY).",
                example: "2026-03-15",
              },
              {
                name: "mic",
                required: false,
                description: "Market Identifier Code to narrow venue matching.",
                example: "XLON",
              },
            ]}
            notes="All other columns in the input file are preserved unchanged in the output."
          />
          <Field label="Input File" hint="CSV file containing ISIN column for batch reportability checking." error={errors.inputFile?.message}>
            <PathPickerInput
              value={watch("inputFile") ?? ""}
              onChange={(v) => setValue("inputFile", v)}
              mode="file"
              placeholder="/path/to/input.csv"
              disabled={isPending}
            />
          </Field>
          <Field label="Output File" hint="Output CSV with reportability results appended." error={errors.outputFile?.message}>
            <PathPickerInput
              value={watch("outputFile") ?? ""}
              onChange={(v) => setValue("outputFile", v)}
              mode="file"
              placeholder="/path/to/output.csv"
              disabled={isPending}
            />
          </Field>
        </>
      )}

      <AdvancedSection isOpen={showAdvanced} onToggle={() => setShowAdvanced(!showAdvanced)}>
        <Field label="Log Level" hint="Logging verbosity level." error={errors.logLevel?.message}>
          <select {...register("logLevel")} disabled={isPending} className={selectCls}>
            {LOG_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </Field>
      </AdvancedSection>

      <Button type="submit" disabled={isPending} className="w-full">
        {isPending ? "Running…" : "Check"}
      </Button>

      {(batchMutation.isError || lookupMutation.isError) && (
        <p className="text-sm text-destructive">
          {(() => {
            const err = batchMutation.error ?? lookupMutation.error;
            return err instanceof Error ? err.message : "An error occurred";
          })()}
        </p>
      )}

      {lookupResult && (
        <div
          className={cn(
            "rounded-lg border p-4 space-y-2",
            lookupResult.isReportable
              ? "border-green-300 bg-green-50 dark:border-green-700 dark:bg-green-900/20"
              : "border-red-300 bg-red-50 dark:border-red-700 dark:bg-red-900/20",
          )}
        >
          <div className="flex items-center justify-between">
            <span className="font-semibold text-sm">{lookupResult.isin}</span>
            <span
              className={cn(
                "rounded-full px-2.5 py-0.5 text-xs font-medium",
                lookupResult.isReportable
                  ? "bg-green-200 text-green-800 dark:bg-green-800 dark:text-green-200"
                  : "bg-red-200 text-red-800 dark:bg-red-800 dark:text-red-200",
              )}
            >
              {lookupResult.isReportable ? "Reportable" : "Not Reportable"}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">{lookupResult.reason}</p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span>Trade Date: {lookupResult.tradeDate}</span>
            <span>MIC: {lookupResult.mic ?? "—"}</span>
            {lookupResult.matchedMics.length > 0 && (
              <span className="col-span-2">
                Matched MICs: {lookupResult.matchedMics.join(", ")}
              </span>
            )}
          </div>
        </div>
      )}
    </form>
  );
};

// ---------------------------------------------------------------------------
// Backfill Form
// ---------------------------------------------------------------------------

const backfillSchema = z.object({
  inputFile: z.string().min(1, "Required"),
  outputFile: z.string().min(1, "Required"),
  format: z.enum(["auto", "incident", "generic"]),
  skipRefresh: z.boolean(),
  logLevel: z.string(),
});

type BackfillFormValues = z.infer<typeof backfillSchema>;

const BackfillForm: React.FC = () => {
  const navigate = useNavigate();
  const [showAdvanced, setShowAdvanced] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<BackfillFormValues>({
    resolver: zodResolver(backfillSchema),
    defaultValues: loadCache("firds_backfill", {
      inputFile: "",
      outputFile: "",
      format: "auto" as const,
      skipRefresh: false,
      logLevel: "INFO",
    }),
  });

  useEffect(() => {
    const sub = watch((values) => {
      try { localStorage.setItem("txr_form_firds_backfill", JSON.stringify(values)); } catch { /* ignore */ }
    });
    return () => sub.unsubscribe();
  }, [watch]);

  const mutation = useMutation({
    mutationFn: firdsBackfill,
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const onSubmit = (values: BackfillFormValues) => {
    mutation.mutate({
      inputFile: values.inputFile,
      outputFile: values.outputFile,
      format: values.format,
      skipRefresh: values.skipRefresh || undefined,
      logLevel: values.logLevel,
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Backfill FIRDS reportability data onto a CSV file.
      </p>

      <CsvFormatHint
        title="Generic CSV format"
        columns={[
          {
            name: "isin",
            required: true,
            description: "ISIN code for the instrument.",
            example: "GB00B3FLWH99",
          },
          {
            name: "trade_date",
            required: true,
            description: "Trade date in YYYY-MM-DD or DD/MM/YYYY format.",
            example: "2026-03-15",
          },
          {
            name: "mic",
            required: false,
            description: "Market Identifier Code to narrow venue matching.",
            example: "XLON",
          },
        ]}
        notes={`Use format "incident" for FCA incident files, which instead use "Instrument identification code" and "Transaction Reference Number" columns. Format auto-detects from headers by default.`}
      />

      <Field label="Input File" hint="CSV file containing transactions to backfill FIRDS reportability data for." error={errors.inputFile?.message}>
        <PathPickerInput
          value={watch("inputFile")}
          onChange={(v) => setValue("inputFile", v)}
          mode="file"
          placeholder="/path/to/input.csv"
          disabled={isPending}
        />
      </Field>

      <Field label="Output File" hint="Where to write the backfilled output CSV." error={errors.outputFile?.message}>
        <PathPickerInput
          value={watch("outputFile")}
          onChange={(v) => setValue("outputFile", v)}
          mode="file"
          placeholder="/path/to/output.csv"
          disabled={isPending}
        />
      </Field>

      <Field label="CSV Format" hint="Auto-detects from column headers. Use Incident for FCA incident files; Generic for standard CSV." error={errors.format?.message}>
        <select {...register("format")} disabled={isPending} className={selectCls}>
          <option value="auto">Auto-detect</option>
          <option value="incident">Incident</option>
          <option value="generic">Generic</option>
        </select>
      </Field>

      <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
        <input
          type="checkbox"
          {...register("skipRefresh")}
          disabled={isPending}
          className="rounded border-input"
        />
        Skip cache refresh before backfill
      </label>

      <AdvancedSection isOpen={showAdvanced} onToggle={() => setShowAdvanced(!showAdvanced)}>
        <Field label="Log Level" hint="Logging verbosity level." error={errors.logLevel?.message}>
          <select {...register("logLevel")} disabled={isPending} className={selectCls}>
            {LOG_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </Field>
      </AdvancedSection>

      <Button type="submit" disabled={isPending} className="w-full">
        {isPending ? "Running…" : "Backfill"}
      </Button>

      {mutation.isError && (
        <p className="text-sm text-destructive">
          {mutation.error instanceof Error ? mutation.error.message : "An error occurred"}
        </p>
      )}
    </form>
  );
};

// ---------------------------------------------------------------------------
// Main FIRDS page
// ---------------------------------------------------------------------------

const FORM_COMPONENTS: Record<FirdsSection, React.FC> = {
  refresh: RefreshForm,
  check: CheckForm,
  backfill: BackfillForm,
};

const FIRDS: React.FC = () => {
  const [selected, setSelected] = useState<FirdsSection>("refresh");

  const ActiveForm = FORM_COMPONENTS[selected];
  const activeLabel = SECTIONS.find((s) => s.key === selected)?.label ?? "";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">FIRDS</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage the FCA FIRDS reportability database and check ISINs.
        </p>
      </div>

      <div className="flex gap-6 min-h-[500px]">
        {/* Sidebar */}
        <nav className="w-64 shrink-0 space-y-1">
          {SECTIONS.map((s) => (
            <button
              key={s.key}
              type="button"
              onClick={() => setSelected(s.key)}
              className={navItemCls(selected === s.key)}
            >
              {s.label}
            </button>
          ))}
        </nav>

        {/* Panel */}
        <div className="flex-1 min-w-0 rounded-lg border border-border p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold">{activeLabel}</h2>
            <LastRunBadge
              scriptName={
                selected === "refresh"
                  ? "firds_refresh"
                  : selected === "check"
                    ? "firds_check"
                    : "firds_backfill"
              }
            />
          </div>
          <ActiveForm key={selected} />
        </div>
      </div>
    </div>
  );
};

export default FIRDS;
