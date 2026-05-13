import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import JobCard from "@/components/JobCard";
import { PathPickerInput } from "@/components/PathPickerInput";
import { listJobs, clearJobHistory } from "@/api/jobs";
import { getFilesystemConfig } from "@/api/filesystem";
import type { JobResponse } from "@/types";
import { cn } from "@/lib/utils";

const GLOBAL_LOG_KEY = "txr_global_log_output";

function readGlobalLog(): string {
  try { return localStorage.getItem(GLOBAL_LOG_KEY) || ""; } catch { return ""; }
}

interface AdvancedSectionProps { show: boolean; onToggle: () => void; children: React.ReactNode; }
const AdvancedSection: React.FC<AdvancedSectionProps> = ({ show, onToggle, children }) => (
  <div className="rounded-md border border-border">
    <button type="button" onClick={onToggle}
      className="flex w-full items-center justify-between px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors">
      Settings
      <span className={cn("transition-transform text-[10px]", show && "rotate-180")}>▾</span>
    </button>
    {show && <div className="space-y-3 px-3 pb-3 border-t border-border pt-3">{children}</div>}
  </div>
);

const Jobs: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showSettings, setShowSettings] = useState(false);
  const [logOutput, setLogOutput] = useState<string>(readGlobalLog);

  // Populate log path default from server config when localStorage is empty.
  const { data: fsConfig } = useQuery({
    queryKey: ["filesystem-config"],
    queryFn: getFilesystemConfig,
    staleTime: Infinity,
  });
  useEffect(() => {
    if (!logOutput && fsConfig?.dataRoot) {
      setLogOutput(fsConfig.dataRoot + "/logs");
    }
  }, [fsConfig, logOutput]);

  const clearMutation = useMutation({
    mutationFn: clearJobHistory,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });

  const handleClearHistory = () => {
    if (!window.confirm("Delete all completed, failed, and cancelled jobs? Active jobs will not be affected.")) return;
    clearMutation.mutate();
  };

  useEffect(() => {
    try { localStorage.setItem(GLOBAL_LOG_KEY, logOutput); } catch { /* ignore */ }
  }, [logOutput]);

  const { data: jobs, isLoading, isError, error } = useQuery<JobResponse[]>({
    queryKey: ["jobs"],
    queryFn: () => listJobs(),
    refetchInterval: 5000,
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold tracking-tight">Job History</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Card key={i}>
              <CardContent className="pt-4 pb-4 space-y-3">
                <Skeleton className="h-5 w-20" />
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-3 w-24" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6">
        <h2 className="text-2xl font-bold tracking-tight">Job History</h2>
        <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-red-800 text-sm">
          {error instanceof Error ? error.message : "Failed to load jobs."}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <h2 className="text-2xl font-bold tracking-tight">Job History</h2>
        {jobs && jobs.length > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleClearHistory}
            disabled={clearMutation.isPending}
            className="text-red-600 border-red-300 hover:bg-red-50 hover:text-red-700"
          >
            {clearMutation.isPending ? "Clearing…" : "Clear History"}
          </Button>
        )}
      </div>

      <AdvancedSection show={showSettings} onToggle={() => setShowSettings((v) => !v)}>
        <div className="flex flex-col gap-1 max-w-sm">
          <label className="text-xs font-medium text-muted-foreground">Log Output Directory</label>
          <PathPickerInput
            value={logOutput}
            onChange={setLogOutput}
            mode="directory"
            placeholder="logs"
          />
          <p className="text-[11px] text-muted-foreground">
            Directory where all scripts write their log files. Applied globally to all runs.
          </p>
        </div>
      </AdvancedSection>

      {jobs && jobs.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No jobs yet. Run a validation to see results here.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {jobs?.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              onClick={() => navigate(`/jobs/${job.id}`)}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default Jobs;
