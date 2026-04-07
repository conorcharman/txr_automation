import React, { useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";

interface LogViewerProps {
  lines: string[];
  isRunning: boolean;
  onSave?: () => void;
  maxHeight?: string;
}

function getLineClass(line: string): string {
  if (/error/i.test(line)) return "text-red-400";
  if (/warning/i.test(line)) return "text-yellow-400";
  if (/success/i.test(line)) return "text-green-400";
  return "text-gray-100";
}

const LogViewer: React.FC<LogViewerProps> = ({
  lines,
  isRunning,
  onSave,
  maxHeight = "400px",
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const userScrolledRef = useRef(false);

  const handleScroll = () => {
    const el = containerRef.current;
    if (!el) return;
    const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 10;
    userScrolledRef.current = !atBottom;
  };

  useEffect(() => {
    if (userScrolledRef.current) return;
    const el = containerRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [lines.length]);

  return (
    <div className="rounded-lg overflow-hidden border border-gray-800">
      {/* Header */}
      <div className="flex items-center justify-between bg-gray-900 px-4 py-2 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-200">Logs</span>
          {isRunning && (
            <svg
              className="animate-spin h-4 w-4 text-blue-400"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              aria-label="Running"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
              />
            </svg>
          )}
        </div>
        {onSave && (
          <Button variant="outline" size="sm" onClick={onSave}>
            Save
          </Button>
        )}
      </div>

      {/* Log body */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="bg-gray-950 overflow-y-auto font-mono text-sm px-4 py-3"
        style={{ maxHeight }}
      >
        {lines.length === 0 ? (
          <p className="text-gray-600 italic">Waiting for output...</p>
        ) : (
          lines.map((line, i) => (
            <div
              key={i}
              className={`whitespace-pre-wrap break-all leading-5 ${getLineClass(line)}`}
            >
              {line}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default LogViewer;
