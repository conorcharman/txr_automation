import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Download,
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Eye,
  EyeOff,
  RotateCw,
  X,
  Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import {
  getRun,
  approveRow,
  unapproveRow,
  applyCorrection,
  acceptSuggestion,
  exportRun,
  revalidateRun,
  cancelRevalidationRun,
  deleteRun,
} from "@/api/dailyRecon";
import type {
  DailyReconRow,
  DailyReconCell,
  CellIssue,
} from "@/types";
import { useState } from "react";

// ────────────────────────────────────────────────────────────────────────────
// Cell Error Detail Modal
// ────────────────────────────────────────────────────────────────────────────

interface CellDetailModalProps {
  cell: DailyReconCell | null;
  onClose: () => void;
  onAcceptSuggestion?: () => void;
  onCorrectionApplied?: () => void;
}

function CellDetailModal({
  cell,
  onClose,
  onAcceptSuggestion,
  onCorrectionApplied,
}: CellDetailModalProps) {
  const [correctedValue, setCorrectedValue] = useState(cell?.correctedValue || "");
  const queryClient = useQueryClient();

  const correctionMutation = useMutation({
    mutationFn: (value: string) =>
      applyCorrection(cell!.id, { correctedValue: value }),
    onSuccess: async () => {
      toast.success("Correction applied");
      await queryClient.invalidateQueries({ queryKey: ["daily-recon-run"] });
      onCorrectionApplied?.();
    },
    onError: (err) => toast.error(String(err)),
  });

  const acceptMutation = useMutation({
    mutationFn: () => acceptSuggestion(cell!.id),
    onSuccess: async () => {
      toast.success("Suggestion accepted");
      await queryClient.invalidateQueries({ queryKey: ["daily-recon-run"] });
      onAcceptSuggestion?.();
    },
    onError: (err) => toast.error(String(err)),
  });

  if (!cell) return null;

  return (
    <Dialog open={!!cell} onOpenChange={onClose}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {cell.isErrored ? (
              <AlertCircle className="h-5 w-5 text-destructive" />
            ) : (
              <CheckCircle2 className="h-5 w-5 text-green-600" />
            )}
            {cell.columnName}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Original Value */}
          <div>
            <label className="text-sm font-medium">Original Value</label>
            <div className="mt-1 p-2 bg-muted rounded text-sm font-mono">
              {cell.originalValue || "(empty)"}
            </div>
          </div>

          {/* Issues */}
          {cell.issues && cell.issues.length > 0 && (
            <div>
              <label className="text-sm font-medium">Validation Issues</label>
              <div className="mt-1 space-y-2">
                {cell.issues.map((issue: CellIssue, idx: number) => (
                  <div key={idx} className="p-2 bg-destructive/10 rounded text-sm">
                    <div className="font-medium text-destructive">
                      {issue.ruleId}
                    </div>
                    <div className="mt-1 text-foreground">
                      {issue.message}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Suggested Fix */}
          {cell.suggestedFix && (
            <div>
              <label className="text-sm font-medium">Suggested Fix</label>
              <div className="mt-1 p-2 bg-blue-50 rounded text-sm font-mono flex items-center justify-between">
                <span>{cell.suggestedFix}</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => acceptMutation.mutate()}
                  disabled={acceptMutation.isPending}
                >
                  Accept
                </Button>
              </div>
            </div>
          )}

          {/* Manual Correction */}
          <div>
            <label className="text-sm font-medium">Manual Correction</label>
            <div className="mt-1 flex gap-2">
              <input
                type="text"
                value={correctedValue}
                onChange={(e) => setCorrectedValue(e.target.value)}
                placeholder="Enter corrected value..."
                className="flex-1 px-3 py-2 border rounded text-sm"
              />
              <Button
                onClick={() => correctionMutation.mutate(correctedValue)}
                disabled={correctionMutation.isPending}
              >
                Apply
              </Button>
            </div>
          </div>

          {/* Corrected Value Display */}
          {cell.correctedValue && (
            <div>
              <label className="text-sm font-medium text-green-600">
                Corrected Value
              </label>
              <div className="mt-1 p-2 bg-green-50 rounded text-sm font-mono">
                {cell.correctedValue}
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">Close</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Row Inspector
// ────────────────────────────────────────────────────────────────────────────

interface RowInspectorProps {
  row: DailyReconRow;
  onApprovalChange: () => void;
}

function RowInspector({ row, onApprovalChange }: RowInspectorProps) {
  const [expanded, setExpanded] = useState(false);
  const [selectedCell, setSelectedCell] = useState<DailyReconCell | null>(null);
  const [showAllCells, setShowAllCells] = useState(false);
  const queryClient = useQueryClient();

  const approveMutation = useMutation({
    mutationFn: () =>
      row.approved ? unapproveRow(row.id) : approveRow(row.id),
    onSuccess: async () => {
      toast.success(
        row.approved ? "Row unmarked for approval" : "Row approved"
      );
      await queryClient.invalidateQueries({ queryKey: ["daily-recon-run"] });
      onApprovalChange();
    },
    onError: (err) => toast.error(String(err)),
  });

  const errorCells = row.cells.filter((c) => c.isErrored);
  const displayCells = showAllCells ? row.cells : errorCells;

  return (
    <div className="border rounded-lg mb-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-3 hover:bg-accent transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-3 flex-1 text-left">
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}

          <div className="flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-muted-foreground uppercase tracking-wide">
                Trade Ref
              </span>
              <span className="font-medium font-mono text-sm">
                {row.tradeRef || `Row ${row.rowIndex}`}
              </span>
              {row.hasError ? (
                <Badge variant="destructive" className="gap-1">
                  <AlertCircle className="h-3 w-3" />
                  {errorCells.length} error{errorCells.length !== 1 ? "s" : ""}
                </Badge>
              ) : (
                <Badge variant="outline" className="gap-1 text-green-600 border-green-300">
                  <CheckCircle2 className="h-3 w-3" />
                  Clean
                </Badge>
              )}
              {row.approved && (
                <Badge variant="outline" className="gap-1 text-blue-600 border-blue-300">
                  Approved
                </Badge>
              )}
            </div>
          </div>

          <Button
            variant={row.approved ? "secondary" : "outline"}
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              approveMutation.mutate();
            }}
            disabled={approveMutation.isPending}
          >
            {row.approved ? "Unapprove" : "Approve"}
          </Button>
        </div>
      </button>

      {expanded && (
        <div className="px-3 pb-3 bg-muted/30 border-t">
          {/* Sub-header: column count + toggle */}
          <div className="flex items-center justify-between py-2">
            <span className="text-xs text-muted-foreground">
              {row.cells.length} columns
              {errorCells.length > 0
                ? ` · ${errorCells.length} with errors`
                : " · no errors"}
            </span>
            {row.cells.length > 0 && (
              <button
                onClick={() => setShowAllCells(!showAllCells)}
                className="text-xs text-primary hover:underline cursor-pointer"
              >
                {showAllCells ? "Show errors only" : "Show all columns"}
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 gap-1">
            {displayCells.length === 0 && !showAllCells && (
              <p className="text-xs text-muted-foreground py-3 text-center">
                No validation errors — row is clean ✓
              </p>
            )}
            {displayCells.map((cell) => (
              <button
                key={cell.id}
                onClick={() => setSelectedCell(cell)}
                className={`text-left p-2 rounded border transition-colors cursor-pointer ${
                  cell.isErrored
                    ? "bg-destructive/5 border-destructive/20 hover:bg-destructive/10"
                    : "bg-background border-border hover:bg-accent"
                }`}
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      {cell.isErrored && (
                        <AlertCircle className="h-3 w-3 text-destructive shrink-0" />
                      )}
                      <span className="font-medium text-xs uppercase tracking-wide text-muted-foreground">
                        {cell.columnName}
                      </span>
                    </div>
                    <div className="text-sm font-mono mt-0.5 truncate">
                      {cell.correctedValue ? (
                        <span className="text-green-700">{cell.correctedValue}</span>
                      ) : cell.originalValue ? (
                        <span className={cell.isErrored ? "text-destructive" : ""}>
                          {cell.originalValue}
                        </span>
                      ) : (
                        <span className="italic text-muted-foreground">(empty)</span>
                      )}
                    </div>
                    {cell.suggestedFix && (
                      <div className="text-xs text-blue-600 mt-0.5">
                        → Suggested: {cell.suggestedFix}
                      </div>
                    )}
                  </div>
                  <Eye className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      <CellDetailModal
        cell={selectedCell}
        onClose={() => setSelectedCell(null)}
        onCorrectionApplied={() => setSelectedCell(null)}
        onAcceptSuggestion={() => setSelectedCell(null)}
      />
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Run Detail Page
// ────────────────────────────────────────────────────────────────────────────

export default function DailyReconciliationDetail() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [showErrorsOnly, setShowErrorsOnly] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const queryClient = useQueryClient();

  const { data: run, isLoading, error } = useQuery({
    queryKey: ["daily-recon-run", runId],
    queryFn: () => getRun(runId!),
    refetchInterval: 5000,
  });

  const revalidateMutation = useMutation({
    mutationFn: () => revalidateRun(runId!),
    onSuccess: async () => {
      toast.success("Revalidation started");
      await queryClient.invalidateQueries({ queryKey: ["daily-recon-run", runId] });
    },
    onError: (err) => toast.error(String(err)),
  });

  const cancelMutation = useMutation({
    mutationFn: () => cancelRevalidationRun(runId!),
    onSuccess: () => {
      toast.success("Cancellation requested");
      queryClient.invalidateQueries({ queryKey: ["daily-recon-run", runId] });
    },
    onError: (err) => toast.error(String(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteRun(runId!),
    onSuccess: () => {
      toast.success("Run deleted");
      navigate("/daily-recon");
    },
    onError: (err) => toast.error(String(err)),
  });

  const exportMutation = useMutation({
    mutationFn: () => exportRun(runId!),
    onSuccess: (blob) => {
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `daily-recon-${runId}.csv`;
      link.click();
      window.URL.revokeObjectURL(url);
      toast.success("CSV exported");
    },
    onError: (err) => toast.error(String(err)),
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Loading...</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </CardContent>
      </Card>
    );
  }

  if (error || !run) {
    return (
      <Card>
        <CardContent className="pt-6">
          <p className="text-destructive">{String(error) || "Run not found"}</p>
          <Button onClick={() => navigate(-1)} className="mt-4">
            Back to Runs
          </Button>
        </CardContent>
      </Card>
    );
  }

  const rows = run.rows || [];
  const displayRows = showErrorsOnly ? rows.filter((r) => r.hasError) : rows;
  const approvedCount = rows.filter((r) => r.approved).length;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <CardTitle>Run Details</CardTitle>
              <CardDescription>{run.id}</CardDescription>
            </div>
            <div className="flex items-center gap-2">
              {run.status === "running" && (
                <Badge variant="secondary" className="gap-1 animate-pulse">
                  <div className="h-2 w-2 rounded-full bg-current" />
                  Running
                </Badge>
              )}
              {run.status === "cancelled" && (
                <Badge variant="outline" className="gap-1 text-gray-600 border-gray-300">
                  <X className="h-3 w-3" />
                  Cancelled
                </Badge>
              )}
              {run.status === "running" && (
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => cancelMutation.mutate()}
                  disabled={cancelMutation.isPending}
                  className="gap-2"
                >
                  <X className="h-4 w-4" />
                  {cancelMutation.isPending ? "Cancelling..." : "Cancel"}
                </Button>
              )}
              {run.status !== "running" && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => revalidateMutation.mutate()}
                  disabled={revalidateMutation.isPending}
                  className="gap-2"
                >
                  <RotateCw className="h-4 w-4" />
                  {revalidateMutation.isPending ? "Validating..." : "Re-run Validations"}
                </Button>
              )}
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setShowDeleteConfirm(true)}
                disabled={deleteMutation.isPending || run.status === "running"}
                className="gap-2"
              >
                <Trash2 className="h-4 w-4" />
                {deleteMutation.isPending ? "Deleting..." : "Delete"}
              </Button>
              <Button variant="outline" onClick={() => navigate(-1)}>
                Back to Runs
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-4 gap-4">
            <div>
              <div className="text-sm text-muted-foreground">Status</div>
              <Badge className="mt-1">{run.status}</Badge>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Total Rows</div>
              <div className="text-2xl font-bold mt-1">{run.rowCount}</div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Error Rows</div>
              <div className="text-2xl font-bold text-destructive mt-1">
                {run.errorRowCount}
              </div>
            </div>
            <div>
              <div className="text-sm text-muted-foreground">Approved</div>
              <div className="text-2xl font-bold text-green-600 mt-1">
                {approvedCount}
              </div>
            </div>
          </div>

          {run.status === "validated" && (
            <Button
              onClick={() => exportMutation.mutate()}
              disabled={exportMutation.isPending || approvedCount === 0}
              className="gap-2 w-full"
            >
              <Download className="h-4 w-4" />
              Export {approvedCount > 0 ? `${approvedCount} Approved Rows` : "(No approved rows)"}
            </Button>
          )}
         </CardContent>
       </Card>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-destructive" />
              Delete Run?
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <p className="text-sm text-muted-foreground">
              Are you sure you want to delete this run? This will permanently remove all {run.rowCount} rows and all validation issues.
            </p>
            <p className="text-sm font-medium text-destructive">
              This action cannot be undone.
            </p>
          </div>
          <DialogFooter className="gap-2">
            <DialogClose asChild>
              <Button variant="outline">Cancel</Button>
            </DialogClose>
            <Button
              variant="destructive"
              onClick={() => {
                deleteMutation.mutate();
                setShowDeleteConfirm(false);
              }}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? "Deleting..." : "Delete Run"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

       <Card>
         <CardHeader>
           <div className="flex items-center justify-between">
             <CardTitle>Rows</CardTitle>
             <button
               onClick={() => setShowErrorsOnly(!showErrorsOnly)}
              className="flex items-center gap-2 px-3 py-1 text-sm rounded border hover:bg-accent transition-colors"
            >
              {showErrorsOnly ? (
                <>
                  <EyeOff className="h-4 w-4" />
                  Showing errors only
                </>
              ) : (
                <>
                  <Eye className="h-4 w-4" />
                  Show all
                </>
              )}
            </button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-1 max-h-150 overflow-y-auto">
            {displayRows.length === 0 ? (
              <p className="text-sm text-muted-foreground p-3">
                No rows {showErrorsOnly ? "with errors" : ""}
              </p>
            ) : (
              displayRows.map((row) => (
                <RowInspector
                  key={row.id}
                  row={row}
                  onApprovalChange={() => {
                    // Trigger refetch
                  }}
                />
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
