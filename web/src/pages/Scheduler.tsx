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
  listSchedules,
  createSchedule,
  updateSchedule,
  deleteSchedule,
  triggerSchedule,
  toggleSchedule,
} from "@/api/scheduler";
import { cn } from "@/lib/utils";
import type { Schedule, ScheduleCreate, ScheduleUpdate, ScheduleFrequency } from "@/types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FREQUENCIES: { value: ScheduleFrequency; label: string }[] = [
  { value: "hourly", label: "Hourly" },
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly (Mondays)" },
  { value: "monthly", label: "Monthly (1st)" },
  { value: "custom", label: "Custom (cron)" },
];

const SCRIPTS: { value: string; label: string }[] = [
  { value: "buyer_id_validation", label: "Buyer ID Validation" },
  { value: "seller_id_validation", label: "Seller ID Validation" },
  { value: "inconsistent_buyer_id_validation", label: "Inconsistent Buyer ID" },
  { value: "inconsistent_seller_id_validation", label: "Inconsistent Seller ID" },
  { value: "validate_ftbdm", label: "Fund Trade Buyer DM" },
  { value: "validate_ftsdm", label: "Fund Trade Seller DM" },
  { value: "incorrect_net_amount_validation", label: "Incorrect Net Amount" },
  { value: "non_zero_net_quantity", label: "Non-Zero Net Quantity" },
  { value: "non_zero_net_amount", label: "Non-Zero Net Amount" },
  { value: "run_all_validations", label: "Run All Validations" },
  { value: "sql_extract_generator", label: "SQL Extract Generator" },
  { value: "accuracy_template_generator", label: "Accuracy Template Generator" },
  { value: "collate_csv_extracts", label: "Collate CSV Extracts" },
  { value: "data_push", label: "Data Push" },
  { value: "replay_phase2", label: "Replay Phase 2" },
  { value: "replay_phase3", label: "Replay Phase 3" },
  { value: "replay_phase3_final", label: "Replay Phase 3 Final Lookup" },
  { value: "replay_merge_inconsistent", label: "Replay Merge Inconsistent" },
  { value: "firds_refresh", label: "FIRDS Refresh Cache" },
  { value: "firds_check", label: "FIRDS Check Reportability" },
  { value: "firds_backfill", label: "FIRDS Backfill" },
  { value: "gleif_refresh", label: "GLEIF Refresh Cache" },
  { value: "gleif_check", label: "GLEIF Check LEI" },
  { value: "gleif_backfill", label: "GLEIF Backfill" },
  { value: "xlsx_csv_converter", label: "XLSX → CSV Converter" },
  { value: "xml_csv_converter", label: "XML → CSV Converter" },
];

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

