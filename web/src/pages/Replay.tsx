import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import TestingPeriodSelector from "@/components/TestingPeriodSelector";
import {
  runReplayPhase2,
  runReplayPhase3,
  runReplayPhase3Final,
  runReplayMerge,
} from "@/api/replay";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"] as const;

type ReplaySection = "phase2" | "phase3" | "phase3final" | "merge";

const SECTIONS: Array<{ key: ReplaySection; label: string }> = [
  { key: "phase2", label: "Phase II — Replay Processing" },
  { key: "phase3", label: "Phase III — Feedback" },
  { key: "phase3final", label: "Phase III — Final Lookup" },
  { key: "merge", label: "Merge Inconsistent Summaries" },
];

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
// Phase II Form
// ---------------------------------------------------------------------------

const phase2Schema = z.object({
  testingPeriod: z.object({ fiscalYear: z.string(), quarter: z.string() }),
  inputFile: z.string().min(1, "Required"),
  outputFile: z.string().min(1, "Required"),
  logLevel: z.string(),
});

type Phase2FormValues = z.infer<typeof phase2Schema>;

const Phase2Form: React.FC = () => {
  const navigate = useNavigate();

  const {
    control,
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Phase2FormValues>({
    resolver: zodResolver(phase2Schema),
    defaultValues: {
      testingPeriod: { fiscalYear: currentFY(), quarter: "Q1" },
      inputFile: "",
      outputFile: "",
      logLevel: "INFO",
    },
  });

  const mutation = useMutation({
    mutationFn: runReplayPhase2,
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const onSubmit = (values: Phase2FormValues) => {
    mutation.mutate({
      inputFile: values.inputFile,
      outputFile: values.outputFile,
      fiscalYear: values.testingPeriod.fiscalYear,
      quarter: values.testingPeriod.quarter,
      logLevel: values.logLevel,
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Process replay Phase II — initial replay processing against the input file.
      </p>

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
// Phase III Form
// ---------------------------------------------------------------------------

const phase3Schema = z.object({
  testingPeriod: z.object({ fiscalYear: z.string(), quarter: z.string() }),
  inputFile: z.string().min(1, "Required"),
  feedbackFile: z.string().min(1, "Required"),
  outputFile: z.string().min(1, "Required"),
  logLevel: z.string(),
});

type Phase3FormValues = z.infer<typeof phase3Schema>;

const Phase3Form: React.FC = () => {
  const navigate = useNavigate();

  const {
    control,
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Phase3FormValues>({
    resolver: zodResolver(phase3Schema),
    defaultValues: {
      testingPeriod: { fiscalYear: currentFY(), quarter: "Q1" },
      inputFile: "",
      feedbackFile: "",
      outputFile: "",
      logLevel: "INFO",
    },
  });

  const mutation = useMutation({
    mutationFn: runReplayPhase3,
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const onSubmit = (values: Phase3FormValues) => {
    mutation.mutate({
      inputFile: values.inputFile,
      feedbackFile: values.feedbackFile,
      outputFile: values.outputFile,
      fiscalYear: values.testingPeriod.fiscalYear,
      quarter: values.testingPeriod.quarter,
      logLevel: values.logLevel,
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Process replay Phase III — incorporate feedback file into replay output.
      </p>

      <Field label="Input File" error={errors.inputFile?.message}>
        <input
          {...register("inputFile")}
          disabled={isPending}
          className={inputCls}
          placeholder="/path/to/input.csv"
        />
      </Field>

      <Field label="Feedback File" error={errors.feedbackFile?.message}>
        <input
          {...register("feedbackFile")}
          disabled={isPending}
          className={inputCls}
          placeholder="/path/to/feedback.csv"
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
// Phase III Final Form
// ---------------------------------------------------------------------------

const phase3FinalSchema = z.object({
  testingPeriod: z.object({ fiscalYear: z.string(), quarter: z.string() }),
  inputFile: z.string().min(1, "Required"),
  outputFile: z.string().min(1, "Required"),
  logLevel: z.string(),
});

type Phase3FinalFormValues = z.infer<typeof phase3FinalSchema>;

const Phase3FinalForm: React.FC = () => {
  const navigate = useNavigate();

  const {
    control,
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Phase3FinalFormValues>({
    resolver: zodResolver(phase3FinalSchema),
    defaultValues: {
      testingPeriod: { fiscalYear: currentFY(), quarter: "Q1" },
      inputFile: "",
      outputFile: "",
      logLevel: "INFO",
    },
  });

  const mutation = useMutation({
    mutationFn: runReplayPhase3Final,
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const onSubmit = (values: Phase3FinalFormValues) => {
    mutation.mutate({
      inputFile: values.inputFile,
      outputFile: values.outputFile,
      fiscalYear: values.testingPeriod.fiscalYear,
      quarter: values.testingPeriod.quarter,
      logLevel: values.logLevel,
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Phase III final lookup — perform final ID resolution pass on the replay output.
      </p>

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
// Merge Form
// ---------------------------------------------------------------------------

const mergeSchema = z.object({
  buyerFile: z.string().min(1, "Required"),
  sellerFile: z.string().min(1, "Required"),
  outputFile: z.string().min(1, "Required"),
  logLevel: z.string(),
});

type MergeFormValues = z.infer<typeof mergeSchema>;

const MergeForm: React.FC = () => {
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<MergeFormValues>({
    resolver: zodResolver(mergeSchema),
    defaultValues: {
      buyerFile: "",
      sellerFile: "",
      outputFile: "",
      logLevel: "INFO",
    },
  });

  const mutation = useMutation({
    mutationFn: runReplayMerge,
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const onSubmit = (values: MergeFormValues) => {
    mutation.mutate({
      buyerFile: values.buyerFile,
      sellerFile: values.sellerFile,
      outputFile: values.outputFile,
      logLevel: values.logLevel,
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Merge buyer and seller inconsistent summary files into a single output.
      </p>

      <Field label="Buyer File" error={errors.buyerFile?.message}>
        <input
          {...register("buyerFile")}
          disabled={isPending}
          className={inputCls}
          placeholder="/path/to/buyer_summary.csv"
        />
      </Field>

      <Field label="Seller File" error={errors.sellerFile?.message}>
        <input
          {...register("sellerFile")}
          disabled={isPending}
          className={inputCls}
          placeholder="/path/to/seller_summary.csv"
        />
      </Field>

      <Field label="Output File" error={errors.outputFile?.message}>
        <input
          {...register("outputFile")}
          disabled={isPending}
          className={inputCls}
          placeholder="/path/to/merged_output.csv"
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
// Main Replay page
// ---------------------------------------------------------------------------

const FORM_COMPONENTS: Record<ReplaySection, React.FC> = {
  phase2: Phase2Form,
  phase3: Phase3Form,
  phase3final: Phase3FinalForm,
  merge: MergeForm,
};

const Replay: React.FC = () => {
  const [selected, setSelected] = useState<ReplaySection>("phase2");

  const ActiveForm = FORM_COMPONENTS[selected];
  const activeLabel = SECTIONS.find((s) => s.key === selected)?.label ?? "";

  return (
    <div className="space-y-6">
      {/* Page heading */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Replay</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Run replay processing scripts across all phases.
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

export default Replay;
