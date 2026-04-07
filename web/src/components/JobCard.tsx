import React from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { JobResponse, JobStatus } from "@/types";
import { formatRelativeTime, formatElapsed } from "@/lib/time";

interface JobCardProps {
  job: JobResponse;
  onClick?: () => void;
}

const STATUS_CLASSES: Record<JobStatus, string> = {
  pending: "bg-gray-200 text-gray-800",
  running: "bg-blue-100 text-blue-800",
  success: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  cancelled: "bg-gray-200 text-gray-800",
};

const JobCard: React.FC<JobCardProps> = ({ job, onClick }) => {
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
      </CardContent>
    </Card>
  );
};

export default JobCard;
