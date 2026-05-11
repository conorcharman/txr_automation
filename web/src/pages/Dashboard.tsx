import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import JobCard from "@/components/JobCard";
import { fetchDashboardStats } from "@/api/dashboard";
import { listJobs } from "@/api/jobs";
import { browseDirectory, readFile } from "@/api/filesystem";
import type { FilesystemEntry, FileReadResponse } from "@/types";

interface StatCardProps {
  title: string;
  value: React.ReactNode;
  loading: boolean;
}

const StatCard: React.FC<StatCardProps> = ({ title, value, loading }) => (
  <Card>
    <CardHeader className="pb-2">
      <CardTitle className="text-sm font-medium text-muted-foreground">
        {title}
      </CardTitle>
    </CardHeader>
    <CardContent>
      {loading ? (
        <Skeleton className="h-8 w-24" />
      ) : (
        <div className="text-2xl font-bold">{value}</div>
      )}
    </CardContent>
  </Card>
);

const Dashboard: React.FC = () => {
  const navigate = useNavigate();

  const {
    data: statsData,
    isLoading: statsLoading,
    isError: statsError,
  } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: fetchDashboardStats,
    refetchInterval: 10_000,
  });

  const { data: jobs, isLoading: jobsLoading } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => listJobs(),
  });

  const recentJobs = jobs?.slice(0, 5) ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
        <p className="text-muted-foreground mt-1">
          Welcome to TXR Automation — your central hub for transaction reporting
          validation workflows.
        </p>
        {statsError && (
          <p className="mt-2 text-sm text-destructive">
            Unable to load dashboard statistics. Retrying...
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Jobs Today"
          loading={statsLoading}
          value={statsData?.jobsToday}
        />
        <StatCard
          title="Running Now"
          loading={statsLoading}
          value={
            <div className="flex items-center gap-2">
              {(statsData?.runningNow ?? 0) > 0 && (
                <div className="h-2.5 w-2.5 rounded-full bg-green-500 animate-pulse" />
              )}
              {statsData?.runningNow}
            </div>
          }
        />
        <StatCard
          title="Success Rate"
          loading={statsLoading}
          value={
            statsData != null
              ? `${Math.round(statsData.successRate * 100)}%`
              : undefined
          }
        />
        <StatCard
          title="Saved Configs"
          loading={statsLoading}
          value={statsData?.totalSavedConfigs}
        />
      </div>

      <div className="space-y-3">
        <h3 className="text-lg font-semibold tracking-tight">Recent Jobs</h3>

        {jobsLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
          </div>
        ) : recentJobs.length === 0 ? (
          <p className="text-sm text-muted-foreground">No recent jobs.</p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {recentJobs.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                onClick={() => navigate(`/jobs/${job.id}`)}
              />
            ))}
          </div>
        )}

        <div className="pt-1">
          <Link
            to="/jobs"
            className="text-sm text-primary hover:underline underline-offset-2"
          >
            View all jobs →
          </Link>
        </div>
      </div>

      <div className="space-y-3">
        <h3 className="text-lg font-semibold tracking-tight">Files</h3>
        <FileBrowserCard />
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// File Browser tile
// ---------------------------------------------------------------------------

const ROOT_PATH = "/app/data";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

const FileBrowserCard: React.FC = () => {
  const [currentPath, setCurrentPath] = useState<string>(ROOT_PATH);
  const [selectedFile, setSelectedFile] = useState<FilesystemEntry | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const { data: browse, isLoading: browseLoading, isError: browseError } = useQuery({
    queryKey: ["filesystem-browse", currentPath],
    queryFn: () => browseDirectory(currentPath),
    staleTime: 5_000,
  });

  const { data: fileData, isLoading: fileLoading } = useQuery<FileReadResponse>({
    queryKey: ["filesystem-read", selectedFile?.path],
    queryFn: () => readFile(selectedFile!.path),
    enabled: dialogOpen && selectedFile != null,
  });

  const handleEntry = (entry: FilesystemEntry) => {
    if (entry.isDir) {
      setCurrentPath(entry.path);
    } else {
      setSelectedFile(entry);
      setDialogOpen(true);
    }
  };

  const handleUp = () => {
    if (browse?.parent) setCurrentPath(browse.parent);
  };

  // Breadcrumb: split path relative to ROOT_PATH
  const relParts = currentPath.startsWith(ROOT_PATH)
    ? currentPath.slice(ROOT_PATH.length).split("/").filter(Boolean)
    : [];

  return (
    <>
      <Card>
        <CardHeader className="pb-2 flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-medium">File Browser</CardTitle>
          <span className="text-xs text-muted-foreground font-mono truncate max-w-xs">
            {ROOT_PATH}
            {relParts.map((p, i) => (
              <span key={i}> / {p}</span>
            ))}
          </span>
        </CardHeader>
        <CardContent className="p-0">
          {browseLoading ? (
            <div className="space-y-2 p-4">
              <Skeleton className="h-5 w-full" />
              <Skeleton className="h-5 w-full" />
              <Skeleton className="h-5 w-3/4" />
            </div>
          ) : browseError ? (
            <p className="px-4 py-3 text-sm text-destructive">
              Unable to browse directory. Is the API running?
            </p>
          ) : (
            <div className="divide-y divide-border max-h-64 overflow-y-auto text-sm">
              {browse?.parent && (
                <button
                  onClick={handleUp}
                  className="flex w-full items-center gap-2 px-4 py-2 text-left text-muted-foreground hover:bg-muted transition-colors"
                >
                  <span className="text-base">↑</span>
                  <span className="font-mono text-xs">..</span>
                </button>
              )}
              {browse?.entries.length === 0 && (
                <p className="px-4 py-3 text-muted-foreground">Empty directory.</p>
              )}
              {browse?.entries.map((entry) => (
                <button
                  key={entry.path}
                  onClick={() => handleEntry(entry)}
                  className="flex w-full items-center gap-2 px-4 py-2 text-left hover:bg-muted transition-colors"
                >
                  <span className={entry.isDir ? "text-amber-500" : "text-muted-foreground"}>
                    {entry.isDir ? "📁" : "📄"}
                  </span>
                  <span className={entry.isDir ? "font-medium" : ""}>{entry.name}</span>
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-3xl w-full">
          <DialogHeader>
            <DialogTitle className="font-mono text-sm truncate">
              {selectedFile?.name}
            </DialogTitle>
          </DialogHeader>
          {fileLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <Skeleton className="h-4 w-full" />
            </div>
          ) : fileData ? (
            <div className="space-y-2">
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <span>{formatBytes(fileData.sizeBytes)}</span>
                {fileData.truncated && (
                  <span className="rounded bg-yellow-100 px-1.5 py-0.5 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300">
                    Showing first 1 MB
                  </span>
                )}
              </div>
              <pre className="max-h-[60vh] overflow-auto rounded-md bg-muted p-3 text-xs font-mono whitespace-pre-wrap break-words">
                {fileData.content}
              </pre>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
};

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

export default Dashboard;

