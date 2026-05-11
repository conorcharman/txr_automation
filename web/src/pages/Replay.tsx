import React, { useState, useEffect, useCallback, useRef } from "react";
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
import SmartPathConfig from "@/components/SmartPathConfig";
import ConfigLoader from "@/components/ConfigLoader";
import { browseDirectory, resolvePaths } from "@/api/filesystem";
import type { ResolvedPaths } from "@/types";
import {
  runReplayPhase2,
  runReplayPhase2Final,
  runReplayPhase3,
  runReplayPhase3Final,
  runReplayMerge,
} from "@/api/replay";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"] as const;

type ReplaySection = "phase2" | "phase2final" | "phase3" | "phase3final" | "merge";
type ActivePhase = "phase2" | "phase3";

type PhaseSubItem = { key: ReplaySection; label: string };

const PHASE2_SUBNAV: PhaseSubItem[] = [
  { key: "phase2",      label: "Feedback" },
  { key: "phase2final", label: "Final Lookup" },
];

const PHASE3_SUBNAV: PhaseSubItem[] = [
  { key: "phase3",      label: "Feedback" },
  { key: "phase3final", label: "Final Lookup" },
  { key: "merge",       label: "Merge" },
];

const SCRIPT_NAMES: Record<ReplaySection, string> = {
  phase2:      "replay_phase2",
  phase2final: "replay_phase2_final",
  phase3:      "replay_phase3",
  phase3final: "replay_phase3_final",
  merge:       "replay_merge_inconsistent",
};

