import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FloatingAICopilot } from "../components/ai/FloatingAICopilot";

describe("FloatingAICopilot", () => {
  it("renders floating trigger with context tag", () => {
    render(<FloatingAICopilot viewMode="research" />);
    const trigger = screen.getByRole("button", { name: /Open UrbanFlow AI Research Copilot/i });
    expect(trigger).toBeDefined();
    expect(screen.getByText("Research")).toBeDefined();
  });

  it("opens popup with research context and suggested questions", () => {
    render(<FloatingAICopilot viewMode="research" />);
    const trigger = screen.getByRole("button", { name: /Open UrbanFlow AI Research Copilot/i });
    fireEvent.click(trigger);

    expect(screen.getByRole("dialog", { name: /UrbanFlow AI Copilot/i })).toBeDefined();
    expect(screen.getByText("Research Lab")).toBeDefined();
    expect(
      screen.getByText("Which traffic-control strategy performed better?")
    ).toBeDefined();
  });

  it("adapts suggested questions dynamically for scenario planning", () => {
    render(<FloatingAICopilot viewMode="planner" />);
    const trigger = screen.getByRole("button", { name: /Open UrbanFlow AI Research Copilot/i });
    fireEvent.click(trigger);

    expect(screen.getByText("Scenario Planning")).toBeDefined();
    expect(
      screen.getByText("Which scenario experienced the longest queues?")
    ).toBeDefined();
  });

  it("can be closed with close button", () => {
    render(<FloatingAICopilot viewMode="comparative" />);
    const trigger = screen.getByRole("button", { name: /Open UrbanFlow AI Research Copilot/i });
    fireEvent.click(trigger);

    const closeBtn = screen.getByRole("button", { name: /Close AI Assistant/i });
    fireEvent.click(closeBtn);

    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
