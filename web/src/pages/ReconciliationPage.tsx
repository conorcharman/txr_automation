import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Play,
  Pencil,
  Trash2,
  Plus,
  Clock,
  CalendarCheck,
  PowerOff,
  Power,
  CheckCircle2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardAction,
  CardContent,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import {
  listReconciliations,
  createReconciliation,
  updateReconciliation,
  deleteReconciliation,
  triggerReconciliation,
  toggleReconciliation,
} from "@/api/reconciliation";
import { cn } from "@/lib/utils";
import type {
  ReconciliationSchedule,
  ReconciliationScheduleCreate,
  ReconciliationScheduleUpdate,
} from "@/types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FREQUENCIES: { value: string; label: string }[] = [
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly (Mondays)" },
  { value: "monthly", label: "Monthly (1st)" },
  { value: "quarterly", label: "Quarterly" },
  { value: "custom", label: "Custom (cron)" },
];

const RECONCILIATION_SCRIPTS = [
  {
    key: "buyer_id_validation",
    label: "Buyer ID Validation",
    group: "trade-by-trade" as const,
  },
  {
    key: "seller_id_validation",
    label: "Seller ID Validation",
    group: "trade-by-trade" as const,
  },
  {
    key: "validate_ftbdm",
    label: "Fund Trade Buyer DM",
    group: "trade-by-trade" as const,
  },
  {
    key: "validate_ftsdm",
    label: "Fund Trade Seller DM",
    group: "trade-by-trade" as const,
  },
  {
    key: "inconsistent_buyer_id_validation",
    label: "Inconsistent Buyer ID",
    group: "inconsistent-id" as const,
  },
  {
    key: "inconsistent_seller_id_validation",
    label: "Inconsistent Seller ID",
    group: "inconsistent-id" as const,
  },
] as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function frequencyLabel(value: string): string {
  return FREQUENCIES.find((f) => f.value === value)?.label ?? value;
}

function scriptLabel(key: string): string {
  return RECONCILIATION_SCRIPTS.find((s) => s.key === key)?.label ?? key;
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string | null }) {
  if (!status) return <Badge variant="outline">Never run</Badge>;
  const map: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
    success: "default",
    pending: "secondary",
    running: "secondary",
    failed: "destructive",
    cancelled: "outline",
  };
  return <Badge variant={map[status] ?? "outline"}>{status}</Badge>;
}

// ---------------------------------------------------------------------------
// Shared input styles
// ---------------------------------------------------------------------------

const inputCls =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm " +
  "focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50 " +
  "placeholder:text-muted-foreground";

const selectCls =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm " +
  "focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50";

// ---------------------------------------------------------------------------
// Form values
// ---------------------------------------------------------------------------

interface RecFormValues {
  name: string;
  recPeriodDays: number;
  lookbackDays: number;
  selectedScripts: string[];
  frequency: string;
  cronExpression: string;
  stopOnError: boolean;
  isActive: boolean;
}

const EMPTY_FORM: RecFormValues = {
  name: "",
  recPeriodDays: 90,
  lookbackDays: 365,
  selectedScripts: RECONCILIATION_SCRIPTS.map((s) => s.key),
  frequency: "weekly",
  cronExpression: "",
  stopOnError: true,
  isActive: true,
};

function recToForm(r: ReconciliationSchedule): RecFormValues {
  return {
    name: r.name,
    recPeriodDays: r.recPeriodDays,
    lookbackDays: r.lookbackDays,
    selectedScripts: r.selectedScripts,
    frequency: r.frequency,
    cronExpression: r.cronExpression ?? "",
    stopOnError: r.stopOnError,
    isActive: r.isActive,
  };
}

// ---------------------------------------------------------------------------
// ReconciliationForm
// ---------------------------------------------------------------------------

interface RecFormProps {
  defaultValues: RecFormValues;
  onSubmit: (values: RecFormValues) => void;
  isLoading: boolean;
  submitLabel: string;
}

