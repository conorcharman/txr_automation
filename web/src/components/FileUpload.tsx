import React, { useRef, useState, useCallback } from "react";
import { Upload } from "lucide-react";
import { cn } from "@/lib/utils";

interface FileUploadProps {
  onFileSelect: (file: File) => void;
  accept?: string;
  label?: string;
  maxSizeMb?: number;
  disabled?: boolean;
  selectedFile?: File | null;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

const FileUpload: React.FC<FileUploadProps> = ({
  onFileSelect,
  accept = ".csv",
  label = "Drop a CSV file here or click to browse",
  maxSizeMb = 100,
  disabled = false,
  selectedFile = null,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validateAndSelect = useCallback(
    (file: File) => {
      setError(null);
      const limitBytes = maxSizeMb * 1024 * 1024;
      if (file.size > limitBytes) {
        setError(
          `File exceeds ${maxSizeMb} MB limit (${(file.size / 1024 / 1024).toFixed(1)} MB)`,
        );
        return;
      }
      onFileSelect(file);
    },
    [maxSizeMb, onFileSelect],
  );

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (!disabled) setDragging(true);
  };

  const handleDragLeave = () => setDragging(false);

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    if (disabled) return;
    const file = e.dataTransfer.files[0];
    if (file) validateAndSelect(file);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) validateAndSelect(file);
    e.target.value = "";
  };

  const handleClick = () => {
    if (!disabled) inputRef.current?.click();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      handleClick();
    }
  };

  return (
    <div>
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          "border-2 border-dashed border-border rounded-lg p-8 text-center transition-colors",
          !disabled && "cursor-pointer hover:border-primary/50",
          dragging && "border-primary bg-primary/5",
          disabled && "opacity-50 cursor-not-allowed",
          selectedFile && !dragging && "border-green-500/50 bg-green-500/5",
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          onChange={handleChange}
          className="hidden"
          disabled={disabled}
          aria-hidden
        />
        <div className="flex flex-col items-center gap-3">
          <Upload size={40} className="text-muted-foreground" />
          {selectedFile ? (
            <div>
              <p className="text-sm font-medium text-foreground">
                {selectedFile.name}
              </p>
              <p className="text-xs text-muted-foreground">
                {formatSize(selectedFile.size)}
              </p>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">{label}</p>
          )}
        </div>
      </div>
      {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
    </div>
  );
};

export default FileUpload;
