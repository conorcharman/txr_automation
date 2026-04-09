import React from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface Step {
  label: string;
  description?: string;
}

interface StepWizardProps {
  steps: Step[];
  currentStep: number;
  onStepClick?: (index: number) => void;
}

const StepWizard: React.FC<StepWizardProps> = ({
  steps,
  currentStep,
  onStepClick,
}) => {
  return (
    <div className="w-full">
      <div className="flex w-full items-start">
        {steps.map((step, index) => {
          const isCompleted = index < currentStep;
          const isCurrent = index === currentStep;
          const isFuture = index > currentStep;
          const isClickable = isCompleted && onStepClick != null;

          return (
            <React.Fragment key={index}>
              {/* Step column */}
              <div className="flex flex-col items-center">
                <button
                  type="button"
                  disabled={!isClickable}
                  onClick={isClickable ? () => onStepClick(index) : undefined}
                  className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-semibold transition-all",
                    isCompleted &&
                      "bg-primary text-primary-foreground",
                    isCurrent &&
                      "bg-primary text-primary-foreground ring-2 ring-primary ring-offset-2",
                    isFuture &&
                      "border-2 border-border bg-background text-muted-foreground",
                    isClickable ? "cursor-pointer" : "cursor-default",
                  )}
                >
                  {isCompleted ? <Check size={14} /> : index + 1}
                </button>
                <div className="mt-2 max-w-[8rem] px-1 text-center">
                  <p
                    className={cn(
                      "text-xs font-medium leading-tight",
                      isFuture && "text-muted-foreground",
                    )}
                  >
                    {step.label}
                  </p>
                  {step.description && (
                    <p className="mt-0.5 text-xs leading-tight text-muted-foreground">
                      {step.description}
                    </p>
                  )}
                </div>
              </div>

              {/* Connector line between steps */}
              {index < steps.length - 1 && (
                <div className="mt-4 flex flex-1 items-center px-1">
                  <div className="h-0.5 w-full overflow-hidden rounded-full bg-border">
                    <div
                      className={cn(
                        "h-full bg-primary transition-all",
                        isCompleted ? "w-full" : "w-0",
                      )}
                    />
                  </div>
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};

export default StepWizard;
