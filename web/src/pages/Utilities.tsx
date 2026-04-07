import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { xlsxConvert, xmlConvert } from "@/api/utilities";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"] as const;

type UtilSection = "xlsx" | "xml";

const SECTIONS: Array<{ key: UtilSection; label: string }> = [
  { key: "xlsx", label: "XLSX Converter" },
  { key: "xml", label: "XML Converter" },
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
// XLSX Converter Form
// ---------------------------------------------------------------------------

const xlsxSchema = z
  .object({
    mode: z.enum(["single", "batch"]),
    parentDir: z.string().optional(),
    inputDir: z.string().optional(),
    outputDir: z.string().optional(),
    logLevel: z.string(),
  })
  .superRefine((data, ctx) => {
    if (data.mode === "single") {
      if (!data.inputDir) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Required", path: ["inputDir"] });
      }
      if (!data.outputDir) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Required", path: ["outputDir"] });
      }
    }
    if (data.mode === "batch" && !data.parentDir) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: "Required", path: ["parentDir"] });
    }
  });

type XlsxFormValues = z.infer<typeof xlsxSchema>;

const XlsxForm: React.FC = () => {
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<XlsxFormValues>({
    resolver: zodResolver(xlsxSchema),
    defaultValues: {
      mode: "single",
      parentDir: "",
      inputDir: "",
      outputDir: "",
      logLevel: "INFO",
    },
  });

  const mode = watch("mode");

  const mutation = useMutation({
    mutationFn: xlsxConvert,
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const onSubmit = (values: XlsxFormValues) => {
    mutation.mutate({
      mode: values.mode,
      parentDir: values.parentDir || undefined,
      inputDir: values.inputDir || undefined,
      outputDir: values.outputDir || undefined,
      logLevel: values.logLevel,
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Convert XLSX files to CSV format, either individually or in batch across subfolders.
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
        <>
          <Field label="Input Directory" error={errors.inputDir?.message}>
            <input
              {...register("inputDir")}
              disabled={isPending}
              className={inputCls}
              placeholder="/path/to/input/dir"
            />
          </Field>
          <Field label="Output Directory" error={errors.outputDir?.message}>
            <input
              {...register("outputDir")}
              disabled={isPending}
              className={inputCls}
              placeholder="/path/to/output/dir"
            />
          </Field>
        </>
      )}

      {mode === "batch" && (
        <Field label="Parent Directory" error={errors.parentDir?.message}>
          <input
            {...register("parentDir")}
            disabled={isPending}
            className={inputCls}
            placeholder="/path/to/parent/dir"
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
        {isPending ? "Running…" : "Convert"}
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
// XML Converter Form
// ---------------------------------------------------------------------------

const xmlSchema = z.object({
  inputFile: z.string().optional(),
  parentDir: z.string().optional(),
  outputDir: z.string().optional(),
  logLevel: z.string(),
});

type XmlFormValues = z.infer<typeof xmlSchema>;

const XmlForm: React.FC = () => {
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<XmlFormValues>({
    resolver: zodResolver(xmlSchema),
    defaultValues: {
      inputFile: "",
      parentDir: "",
      outputDir: "",
      logLevel: "INFO",
    },
  });

  const mutation = useMutation({
    mutationFn: xmlConvert,
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const onSubmit = (values: XmlFormValues) => {
    mutation.mutate({
      inputFile: values.inputFile || undefined,
      parentDir: values.parentDir || undefined,
      outputDir: values.outputDir || undefined,
      logLevel: values.logLevel,
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Convert XML files to CSV format.
      </p>

      <Field label="Input File" error={errors.inputFile?.message}>
        <input
          {...register("inputFile")}
          disabled={isPending}
          className={inputCls}
          placeholder="/path/to/input.xml"
        />
      </Field>

      <Field label="Parent Directory" error={errors.parentDir?.message}>
        <input
          {...register("parentDir")}
          disabled={isPending}
          className={inputCls}
          placeholder="/path/to/parent/dir"
        />
      </Field>

      <Field label="Output Directory" error={errors.outputDir?.message}>
        <input
          {...register("outputDir")}
          disabled={isPending}
          className={inputCls}
          placeholder="/path/to/output/dir"
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
        {isPending ? "Running…" : "Convert"}
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
// Main Utilities page
// ---------------------------------------------------------------------------

const FORM_COMPONENTS: Record<UtilSection, React.FC> = {
  xlsx: XlsxForm,
  xml: XmlForm,
};

const Utilities: React.FC = () => {
  const [selected, setSelected] = useState<UtilSection>("xlsx");

  const ActiveForm = FORM_COMPONENTS[selected];
  const activeLabel = SECTIONS.find((s) => s.key === selected)?.label ?? "";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Utilities</h1>
        <p className="text-sm text-muted-foreground mt-1">
          File conversion and data preparation utilities.
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

export default Utilities;
