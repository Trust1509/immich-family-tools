import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./client";

afterEach(() => vi.unstubAllGlobals());

describe("auth client", () => {
  it("sends the shared token only to the login endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ authenticated: true }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await api.auth.login("top-secret");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/login",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({ token: "top-secret" }),
      })
    );
  });

  it("carries the HTTP status code on a failed request (A3: callers need it to branch)", async () => {
    // Without this, a caller (AuthGate) can only ever show the raw
    // `detail` text and has no way to tell a 401 from a 429 to show a
    // translated, status-specific message instead. Checked via a plain
    // catch (rather than `.rejects.toMatchObject`) because `Error.message`
    // is a non-enumerable property that object-matcher assertions don't
    // reliably see.
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Invalid token" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const err = await api.auth.login("wrong").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(401);
    expect((err as ApiError).message).toBe("Invalid token");
  });
});
