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
import { fcaLookup, fcaSearch, fcaCheck, fcaLookupByLei } from "@/api/fca";
import { cn } from "@/lib/utils";
import type { FcaLeiSearchResponse, FcaLookupResponse, FcaSearchResult } from "@/types";

/* eslint-disable react-hooks/incompatible-library -- Intentional watch subscriptions persist form state safely for this page. */

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

// Matches the standard 20-character LEI format: 18 alphanumeric + 2 check digits.
const LEI_REGEX = /^[A-Z0-9]{18}\d{2}$/i;

const LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"] as const;

const KNOWN_PERMISSIONS = [
  "Accepting deposits",
  "Advising on investments (except pension transfers)",
  "Advising on P2P agreements",
  "Advising on pension transfers and pension opt-outs",
  "Advising on regulated mortgage contracts",
  "Advising on syndicate participation at Lloyd's",
  "Arranging (bringing about) deals in investments",
  "Arranging (bringing about) regulated mortgage contracts",
  "Arranging safeguarding and administration of assets",
  "Communicating financial promotions",
  "Dealing in investments as agent",
  "Dealing in investments as principal",
  "Effecting contracts of insurance",
  "Establishing, operating or winding up a collective investment scheme",
  "Insurance distribution activity",
  "Issuing electronic money",
  "Making arrangements with a view to transactions in investments",
  "Managing a UCITS",
  "Managing an AIF",
  "Managing investments",
  "Operating a multilateral trading facility",
  "Operating an organised trading facility",
  "Safeguarding and administering investments",
  "Sending dematerialised instructions",
  "Undertaking activities in relation to a regulated benchmark",
] as const;

type FcaSection = "lookup" | "batch";

