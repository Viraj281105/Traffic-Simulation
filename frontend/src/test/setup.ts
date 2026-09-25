import "@testing-library/jest-dom/vitest";
import React from "react";
import { vi } from "vitest";

// jsdom has no 2D canvas implementation, so every component that draws a map
// throws "Not implemented: HTMLCanvasElement.prototype.getContext" on mount.
// That noise buries real failures and makes any test rendering the dashboard
// shell unreadable. Install a no-op context so the drawing code runs to
// completion; tests that need to assert on drawing calls (see
// IntersectionCanvas.test.tsx) override this with their own recording stub.
const noop = (): void => undefined;

HTMLCanvasElement.prototype.getContext = vi.fn(
  () =>
    ({
      fillRect: noop,
      clearRect: noop,
      strokeRect: noop,
      beginPath: noop,
      closePath: noop,
      moveTo: noop,
      lineTo: noop,
      arc: noop,
      quadraticCurveTo: noop,
      createPattern: () => ({ setTransform: noop }),
      ellipse: noop,
      fill: noop,
      stroke: noop,
      save: noop,
      restore: noop,
      translate: noop,
      rotate: noop,
      scale: noop,
      setTransform: noop,
      fillText: noop,
      strokeText: noop,
      setLineDash: noop,
      createLinearGradient: () => ({ addColorStop: noop }),
      createRadialGradient: () => ({ addColorStop: noop }),
      measureText: () => ({ width: 0 }),
      drawImage: noop,
      putImageData: noop,
      getImageData: () => ({ data: new Uint8ClampedArray() }),
    }) as unknown as CanvasRenderingContext2D,
) as unknown as HTMLCanvasElement["getContext"];

vi.mock("recharts", () => {
  return {
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) =>
      React.createElement(
        "div",
        { className: "recharts-responsive-container" },
        children,
      ),
    LineChart: ({ children }: { children: React.ReactNode }) =>
      React.createElement(
        "div",
        { className: "recharts-line-chart" },
        children,
      ),
    Line: () => React.createElement("div", { className: "recharts-line" }),
    XAxis: () => React.createElement("div", { className: "recharts-xaxis" }),
    YAxis: () => React.createElement("div", { className: "recharts-yaxis" }),
    CartesianGrid: () =>
      React.createElement("div", { className: "recharts-grid" }),
    Tooltip: () =>
      React.createElement("div", { className: "recharts-tooltip" }),
    BarChart: ({ children }: { children: React.ReactNode }) =>
      React.createElement("div", { className: "recharts-bar-chart" }, children),
    Bar: () => React.createElement("div", { className: "recharts-bar" }),
    Legend: () => React.createElement("div", { className: "recharts-legend" }),
    ReferenceLine: () =>
      React.createElement("div", { className: "recharts-reference-line" }),
  };
});
