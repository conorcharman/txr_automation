import React from "react";
import { cn } from "@/lib/utils";

interface TestingPeriodValue {
  fiscalYear: string;
  quarter: string;
}

interface TestingPeriodSelectorProps {
  value: TestingPeriodValue;
  onChange: (value: TestingPeriodValue) => void;
  disabled?: boolean;
}

const QUARTERS = ["Q1", "Q2", "Q3", "Q4"];

function getFiscalYears(): string[] {
  const currentYear = new Date().getFullYear();
  return [
    currentYear - 2,
    currentYear - 1,
    currentYear,
    currentYear + 1,
  ].map((y) => `FY${String(y).slice(-2)}`);
}

const TestingPeriodSelector: React.FC<TestingPeriodSelectorProps> = ({
  value,
  onChange,
  disabled = false,
}) => {
  const fiscalYears = getFiscalYears();

  const selectClass = cn(
    "h-9 rounded-md border border-input bg-background px-3 text-sm",
    "focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50",
  );

  return (
    <div className="flex items-end gap-3">
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">Fiscal Year</label>
        <select
          value={value.fiscalYear}
          onChange={(e) => onChange({ ...value, fiscalYear: e.target.value })}
          disabled={disabled}
          className={selectClass}
        >
          {fiscalYears.map((fy) => (
            <option key={fy} value={fy}>
              {fy}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground">Quarter</label>
        <select
          value={value.quarter}
          onChange={(e) => onChange({ ...value, quarter: e.target.value })}
          disabled={disabled}
          className={selectClass}
        >
          {QUARTERS.map((q) => (
            <option key={q} value={q}>
              {q}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
};

export default TestingPeriodSelector;
