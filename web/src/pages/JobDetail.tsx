import React, { useState, useCallback, useEffect } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import LogViewer from "@/components/LogViewer";
import { getJob, cancelJob } from "@/api/jobs";
import { useWebSocket } from "@/hooks/useWebSocket";
import { getJobProgress, setJobProgress } from "@/lib/jobProgressCache";
import type { JobResponse, JobStatus, WsMessage } from "@/types";
import { formatRelativeTime } from "@/lib/time";

const STATUS_CLASSES: Record<JobStatus, string> = {
  pending: "bg-gray-200 text-gray-800",
  running: "bg-blue-100 text-blue-800",
  waiting: "bg-amber-100 text-amber-800",
  success: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  cancelled: "bg-gray-200 text-gray-800",
};

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");

function clampProgress(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function statusToProgress(status: JobStatus): number {
  if (status === "success" || status === "failed" || status === "cancelled") {
    return 100;
  }
  return 0;
}

function buildWsUrl(jobId: string): string {
  if (API_BASE_URL) {
    const apiUrl = new URL(API_BASE_URL, window.location.origin);
    const protocol = apiUrl.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${apiUrl.host}/api/ws/jobs/${jobId}/logs`;
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/ws/jobs/${jobId}/logs`;
}

const JobDetail: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  const queryClient = useQueryClient();
  const [logLines, setLogLines] = useState<string[]>([]);
  const [isCancelling, setIsCancelling] = useState(false);
  const [progress, setProgress] = useState<number>(() => {
    if (!jobId) {
      return 0;
    }
    const cached = getJobProgress(jobId);
    return cached ?? 0;
  });

  const { data: job, isLoading, isError, error } = useQuery<JobResponse>({
    queryKey: ["jobs", jobId],
    queryFn: () => getJob(jobId!),
    enabled: jobId !== undefined,
    refetchInterval: (query) => {
      const data = query.state.data as JobResponse | undefined;
      return data?.status === "running" || data?.status === "pending" ? 2000 : false;
    },
  });

  useEffect(() => {
    setLogLines([]);
    if (!jobId) {
      setProgress(0);
      return;
    }
    const cached = getJobProgress(jobId);
    setProgress(cached ?? 0);
  }, [jobId]);

  const handleMessage = useCallback((msg: WsMessage) => {
    if (msg.type === "log") {
      setLogLines((prev) => [...prev, String(msg.data)]);
      return;
    }

    if (msg.type === "progress" && typeof msg.data === "number") {
      const next = clampProgress(msg.data);
      setProgress((prev) => {
        const updated = next > prev ? next : prev;
        if (jobId) {
          setJobProgress(jobId, updated);
        }
        return updated;
      });
      return;
    }

    if (msg.type === "status" && typeof msg.data === "string") {
      if (msg.data === "success" || msg.data === "failed" || msg.data === "cancelled") {
        setProgress(100);
        if (jobId) {
          setJobProgress(jobId, 100);
        }
      }
    }
  }, [jobId]);

  // For completed/failed jobs, seed logLines from the persisted log_output
  // returned by the API (WebSocket is only active whilst the job is running).
  useEffect(() => {
    if (
      job?.logOutput &&
      job.status !== "running" &&
      job.status !== "pending"
    ) {
      setLogLines(job.logOutput.split("\n"));
    }
  }, [job?.logOutput, job?.status]);

  useEffect(() => {
    if (!job) {
      return;
    }
    const baseline = statusToProgress(job.status);
    setProgress((prev) => {
      const cached = getJobProgress(job.id);
      const updated = Math.max(prev, baseline, cached ?? 0);
      setJobProgress(job.id, updated);
      return updated;
    });
  }, [job]);

  const wsUrl = jobId ? buildWsUrl(jobId) : "";

  useWebSocket(wsUrl, {
    onMessage: handleMessage,
    enabled:
      job?.status === "pending" ||
      job?.status === "waiting" ||
      job?.status === "running",
  });

  const handleCancel = async () => {
    if (!jobId) return;
    setIsCancelling(true);
    try {
      await cancelJob(jobId);
      await queryClient.invalidateQueries({ queryKey: ["jobs", jobId] });
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    } finally {
      setIsCancelling(false);
    }
  };

  const handleSave = () => {
    const blob = new Blob([logLines.join("\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `job-${jobId ?? "unknown"}-logs.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (isError || !job) {
    return (
      <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-red-800 text-sm">
        {error instanceof Error ? error.message : "Failed to load job."}
      </div>
    );
  }

  const canCancel = job.status === "running" || job.status === "pending";
  const isRunning = job.status === "running";

  const incidentCodes: string[] = (() => {
    const incidents = job.configSnapshot?.incidents;
    if (!Array.isArray(incidents)) return [];
    return incidents.map((inc) => (inc as Record<string, unknown>).incident_code as string).filter(Boolean);
  })();

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-2xl font-bold tracking-tight">{job.scriptName}</h2>
          <Badge className={`text-xs font-semibold ${STATUS_CLASSES[job.status]}`}>
            {job.status}
          </Badge>
        </div>
        {canCancel && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => void handleCancel()}
            disabled={isCancelling}
            className="text-red-600 border-red-300 hover:bg-red-50 hover:text-red-700"
          >
            {isCancelling ? "Cancelling…" : "Cancel"}
          </Button>
        )}
      </div>

      {/* Incidents */}
      {incidentCodes.length > 0 && (
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
            Incidents ({incidentCodes.length})
          </p>
          <div className="flex flex-wrap gap-1.5">
            {incidentCodes.map((code) => (
              <span
                key={code}
                className="inline-flex items-center rounded-md border border-border bg-muted px-2 py-0.5 text-xs font-mono text-foreground"
              >
                {code}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Metadata */}
      <div className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-3">
        <div>
          <p className="text-muted-foreground text-xs uppercase tracking-wide">Created</p>
          <p>{formatRelativeTime(job.createdAt)}</p>
        </div>
        {job.startedAt && (
          <div>
            <p className="text-muted-foreground text-xs uppercase tracking-wide">Started</p>
            <p>{formatRelativeTime(job.startedAt)}</p>
          </div>
        )}
        {job.completedAt && (
          <div>
            <p className="text-muted-foreground text-xs uppercase tracking-wide">Completed</p>
            <p>{formatRelativeTime(job.completedAt)}</p>
          </div>
        )}
      </div>

      {/* Progress */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs uppercase tracking-wide text-muted-foreground">
          <span>Progress</span>
          <span>{progress}%</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-all duration-300 ease-out"
            style={{ width: `${progress}%` }}
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress}
            aria-label="Job progress"
          />
        </div>
      </div>

      {/* Error message */}
      {job.errorMessage && (
        <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 text-red-800 text-sm">
          {job.errorMessage}
        </div>
      )}

      {/* Output files */}
      {job.outputFiles && job.outputFiles.length > 0 && (
        <div>
          <p className="text-sm font-medium mb-1">Output Files</p>
          <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
            {job.outputFiles.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Log viewer */}
      <LogViewer
        lines={logLines}
        isRunning={isRunning}
        onSave={handleSave}
        maxHeight="500px"
      />
    </div>
  );
};

export default JobDetail;
