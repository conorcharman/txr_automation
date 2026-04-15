import React, { useId } from "react";
import { Info } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface FieldProps {
  label: string;
  error?: string;
  hint?: string;
  children: React.ReactNode;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const Field: React.FC<FieldProps> = ({ label, error, hint, children }) => {
  const fieldId = useId();

  // Inject `id` onto the first React element child so the label `htmlFor`
  // correctly associates with the underlying form control.
  const childArray = React.Children.toArray(children);
  const enhancedChildren = childArray.map((child, i) =>
    i === 0 && React.isValidElement(child)
      ? React.cloneElement(child as React.ReactElement<{ id?: string }>, {
          id: (child.props as { id?: string }).id ?? fieldId,
        })
      : child,
  );

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1">
        <label htmlFor={fieldId} className="text-xs font-medium text-muted-foreground">
          {label}
        </label>
        {hint && (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="rounded-sm text-muted-foreground/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                aria-label={`More information about ${label}`}
              >
                <Info className="h-3 w-3" aria-hidden="true" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="top">{hint}</TooltipContent>
          </Tooltip>
        )}
      </div>
      {enhancedChildren}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
};

export default Field;
