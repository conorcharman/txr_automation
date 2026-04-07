import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import LogViewer from "@/components/LogViewer";

describe("LogViewer", () => {
  it('renders "Waiting for output..." when lines is empty', () => {
    render(<LogViewer lines={[]} isRunning={false} />);
    expect(screen.getByText("Waiting for output...")).toBeInTheDocument();
  });

  it("renders log lines when provided", () => {
    render(<LogViewer lines={["Line one", "Line two"]} isRunning={false} />);
    expect(screen.getByText("Line one")).toBeInTheDocument();
    expect(screen.getByText("Line two")).toBeInTheDocument();
  });

  it("shows ERROR lines with red text class", () => {
    render(<LogViewer lines={["ERROR: something went wrong"]} isRunning={false} />);
    const line = screen.getByText("ERROR: something went wrong");
    expect(line).toHaveClass("text-red-400");
  });

  it("shows SUCCESS lines with green text class", () => {
    render(<LogViewer lines={["SUCCESS: all done"]} isRunning={false} />);
    const line = screen.getByText("SUCCESS: all done");
    expect(line).toHaveClass("text-green-400");
  });

  it("does not show Save button when onSave is not provided", () => {
    render(<LogViewer lines={[]} isRunning={false} />);
    expect(screen.queryByRole("button", { name: /save/i })).not.toBeInTheDocument();
  });

  it("shows Save button when onSave is provided and calls it on click", () => {
    const onSave = vi.fn();
    render(<LogViewer lines={[]} isRunning={false} onSave={onSave} />);
    const btn = screen.getByRole("button", { name: /save/i });
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(onSave).toHaveBeenCalledTimes(1);
  });
});
