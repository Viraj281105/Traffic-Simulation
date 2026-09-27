import { act, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useContainerSize } from "../hooks/useContainerSize";

// jsdom has no layout: give every element a fixed size and a no-op observer.
beforeEach(() => {
  vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockReturnValue(640);
  vi.spyOn(HTMLElement.prototype, "clientHeight", "get").mockReturnValue(480);
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function LateContainer() {
  const [ref, size] = useContainerSize();
  const [shown, setShown] = useState(false);
  return (
    <>
      <button
        onClick={() => {
          setShown(true);
        }}
      >
        show
      </button>
      {shown && <div ref={ref} />}
      <output>{`${String(size.width)}x${String(size.height)}`}</output>
    </>
  );
}

describe("useContainerSize", () => {
  it("measures a container that mounts after the hook's owner", () => {
    render(<LateContainer />);
    expect(screen.getByRole("status")).toHaveTextContent("0x0");

    act(() => {
      screen.getByRole("button").click();
    });

    expect(screen.getByRole("status")).toHaveTextContent("640x480");
  });
});
