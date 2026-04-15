import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { PathPickerInput } from "@/components/PathPickerInput";
import TestingPeriodSelector from "@/components/TestingPeriodSelector";
import LastRunBadge from "@/components/LastRunBadge";
import Field from "@/components/Field";
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
// Phase II Form
// ---------------------------------------------------------------------------

const phase2Schema = z.object({
  testingPeriod: z.object({ fiscalYear: z.string(), quarter: z.string() }),
  inputFile: z.string().min(1, "Required"),
  outputFile: z.string().min(1, "Required"),
  logLevel: z.string(),
});

type Phase2FormValues = z.infer<typeof phase2Schema>;

const PHASE2_DEFAULTS: Phase2FormValues = {
  testingPeriod: { fiscalYear: currentFY(), quarter: "Q1" },
  inputFile: "",
  outputFile: "",
  logLevel: "INFO",
};

const Phase2Form: React.FC = () => {
  const navigate = useNavigate();
  const [showAdvanced, setShowAdvanced] = useState(false);

  const {
    control,
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<Phase2FormValues>({
    resolver: zodResolver(phase2Schema),
    defaultValues: loadCache("replay_phase2", PHASE2_DEFAULTS),
  });

  useEffect(() => {
    const sub = watch((values) => {
      try { localStorage.setItem("txr_form_replay_phase2", JSON.stringify(values)); } catch { /* ignore */ }
    });
    return () => sub.unsubscribe();
  }, [watch]);

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
      logOutput: ((): string => { try { return localStorage.getItem("txr_global_log_output") || "logs"; } catch { return "logs"; } })(),
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Process replay Phase II — initial replay processing against the input file.
      </p>

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

      <Field label="Input File" hint="Directory containing the Phase II replay CSV/XLSX input files." error={errors.inputFile?.message}>
        <PathPickerInput
          value={watch("inputFile") ?? ""}
          onChange={(v) => setValue("inputFile", v)}
          mode="file"
          placeholder="/path/to/input.csv"
          disabled={isPending}
        />
      </Field>

      <Field label="Output File" hint="Directory for Phase II processed output files." error={errors.outputFile?.message}>
        <PathPickerInput
          value={watch("outputFile") ?? ""}
          onChange={(v) => setValue("outputFile", v)}
          mode="file"
          placeholder="/path/to/output.csv"
          disabled={isPending}
        />
      </Field>

      <AdvancedSection isOpen={showAdvanced} onToggle={() => setShowAdvanced(!showAdvanced)}>
        <Field label="Log Level" hint="Logging verbosity level." error={errors.logLevel?.message}>
          <select {...register("logLevel")} disabled={isPending} className={selectCls}>
            {LOG_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </Field>
      </AdvancedSection>

      <Button type="submit" disabled={isPending} className="w-full">
        {isPending ? "Running…" : "Run"}
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

const PHASE3_DEFAULTS: Phase3FormValues = {
  testingPeriod: { fiscalYear: currentFY(), quarter: "Q1" },
  inputFile: "",
  feedbackFile: "",
  outputFile: "",
  logLevel: "INFO",
};

const Phase3Form: React.FC = () => {
  const navigate = useNavigate();
  const [showAdvanced, setShowAdvanced] = useState(false);

  const {
    control,
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<Phase3FormValues>({
    resolver: zodResolver(phase3Schema),
    defaultValues: loadCache("replay_phase3", PHASE3_DEFAULTS),
  });

  useEffect(() => {
    const sub = watch((values) => {
      try { localStorage.setItem("txr_form_replay_phase3", JSON.stringify(values)); } catch { /* ignore */ }
    });
    return () => sub.unsubscribe();
  }, [watch]);

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
      logOutput: ((): string => { try { return localStorage.getItem("txr_global_log_output") || "logs"; } catch { return "logs"; } })(),
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Process replay Phase III — incorporate feedback file into replay output.
      </p>

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

      <Field label="Input File" hint="Directory containing the Phase III replay input files." error={errors.inputFile?.message}>
        <PathPickerInput
          value={watch("inputFile") ?? ""}
          onChange={(v) => setValue("inputFile", v)}
          mode="file"
          placeholder="/path/to/input.csv"
          disabled={isPending}
        />
      </Field>

      <Field label="Feedback File" hint="Directory containing incident code analysis CSVs." error={errors.feedbackFile?.message}>
        <PathPickerInput
          value={watch("feedbackFile") ?? ""}
          onChange={(v) => setValue("feedbackFile", v)}
          mode="file"
          placeholder="/path/to/feedback.csv"
          disabled={isPending}
        />
      </Field>

      <Field label="Output File" hint="Directory for Phase III processed output files." error={errors.outputFile?.message}>
        <PathPickerInput
          value={watch("outputFile") ?? ""}
          onChange={(v) => setValue("outputFile", v)}
          mode="file"
          placeholder="/path/to/output.csv"
          disabled={isPending}
        />
      </Field>

      <AdvancedSection isOpen={showAdvanced} onToggle={() => setShowAdvanced(!showAdvanced)}>
        <Field label="Log Level" hint="Logging verbosity level." error={errors.logLevel?.message}>
          <select {...register("logLevel")} disabled={isPending} className={selectCls}>
            {LOG_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </Field>
      </AdvancedSection>

      <Button type="submit" disabled={isPending} className="w-full">
        {isPending ? "Running…" : "Run"}
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
// Phase III Final Form
// ---------------------------------------------------------------------------

const phase3FinalSchema = z.object({
  testingPeriod: z.object({ fiscalYear: z.string(), quarter: z.string() }),
  inputFile: z.string().min(1, "Required"),
  outputFile: z.string().min(1, "Required"),
  logLevel: z.string(),
});

type Phase3FinalFormValues = z.infer<typeof phase3FinalSchema>;

const PHASE3FINAL_DEFAULTS: Phase3FinalFormValues = {
  testingPeriod: { fiscalYear: currentFY(), quarter: "Q1" },
  inputFile: "",
  outputFile: "",
  logLevel: "INFO",
};

const Phase3FinalForm: React.FC = () => {
  const navigate = useNavigate();
  const [showAdvanced, setShowAdvanced] = useState(false);

  const {
    control,
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<Phase3FinalFormValues>({
    resolver: zodResolver(phase3FinalSchema),
    defaultValues: loadCache("replay_phase3final", PHASE3FINAL_DEFAULTS),
  });

  useEffect(() => {
    const sub = watch((values) => {
      try { localStorage.setItem("txr_form_replay_phase3final", JSON.stringify(values)); } catch { /* ignore */ }
    });
    return () => sub.unsubscribe();
  }, [watch]);

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
      logOutput: ((): string => { try { return localStorage.getItem("txr_global_log_output") || "logs"; } catch { return "logs"; } })(),
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Phase III final lookup — perform final ID resolution pass on the replay output.
      </p>

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

      <Field label="Input File" hint="Phase III output directory containing inconsistent summary files." error={errors.inputFile?.message}>
        <PathPickerInput
          value={watch("inputFile") ?? ""}
          onChange={(v) => setValue("inputFile", v)}
          mode="file"
          placeholder="/path/to/input.csv"
          disabled={isPending}
        />
      </Field>

      <Field label="Output File" hint="Directory for Phase III final lookup output files." error={errors.outputFile?.message}>
        <PathPickerInput
          value={watch("outputFile") ?? ""}
          onChange={(v) => setValue("outputFile", v)}
          mode="file"
          placeholder="/path/to/output.csv"
          disabled={isPending}
        />
      </Field>

      <AdvancedSection isOpen={showAdvanced} onToggle={() => setShowAdvanced(!showAdvanced)}>
        <Field label="Log Level" hint="Logging verbosity level." error={errors.logLevel?.message}>
          <select {...register("logLevel")} disabled={isPending} className={selectCls}>
            {LOG_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </Field>
      </AdvancedSection>

      <Button type="submit" disabled={isPending} className="w-full">
        {isPending ? "Running…" : "Run"}
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
// Merge Form
// ---------------------------------------------------------------------------

const mergeSchema = z.object({
  buyerFile: z.string().min(1, "Required"),
  sellerFile: z.string().min(1, "Required"),
  outputFile: z.string().min(1, "Required"),
  logLevel: z.string(),
  dryRun: z.boolean(),
});

type MergeFormValues = z.infer<typeof mergeSchema>;

const MERGE_DEFAULTS: MergeFormValues = {
  buyerFile: "",
  sellerFile: "",
  outputFile: "",
  logLevel: "INFO",
  dryRun: false,
};

const MergeForm: React.FC = () => {
  const navigate = useNavigate();
  const [showAdvanced, setShowAdvanced] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<MergeFormValues>({
    resolver: zodResolver(mergeSchema),
    defaultValues: loadCache("replay_merge", MERGE_DEFAULTS),
  });

  useEffect(() => {
    const sub = watch((values) => {
      try { localStorage.setItem("txr_form_replay_merge", JSON.stringify(values)); } catch { /* ignore */ }
    });
    return () => sub.unsubscribe();
  }, [watch]);

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
      dryRun: values.dryRun || undefined,
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Merge buyer and seller inconsistent summary files into a single output.
      </p>

      <Field label="Buyer File" hint="Directory containing Inconsistent IDs summary CSV files." error={errors.buyerFile?.message}>
        <PathPickerInput
          value={watch("buyerFile") ?? ""}
          onChange={(v) => setValue("buyerFile", v)}
          mode="file"
          placeholder="/path/to/buyer_summary.csv"
          disabled={isPending}
        />
      </Field>

      <Field label="Seller File" hint="Directory containing Inconsistent Names summary CSV files." error={errors.sellerFile?.message}>
        <PathPickerInput
          value={watch("sellerFile") ?? ""}
          onChange={(v) => setValue("sellerFile", v)}
          mode="file"
          placeholder="/path/to/seller_summary.csv"
          disabled={isPending}
        />
      </Field>

      <Field label="Output File" hint="Directory for merged output files." error={errors.outputFile?.message}>
        <PathPickerInput
          value={watch("outputFile") ?? ""}
          onChange={(v) => setValue("outputFile", v)}
          mode="file"
          placeholder="/path/to/merged_output.csv"
          disabled={isPending}
        />
      </Field>

      <AdvancedSection isOpen={showAdvanced} onToggle={() => setShowAdvanced(!showAdvanced)}>
        <div className="flex flex-wrap gap-4 items-end">
          <Field label="Log Level" hint="Logging verbosity level." error={errors.logLevel?.message}>
            <select {...register("logLevel")} disabled={isPending} className={selectCls}>
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
          {mutation.error instanceof Error ? mutation.error.message : "An error occurred"}
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
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold">{activeLabel}</h2>
            <LastRunBadge
              scriptName={
                selected === "phase2"
                  ? "replay_phase2"
                  : selected === "phase3"
                    ? "replay_phase3"
                    : selected === "phase3final"
                      ? "replay_phase3_final"
                      : "replay_merge_inconsistent"
              }
            />
          </div>
          <ActiveForm key={selected} />
        </div>
      </div>
    </div>
  );
};

export default Replay;
