import React, { useState } from "react";
import { Info, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ColumnSpec {
  name: string;
  required: boolean;
  description: string;
  example?: string;
}

interface CsvFormatHintProps {
  columns: ColumnSpec[];
  /** Optional prose note rendered below the column table. */
  notes?: string;
  /** Defaults to "Expected CSV column format". */
  title?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const CsvFormatHint: React.FC<CsvFormatHintProps> = ({
  columns,
  notes,
  title = "Expected CSV column format",
}) => {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-md border border-blue-200 bg-blue-50 text-sm dark:border-blue-800 dark:bg-blue-900/20">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="flex w-full items-center gap-2 px-3 py-2 text-xs font-medium text-blue-700 dark:text-blue-300"
        aria-expanded={open}
      >
        <Info className="h-3.5 w-3.5 shrink-0" />
        <span>{title}</span>
        <ChevronDown
          className={cn(
            "ml-auto h-3.5 w-3.5 transition-transform duration-150",
            open && "rotate-180",
          )}
        />
      </button>

      {open && (
        <div className="border-t border-blue-200 px-3 pb-3 pt-2 dark:border-blue-800">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left">
                <th className="pb-1.5 pr-4 font-semibold text-blue-800 dark:text-blue-200">
                  Column
                </th>
                <th className="pb-1.5 pr-4 font-semibold text-blue-800 dark:text-blue-200">
                  Required
                </th>
                <th className="pb-1.5 font-semibold text-blue-800 dark:text-blue-200">
                  Description
                </th>
              </tr>
            </thead>
            <tbody>
              {columns.map((col) => (
                <tr
                  key={col.name}
                  className="border-t border-blue-100 dark:border-blue-900/50"
                >
                  <td className="py-1 pr-4 font-mono text-blue-900 dark:text-blue-100">
                    {col.name}
                  </td>
                  <td className="py-1 pr-4 text-blue-700 dark:text-blue-300">
                    {col.required ? "Yes" : "No"}
                  </td>
                  <td className="py-1 text-muted-foreground">
                    {col.description}
                    {col.example && (
                      <span className="ml-1 italic">e.g. {col.example}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {notes && (
            <p className="mt-2 text-xs text-blue-700 dark:text-blue-400">{notes}</p>
          )}
        </div>
      )}
    </div>
  );
};

export default CsvFormatHint;
