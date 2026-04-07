import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { firdsRefresh, firdsCheck, firdsBackfill } from "@/api/firds";
import { cn } from "@/lib/utils";

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
  publicationDate: z.string().optional(),
  logLevel: z.string(),
});

type RefreshFormValues = z.infer<typeof refreshSchema>;

const RefreshForm: React.FC = () => {
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<RefreshFormValues>({
    resolver: zodResolver(refreshSchema),
    defaultValues: {
      refreshType: "auto",
      publicationDate: "",
      logLevel: "INFO",
    },
  });

  const refreshType = watch("refreshType");

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
      publicationDate: values.publicationDate || undefined,
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
        <Field label="Publication Date (YYYY-MM-DD)" error={errors.publicationDate?.message}>
          <input
            type="date"
            {...register("publicationDate")}
            disabled={isPending}
            className={inputCls}
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
    inputFile: z.string().optional(),
    outputFile: z.string().optional(),
    logLevel: z.string(),
  })
  .superRefine((data, ctx) => {
    if (data.mode === "single" && !data.isin) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Required", path: ["isin"] });
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

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<CheckFormValues>({
    resolver: zodResolver(checkSchema),
    defaultValues: {
      mode: "single",
      isin: "",
      inputFile: "",
      outputFile: "",
      logLevel: "INFO",
    },
  });

  const mode = watch("mode");

  const mutation = useMutation({
    mutationFn: firdsCheck,
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const onSubmit = (values: CheckFormValues) => {
    mutation.mutate({
      mode: values.mode,
      isin: values.isin || undefined,
      inputFile: values.inputFile || undefined,
      outputFile: values.outputFile || undefined,
      logLevel: values.logLevel,
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Check whether one or more ISINs are reportable under FIRDS.
      </p>

      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-muted-foreground">Mode</label>
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
        <Field label="ISIN" error={errors.isin?.message}>
          <input
            {...register("isin")}
            disabled={isPending}
            className={inputCls}
            placeholder="e.g. GB00B3FLWH99"
          />
        </Field>
      )}

      {mode === "batch" && (
        <>
          <Field label="Input File" error={errors.inputFile?.message}>
            <input
              {...register("inputFile")}
              disabled={isPending}
              className={inputCls}
              placeholder="/path/to/input.csv"
            />
          </Field>
          <Field label="Output File" error={errors.outputFile?.message}>
            <input
              {...register("outputFile")}
              disabled={isPending}
              className={inputCls}
              placeholder="/path/to/output.csv"
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

      {mutation.isError && (
        <p className="text-sm text-destructive">
          {mutation.error instanceof Error ? mutation.error.message : "An error occurred"}
        </p>
      )}
    </form>
  );
};

// ---------------------------------------------------------------------------
// Backfill Form
// ---------------------------------------------------------------------------

const backfillSchema = z.object({
  startDate: z.string().min(1, "Required"),
  endDate: z.string().min(1, "Required"),
  logLevel: z.string(),
});

type BackfillFormValues = z.infer<typeof backfillSchema>;

const BackfillForm: React.FC = () => {
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<BackfillFormValues>({
    resolver: zodResolver(backfillSchema),
    defaultValues: {
      startDate: "",
      endDate: "",
      logLevel: "INFO",
    },
  });

  const mutation = useMutation({
    mutationFn: firdsBackfill,
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const onSubmit = (values: BackfillFormValues) => {
    mutation.mutate({
      startDate: values.startDate,
      endDate: values.endDate,
      logLevel: values.logLevel,
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Backfill FIRDS data for a date range from the FCA FIRDS API.
      </p>

      <Field label="Start Date" error={errors.startDate?.message}>
        <input
          type="date"
          {...register("startDate")}
          disabled={isPending}
          className={inputCls}
        />
      </Field>

      <Field label="End Date" error={errors.endDate?.message}>
        <input
          type="date"
          {...register("endDate")}
          disabled={isPending}
          className={inputCls}
        />
      </Field>

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
          <h2 className="text-lg font-semibold mb-5">{activeLabel}</h2>
          <ActiveForm key={selected} />
        </div>
      </div>
    </div>
  );
};

export default FIRDS;
