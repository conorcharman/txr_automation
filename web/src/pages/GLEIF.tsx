import React, { useState } from "react";
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
import { gleifRefresh, gleifCheck, gleifBackfill, gleifLookup, gleifSearch } from "@/api/gleif";
import { cn } from "@/lib/utils";
import type { GleifLookupResponse, GleifSearchResult } from "@/types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"] as const;

type GleifSection = "refresh" | "check" | "backfill";

const SECTIONS: Array<{ key: GleifSection; label: string }> = [
  { key: "refresh", label: "Refresh Database" },
  { key: "check", label: "Check LEI" },
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

function navItemCls(active: boolean): string {
  return cn(
    "w-full text-left px-3 py-2 rounded-md text-sm transition-colors",
    active
      ? "bg-primary/10 text-primary font-medium"
      : "text-muted-foreground hover:bg-muted hover:text-foreground",
  );
}

// ---------------------------------------------------------------------------
// Refresh Form
// ---------------------------------------------------------------------------

const refreshSchema = z.object({
  refreshType: z.enum(["full", "delta", "auto"]),
  deltaType: z.enum(["monthly", "weekly", "daily"]).optional(),
  dbPath: z.string().optional(),
  skipIsinMap: z.boolean(),
  logLevel: z.string(),
});

type RefreshFormValues = z.infer<typeof refreshSchema>;

const RefreshForm: React.FC = () => {
  const navigate = useNavigate();
  const [showDbPath, setShowDbPath] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<RefreshFormValues>({
    resolver: zodResolver(refreshSchema),
    defaultValues: {
      refreshType: "auto",
      deltaType: "monthly",
      dbPath: "",
      skipIsinMap: false,
      logLevel: "INFO",
    },
  });

  const refreshType = watch("refreshType");

  const mutation = useMutation({
    mutationFn: gleifRefresh,
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const onSubmit = (values: RefreshFormValues) => {
    mutation.mutate({
      refreshType: values.refreshType,
      deltaType: values.refreshType === "delta" ? values.deltaType : undefined,
      dbPath: (showDbPath && values.dbPath) ? values.dbPath : undefined,
      skipIsinMap: values.skipIsinMap || undefined,
      logLevel: values.logLevel,
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Refresh the local GLEIF LEI database from the GLEIF API.
      </p>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-muted-foreground">Refresh Type</label>
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

      {refreshType === "delta" && (
        <Field label="Delta Type" error={errors.deltaType?.message}>
          <select {...register("deltaType")} disabled={isPending} className={selectCls}>
            <option value="monthly">Monthly</option>
            <option value="weekly">Weekly</option>
            <option value="daily">Daily</option>
          </select>
        </Field>
      )}

      <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
        <input
          type="checkbox"
          checked={showDbPath}
          onChange={(e) => {
            setShowDbPath(e.target.checked);
            if (!e.target.checked) setValue("dbPath", "");
          }}
          disabled={isPending}
          className="rounded border-input"
        />
        Custom database file path
      </label>

      {showDbPath && (
        <Field label="Database File Path" error={errors.dbPath?.message}>
          <PathPickerInput
            value={watch("dbPath") ?? ""}
            onChange={(v) => setValue("dbPath", v)}
            mode="file"
            placeholder="/app/data/gleif_cache.db"
            disabled={isPending}
          />
        </Field>
      )}

      <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
        <input
          type="checkbox"
          {...register("skipIsinMap")}
          disabled={isPending}
          className="rounded border-input"
        />
        Skip ISIN-to-LEI mapping download
      </label>

      <Field label="Log Level" error={errors.logLevel?.message}>
        <select {...register("logLevel")} disabled={isPending} className={selectCls}>
          {LOG_LEVELS.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
      </Field>

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
// Check LEI Form
// ---------------------------------------------------------------------------

const checkSchema = z
  .object({
    mode: z.enum(["single", "name_search", "batch"]),
    lei: z.string().optional(),
    name: z.string().optional(),
    limit: z.number().int().min(1).max(100).optional(),
    inputFile: z.string().optional(),
    outputFile: z.string().optional(),
    logLevel: z.string(),
  })
  .superRefine((data, ctx) => {
    if (data.mode === "single" && !data.lei) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Required", path: ["lei"] });
    }
    if (data.mode === "name_search" && !data.name) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Required", path: ["name"] });
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
  const [lookupResult, setLookupResult] = useState<GleifLookupResponse | null>(null);
  const [searchResults, setSearchResults] = useState<GleifSearchResult[]>([]);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<CheckFormValues>({
    resolver: zodResolver(checkSchema),
    defaultValues: {
      mode: "single",
      lei: "",
      name: "",
      limit: 20,
      inputFile: "",
      outputFile: "",
      logLevel: "INFO",
    },
  });

  const mode = watch("mode");

  const batchMutation = useMutation({
    mutationFn: gleifCheck,
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const leiLookupMutation = useMutation({
    mutationFn: (vals: { lei: string }) => gleifLookup(vals.lei),
    onSuccess: (result) => {
      setLookupResult(result);
      setSearchResults([]);
    },
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Lookup failed");
    },
  });

  const nameSearchMutation = useMutation({
    mutationFn: (vals: { name: string; limit: number }) =>
      gleifSearch(vals.name, vals.limit),
    onSuccess: (result) => {
      setSearchResults(result.results);
      setLookupResult(null);
    },
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Search failed");
    },
  });

  const onSubmit = (values: CheckFormValues) => {
    if (values.mode === "single") {
      setLookupResult(null);
      setSearchResults([]);
      leiLookupMutation.mutate({ lei: values.lei ?? "" });
    } else if (values.mode === "name_search") {
      setLookupResult(null);
      setSearchResults([]);
      nameSearchMutation.mutate({
        name: values.name ?? "",
        limit: values.limit ?? 20,
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

  const isPending =
    batchMutation.isPending || leiLookupMutation.isPending || nameSearchMutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Look up LEIs by code, search by company name, or process a batch file.
      </p>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-muted-foreground">Mode</label>
        <div className="flex gap-4">
          {([
            ["single", "Single LEI"],
            ["name_search", "Name Search"],
            ["batch", "Batch"],
          ] as const).map(([val, label]) => (
            <label key={val} className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="radio"
                value={val}
                disabled={isPending}
                {...register("mode")}
              />
              {label}
            </label>
          ))}
        </div>
      </div>

      {mode === "single" && (
        <Field label="LEI" error={errors.lei?.message}>
          <input
            {...register("lei")}
            disabled={isPending}
            className={inputCls}
            placeholder="e.g. 5493001KJTIIGC8Y1R12"
          />
        </Field>
      )}

      {mode === "name_search" && (
        <>
          <Field label="Company Name" error={errors.name?.message}>
            <input
              {...register("name")}
              disabled={isPending}
              className={inputCls}
              placeholder="e.g. Citibank"
            />
          </Field>
          <Field label="Max Results" error={errors.limit?.message}>
            <input
              type="number"
              {...register("limit", { valueAsNumber: true })}
              disabled={isPending}
              className={inputCls}
              min={1}
              max={100}
            />
          </Field>
        </>
      )}

      {mode === "batch" && (
        <>
          <CsvFormatHint
            columns={[
              {
                name: "lei",
                required: true,
                description: "Legal Entity Identifier (20-character alphanumeric code).",
                example: "5493001KJTIIGC8Y1R12",
              },
              {
                name: "trade_date",
                required: false,
                description: "Trade date in YYYY-MM-DD format. Used to assess LAPSED LEI status at the time of the trade.",
                example: "2026-03-15",
              },
            ]}
            notes="Columns are matched case-insensitively. All other columns in the input file are preserved unchanged in the output."
          />
          <Field label="Input File" error={errors.inputFile?.message}>
            <PathPickerInput
              value={watch("inputFile") ?? ""}
              onChange={(v) => setValue("inputFile", v)}
              mode="file"
              placeholder="/path/to/input.csv"
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
        </>
      )}

      <Field label="Log Level" error={errors.logLevel?.message}>
        <select {...register("logLevel")} disabled={isPending} className={selectCls}>
          {LOG_LEVELS.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
      </Field>

      <Button type="submit" disabled={isPending} className="w-full">
        {isPending ? "Running…" : "Check"}
      </Button>

      {(batchMutation.isError || leiLookupMutation.isError || nameSearchMutation.isError) && (
        <p className="text-sm text-destructive">
          {(() => {
            const err = batchMutation.error ?? leiLookupMutation.error ?? nameSearchMutation.error;
            return err instanceof Error ? err.message : "An error occurred";
          })()}
        </p>
      )}

      {lookupResult && (
        <div
          className={cn(
            "rounded-lg border p-4 space-y-2",
            lookupResult.isValid
              ? "border-green-300 bg-green-50 dark:border-green-700 dark:bg-green-900/20"
              : "border-red-300 bg-red-50 dark:border-red-700 dark:bg-red-900/20",
          )}
        >
          <div className="flex items-center justify-between">
            <span className="font-semibold text-sm">{lookupResult.lei}</span>
            <span
              className={cn(
                "rounded-full px-2.5 py-0.5 text-xs font-medium",
                lookupResult.isValid
                  ? "bg-green-200 text-green-800 dark:bg-green-800 dark:text-green-200"
                  : "bg-red-200 text-red-800 dark:bg-red-800 dark:text-red-200",
              )}
            >
              {lookupResult.isValid ? "Valid" : "Invalid"}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">{lookupResult.reason}</p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-muted-foreground">
            {lookupResult.legalName && <span>Name: {lookupResult.legalName}</span>}
            {lookupResult.entityStatus && <span>Status: {lookupResult.entityStatus}</span>}
            {lookupResult.legalAddressCountry && (
              <span>Country: {lookupResult.legalAddressCountry}</span>
            )}
            {lookupResult.registrationStatus && (
              <span>Registration: {lookupResult.registrationStatus}</span>
            )}
          </div>
        </div>
      )}

      {searchResults.length > 0 && (
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-medium">LEI</th>
                <th className="px-3 py-2 text-left font-medium">Legal Name</th>
                <th className="px-3 py-2 text-left font-medium">Status</th>
                <th className="px-3 py-2 text-left font-medium">Country</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {searchResults.map((r) => (
                <tr key={r.lei} className="hover:bg-muted/50">
                  <td className="px-3 py-2 font-mono text-xs">{r.lei}</td>
                  <td className="px-3 py-2">{r.legalName}</td>
                  <td className="px-3 py-2 text-xs">{r.status}</td>
                  <td className="px-3 py-2 text-xs">{r.country}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
  dbPath: z.string().optional(),
  skipRefresh: z.boolean(),
  logLevel: z.string(),
});

type BackfillFormValues = z.infer<typeof backfillSchema>;

const BackfillForm: React.FC = () => {
  const navigate = useNavigate();
  const [showDbPath, setShowDbPath] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<BackfillFormValues>({
    resolver: zodResolver(backfillSchema),
    defaultValues: {
      inputFile: "",
      outputFile: "",
      format: "auto",
      dbPath: "",
      skipRefresh: false,
      logLevel: "INFO",
    },
  });

  const mutation = useMutation({
    mutationFn: gleifBackfill,
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
      dbPath: (showDbPath && values.dbPath) ? values.dbPath : undefined,
      skipRefresh: values.skipRefresh || undefined,
      logLevel: values.logLevel,
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Backfill GLEIF LEI data onto a CSV file.
      </p>

      <CsvFormatHint
        title="Generic CSV format"
        columns={[
          {
            name: "lei",
            required: true,
            description: "Legal Entity Identifier (20-character alphanumeric code).",
            example: "5493001KJTIIGC8Y1R12",
          },
          {
            name: "trade_date",
            required: false,
            description: "Trade date in YYYY-MM-DD format. Used to assess LAPSED LEI status.",
            example: "2026-03-15",
          },
        ]}
        notes={`Use format "incident" for FCA incident files, which instead use "Buyer identifier value", "Seller identifier value", and "Trading date time_Date" columns. Format auto-detects from headers by default.`}
      />

      <Field label="Input File" error={errors.inputFile?.message}>
        <PathPickerInput
          value={watch("inputFile")}
          onChange={(v) => setValue("inputFile", v)}
          mode="file"
          placeholder="/path/to/input.csv"
          disabled={isPending}
        />
      </Field>

      <Field label="Output File" error={errors.outputFile?.message}>
        <PathPickerInput
          value={watch("outputFile")}
          onChange={(v) => setValue("outputFile", v)}
          mode="file"
          placeholder="/path/to/output.csv"
          disabled={isPending}
        />
      </Field>

      <Field label="CSV Format" error={errors.format?.message}>
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

      <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
        <input
          type="checkbox"
          checked={showDbPath}
          onChange={(e) => {
            setShowDbPath(e.target.checked);
            if (!e.target.checked) setValue("dbPath", "");
          }}
          disabled={isPending}
          className="rounded border-input"
        />
        Custom database file path
      </label>

      {showDbPath && (
        <Field label="Database File Path" error={errors.dbPath?.message}>
          <PathPickerInput
            value={watch("dbPath") ?? ""}
            onChange={(v) => setValue("dbPath", v)}
            mode="file"
            placeholder="/app/data/gleif_cache.db"
            disabled={isPending}
          />
        </Field>
      )}

      <Field label="Log Level" error={errors.logLevel?.message}>
        <select {...register("logLevel")} disabled={isPending} className={selectCls}>
          {LOG_LEVELS.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
      </Field>

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
// Main GLEIF page
// ---------------------------------------------------------------------------

const FORM_COMPONENTS: Record<GleifSection, React.FC> = {
  refresh: RefreshForm,
  check: CheckForm,
  backfill: BackfillForm,
};

const GLEIF: React.FC = () => {
  const [selected, setSelected] = useState<GleifSection>("refresh");

  const ActiveForm = FORM_COMPONENTS[selected];
  const activeLabel = SECTIONS.find((s) => s.key === selected)?.label ?? "";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">GLEIF</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage the GLEIF LEI database and look up legal entity identifiers.
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
                  ? "gleif_refresh"
                  : selected === "check"
                    ? "gleif_check"
                    : "gleif_backfill"
              }
            />
          </div>
          <ActiveForm key={selected} />
        </div>
      </div>
    </div>
  );
};

export default GLEIF;