const ReconciliationForm: React.FC<RecFormProps> = ({
  defaultValues,
  onSubmit,
  isLoading,
  submitLabel,
}) => {
  const [values, setValues] = useState<RecFormValues>(defaultValues);

  function set<K extends keyof RecFormValues>(key: K, value: RecFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  function toggleScript(key: string) {
    setValues((prev) => ({
      ...prev,
      selectedScripts: prev.selectedScripts.includes(key)
        ? prev.selectedScripts.filter((k) => k !== key)
        : [...prev.selectedScripts, key],
    }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit(values);
  }

  const tradeByTrade = RECONCILIATION_SCRIPTS.filter(
    (s) => s.group === "trade-by-trade",
  );
  const inconsistentId = RECONCILIATION_SCRIPTS.filter(
    (s) => s.group === "inconsistent-id",
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Name */}
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-muted-foreground">
          Schedule Name
        </label>
        <input
          className={inputCls}
          value={values.name}
          onChange={(e) => set("name", e.target.value)}
          placeholder="e.g. Weekly Reconciliation"
          required
          disabled={isLoading}
        />
      </div>

      {/* Period windows */}
      <div className="grid grid-cols-2 gap-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-muted-foreground">
            Rec Period (days)
            <span className="ml-1 text-muted-foreground/60 font-normal">
              trade-by-trade window
            </span>
          </label>
          <input
            type="number"
            className={inputCls}
            value={values.recPeriodDays}
            onChange={(e) => set("recPeriodDays", Number(e.target.value))}
            min={1}
            required
            disabled={isLoading}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-muted-foreground">
            Lookback (days)
            <span className="ml-1 text-muted-foreground/60 font-normal">
              inconsistent ID window
            </span>
          </label>
          <input
            type="number"
            className={inputCls}
            value={values.lookbackDays}
            onChange={(e) => set("lookbackDays", Number(e.target.value))}
            min={1}
            required
            disabled={isLoading}
          />
        </div>
      </div>

      {/* Script selection — grouped */}
      <div className="rounded-lg border border-border p-4 space-y-3">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          Validation Scripts
        </p>

        {/* Trade-by-trade */}
        <div>
          <p className="text-xs font-medium text-foreground/70 mb-1">
            Trade-by-trade
            <span className="ml-1 text-muted-foreground/60 font-normal">
              (uses rec period window)
            </span>
          </p>
          {tradeByTrade.map((s) => (
            <label
              key={s.key}
              className="flex items-center gap-2 cursor-pointer text-sm py-0.5"
            >
              <input
                type="checkbox"
                checked={values.selectedScripts.includes(s.key)}
                onChange={() => toggleScript(s.key)}
                className="accent-primary h-4 w-4"
                disabled={isLoading}
              />
              {s.label}
            </label>
          ))}
        </div>

        {/* Inconsistent ID */}
        <div>
          <p className="text-xs font-medium text-foreground/70 mb-1">
            Inconsistent ID
            <span className="ml-1 text-muted-foreground/60 font-normal">
              (uses lookback window)
            </span>
          </p>
          {inconsistentId.map((s) => (
            <label
              key={s.key}
              className="flex items-center gap-2 cursor-pointer text-sm py-0.5"
            >
              <input
                type="checkbox"
                checked={values.selectedScripts.includes(s.key)}
                onChange={() => toggleScript(s.key)}
                className="accent-primary h-4 w-4"
                disabled={isLoading}
              />
              {s.label}
            </label>
          ))}
        </div>
      </div>

      {/* Frequency */}
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-muted-foreground">
          Frequency
        </label>
        <select
          className={selectCls}
          value={values.frequency}
          onChange={(e) => set("frequency", e.target.value)}
          disabled={isLoading}
        >
          {FREQUENCIES.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </select>
      </div>

      {/* Cron expression (custom only) */}
      {values.frequency === "custom" && (
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-muted-foreground">
            Cron Expression
            <span className="ml-1 text-muted-foreground/60 font-normal">
              (5-field, e.g. 0 6 * * 1)
            </span>
          </label>
          <input
            className={inputCls}
            value={values.cronExpression}
            onChange={(e) => set("cronExpression", e.target.value)}
            placeholder="0 6 * * 1"
            required
            disabled={isLoading}
          />
        </div>
      )}

      {/* Stop on error */}
      <label className="flex items-center gap-2 cursor-pointer text-sm">
        <input
          type="checkbox"
          checked={values.stopOnError}
          onChange={(e) => set("stopOnError", e.target.checked)}
          disabled={isLoading}
          className="accent-primary h-4 w-4"
        />
        Stop on first error
      </label>

      {/* Active toggle */}
      <label className="flex items-center gap-2 cursor-pointer text-sm">
        <input
          type="checkbox"
          checked={values.isActive}
          onChange={(e) => set("isActive", e.target.checked)}
          disabled={isLoading}
          className="accent-primary h-4 w-4"
        />
        Active (will fire automatically on schedule)
      </label>

      <DialogFooter>
        <DialogClose asChild>
          <Button type="button" variant="outline" disabled={isLoading} size="sm">
            Cancel
          </Button>
        </DialogClose>
        <Button
          type="submit"
          disabled={isLoading || values.selectedScripts.length === 0}
          size="sm"
        >
          {isLoading ? "Saving…" : submitLabel}
        </Button>
      </DialogFooter>
    </form>
  );
};

// ---------------------------------------------------------------------------
// ReconciliationCard
// ---------------------------------------------------------------------------

interface RecCardProps {
  rec: ReconciliationSchedule;
  onEdit: (r: ReconciliationSchedule) => void;
  onDelete: (r: ReconciliationSchedule) => void;
  onTrigger: (r: ReconciliationSchedule) => void;
  onToggle: (r: ReconciliationSchedule) => void;
  isTriggering: boolean;
  isToggling: boolean;
}

const ReconciliationCard: React.FC<RecCardProps> = ({
  rec,
  onEdit,
  onDelete,
  onTrigger,
  onToggle,
  isTriggering,
  isToggling,
}) => {
  const tradeScripts = rec.selectedScripts.filter((s) =>
    ["buyer_id_validation", "seller_id_validation", "validate_ftbdm", "validate_ftsdm"].includes(s),
  );
  const inconsistentScripts = rec.selectedScripts.filter((s) =>
    s.startsWith("inconsistent_"),
  );

  return (
    <Card className={cn("transition-opacity", !rec.isActive && "opacity-60")}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <CalendarCheck size={16} className="shrink-0 text-primary" />
          {rec.name}
        </CardTitle>
        <CardDescription>
          {rec.selectedScripts.length} script(s) · {frequencyLabel(rec.frequency)}
        </CardDescription>
        <CardAction>
          <StatusBadge status={rec.lastStatus} />
        </CardAction>
      </CardHeader>

      <CardContent className="space-y-3 text-sm">
        {/* Script chips */}
        <div className="flex flex-wrap gap-1">
          {rec.selectedScripts.map((s) => (
            <span
              key={s}
              className="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium bg-primary/10 text-primary border border-primary/30"
            >
              <CheckCircle2 size={10} className="shrink-0" />
              {scriptLabel(s)}
            </span>
          ))}
        </div>

        {/* Window info */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {tradeScripts.length > 0 && (
            <>
              <span className="font-medium text-foreground/70">Rec period</span>
              <span>{rec.recPeriodDays} days</span>
            </>
          )}
          {inconsistentScripts.length > 0 && (
            <>
              <span className="font-medium text-foreground/70">Lookback</span>
              <span>{rec.lookbackDays} days</span>
            </>
          )}
        </div>

        {/* Schedule info */}
        <div className="flex items-center gap-2 text-muted-foreground">
          <Clock size={14} />
          <span>{frequencyLabel(rec.frequency)}</span>
          {rec.frequency === "custom" && rec.cronExpression && (
            <code className="text-xs bg-muted px-1 rounded">
              {rec.cronExpression}
            </code>
          )}
        </div>

        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span className="font-medium text-foreground/70">Next run</span>
          <span>{formatDateTime(rec.nextRunAt)}</span>
          <span className="font-medium text-foreground/70">Last run</span>
          <span>{formatDateTime(rec.lastRunAt)}</span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 pt-1">
          <Button
            size="sm"
            variant="outline"
            onClick={() => onTrigger(rec)}
            disabled={isTriggering}
            title="Run now"
          >
            <Play size={14} /> Run now
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => onToggle(rec)}
            disabled={isToggling}
            title={rec.isActive ? "Disable" : "Enable"}
          >
            {rec.isActive ? <PowerOff size={14} /> : <Power size={14} />}
            {rec.isActive ? "Disable" : "Enable"}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onEdit(rec)}
            title="Edit"
          >
            <Pencil size={14} />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onDelete(rec)}
            title="Delete"
            className="text-destructive hover:text-destructive"
          >
            <Trash2 size={14} />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

// ---------------------------------------------------------------------------
// Confirm delete dialog
// ---------------------------------------------------------------------------

interface ConfirmDeleteDialogProps {
  rec: ReconciliationSchedule | null;
  onConfirm: () => void;
  onCancel: () => void;
  isLoading: boolean;
}

const ConfirmDeleteDialog: React.FC<ConfirmDeleteDialogProps> = ({
  rec,
  onConfirm,
  onCancel,
  isLoading,
}) => (
  <Dialog open={rec !== null} onOpenChange={(open) => !open && onCancel()}>
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Delete Reconciliation Schedule</DialogTitle>
      </DialogHeader>
      <p className="text-sm text-muted-foreground">
        Are you sure you want to permanently delete{" "}
        <strong>{rec?.name}</strong>? This action cannot be undone.
      </p>
      <DialogFooter>
        <Button variant="outline" size="sm" onClick={onCancel} disabled={isLoading}>
          Cancel
        </Button>
        <Button
          variant="destructive"
          size="sm"
          onClick={onConfirm}
          disabled={isLoading}
        >
          {isLoading ? "Deleting…" : "Delete"}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
);

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

const ReconciliationPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [showCreate, setShowCreate] = useState(false);
  const [editTarget, setEditTarget] = useState<ReconciliationSchedule | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ReconciliationSchedule | null>(null);
  const [triggeringId, setTriggeringId] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // Data fetching
  // ---------------------------------------------------------------------------

  const {
    data: reconciliations,
    isLoading,
    isError,
    error,
  } = useQuery<ReconciliationSchedule[]>({
    queryKey: ["reconciliations"],
    queryFn: listReconciliations,
    refetchInterval: 30_000,
  });

  // ---------------------------------------------------------------------------
  // Mutations
  // ---------------------------------------------------------------------------

  const createMutation = useMutation({
    mutationFn: (values: RecFormValues) => {
      const req: ReconciliationScheduleCreate = {
        name: values.name,
        recPeriodDays: values.recPeriodDays,
        lookbackDays: values.lookbackDays,
        selectedScripts: values.selectedScripts,
        frequency: values.frequency,
        cronExpression:
          values.frequency === "custom" ? values.cronExpression || null : null,
        stopOnError: values.stopOnError,
        isActive: values.isActive,
      };
      return createReconciliation(req);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reconciliations"] });
      setShowCreate(false);
      toast.success("Reconciliation schedule created.");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      values,
    }: {
      id: string;
      values: RecFormValues;
    }) => {
      const req: ReconciliationScheduleUpdate = {
        name: values.name,
        recPeriodDays: values.recPeriodDays,
        lookbackDays: values.lookbackDays,
        selectedScripts: values.selectedScripts,
        frequency: values.frequency,
        cronExpression:
          values.frequency === "custom" ? values.cronExpression || null : null,
        stopOnError: values.stopOnError,
        isActive: values.isActive,
      };
      return updateReconciliation(id, req);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reconciliations"] });
      setEditTarget(null);
      toast.success("Reconciliation schedule updated.");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteReconciliation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reconciliations"] });
      setDeleteTarget(null);
      toast.success("Reconciliation schedule deleted.");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const triggerMutation = useMutation({
    mutationFn: (id: string) => triggerReconciliation(id),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["reconciliations"] });
      toast.success("Reconciliation triggered. Navigating to job…");
      navigate(`/jobs/${data.jobId}`);
    },
    onError: (err: Error) => toast.error(err.message),
    onSettled: () => setTriggeringId(null),
  });

  const toggleMutation = useMutation({
    mutationFn: (id: string) => toggleReconciliation(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["reconciliations"] }),
    onError: (err: Error) => toast.error(err.message),
    onSettled: () => setTogglingId(null),
  });

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  function handleTrigger(r: ReconciliationSchedule) {
    setTriggeringId(r.id);
    triggerMutation.mutate(r.id);
  }

  function handleToggle(r: ReconciliationSchedule) {
    setTogglingId(r.id);
    toggleMutation.mutate(r.id);
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Reconciliation</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Scheduled reconciliation of transactions using configurable validation
            windows. Data push always runs as the final stage.
          </p>
        </div>
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <Plus size={16} />
          New Schedule
        </Button>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {[0, 1].map((i) => (
            <Card key={i}>
              <CardContent className="space-y-3 pt-4 pb-4">
                <Skeleton className="h-5 w-40" />
                <Skeleton className="h-4 w-56" />
                <Skeleton className="h-3 w-24" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-red-800 text-sm">
          {error instanceof Error ? error.message : "Failed to load reconciliation schedules."}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && reconciliations?.length === 0 && (
        <div className="rounded-lg border border-dashed px-6 py-10 text-center text-muted-foreground text-sm">
          No reconciliation schedules configured yet.{" "}
          <button
            className="text-primary underline-offset-2 hover:underline"
            onClick={() => setShowCreate(true)}
          >
            Create one
          </button>{" "}
          to automate transaction reconciliation.
        </div>
      )}

      {/* Card grid */}
      {!isLoading && !isError && reconciliations && reconciliations.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {reconciliations.map((r) => (
            <ReconciliationCard
              key={r.id}
              rec={r}
              onEdit={(rec) => setEditTarget(rec)}
              onDelete={(rec) => setDeleteTarget(rec)}
              onTrigger={handleTrigger}
              onToggle={handleToggle}
              isTriggering={triggeringId === r.id}
              isToggling={togglingId === r.id}
            />
          ))}
        </div>
      )}

      {/* Create dialog */}
      <Dialog open={showCreate} onOpenChange={(open) => !open && setShowCreate(false)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>New Reconciliation Schedule</DialogTitle>
          </DialogHeader>
          <ReconciliationForm
            defaultValues={EMPTY_FORM}
            onSubmit={(values) => createMutation.mutate(values)}
            isLoading={createMutation.isPending}
            submitLabel="Create Schedule"
          />
        </DialogContent>
      </Dialog>

      {/* Edit dialog */}
      <Dialog
        open={editTarget !== null}
        onOpenChange={(open) => !open && setEditTarget(null)}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Edit Reconciliation Schedule</DialogTitle>
          </DialogHeader>
          {editTarget && (
            <ReconciliationForm
              defaultValues={recToForm(editTarget)}
              onSubmit={(values) =>
                updateMutation.mutate({ id: editTarget.id, values })
              }
              isLoading={updateMutation.isPending}
              submitLabel="Save Changes"
            />
          )}
        </DialogContent>
      </Dialog>

      {/* Confirm delete dialog */}
      <ConfirmDeleteDialog
        rec={deleteTarget}
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
};

export default ReconciliationPage;
