import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Plus,
  AlertCircle,
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
  Alert,
  AlertTitle,
  AlertDescription,
} from "@/components/ui/alert";
import {
  listRuns,
  triggerRun,
} from "@/api/dailyRecon";
import type {
  DailyReconRun,
} from "@/types";

// ────────────────────────────────────────────────────────────────────────────
// Run List View
// ────────────────────────────────────────────────────────────────────────────

interface RunListProps {
  onSelectRun: (run: DailyReconRun) => void;
}

function RunList({ onSelectRun }: RunListProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["daily-recon-runs"],
    queryFn: () => listRuns(50, 0),
    refetchInterval: 10000, // Poll every 10s
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Reconciliation Runs</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent className="pt-6">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Error loading runs</AlertTitle>
            <AlertDescription>{String(error)}</AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  const runs = data?.data || [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Reconciliation Runs</CardTitle>
        <CardDescription>
          {runs.length} run(s) available
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {runs.length === 0 ? (
            <p className="text-sm text-muted-foreground">No runs yet</p>
          ) : (
            runs.map((run) => (
              <button
                key={run.id}
                onClick={() => onSelectRun(run)}
                className="w-full flex items-center justify-between p-3 rounded-lg border hover:bg-accent transition-colors text-left cursor-pointer"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <Badge
                      variant={
                        run.status === "validated"
                          ? "default"
                          : run.status === "failed"
                            ? "destructive"
                            : "secondary"
                      }
                    >
                      {run.status}
                    </Badge>
                    <span className="font-medium">
                      {run.rowCount} rows
                    </span>
                  </div>
                  <div className="text-sm text-muted-foreground mt-1">
                    Created {new Date(run.createdAt || "").toLocaleDateString()}
                  </div>
                </div>
                {run.errorRowCount > 0 && (
                  <div className="text-sm font-medium text-destructive">
                    {run.errorRowCount} errors
                  </div>
                )}
              </button>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Main Page
// ────────────────────────────────────────────────────────────────────────────

export default function DailyReconciliationPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const triggerMutation = useMutation({
    mutationFn: () => triggerRun({}),
    onSuccess: async (run) => {
      toast.success("Reconciliation run started");
      await queryClient.invalidateQueries({ queryKey: ["daily-recon-runs"] });
      navigate(`/daily-recon/${run.id}`);
    },
    onError: (err) => toast.error(String(err)),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Daily Reconciliation</h1>
          <p className="text-muted-foreground mt-1">
            Extract, validate, review, and export transaction data
          </p>
        </div>
        <Button
          className="gap-2"
          onClick={() => triggerMutation.mutate()}
          disabled={triggerMutation.isPending}
        >
          <Plus className="h-4 w-4" />
          {triggerMutation.isPending ? "Running..." : "Run Query Now"}
        </Button>
      </div>

      <RunList onSelectRun={(run) => navigate(`/daily-recon/${run.id}`)} />
    </div>
  );
}
