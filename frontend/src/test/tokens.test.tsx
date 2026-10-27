import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const listTokens = vi.fn();
const createToken = vi.fn();
const revokeToken = vi.fn();

vi.mock("../services/v3/tokens", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../services/v3/tokens")>()),
  listTokens: () => listTokens() as Promise<unknown>,
  createToken: (b: unknown) => createToken(b) as Promise<unknown>,
  revokeToken: (id: string) => revokeToken(id) as Promise<unknown>,
}));

import { TokensPage } from "../components/tokens/TokensPage";

const existing = {
  id: "pat_1",
  name: "CI script",
  scopes: ["experiments:read"],
  createdAt: "2026-10-27T00:00:00+00:00",
  expiresAt: "2026-11-26T00:00:00+00:00",
  lastUsedAt: null,
};

describe("TokensPage", () => {
  beforeEach(() => {
    listTokens.mockResolvedValue({ tokens: [existing] });
    createToken.mockResolvedValue({
      ...existing,
      id: "pat_2",
      token: "uf_pat_secretvalue",
    });
    revokeToken.mockResolvedValue(undefined);
  });

  it("creates a token with the chosen scopes, shows the secret once, and revokes", async () => {
    const user = userEvent.setup();
    render(<TokensPage />);
    expect(await screen.findByText("CI script")).toBeInTheDocument();
    await user.click(screen.getByLabelText(/experiments:run/));
    await user.click(screen.getByRole("button", { name: /Create token/ }));
    expect(createToken).toHaveBeenCalledWith({
      name: "My script",
      scopes: ["experiments:read", "experiments:run"],
      expiresInDays: 30,
    });
    expect(await screen.findByLabelText("New token secret")).toHaveValue(
      "uf_pat_secretvalue",
    );
    await user.click(screen.getByRole("button", { name: "Revoke CI script" }));
    await waitFor(() => {
      expect(revokeToken).toHaveBeenCalledWith("pat_1");
    });
  });
});