function scriptLabel(value: string): string {
  return SCRIPTS.find((s) => s.value === value)?.label ?? value;
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
// Schedule form (create + edit)
// ---------------------------------------------------------------------------

interface ScheduleFormValues {
  name: string;
  scriptName: string;
  frequency: ScheduleFrequency;
  cronExpression: string;
  configJson: string;
  isActive: boolean;
}

const EMPTY_FORM: ScheduleFormValues = {
  name: "",
  scriptName: "buyer_id_validation",
  frequency: "daily",
  cronExpression: "",
  configJson: "{}",
  isActive: true,
};

function scheduleToForm(s: Schedule): ScheduleFormValues {
  return {
    name: s.name,
    scriptName: s.scriptName,
    frequency: s.frequency,
    cronExpression: s.cronExpression ?? "",
    configJson: s.configData ? JSON.stringify(s.configData, null, 2) : "{}",
    isActive: s.isActive,
  };
}

interface ScheduleFormProps {
  defaultValues: ScheduleFormValues;
  onSubmit: (values: ScheduleFormValues) => void;
  isLoading: boolean;
  submitLabel: string;
}

const ScheduleForm: React.FC<ScheduleFormProps> = ({
  defaultValues,
  onSubmit,
  isLoading,
  submitLabel,
}) => {
  const [values, setValues] = useState<ScheduleFormValues>(defaultValues);
  const [jsonError, setJsonError] = useState<string | null>(null);

  function set<K extends keyof ScheduleFormValues>(
    key: K,
    value: ScheduleFormValues[K],
  ) {
    setValues((prev) => ({ ...prev, [key]: value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      JSON.parse(values.configJson || "{}");
      setJsonError(null);
    } catch {
      setJsonError("Invalid JSON — please check the configuration.");
      return;
    }
    onSubmit(values);
  }

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
          placeholder="e.g. Daily Buyer Validation"
          required
          disabled={isLoading}
        />
      </div>

      {/* Script */}
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-muted-foreground">Script</label>
        <select
          className={selectCls}
          value={values.scriptName}
          onChange={(e) => set("scriptName", e.target.value)}
          disabled={isLoading}
        >
          {SCRIPTS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      {/* Frequency */}
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-muted-foreground">Frequency</label>
        <select
          className={selectCls}
          value={values.frequency}
          onChange={(e) => set("frequency", e.target.value as ScheduleFrequency)}
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
            required={values.frequency === "custom"}
            disabled={isLoading}
          />
        </div>
      )}

      {/* Config JSON */}
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-muted-foreground">
          Configuration
          <span className="ml-1 text-muted-foreground/60 font-normal">(JSON)</span>
        </label>
        <textarea
          className={cn(
            inputCls,
            "h-32 resize-y font-mono text-xs",
          )}
          value={values.configJson}
          onChange={(e) => set("configJson", e.target.value)}
          disabled={isLoading}
          spellCheck={false}
        />
        {jsonError && <p className="text-xs text-destructive">{jsonError}</p>}
      </div>

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
        <Button type="submit" disabled={isLoading} size="sm">
          {isLoading ? "Saving…" : submitLabel}
        </Button>
      </DialogFooter>
    </form>
  );
};

// ---------------------------------------------------------------------------
// Schedule card
// ---------------------------------------------------------------------------

interface ScheduleCardProps {
  schedule: Schedule;
  onEdit: (s: Schedule) => void;
  onDelete: (s: Schedule) => void;
  onTrigger: (s: Schedule) => void;
  onToggle: (s: Schedule) => void;
  isTriggering: boolean;
  isToggling: boolean;
}

const ScheduleCard: React.FC<ScheduleCardProps> = ({
  schedule,
  onEdit,
  onDelete,
  onTrigger,
  onToggle,
  isTriggering,
  isToggling,
}) => (
  <Card className={cn("transition-opacity", !schedule.isActive && "opacity-60")}>
    <CardHeader>
      <CardTitle className="flex items-center gap-2 text-base">
        <CalendarCheck size={16} className="shrink-0 text-primary" />
        {schedule.name}
      </CardTitle>
      <CardDescription>{scriptLabel(schedule.scriptName)}</CardDescription>
      <CardAction>
        <StatusBadge status={schedule.lastStatus} />
      </CardAction>
    </CardHeader>

    <CardContent className="space-y-2 text-sm">
      <div className="flex items-center gap-2 text-muted-foreground">
        <Clock size={14} />
        <span>{frequencyLabel(schedule.frequency)}</span>
        {schedule.frequency === "custom" && schedule.cronExpression && (
          <code className="text-xs bg-muted px-1 rounded">{schedule.cronExpression}</code>
        )}
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="font-medium text-foreground/70">Next run</span>
        <span>{formatDateTime(schedule.nextRunAt)}</span>
        <span className="font-medium text-foreground/70">Last run</span>
        <span>{formatDateTime(schedule.lastRunAt)}</span>
      </div>

      <div className="flex items-center gap-2 pt-2">
        {/* Trigger */}
        <Button
          size="sm"
          variant="outline"
          onClick={() => onTrigger(schedule)}
          disabled={isTriggering}
          title="Run now"
        >
          <Play size={14} />
          Run now
        </Button>

        {/* Toggle active */}
        <Button
          size="sm"
          variant="outline"
          onClick={() => onToggle(schedule)}
          disabled={isToggling}
          title={schedule.isActive ? "Disable" : "Enable"}
        >
          {schedule.isActive ? (
            <PowerOff size={14} />
          ) : (
            <Power size={14} />
          )}
          {schedule.isActive ? "Disable" : "Enable"}
        </Button>

        {/* Edit */}
        <Button
          size="sm"
          variant="ghost"
          onClick={() => onEdit(schedule)}
          title="Edit"
        >
          <Pencil size={14} />
        </Button>

        {/* Delete */}
        <Button
          size="sm"
          variant="ghost"
          onClick={() => onDelete(schedule)}
          title="Delete"
          className="text-destructive hover:text-destructive"
        >
          <Trash2 size={14} />
        </Button>
      </div>
    </CardContent>
  </Card>
);

// ---------------------------------------------------------------------------
// Confirm delete dialog
// ---------------------------------------------------------------------------

interface ConfirmDeleteDialogProps {
  schedule: Schedule | null;
  onConfirm: () => void;
  onCancel: () => void;
  isLoading: boolean;
}

const ConfirmDeleteDialog: React.FC<ConfirmDeleteDialogProps> = ({
  schedule,
  onConfirm,
  onCancel,
  isLoading,
}) => (
  <Dialog open={schedule !== null} onOpenChange={(open) => !open && onCancel()}>
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Delete Schedule</DialogTitle>
      </DialogHeader>
      <p className="text-sm text-muted-foreground">
        Are you sure you want to permanently delete{" "}
        <strong>{schedule?.name}</strong>? This action cannot be undone.
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
// Main Scheduler page
// ---------------------------------------------------------------------------

const Scheduler: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Dialog state
  const [showCreate, setShowCreate] = useState(false);
  const [editTarget, setEditTarget] = useState<Schedule | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Schedule | null>(null);

  // Track which schedule is currently being triggered / toggled
  const [triggeringId, setTriggeringId] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // Data fetching
  // ---------------------------------------------------------------------------

  const {
    data: schedules,
    isLoading,
    isError,
    error,
  } = useQuery<Schedule[]>({
    queryKey: ["schedules"],
    queryFn: listSchedules,
    refetchInterval: 30_000,
  });

  // ---------------------------------------------------------------------------
  // Mutations
  // ---------------------------------------------------------------------------

  const createMutation = useMutation({
    mutationFn: (values: ScheduleFormValues) => {
      const req: ScheduleCreate = {
        name: values.name,
        scriptName: values.scriptName,
        frequency: values.frequency,
        cronExpression: values.frequency === "custom" ? values.cronExpression || null : null,
        configData: JSON.parse(values.configJson || "{}") as Record<string, unknown>,
        isActive: values.isActive,
      };
      return createSchedule(req);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
      setShowCreate(false);
      toast.success("Schedule created successfully.");
    },
    onError: (err: Error) => {
      toast.error(`Failed to create schedule: ${err.message}`);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, values }: { id: string; values: ScheduleFormValues }) => {
      const req: ScheduleUpdate = {
        name: values.name,
        scriptName: values.scriptName,
        frequency: values.frequency,
        cronExpression: values.frequency === "custom" ? values.cronExpression || null : null,
        configData: JSON.parse(values.configJson || "{}") as Record<string, unknown>,
        isActive: values.isActive,
      };
      return updateSchedule(id, req);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
      setEditTarget(null);
      toast.success("Schedule updated successfully.");
    },
    onError: (err: Error) => {
      toast.error(`Failed to update schedule: ${err.message}`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (scheduleId: string) => deleteSchedule(scheduleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
      setDeleteTarget(null);
      toast.success("Schedule deleted.");
    },
    onError: (err: Error) => {
      toast.error(`Failed to delete schedule: ${err.message}`);
    },
  });

  const triggerMutation = useMutation({
    mutationFn: (scheduleId: string) => triggerSchedule(scheduleId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
      toast.success("Schedule triggered. Navigating to job…");
      navigate(`/jobs/${data.jobId}`);
    },
    onError: (err: Error) => {
      toast.error(`Failed to trigger schedule: ${err.message}`);
    },
    onSettled: () => setTriggeringId(null),
  });

  const toggleMutation = useMutation({
    mutationFn: (scheduleId: string) => toggleSchedule(scheduleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schedules"] });
    },
    onError: (err: Error) => {
      toast.error(`Failed to toggle schedule: ${err.message}`);
    },
    onSettled: () => setTogglingId(null),
  });

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  function handleTrigger(s: Schedule) {
    setTriggeringId(s.id);
    triggerMutation.mutate(s.id);
  }

  function handleToggle(s: Schedule) {
    setTogglingId(s.id);
    toggleMutation.mutate(s.id);
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Scheduler</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Manage automated pipeline runs. Schedules are checked every minute.
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)} size="sm">
          <Plus size={16} />
          New Schedule
        </Button>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Card key={i}>
              <CardContent className="space-y-3 pt-4 pb-4">
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-3 w-24" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Error */}
      {isError && (
        <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-red-800 text-sm">
          {error instanceof Error ? error.message : "Failed to load schedules."}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && schedules?.length === 0 && (
        <div className="rounded-lg border border-dashed px-6 py-10 text-center text-muted-foreground text-sm">
          No schedules configured yet.{" "}
          <button
            className="text-primary underline-offset-2 hover:underline"
            onClick={() => setShowCreate(true)}
          >
            Create one
          </button>{" "}
          to automate a pipeline.
        </div>
      )}

      {/* Schedule grid */}
      {!isLoading && !isError && schedules && schedules.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {schedules.map((s) => (
            <ScheduleCard
              key={s.id}
              schedule={s}
              onEdit={(schedule) => setEditTarget(schedule)}
              onDelete={(schedule) => setDeleteTarget(schedule)}
              onTrigger={handleTrigger}
              onToggle={handleToggle}
              isTriggering={triggeringId === s.id}
              isToggling={togglingId === s.id}
            />
          ))}
        </div>
      )}

      {/* Create dialog */}
      <Dialog open={showCreate} onOpenChange={(open) => !open && setShowCreate(false)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>New Schedule</DialogTitle>
          </DialogHeader>
          <ScheduleForm
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
            <DialogTitle>Edit Schedule</DialogTitle>
          </DialogHeader>
          {editTarget && (
            <ScheduleForm
              defaultValues={scheduleToForm(editTarget)}
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
        schedule={deleteTarget}
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
};

export default Scheduler;