const SECTION_LABELS: Record<ReplaySection, string> = {
  phase2:      "Feedback",
  phase2final: "Final Lookup",
  phase3:      "Feedback",
  phase3final: "Final Lookup",
  merge:       "Merge Inconsistent Summaries",
};

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
// Phase 2 Form
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
    getValues,
    reset,
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

  const testingPeriod = watch("testingPeriod");
  const [sourceFileCount, setSourceFileCount] = useState<number | null>(null);
  const resolvedLogPath = useRef<string>("");

  const handlePathsResolved = useCallback(
    async (paths: ResolvedPaths) => {
      resolvedLogPath.current = paths.logs;
      if (!watch("outputFile")) setValue("outputFile", paths.output);
      const { fiscalYear, quarter } = watch("testingPeriod");
      try {
        const atPaths = await resolvePaths({ fiscalYear, quarter, module: "accuracy_testing" });
        if (!watch("inputFile")) setValue("inputFile", atPaths.templates);
        const res = await browseDirectory(atPaths.templates);
        setSourceFileCount(res.entries.filter((e) => !e.isDir).length);
      } catch {
        setSourceFileCount(0);
      }
    },
    [setValue, watch],
  );

  const handleLoadConfig = (config: Record<string, unknown>) => {
    reset(config as unknown as Phase2FormValues);
  };

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
      logOutput: resolvedLogPath.current || "/app/data/logs",
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Process replay Phase 2 — initial replay processing against the input file.
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

      <SmartPathConfig
        fiscalYear={testingPeriod.fiscalYear}
        quarter={testingPeriod.quarter}
        module="replay"
        visibleStages={["kaizen", "output", "logs"]}
        onChange={handlePathsResolved}
        disabled={isPending}
      />

      {sourceFileCount !== null && (
        <div className="rounded-md border border-border px-3 py-3 space-y-2">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Source Files (Accuracy Testing — Templates)
          </p>
          <div className="flex items-center gap-2">
            <span className={cn("h-2 w-2 rounded-full shrink-0", sourceFileCount > 0 ? "bg-green-500" : "bg-orange-400")} />
            <span className="text-xs text-muted-foreground shrink-0">Input directory</span>
            <span className="truncate text-xs font-mono text-foreground/80">
              {sourceFileCount > 0 ? `${sourceFileCount} file(s) found` : "no files found"}
            </span>
          </div>
        </div>
      )}

      <AdvancedSection isOpen={showAdvanced} onToggle={() => setShowAdvanced(!showAdvanced)}>
        <Field label="Log Level" hint="Logging verbosity level." error={errors.logLevel?.message}>
          <select {...register("logLevel")} disabled={isPending} className={selectCls}>
            {LOG_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </Field>
        <Field label="Input Directory" hint="Override: directory containing Phase 2 replay source CSV files (auto-resolved from accuracy_testing/templates)." error={errors.inputFile?.message}>
          <PathPickerInput
            value={watch("inputFile") ?? ""}
            onChange={(v) => setValue("inputFile", v)}
            mode="directory"
            placeholder="auto-resolved"
            disabled={isPending}
          />
        </Field>
        <Field label="Output Directory" hint="Override: directory for Phase 2 processed output files (auto-resolved from replay/output)." error={errors.outputFile?.message}>
          <PathPickerInput
            value={watch("outputFile") ?? ""}
            onChange={(v) => setValue("outputFile", v)}
            mode="directory"
            placeholder="auto-resolved"
            disabled={isPending}
          />
        </Field>
        <ConfigLoader
          scriptName="replay_phase2"
          currentConfig={getValues() as unknown as Record<string, unknown>}
          onLoad={handleLoadConfig}
        />
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
// Phase 2 Final Form
// ---------------------------------------------------------------------------

const phase2FinalSchema = z.object({
  testingPeriod: z.object({ fiscalYear: z.string(), quarter: z.string() }),
  replayOutputFile: z.string().min(1, "Required"),
  unavistaFiles: z.string().min(1, "Required"),
  outputFile: z.string().min(1, "Required"),
  logLevel: z.string(),
});

type Phase2FinalFormValues = z.infer<typeof phase2FinalSchema>;

const PHASE2FINAL_DEFAULTS: Phase2FinalFormValues = {
  testingPeriod: { fiscalYear: currentFY(), quarter: "Q1" },
  replayOutputFile: "",
  unavistaFiles: "",
  outputFile: "",
  logLevel: "INFO",
};

const Phase2FinalForm: React.FC = () => {
  const navigate = useNavigate();
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
  } = useForm<Phase2FinalFormValues>({
    resolver: zodResolver(phase2FinalSchema),
    defaultValues: loadCache("replay_phase2final", PHASE2FINAL_DEFAULTS),
  });

  useEffect(() => {
    const sub = watch((values) => {
      try { localStorage.setItem("txr_form_replay_phase2final", JSON.stringify(values)); } catch { /* ignore */ }
    });
    return () => sub.unsubscribe();
  }, [watch]);

  const testingPeriod = watch("testingPeriod");
  const [outputFileCount, setOutputFileCount] = useState<number | null>(null);
  const [unavistaFileCount, setUnavistaFileCount] = useState<number | null>(null);
  const resolvedLogPath = useRef<string>("");

  const handlePathsResolved = useCallback(
    async (paths: ResolvedPaths) => {
      resolvedLogPath.current = paths.logs;
      if (!watch("replayOutputFile")) setValue("replayOutputFile", paths.output);
      if (!watch("outputFile")) setValue("outputFile", paths.output);
      if (!watch("unavistaFiles")) setValue("unavistaFiles", paths.kaizen);
      try {
        const res = await browseDirectory(paths.output);
        setOutputFileCount(res.entries.filter((e) => !e.isDir).length);
      } catch {
        setOutputFileCount(0);
      }
      try {
        const res = await browseDirectory(paths.kaizen);
        setUnavistaFileCount(res.entries.filter((e) => !e.isDir).length);
      } catch {
        setUnavistaFileCount(0);
      }
    },
    [setValue, watch],
  );

  const handleLoadConfig = (config: Record<string, unknown>) => {
    reset(config as unknown as Phase2FinalFormValues);
  };

  const mutation = useMutation({
    mutationFn: runReplayPhase2Final,
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const onSubmit = (values: Phase2FinalFormValues) => {
    mutation.mutate({
      replayOutputFile: values.replayOutputFile,
      unavistaFiles: values.unavistaFiles,
      outputFile: values.outputFile,
      fiscalYear: values.testingPeriod.fiscalYear,
      quarter: values.testingPeriod.quarter,
      logLevel: values.logLevel,
      logOutput: resolvedLogPath.current || "/app/data/logs",
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Phase 2 final lookup — validate corrections from Phase 2 output against UnaVista
        transaction data and annotate any discrepancies.
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

      <SmartPathConfig
        fiscalYear={testingPeriod.fiscalYear}
        quarter={testingPeriod.quarter}
        module="replay"
        visibleStages={["kaizen", "output", "logs"]}
        onChange={handlePathsResolved}
        disabled={isPending}
      />

      {(outputFileCount !== null || unavistaFileCount !== null) && (
        <div className="rounded-md border border-border px-3 py-3 space-y-2">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Discovered Files
          </p>
          <div className="space-y-1">
            {outputFileCount !== null && (
              <div className="flex items-center gap-2">
                <span className={cn("h-2 w-2 rounded-full shrink-0", outputFileCount > 0 ? "bg-green-500" : "bg-orange-400")} />
                <span className="text-xs text-muted-foreground shrink-0">Phase 2 output</span>
                <span className="truncate text-xs font-mono text-foreground/80">
                  {outputFileCount > 0 ? `${outputFileCount} file(s) found` : "no files found"}
                </span>
              </div>
            )}
            {unavistaFileCount !== null && (
              <div className="flex items-center gap-2">
                <span className={cn("h-2 w-2 rounded-full shrink-0", unavistaFileCount > 0 ? "bg-green-500" : "bg-orange-400")} />
                <span className="text-xs text-muted-foreground shrink-0">UnaVista (replay/kaizen)</span>
                <span className="truncate text-xs font-mono text-foreground/80">
                  {unavistaFileCount > 0 ? `${unavistaFileCount} file(s) found` : "no files found"}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      <AdvancedSection isOpen={showAdvanced} onToggle={() => setShowAdvanced(!showAdvanced)}>
        <Field label="Log Level" hint="Logging verbosity level." error={errors.logLevel?.message}>
          <select {...register("logLevel")} disabled={isPending} className={selectCls}>
            {LOG_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </Field>
        <Field label="UnaVista Files" hint="Override: directory containing UnaVista transaction CSV files (auto-resolved from replay/kaizen)." error={errors.unavistaFiles?.message}>
          <PathPickerInput
            value={watch("unavistaFiles") ?? ""}
            onChange={(v) => setValue("unavistaFiles", v)}
            mode="directory"
            placeholder="auto-resolved from replay/kaizen"
            disabled={isPending}
          />
        </Field>
        <Field label="Phase 2 Output Directory" hint="Override: directory containing Phase 2 processor output CSV files." error={errors.replayOutputFile?.message}>
          <PathPickerInput
            value={watch("replayOutputFile") ?? ""}
            onChange={(v) => setValue("replayOutputFile", v)}
            mode="directory"
            placeholder="auto-resolved from replay/output"
            disabled={isPending}
          />
        </Field>
        <Field label="Output Directory" hint="Override: directory for Phase 2 final lookup annotated output files." error={errors.outputFile?.message}>
          <PathPickerInput
            value={watch("outputFile") ?? ""}
            onChange={(v) => setValue("outputFile", v)}
            mode="directory"
            placeholder="auto-resolved from replay/output"
            disabled={isPending}
          />
        </Field>
        <ConfigLoader
          scriptName="replay_phase2_final"
          currentConfig={getValues() as unknown as Record<string, unknown>}
          onLoad={handleLoadConfig}
        />
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
// Phase 3 Form
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
    getValues,
    reset,
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

  const testingPeriod = watch("testingPeriod");
  const [inputFileCount, setInputFileCount] = useState<number | null>(null);
  const [feedbackFileCount, setFeedbackFileCount] = useState<number | null>(null);
  const resolvedLogPath = useRef<string>("");

  const handlePathsResolved = useCallback(
    async (paths: ResolvedPaths) => {
      resolvedLogPath.current = paths.logs;
      if (!watch("inputFile")) setValue("inputFile", paths.output);
      if (!watch("outputFile")) setValue("outputFile", paths.output);
      try {
        const res = await browseDirectory(paths.output);
        setInputFileCount(res.entries.filter((e) => !e.isDir).length);
      } catch {
        setInputFileCount(0);
      }
      const { fiscalYear, quarter } = watch("testingPeriod");
      try {
        const atPaths = await resolvePaths({ fiscalYear, quarter, module: "accuracy_testing" });
        if (!watch("feedbackFile")) setValue("feedbackFile", atPaths.templates);
        const res = await browseDirectory(atPaths.templates);
        setFeedbackFileCount(res.entries.filter((e) => !e.isDir).length);
      } catch {
        setFeedbackFileCount(0);
      }
    },
    [setValue, watch],
  );

  const handleLoadConfig = (config: Record<string, unknown>) => {
    reset(config as unknown as Phase3FormValues);
  };

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
      logOutput: resolvedLogPath.current || "/app/data/logs",
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Process replay Phase 3 — incorporate feedback file into replay output.
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

      <SmartPathConfig
        fiscalYear={testingPeriod.fiscalYear}
        quarter={testingPeriod.quarter}
        module="replay"
        visibleStages={["kaizen", "output", "logs"]}
        onChange={handlePathsResolved}
        disabled={isPending}
      />

      {(inputFileCount !== null || feedbackFileCount !== null) && (
        <div className="rounded-md border border-border px-3 py-3 space-y-2">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Discovered Files
          </p>
          <div className="space-y-1">
            {inputFileCount !== null && (
              <div className="flex items-center gap-2">
                <span className={cn("h-2 w-2 rounded-full shrink-0", inputFileCount > 0 ? "bg-green-500" : "bg-orange-400")} />
                <span className="text-xs text-muted-foreground shrink-0">Phase 2 output</span>
                <span className="truncate text-xs font-mono text-foreground/80">
                  {inputFileCount > 0 ? `${inputFileCount} file(s) found` : "no files found"}
                </span>
              </div>
            )}
            {feedbackFileCount !== null && (
              <div className="flex items-center gap-2">
                <span className={cn("h-2 w-2 rounded-full shrink-0", feedbackFileCount > 0 ? "bg-green-500" : "bg-orange-400")} />
                <span className="text-xs text-muted-foreground shrink-0">Feedback (AT Templates)</span>
                <span className="truncate text-xs font-mono text-foreground/80">
                  {feedbackFileCount > 0 ? `${feedbackFileCount} file(s) found` : "no files found"}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      <AdvancedSection isOpen={showAdvanced} onToggle={() => setShowAdvanced(!showAdvanced)}>
        <Field label="Log Level" hint="Logging verbosity level." error={errors.logLevel?.message}>
          <select {...register("logLevel")} disabled={isPending} className={selectCls}>
            {LOG_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </Field>
        <Field label="Input Directory" hint="Override: directory containing Phase 3 replay input CSV files (auto-resolved from replay/output)." error={errors.inputFile?.message}>
          <PathPickerInput
            value={watch("inputFile") ?? ""}
            onChange={(v) => setValue("inputFile", v)}
            mode="directory"
            placeholder="auto-resolved from replay/output"
            disabled={isPending}
          />
        </Field>
        <Field label="Feedback Directory" hint="Override: directory containing incident template CSV files (auto-resolved from accuracy_testing/templates)." error={errors.feedbackFile?.message}>
          <PathPickerInput
            value={watch("feedbackFile") ?? ""}
            onChange={(v) => setValue("feedbackFile", v)}
            mode="directory"
            placeholder="auto-resolved from accuracy_testing/templates"
            disabled={isPending}
          />
        </Field>
        <Field label="Output Directory" hint="Override: directory for Phase 3 processed output files (auto-resolved from replay/output)." error={errors.outputFile?.message}>
          <PathPickerInput
            value={watch("outputFile") ?? ""}
            onChange={(v) => setValue("outputFile", v)}
            mode="directory"
            placeholder="auto-resolved from replay/output"
            disabled={isPending}
          />
        </Field>
        <ConfigLoader
          scriptName="replay_phase3"
          currentConfig={getValues() as unknown as Record<string, unknown>}
          onLoad={handleLoadConfig}
        />
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
// Phase 3 Final Form
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
    getValues,
    reset,
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

  const testingPeriod = watch("testingPeriod");
  const [phase3FileCount, setPhase3FileCount] = useState<number | null>(null);
  const resolvedLogPath = useRef<string>("");

  const handlePathsResolved = useCallback(
    async (paths: ResolvedPaths) => {
      resolvedLogPath.current = paths.logs;
      if (!watch("inputFile")) setValue("inputFile", paths.output);
      if (!watch("outputFile")) setValue("outputFile", paths.output);
      try {
        const res = await browseDirectory(paths.output);
        setPhase3FileCount(res.entries.filter((e) => !e.isDir).length);
      } catch {
        setPhase3FileCount(0);
      }
    },
    [setValue, watch],
  );

  const handleLoadConfig = (config: Record<string, unknown>) => {
    reset(config as unknown as Phase3FinalFormValues);
  };

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
      logOutput: resolvedLogPath.current || "/app/data/logs",
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Phase 3 final lookup — perform final ID resolution pass on the replay output.
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

      <SmartPathConfig
        fiscalYear={testingPeriod.fiscalYear}
        quarter={testingPeriod.quarter}
        module="replay"
        visibleStages={["kaizen", "output", "logs"]}
        onChange={handlePathsResolved}
        disabled={isPending}
      />

      {phase3FileCount !== null && (
        <div className="rounded-md border border-border px-3 py-3 space-y-2">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Phase 3 Output (replay/output)
          </p>
          <div className="flex items-center gap-2">
            <span className={cn("h-2 w-2 rounded-full shrink-0", phase3FileCount > 0 ? "bg-green-500" : "bg-orange-400")} />
            <span className="text-xs text-muted-foreground shrink-0">Files</span>
            <span className="truncate text-xs font-mono text-foreground/80">
              {phase3FileCount > 0 ? `${phase3FileCount} file(s) found` : "no files found"}
            </span>
          </div>
        </div>
      )}

      <AdvancedSection isOpen={showAdvanced} onToggle={() => setShowAdvanced(!showAdvanced)}>
        <Field label="Log Level" hint="Logging verbosity level." error={errors.logLevel?.message}>
          <select {...register("logLevel")} disabled={isPending} className={selectCls}>
            {LOG_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </Field>
        <Field label="Input Directory" hint="Override: Phase 3 output directory containing inconsistent summary files (auto-resolved from replay/output)." error={errors.inputFile?.message}>
          <PathPickerInput
            value={watch("inputFile") ?? ""}
            onChange={(v) => setValue("inputFile", v)}
            mode="directory"
            placeholder="auto-resolved from replay/output"
            disabled={isPending}
          />
        </Field>
        <Field label="Output Directory" hint="Override: directory for Phase 3 final lookup output files (auto-resolved from replay/output)." error={errors.outputFile?.message}>
          <PathPickerInput
            value={watch("outputFile") ?? ""}
            onChange={(v) => setValue("outputFile", v)}
            mode="directory"
            placeholder="auto-resolved from replay/output"
            disabled={isPending}
          />
        </Field>
        <ConfigLoader
          scriptName="replay_phase3_final"
          currentConfig={getValues() as unknown as Record<string, unknown>}
          onLoad={handleLoadConfig}
        />
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
  testingPeriod: z.object({ fiscalYear: z.string(), quarter: z.string() }),
  buyerFile: z.string().min(1, "Required"),
  sellerFile: z.string().min(1, "Required"),
  outputFile: z.string().min(1, "Required"),
  logLevel: z.string(),
  dryRun: z.boolean(),
});

type MergeFormValues = z.infer<typeof mergeSchema>;

const MERGE_DEFAULTS: MergeFormValues = {
  testingPeriod: { fiscalYear: currentFY(), quarter: "Q1" },
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
    control,
    register,
    handleSubmit,
    watch,
    setValue,
    getValues,
    reset,
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

  const testingPeriod = watch("testingPeriod");
  const [mergeFiles, setMergeFiles] = useState<{ ids: string; names: string } | null>(null);

  const handlePathsResolved = useCallback(
    async (paths: ResolvedPaths) => {
      if (!watch("buyerFile")) setValue("buyerFile", paths.output);
      if (!watch("sellerFile")) setValue("sellerFile", paths.output);
      if (!watch("outputFile")) setValue("outputFile", paths.output);
      try {
        const res = await browseDirectory(paths.output);
        const files = res.entries.filter((e) => !e.isDir).map((e) => e.path);
        const idsFile = files.find((f) => /inconsistent.*id/i.test(f)) ?? "";
        const namesFile = files.find((f) => /inconsistent.*name/i.test(f)) ?? "";
        setMergeFiles({ ids: idsFile, names: namesFile });
      } catch {
        setMergeFiles(null);
      }
    },
    [setValue, watch],
  );

  const handleLoadConfig = (config: Record<string, unknown>) => {
    reset(config as unknown as MergeFormValues);
  };

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
        Merges records for one client that are split across multiple rows after Phase 3. Runs on
        both the Inconsistent IDs and Inconsistent Names files; these remain as separate outputs.
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

      <SmartPathConfig
        fiscalYear={testingPeriod.fiscalYear}
        quarter={testingPeriod.quarter}
        module="replay"
        visibleStages={["kaizen", "output", "logs"]}
        onChange={handlePathsResolved}
        disabled={isPending}
      />

      {mergeFiles !== null && (
        <div className="rounded-md border border-border px-3 py-3 space-y-2">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Phase 3 Output (replay/output)
          </p>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className={cn("h-2 w-2 rounded-full shrink-0", mergeFiles.ids ? "bg-green-500" : "bg-orange-400")} />
              <span className="text-xs text-muted-foreground shrink-0">Inconsistent IDs</span>
              <span className="truncate text-xs font-mono text-foreground/80">
                {mergeFiles.ids || "not found"}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className={cn("h-2 w-2 rounded-full shrink-0", mergeFiles.names ? "bg-green-500" : "bg-orange-400")} />
              <span className="text-xs text-muted-foreground shrink-0">Inconsistent Names</span>
              <span className="truncate text-xs font-mono text-foreground/80">
                {mergeFiles.names || "not found"}
              </span>
            </div>
          </div>
        </div>
      )}

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
        <Field label="Inconsistent IDs Directory" hint="Override: directory containing Inconsistent IDs summary CSV files (auto-resolved from replay/output)." error={errors.buyerFile?.message}>
          <PathPickerInput
            value={watch("buyerFile") ?? ""}
            onChange={(v) => setValue("buyerFile", v)}
            mode="directory"
            placeholder="auto-resolved from replay/output"
            disabled={isPending}
          />
        </Field>
        <Field label="Inconsistent Names Directory" hint="Override: directory containing Inconsistent Names summary CSV files (auto-resolved from replay/output)." error={errors.sellerFile?.message}>
          <PathPickerInput
            value={watch("sellerFile") ?? ""}
            onChange={(v) => setValue("sellerFile", v)}
            mode="directory"
            placeholder="auto-resolved from replay/output"
            disabled={isPending}
          />
        </Field>
        <Field label="Output Directory" hint="Override: directory for merged output files (auto-resolved from replay/output)." error={errors.outputFile?.message}>
          <PathPickerInput
            value={watch("outputFile") ?? ""}
            onChange={(v) => setValue("outputFile", v)}
            mode="directory"
            placeholder="auto-resolved from replay/output"
            disabled={isPending}
          />
        </Field>
        <ConfigLoader
          scriptName="replay_merge_inconsistent"
          currentConfig={getValues() as unknown as Record<string, unknown>}
          onLoad={handleLoadConfig}
        />
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
  phase2final: Phase2FinalForm,
  phase3: Phase3Form,
  phase3final: Phase3FinalForm,
  merge: MergeForm,
};

const Replay: React.FC = () => {
  const [activePhase, setActivePhase] = useState<ActivePhase>("phase2");
  const [phase2Section, setPhase2Section] = useState<ReplaySection>("phase2");
  const [phase3Section, setPhase3Section] = useState<ReplaySection>("phase3");

  const activeSection: ReplaySection =
    activePhase === "phase2" ? phase2Section : phase3Section;

  const ActiveForm = FORM_COMPONENTS[activeSection];

  return (
    <div className="space-y-6">
      {/* Page heading */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Replay</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Run replay processing scripts across all phases.
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-border">
        {(["phase2", "phase3"] as const).map((phase) => (
          <button
            key={phase}
            type="button"
            onClick={() => setActivePhase(phase)}
            className={cn(
              "px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors",
              activePhase === phase
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {phase === "phase2" ? "Phase 2" : "Phase 3"}
          </button>
        ))}
      </div>

      {/* Phase 2 tab */}
      {activePhase === "phase2" && (
        <div className="flex gap-6 min-h-[400px]">
          <nav className="w-52 shrink-0 space-y-1">
            {PHASE2_SUBNAV.map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => setPhase2Section(item.key)}
                className={navItemCls(phase2Section === item.key)}
              >
                {item.label}
              </button>
            ))}
          </nav>
          <div className="flex-1 min-w-0 rounded-lg border border-border p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold">{SECTION_LABELS[phase2Section]}</h2>
              <LastRunBadge scriptName={SCRIPT_NAMES[phase2Section]} />
            </div>
            <ActiveForm key={activeSection} />
          </div>
        </div>
      )}

      {/* Phase 3 tab */}
      {activePhase === "phase3" && (
        <div className="flex gap-6 min-h-[400px]">
          <nav className="w-52 shrink-0 space-y-1">
            {PHASE3_SUBNAV.map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => setPhase3Section(item.key)}
                className={navItemCls(phase3Section === item.key)}
              >
                {item.label}
              </button>
            ))}
          </nav>
          <div className="flex-1 min-w-0 rounded-lg border border-border p-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-lg font-semibold">{SECTION_LABELS[phase3Section]}</h2>
              <LastRunBadge scriptName={SCRIPT_NAMES[phase3Section]} />
            </div>
            <ActiveForm key={activeSection} />
          </div>
        </div>
      )}
    </div>
  );
};

export default Replay;
