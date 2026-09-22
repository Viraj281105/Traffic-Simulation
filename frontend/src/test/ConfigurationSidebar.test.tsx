/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ConfigurationSidebar } from "../components/ConfigurationSidebar";
import type { SimulationConfigValues } from "../types/config";
import { DEFAULT_CONFIG_VALUES } from "../types/config";

describe("ConfigurationSidebar", () => {
  const mockConfig: SimulationConfigValues = { ...DEFAULT_CONFIG_VALUES };

  it("does not render when isOpen is false", () => {
    const { container } = render(
      <ConfigurationSidebar
        isOpen={false}
        onClose={vi.fn()}
        config={mockConfig}
        onApply={vi.fn()}
        mode="comparative"
      />,
    );
    expect(container.querySelector(".config-sidebar-panel")).toBeNull();
  });

  it("shows every section in the comparative view as a labelled dialog", () => {
    render(
      <ConfigurationSidebar
        isOpen={true}
        onClose={vi.fn()}
        config={mockConfig}
        onApply={vi.fn()}
        mode="comparative"
      />,
    );

    expect(
      screen.getByRole("dialog", { name: /Scenario settings/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Traffic & demand/i)).toBeInTheDocument();
    expect(screen.getByText(/^Geometry$/)).toBeInTheDocument();
    expect(screen.getByText(/Fixed-time signal timing/i)).toBeInTheDocument();
    expect(screen.getByText(/Roundabout gap acceptance/i)).toBeInTheDocument();
    // Every slider is reachable by its visible label.
    expect(
      screen.getByLabelText(/Arrival rate \(whole junction\)/i),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/Lane width/i)).toBeInTheDocument();
  });

  it("shows only the settings that apply to a single-control view", () => {
    const { unmount } = render(
      <ConfigurationSidebar
        isOpen={true}
        onClose={vi.fn()}
        config={mockConfig}
        onApply={vi.fn()}
        mode="roundabout"
      />,
    );
    expect(screen.queryByText(/Fixed-time signal timing/i)).toBeNull();
    expect(screen.getByText(/Roundabout gap acceptance/i)).toBeInTheDocument();
    unmount();

    render(
      <ConfigurationSidebar
        isOpen={true}
        onClose={vi.fn()}
        config={mockConfig}
        onApply={vi.fn()}
        mode="signal"
      />,
    );
    expect(screen.getByText(/Fixed-time signal timing/i)).toBeInTheDocument();
    expect(screen.queryByText(/Roundabout gap acceptance/i)).toBeNull();
  });

  it("blocks applying an invalid gap-acceptance pair", () => {
    render(
      <ConfigurationSidebar
        isOpen={true}
        onClose={vi.fn()}
        config={{
          ...mockConfig,
          criticalGap: 2.0,
          followUpTime: 3.5, // criticalGap < followUpTime -> error!
        }}
        onApply={vi.fn()}
        mode="roundabout"
      />,
    );

    expect(
      screen.getByText(
        /Critical gap must be longer than the follow-up headway/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Fix the errors above/i }),
    ).toBeDisabled();
  });

  it("applies a changed configuration and resets the run with it", () => {
    const onApply = vi.fn();
    render(
      <ConfigurationSidebar
        isOpen={true}
        onClose={vi.fn()}
        config={mockConfig}
        onApply={onApply}
        mode="signal"
      />,
    );

    expect(screen.getByRole("button", { name: /No changes/i })).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/Lanes per approach/i), {
      target: { value: "3" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Apply & reset run/i }));

    expect(onApply).toHaveBeenCalledTimes(1);
    expect(onApply).toHaveBeenCalledWith(
      expect.objectContaining({
        lanes: 3,
        arrivalRate: mockConfig.arrivalRate,
      }),
    );
  });

  it("offers separate north-south and east-west greens", () => {
    const onApply = vi.fn();
    render(
      <ConfigurationSidebar
        isOpen={true}
        onClose={vi.fn()}
        config={mockConfig}
        onApply={onApply}
        mode="signal"
      />,
    );

    fireEvent.click(
      screen.getByLabelText(/Separate north–south and east–west greens/i),
    );
    fireEvent.change(screen.getByLabelText(/North–south green/i), {
      target: { value: "40" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Apply & reset run/i }));

    expect(onApply).toHaveBeenCalledWith(
      expect.objectContaining({
        nsGreenDuration: 40,
        ewGreenDuration: mockConfig.greenDuration,
      }),
    );
  });

  it("resets the form to the dashboard defaults", () => {
    const customConfig: SimulationConfigValues = {
      ...mockConfig,
      lanes: 4,
      arrivalRate: 0.9,
    };

    render(
      <ConfigurationSidebar
        isOpen={true}
        onClose={vi.fn()}
        config={customConfig}
        onApply={vi.fn()}
        mode="comparative"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Reset to defaults/i }));

    expect(screen.getByLabelText(/Lanes per approach/i)).toHaveValue(
      String(DEFAULT_CONFIG_VALUES.lanes),
    );
  });

  it("closes on Escape", () => {
    const onClose = vi.fn();
    render(
      <ConfigurationSidebar
        isOpen={true}
        onClose={onClose}
        config={mockConfig}
        onApply={vi.fn()}
        mode="comparative"
      />,
    );
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
