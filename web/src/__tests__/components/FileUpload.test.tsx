import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import FileUpload from "@/components/FileUpload";

describe("FileUpload", () => {
  it("renders the upload area with default label text", () => {
    render(<FileUpload onFileSelect={vi.fn()} />);
    expect(
      screen.getByText("Drop a CSV file here or click to browse"),
    ).toBeInTheDocument();
  });

  it("renders the selected filename when selectedFile prop is provided", () => {
    const file = new File(["content"], "report.csv", { type: "text/csv" });
    render(<FileUpload onFileSelect={vi.fn()} selectedFile={file} />);
    expect(screen.getByText("report.csv")).toBeInTheDocument();
  });

  it("calls onFileSelect when a file is chosen via the input", async () => {
    const onFileSelect = vi.fn();
    render(<FileUpload onFileSelect={onFileSelect} />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["content"], "test.csv", { type: "text/csv" });
    await userEvent.upload(input, file);
    expect(onFileSelect).toHaveBeenCalledTimes(1);
    expect(onFileSelect).toHaveBeenCalledWith(file);
  });
});
