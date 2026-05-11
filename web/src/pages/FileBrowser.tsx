import React, { useState, useMemo } from "react";
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
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { readFile } from "@/api/filesystem";
import { listJobs } from "@/api/jobs";
import type { JobResponse, FileReadResponse } from "@/types";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Keys used to store the configured output file path in a job's configSnapshot. */
const OUTPUT_KEYS = ["output_file", "outputFile", "output", "replay_output", "replayOutput"];

const MODULE_LABELS: Record<string, string> = {
  accuracy_testing: "Accuracy Testing",
  fca: "FCA Register",
  firds: "FIRDS",
  gleif: "GLEIF",
  replay: "Replay",
  utils: "Utilities",
  utilities: "Utilities",
  reconciliation: "Reconciliation",
  automation: "Automation",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

function getModuleKey(scriptName: string): string {
  const parts = scriptName.split(".");
  if (parts.length >= 2 && parts[0] === "src") return parts[1];
  return scriptName;
}

function getModuleLabel(key: string): string {
  return MODULE_LABELS[key] ?? key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function extractOutputFiles(snapshot: Record<string, unknown> | null): string[] {
  if (!snapshot) return [];
  const seen = new Set<string>();
  return OUTPUT_KEYS.flatMap((k) => {
    const val = snapshot[k];
    if (typeof val === "string" && val.length > 0 && !seen.has(val)) {
      seen.add(val);
      return [val];
    }
    return [];
  });
}

function formatScriptName(scriptName: string): string {
  const parts = scriptName.split(".");
  const last = parts[parts.length - 1];
  return last.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function basename(path: string): string {
  return path.replace(/\\/g, "/").split("/").pop() ?? path;
}

// ---------------------------------------------------------------------------
// CsvTable — renders CSV content as a scrollable HTML table
// ---------------------------------------------------------------------------

function parseCsvRow(line: string): string[] {
  const result: string[] = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') { current += '"'; i++; }
      else { inQuotes = !inQuotes; }
    } else if (ch === "," && !inQuotes) {
      result.push(current);
      current = "";
    } else {
      current += ch;
    }
  }
  result.push(current);
  return result;
}

const CsvTable: React.FC<{ content: string }> = ({ content }) => {
  const lines = content.replace(/\r\n/g, "\n").replace(/\r/g, "\n").trim().split("\n");
  if (lines.length === 0) return <p className="text-xs text-muted-foreground">Empty file.</p>;
  const headers = parseCsvRow(lines[0]);
  const rows = lines.slice(1).map(parseCsvRow);
  const displayRows = rows.slice(0, 500);
  return (
    <div className="overflow-auto max-h-[55vh] rounded-md border">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-muted">
          <tr>
            {headers.map((h, i) => (
              <th key={i} className="border-b border-border px-3 py-2 text-left font-medium text-muted-foreground whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {displayRows.map((row, ri) => (
            <tr key={ri} className="hover:bg-muted/50">
              {row.map((cell, ci) => (
                <td key={ci} className="max-w-[200px] truncate px-3 py-1.5 whitespace-nowrap" title={cell}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
          {rows.length > 500 && (
            <tr>
              <td colSpan={headers.length} className="px-3 py-2 text-center text-xs text-muted-foreground">
                Showing first 500 of {rows.length} rows.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
};

// ---------------------------------------------------------------------------
// FilePreviewDialog — shows a file's content (CSV table or plain text)
// ---------------------------------------------------------------------------

interface FilePreviewDialogProps {
  open: boolean;
  path: string | null;
  onClose: () => void;
}

const FilePreviewDialog: React.FC<FilePreviewDialogProps> = ({ open, path, onClose }) => {
  const { data, isLoading, isError } = useQuery<FileReadResponse>({
    queryKey: ["file-preview", path],
    queryFn: () => readFile(path!),
    enabled: open && path != null,
    staleTime: 30_000,
  });

  const handleDownload = () => {
    if (!data) return;
    const blob = new Blob([data.content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = data.name;
    a.click();
    URL.revokeObjectURL(url);
  };

  const isCsv = path?.toLowerCase().endsWith(".csv") ?? false;

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-5xl w-full max-h-[85vh] overflow-auto">
        <DialogHeader>
          <DialogTitle className="font-mono text-sm">{path ? basename(path) : ""}</DialogTitle>
        </DialogHeader>
        {isLoading && <Skeleton className="h-40 w-full" />}
        {isError && <p className="text-sm text-destructive">Could not load file. It may not exist or be inaccessible.</p>}
        {data && (
          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <span>{formatBytes(data.sizeBytes)}</span>
                {data.truncated && (
                  <span className="rounded bg-yellow-100 px-1.5 py-0.5 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300">
                    First 1 MB shown
                  </span>
                )}
              </div>
              <Button variant="outline" size="sm" className="h-7 text-xs" onClick={handleDownload}>
                Download
              </Button>
            </div>
            {isCsv ? (
              <CsvTable content={data.content} />
            ) : (
              <pre className="max-h-[60vh] overflow-auto rounded-md bg-muted p-3 text-xs font-mono whitespace-pre-wrap break-words">
                {data.content}
              </pre>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

// ---------------------------------------------------------------------------
// LogDialog — shows logOutput for a job
// ---------------------------------------------------------------------------

interface LogDialogProps {
  open: boolean;
  job: JobResponse | null;
  onClose: () => void;
}

const LogDialog: React.FC<LogDialogProps> = ({ open, job, onClose }) => (
  <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
    <DialogContent className="max-w-3xl w-full max-h-[80vh] overflow-auto">
      <DialogHeader>
        <DialogTitle className="text-sm">
          Log — {job ? formatScriptName(job.scriptName) : ""}
        </DialogTitle>
      </DialogHeader>
      <pre className="max-h-[65vh] overflow-auto rounded-md bg-muted p-3 text-xs font-mono whitespace-pre-wrap break-words">
        {job?.logOutput ?? "(No log output captured for this job.)"}
      </pre>
    </DialogContent>
  </Dialog>
);

// ---------------------------------------------------------------------------
// FileBrowser page
// ---------------------------------------------------------------------------

const FileBrowser: React.FC = () => {
  const [selectedModule, setSelectedModule] = useState<string | null>(null);
  const [filePreviewPath, setFilePreviewPath] = useState<string | null>(null);
  const [fileDialogOpen, setFileDialogOpen] = useState(false);
  const [logDialogJob, setLogDialogJob] = useState<JobResponse | null>(null);
  const [logDialogOpen, setLogDialogOpen] = useState(false);

  const { data: allJobs, isLoading, isError, refetch } = useQuery<JobResponse[]>({
    queryKey: ["jobs-output-browser"],
    queryFn: () => listJobs(200),
    staleTime: 15_000,
  });

  // Only jobs that have finished (either way) are shown.
  const finishedJobs = useMemo(
    () => (allJobs ?? []).filter((j) => j.status === "success" || j.status === "failed"),
    [allJobs],
  );

  // Group by module key, each group sorted newest first.
  const moduleMap = useMemo(() => {
    const map = new Map<string, JobResponse[]>();
    for (const job of finishedJobs) {
      const key = getModuleKey(job.scriptName);
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(job);
    }
    for (const jobs of map.values()) {
      jobs.sort((a, b) =>
        (b.completedAt ?? b.createdAt).localeCompare(a.completedAt ?? a.createdAt),
      );
    }
    return map;
  }, [finishedJobs]);

  const moduleKeys = Array.from(moduleMap.keys());
  const effectiveModule = selectedModule ?? moduleKeys[0] ?? null;
  const moduleJobs = effectiveModule ? (moduleMap.get(effectiveModule) ?? []) : [];

  const handlePreviewFile = (path: string) => {
    setFilePreviewPath(path);
    setFileDialogOpen(true);
  };

  const handleViewLog = (job: JobResponse) => {
    setLogDialogJob(job);
    setLogDialogOpen(true);
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Output Files</h2>
          <p className="text-muted-foreground mt-1">
            Logs and output files from completed automation jobs, grouped by module.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refetch()}>
          Refresh
        </Button>
      </div>

      {/* Body */}
      {isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : isError ? (
        <p className="text-sm text-destructive">Failed to load jobs. Is the API running?</p>
      ) : moduleMap.size === 0 ? (
        <p className="text-sm text-muted-foreground">No completed jobs found yet.</p>
      ) : (
        <div className="flex gap-4">
          {/* Module sidebar */}
          <nav className="w-44 flex-shrink-0 space-y-1">
            {moduleKeys.map((key) => (
              <button
                key={key}
                onClick={() => setSelectedModule(key)}
                className={cn(
                  "flex w-full items-center justify-between rounded-md px-3 py-2 text-sm transition-colors",
                  effectiveModule === key
                    ? "bg-primary/10 font-medium text-primary"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
              >
                <span>{getModuleLabel(key)}</span>
                <span className="text-xs opacity-60">{moduleMap.get(key)!.length}</span>
              </button>
            ))}
          </nav>

          {/* Job list */}
          <div className="min-w-0 flex-1 space-y-3">
            {moduleJobs.map((job) => {
              const outputFiles = extractOutputFiles(job.configSnapshot);
              return (
                <Card key={job.id}>
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <CardTitle className="text-sm">{formatScriptName(job.scriptName)}</CardTitle>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          {job.completedAt
                            ? new Date(job.completedAt).toLocaleString()
                            : "In progress"}
                        </p>
                      </div>
                      <div className="flex flex-shrink-0 items-center gap-2">
                        <Badge
                          variant={job.status === "success" ? "default" : "destructive"}
                          className="text-xs"
                        >
                          {job.status}
                        </Badge>
                        {job.logOutput && (
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-7 text-xs"
                            onClick={() => handleViewLog(job)}
                          >
                            View Log
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardHeader>

                  {outputFiles.length > 0 && (
                    <CardContent className="pt-0">
                      <p className="mb-1 text-xs font-medium text-muted-foreground">Output files</p>
                      <div className="space-y-1">
                        {outputFiles.map((filePath) => (
                          <div
                            key={filePath}
                            className="flex items-center gap-2 rounded-sm px-1 text-xs"
                          >
                            <span className="text-muted-foreground">📄</span>
                            <span className="flex-1 truncate font-mono" title={filePath}>
                              {basename(filePath)}
                            </span>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 px-2 text-xs"
                              onClick={() => handlePreviewFile(filePath)}
                            >
                              Preview
                            </Button>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  )}
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* Dialogs */}
      <FilePreviewDialog
        open={fileDialogOpen}
        path={filePreviewPath}
        onClose={() => setFileDialogOpen(false)}
      />
      <LogDialog
        open={logDialogOpen}
        job={logDialogJob}
        onClose={() => setLogDialogOpen(false)}
      />
    </div>
  );
};

export default FileBrowser;
