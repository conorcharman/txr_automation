import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { FolderOpen, File, ChevronUp, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { browseDirectory } from "@/api/filesystem";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface PathPickerInputProps {
  /** Current value shown in the text input. */
  value: string;
  /** Called when the user confirms a selection or edits the text. */
  onChange: (value: string) => void;
  /** If `"directory"`, only directories can be selected. */
  mode?: "file" | "directory";
  /** Text input placeholder. */
  placeholder?: string;
  /** Disable the input and browse button. */
  disabled?: boolean;
  /** Extra classes applied to the outer wrapper. */
  className?: string;
  /** Starting directory when the dialog opens (default `/app/data`). */
  rootPath?: string;
}

// ---------------------------------------------------------------------------
// Shared styles (matches the inputCls pattern used across forms)
// ---------------------------------------------------------------------------

const inputCls =
  "h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm " +
  "focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50 " +
  "placeholder:text-muted-foreground";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const PathPickerInput: React.FC<PathPickerInputProps> = ({
  value,
  onChange,
  mode = "file",
  placeholder,
  disabled = false,
  className,
  rootPath = "/app/data",
}) => {
  const [open, setOpen] = React.useState(false);
  const [browsePath, setBrowsePath] = React.useState(rootPath);
  const [selected, setSelected] = React.useState<string | null>(null);

  // Reset dialog state each time it opens.
  React.useEffect(() => {
    if (open) {
      // If the current value looks like a valid path, start browsing from
      // its parent directory so the user sees familiar territory.
      if (value && value.startsWith("/")) {
        const dir = mode === "directory" ? value : value.replace(/\/[^/]*$/, "") || rootPath;
        setBrowsePath(dir);
      } else {
        setBrowsePath(rootPath);
      }
      setSelected(null);
    }
  }, [open, value, mode, rootPath]);

  const { data, isLoading, error } = useQuery({
    queryKey: ["filesystem-browse", browsePath],
    queryFn: () => browseDirectory(browsePath),
    enabled: open,
    retry: false,
    staleTime: 30_000,
  });

  const handleEntryClick = (entryPath: string, isDir: boolean) => {
    if (isDir) {
      // Navigate into the directory.
      setBrowsePath(entryPath);
      // In directory mode, selecting a directory is also valid.
      if (mode === "directory") {
        setSelected(entryPath);
      } else {
        setSelected(null);
      }
    } else if (mode === "file") {
      setSelected(entryPath);
    }
  };

  const handleConfirm = () => {
    const pick = mode === "directory" ? (selected ?? browsePath) : selected;
    if (pick) {
      onChange(pick);
    }
    setOpen(false);
  };

  return (
    <div className={cn("flex gap-1.5", className)}>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className={inputCls}
      />
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="h-9 shrink-0 px-2"
        disabled={disabled}
        onClick={() => setOpen(true)}
        title="Browse server filesystem"
      >
        <FolderOpen className="h-4 w-4" />
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {mode === "directory" ? "Select Directory" : "Select File"}
            </DialogTitle>
            <DialogDescription className="text-xs font-mono truncate">
              {data?.current ?? browsePath}
            </DialogDescription>
          </DialogHeader>

          {/* Navigation bar */}
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={!data?.parent}
              onClick={() => data?.parent && setBrowsePath(data.parent)}
            >
              <ChevronUp className="h-4 w-4 mr-1" /> Up
            </Button>
            {mode === "directory" && (
              <span className="ml-auto text-xs text-muted-foreground">
                Select current or double-click to open
              </span>
            )}
          </div>

          {/* File listing */}
          <ScrollArea className="h-64 rounded-md border">
            {isLoading && (
              <div className="flex items-center justify-center h-full">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            )}
            {error && (
              <div className="p-4 text-sm text-destructive">
                {error instanceof Error ? error.message : "Failed to browse."}
              </div>
            )}
            {data && data.entries.length === 0 && (
              <div className="p-4 text-sm text-muted-foreground">
                Directory is empty.
              </div>
            )}
            {data?.entries.map((entry) => (
              <button
                key={entry.path}
                type="button"
                className={cn(
                  "flex w-full items-center gap-2 px-3 py-1.5 text-sm text-left",
                  "hover:bg-accent transition-colors",
                  selected === entry.path && "bg-primary/10 text-primary font-medium",
                  entry.isDir && mode === "file" && "text-muted-foreground",
                )}
                onClick={() => handleEntryClick(entry.path, entry.isDir)}
                onDoubleClick={() => {
                  if (entry.isDir) {
                    setBrowsePath(entry.path);
                  }
                }}
              >
                {entry.isDir ? (
                  <FolderOpen className="h-4 w-4 shrink-0 text-amber-500" />
                ) : (
                  <File className="h-4 w-4 shrink-0 text-muted-foreground" />
                )}
                <span className="truncate">{entry.name}</span>
              </button>
            ))}
          </ScrollArea>

          <DialogFooter>
            <Button type="button" variant="outline" size="sm" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={handleConfirm}
              disabled={mode === "file" && !selected}
            >
              Select
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export { PathPickerInput };
export type { PathPickerInputProps };
