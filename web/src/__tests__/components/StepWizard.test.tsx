import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import StepWizard from "@/components/StepWizard";

const steps = [
  { label: "Upload" },
  { label: "Validate" },
  { label: "Review" },
  { label: "Export" },
];

describe("StepWizard", () => {
  it("renders all step labels", () => {
    render(<StepWizard steps={steps} currentStep={0} />);
    expect(screen.getByText("Upload")).toBeInTheDocument();
    expect(screen.getByText("Validate")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
    expect(screen.getByText("Export")).toBeInTheDocument();
  });

  it("completed steps (index < currentStep) render a button with the Check icon (no step number)", () => {
    render(<StepWizard steps={steps} currentStep={2} />);
    // Steps 0 and 1 are completed — they should NOT show their step number (1, 2)
    // but the current step (2 → label "Review") button shows "3"
    // and future step (3 → label "Export") button shows "4"
    const buttons = screen.getAllByRole("button");
    // First two buttons are completed — their text content should NOT be "1" or "2"
    expect(buttons[0].textContent).not.toBe("1");
    expect(buttons[1].textContent).not.toBe("2");
  });

  it("current step button has ring class", () => {
    render(<StepWizard steps={steps} currentStep={1} />);
    const buttons = screen.getAllByRole("button");
    // Button at index 1 is the current step
    expect(buttons[1].className).toContain("ring");
  });

  it("clicking a completed step calls onStepClick with correct index", () => {
    const onStepClick = vi.fn();
    render(<StepWizard steps={steps} currentStep={2} onStepClick={onStepClick} />);
    const buttons = screen.getAllByRole("button");
    // Steps 0 and 1 are completed and clickable
    fireEvent.click(buttons[0]);
    expect(onStepClick).toHaveBeenCalledWith(0);
    fireEvent.click(buttons[1]);
    expect(onStepClick).toHaveBeenCalledWith(1);
  });

  it("clicking a future step does NOT call onStepClick", () => {
    const onStepClick = vi.fn();
    render(<StepWizard steps={steps} currentStep={1} onStepClick={onStepClick} />);
    const buttons = screen.getAllByRole("button");
    // Steps 2 and 3 are future — buttons are disabled
    fireEvent.click(buttons[2]);
    fireEvent.click(buttons[3]);
    expect(onStepClick).not.toHaveBeenCalled();
  });
});
