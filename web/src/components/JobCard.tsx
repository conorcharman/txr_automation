import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { useWebSocket } from "@/hooks/useWebSocket";
import { getJobProgress, setJobProgress } from "@/lib/jobProgressCache";
import type { JobResponse, JobStatus, WsMessage } from "@/types";
import { formatRelativeTime, formatElapsed } from "@/lib/time";

interface JobCardProps {
  job: JobResponse;
  onClick?: () => void;
}

const STATUS_CLASSES: Record<JobStatus, string> = {
  pending: "bg-gray-200 text-gray-800",
  running: "bg-blue-100 text-blue-800",
  waiting: "bg-amber-100 text-amber-800",
  success: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  cancelled: "bg-gray-200 text-gray-800",
};

function buildWsUrl(jobId: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/ws/jobs/${jobId}/logs`;
}

function statusToProgress(status: JobStatus): number {
  if (status === "success" || status === "failed" || status === "cancelled") {
    return 100;
  }
  return 0;
}

const JobCard: React.FC<JobCardProps> = ({ job, onClick }) => {
  const [progress, setProgress] = useState<number>(() => {
    const cached = getJobProgress(job.id);
    if (cached !== null) {
      return Math.max(cached, statusToProgress(job.status));
    }
    return statusToProgress(job.status);
  });

  useEffect(() => {
    const baseline = statusToProgress(job.status);
    const cached = getJobProgress(job.id);
    const next = cached !== null ? Math.max(cached, baseline) : baseline;
    setProgress(next);
    setJobProgress(job.id, next);
  }, [job.id, job.status]);

  const wsUrl = useMemo(() => buildWsUrl(job.id), [job.id]);

  const handleMessage = useCallback((msg: WsMessage) => {
    if (msg.type === "progress" && typeof msg.data === "number") {
      const next = Math.max(0, Math.min(100, Math.round(msg.data)));
      setProgress((prev) => {
        const updated = next > prev ? next : prev;
        setJobProgress(job.id, updated);
        return updated;
      });
      return;
    }

    if (msg.type === "status" && typeof msg.data === "string") {
      if (msg.data === "success" || msg.data === "failed" || msg.data === "cancelled") {
        setProgress(100);
        setJobProgress(job.id, 100);
      }
    }
  }, [job.id]);

  useWebSocket(wsUrl, {
    onMessage: handleMessage,
    enabled: job.status === "pending" || job.status === "waiting" || job.status === "running",
  });

  const elapsed =
    job.startedAt && job.completedAt
      ? formatElapsed(job.startedAt, job.completedAt)
      : null;

  return (
    <Card
      className={`transition-shadow ${onClick ? "cursor-pointer hover:shadow-md" : ""}`}
      onClick={onClick}
    >
      <CardContent className="pt-4 pb-4 flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <Badge className={`text-xs font-semibold ${STATUS_CLASSES[job.status]}`}>
            {job.status}
          </Badge>
          {elapsed && (
            <span className="text-xs text-muted-foreground">{elapsed}</span>
          )}
        </div>

        <p
          className="text-sm font-medium truncate"
          title={job.scriptName}
        >
          {job.scriptName}
        </p>

        <p className="text-xs text-muted-foreground">
          {formatRelativeTime(job.createdAt)}
        </p>

        <div className="space-y-1">
          <div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-muted-foreground">
            <span>Progress</span>
            <span>{progress}%</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all duration-300 ease-out"
              style={{ width: `${progress}%` }}
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progress}
              aria-label={`Progress for ${job.scriptName}`}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default JobCard;