const SECTIONS: Array<{ key: FcaSection; label: string }> = [
  { key: "lookup", label: "Lookup Firm" },
  { key: "batch", label: "Batch Check" },
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
// Lookup Form
// ---------------------------------------------------------------------------

const lookupSchema = z.object({
  query: z.string().min(1, "Required"),
  permission: z.string().optional(),
  logLevel: z.string(),
});

type LookupFormValues = z.infer<typeof lookupSchema>;

const LookupForm: React.FC = () => {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [lookupResult, setLookupResult] = useState<FcaLookupResponse | null>(null);
  const [searchResults, setSearchResults] = useState<FcaSearchResult[]>([]);
  const [leiResult, setLeiResult] = useState<FcaLeiSearchResponse | null>(null);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<LookupFormValues>({
    resolver: zodResolver(lookupSchema),
    defaultValues: loadCache("fca_lookup", {
      query: "",
      permission: "",
      logLevel: "INFO",
    }),
  });

  useEffect(() => {
    const sub = watch((values) => {
      try { localStorage.setItem("txr_form_fca_lookup", JSON.stringify(values)); } catch { /* ignore */ }
    });
    return () => sub.unsubscribe();
  }, [watch]);

  const frnLookupMutation = useMutation({
    mutationFn: (vals: { frn: string }) => fcaLookup(vals.frn),
    onSuccess: (result) => {
      setLookupResult(result);
      setSearchResults([]);
      setLeiResult(null);
    },
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Lookup failed");
    },
  });

  const nameSearchMutation = useMutation({
    mutationFn: (vals: { name: string }) => fcaSearch(vals.name),
    onSuccess: (result) => {
      setSearchResults(result.results);
      setLookupResult(null);
      setLeiResult(null);
    },
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Search failed");
    },
  });

  const leiSearchMutation = useMutation({
    mutationFn: (vals: { lei: string }) => fcaLookupByLei(vals.lei),
    onSuccess: (result) => {
      setLeiResult(result);
      setLookupResult(null);
      setSearchResults([]);
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "LEI lookup failed";
      toast.error(msg);
    },
  });

  const onSubmit = (values: LookupFormValues) => {
    setLookupResult(null);
    setSearchResults([]);
    setLeiResult(null);
    const trimmed = values.query.trim();
    if (LEI_REGEX.test(trimmed)) {
      leiSearchMutation.mutate({ lei: trimmed });
    } else if (/^\d+$/.test(trimmed)) {
      frnLookupMutation.mutate({ frn: trimmed });
    } else {
      nameSearchMutation.mutate({ name: trimmed });
    }
  };

  const isPending = frnLookupMutation.isPending || nameSearchMutation.isPending || leiSearchMutation.isPending;
  const permission = watch("permission") ?? "";

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Enter a firm reference number (FRN), firm name, or Legal Entity Identifier (LEI).
        Numeric input is looked up as an FRN; a 20-character LEI is resolved via the GLEIF
        database then matched to the closest FCA-registered firm; all other text searches by name.
      </p>

      <Field
        label="FRN or Firm Name"
        hint="Enter a numeric FRN for an exact lookup, or a firm name to search."
        error={errors.query?.message}
      >
        <input
          {...register("query")}
          disabled={isPending}
          className={inputCls}
          placeholder="e.g. 122702 or Barclays"
        />
      </Field>

      <Field
        label="Permission to verify"
        hint="Optional. Select or type a regulated activity name to highlight in the result."
        error={errors.permission?.message}
      >
        <input
          {...register("permission")}
          list="fca-permissions-lookup"
          disabled={isPending}
          className={inputCls}
          placeholder="e.g. Managing investments"
        />
        <datalist id="fca-permissions-lookup">
          {KNOWN_PERMISSIONS.map((p) => <option key={p} value={p} />)}
        </datalist>
      </Field>

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

      {(frnLookupMutation.isError || nameSearchMutation.isError || leiSearchMutation.isError) && (
        <p className="text-sm text-destructive">
          {(() => {
            const err = frnLookupMutation.error ?? nameSearchMutation.error ?? leiSearchMutation.error;
            return err instanceof Error ? err.message : "An error occurred";
          })()}
        </p>
      )}

      {leiResult && (
        <div className="space-y-3">
          <div className="rounded-md border border-blue-300 bg-blue-50 px-3 py-2 text-xs text-blue-800 dark:border-blue-700 dark:bg-blue-900/20 dark:text-blue-300">
            <span className="font-medium">Resolved LEI</span>{" "}
            <span className="font-mono">{leiResult.lei}</span>{" to: "}
            <span className="font-medium">{leiResult.resolvedName}</span>
          </div>
          {leiResult.result ? (
            <div className="rounded-lg border border-border p-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-sm">{leiResult.result.organisationName}</span>
                <span
                  className={cn(
                    "rounded-full px-2.5 py-0.5 text-xs font-medium",
                    leiResult.result.status.toLowerCase().includes("authorised") &&
                    !leiResult.result.status.toLowerCase().includes("no longer")
                      ? "bg-green-200 text-green-800 dark:bg-green-800 dark:text-green-200"
                      : "bg-red-200 text-red-800 dark:bg-red-800 dark:text-red-200",
                  )}
                >
                  {leiResult.result.status}
                </span>
              </div>
              <p className="text-xs text-muted-foreground font-mono">FRN: {leiResult.result.frn}</p>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No matching firm found on the FCA register for{" "}
              <span className="font-medium">{leiResult.resolvedName}</span>.
            </p>
          )}
        </div>
      )}

      {lookupResult && (
        <div
          className={cn(
            "rounded-lg border p-4 space-y-3",
            lookupResult.isAuthorised
              ? "border-green-300 bg-green-50 dark:border-green-700 dark:bg-green-900/20"
              : "border-red-300 bg-red-50 dark:border-red-700 dark:bg-red-900/20",
          )}
        >
          <div className="flex items-center justify-between">
            <span className="font-semibold text-sm">{lookupResult.organisationName}</span>
            <span
              className={cn(
                "rounded-full px-2.5 py-0.5 text-xs font-medium",
                lookupResult.isAuthorised
                  ? "bg-green-200 text-green-800 dark:bg-green-800 dark:text-green-200"
                  : "bg-red-200 text-red-800 dark:bg-red-800 dark:text-red-200",
              )}
            >
              {lookupResult.isAuthorised ? "Authorised" : "Not Authorised"}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-muted-foreground">
            <span>FRN: {lookupResult.frn}</span>
            <span>Status: {lookupResult.status}</span>
            {lookupResult.businessType && <span>Business Type: {lookupResult.businessType}</span>}
            {lookupResult.companiesHouseNumber && (
              <span>Companies House: {lookupResult.companiesHouseNumber}</span>
            )}
            {lookupResult.statusEffectiveDate && (
              <span>Effective Date: {lookupResult.statusEffectiveDate}</span>
            )}
          </div>
          {permission.trim() && (() => {
            const target = permission.trim().toLowerCase();
            const hasPermission = lookupResult.permissions.some(
              (p) => p.activityName.toLowerCase() === target,
            );
            return (
              <div className={cn(
                "flex items-center justify-between rounded-md px-3 py-2 text-xs font-medium",
                hasPermission
                  ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300"
                  : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
              )}>
                <span>{permission.trim()}</span>
                <span className="font-bold">{hasPermission ? "Y" : "N"}</span>
              </div>
            );
          })()}
          {lookupResult.permissions.length > 0 && (
            <div>
              <p className="text-xs font-medium text-muted-foreground mb-1">All Permissions</p>
              <ul className="space-y-1">
                {lookupResult.permissions.map((p, i) => (
                  <li key={i} className="text-xs text-muted-foreground">
                    {p.activityName}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {searchResults.length > 0 && (
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-medium">FRN</th>
                <th className="px-3 py-2 text-left font-medium">Organisation Name</th>
                <th className="px-3 py-2 text-left font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {searchResults.map((r) => (
                <tr key={r.frn} className="hover:bg-muted/50">
                  <td className="px-3 py-2 font-mono text-xs">{r.frn}</td>
                  <td className="px-3 py-2">{r.organisationName}</td>
                  <td className="px-3 py-2 text-xs">{r.status}</td>
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
// Batch Form
// ---------------------------------------------------------------------------

const batchSchema = z.object({
  inputFile: z.string().min(1, "Required"),
  outputFile: z.string().min(1, "Required"),
  permission: z.string().optional(),
  logLevel: z.string(),
});

type BatchFormValues = z.infer<typeof batchSchema>;

const BatchForm: React.FC = () => {
  const navigate = useNavigate();
  const [showAdvanced, setShowAdvanced] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<BatchFormValues>({
    resolver: zodResolver(batchSchema),
    defaultValues: loadCache("fca_batch", {
      inputFile: "",
      outputFile: "",
      permission: "",
      logLevel: "INFO",
    }),
  });

  useEffect(() => {
    const sub = watch((values) => {
      try { localStorage.setItem("txr_form_fca_batch", JSON.stringify(values)); } catch { /* ignore */ }
    });
    return () => sub.unsubscribe();
  }, [watch]);

  const mutation = useMutation({
    mutationFn: fcaCheck,
    onSuccess: (job) => navigate(`/jobs/${job.id}`),
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : "Failed to start job");
    },
  });

  const onSubmit = (values: BatchFormValues) => {
    mutation.mutate({
      mode: "batch",
      inputFile: values.inputFile,
      outputFile: values.outputFile,
      permission: values.permission || undefined,
      logLevel: values.logLevel,
    });
  };

  const isPending = mutation.isPending;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-5 max-w-xl">
      <p className="text-sm text-muted-foreground">
        Process a CSV file containing firm names or FRNs against the FCA Financial Services Register.
      </p>

      <CsvFormatHint
        columns={[
          {
            name: "frn / fca_number / reference_number / firm_ref",
            required: false,
            description: "FCA Reference Number (any of these header names accepted). Takes precedence over firm name if both are present.",
            example: "122702",
          },
          {
            name: "firm_name / name / organisation_name / company_name",
            required: false,
            description: "Firm name to search. Used when no FRN column is present or the FRN cell is empty.",
            example: "Barclays Bank PLC",
          },
        ]}
        notes="At least one of an FRN column or a firm name column must be present. Header matching is case-insensitive and ignores spaces vs underscores."
      />

      <Field
        label="Input File"
        hint="CSV file containing FRN or firm name columns."
        error={errors.inputFile?.message}
      >
        <PathPickerInput
          value={watch("inputFile")}
          onChange={(v) => setValue("inputFile", v)}
          mode="file"
          placeholder="/path/to/input.csv"
          disabled={isPending}
        />
      </Field>

      <Field
        label="Output File"
        hint="Output CSV with FCA lookup results appended."
        error={errors.outputFile?.message}
      >
        <PathPickerInput
          value={watch("outputFile")}
          onChange={(v) => setValue("outputFile", v)}
          mode="file"
          placeholder="/path/to/output.csv"
          disabled={isPending}
        />
      </Field>

      <Field
        label="Permission to verify"
        hint="Optional. When selected, adds a column with that permission name (Y/N) to the output."
        error={errors.permission?.message}
      >
        <input
          {...register("permission")}
          list="fca-permissions-batch"
          disabled={isPending}
          className={inputCls}
          placeholder="e.g. Managing investments"
        />
        <datalist id="fca-permissions-batch">
          {KNOWN_PERMISSIONS.map((p) => <option key={p} value={p} />)}
        </datalist>
      </Field>

      <AdvancedSection isOpen={showAdvanced} onToggle={() => setShowAdvanced(!showAdvanced)}>
        <Field label="Log Level" hint="Logging verbosity level." error={errors.logLevel?.message}>
          <select {...register("logLevel")} disabled={isPending} className={selectCls}>
            {LOG_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </Field>
      </AdvancedSection>

      <Button type="submit" disabled={isPending} className="w-full">
        {isPending ? "Running…" : "Run Batch Check"}
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
// Main FCA page
// ---------------------------------------------------------------------------

const FORM_COMPONENTS: Record<FcaSection, React.FC> = {
  lookup: LookupForm,
  batch: BatchForm,
};

const FCA: React.FC = () => {
  const [selected, setSelected] = useState<FcaSection>("lookup");

  const ActiveForm = FORM_COMPONENTS[selected];
  const activeLabel = SECTIONS.find((s) => s.key === selected)?.label ?? "";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">FCA Register</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Look up firms on the FCA Financial Services Register by FRN or name.
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
            <LastRunBadge scriptName="fca_check" />
          </div>
          <ActiveForm />
        </div>
      </div>
    </div>
  );
};

export default FCA;
