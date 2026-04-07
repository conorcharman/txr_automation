import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import TestingPeriodSelector from "@/components/TestingPeriodSelector";

const defaultValue = { fiscalYear: "FY25", quarter: "Q1" };

describe("TestingPeriodSelector", () => {
  it("renders FY and Quarter selects", () => {
    render(
      <TestingPeriodSelector value={defaultValue} onChange={vi.fn()} />,
    );
    // Two native <select> elements are expected
    const selects = screen.getAllByRole("combobox");
    expect(selects).toHaveLength(2);
    // Label text is visible
    expect(screen.getByText("Fiscal Year")).toBeInTheDocument();
    expect(screen.getByText("Quarter")).toBeInTheDocument();
  });

  it("calls onChange with updated quarter when quarter select changes", () => {
    const onChange = vi.fn();
    render(
      <TestingPeriodSelector value={defaultValue} onChange={onChange} />,
    );
    // Second combobox is the Quarter select
    const [, quarterSelect] = screen.getAllByRole("combobox");
    fireEvent.change(quarterSelect, { target: { value: "Q3" } });
    expect(onChange).toHaveBeenCalledWith({ fiscalYear: "FY25", quarter: "Q3" });
  });

  it("disables both selects when disabled prop is true", () => {
    render(
      <TestingPeriodSelector value={defaultValue} onChange={vi.fn()} disabled />,
    );
    const [fySelect, quarterSelect] = screen.getAllByRole("combobox");
    expect(fySelect).toBeDisabled();
    expect(quarterSelect).toBeDisabled();
  });
});
