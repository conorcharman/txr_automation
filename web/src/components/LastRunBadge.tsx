import React from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchLastRuns } from "@/api/jobs";
import type { LastRunInfo } from "@/types";
import { cn } from "@/lib/utils";

interface LastRunBadgeProps {
  scriptName: string;
  className?: string;
}

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  return `${days}d ago`;
}

const LastRunBadge: React.FC<LastRunBadgeProps> = ({ scriptName, className }) => {
  const { data: lastRuns } = useQuery<Record<string, LastRunInfo>>({
    queryKey: ["last-runs"],
    queryFn: fetchLastRuns,
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  const info = lastRuns?.[scriptName];
  if (!info) return null;

  const isSuccess = info.status === "success";

  const relativeTime = info.completedAt ? formatRelativeTime(info.completedAt) : null;
  const ariaLabel = isSuccess
    ? `Last run passed${relativeTime ? `, ${relativeTime}` : ""}`
    : `Last run failed${relativeTime ? `, ${relativeTime}` : ""}`;

  return (
    <span
      role="status"
      aria-label={ariaLabel}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
        isSuccess
          ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
          : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          isSuccess ? "bg-green-500" : "bg-red-500",
        )}
      />
      {isSuccess ? "Passed" : "Failed"}
      {relativeTime && (
        <span className="text-xs">
          {relativeTime}
        </span>
      )}
    </span>
  );
};

export default LastRunBadge;
