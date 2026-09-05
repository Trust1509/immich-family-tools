import { describe, expect, it } from "vitest";
import { ApiError } from "../api/client";
import type { useT } from "../i18n";
import { authErrorMessage } from "./AuthGate";

// Identity stub, same pattern as FaceCompare.test.ts's `reasonLabel` test:
// returns the translation key unchanged, which is enough to prove *which*
// key a given status code maps to without rendering a LanguageProvider.
const identityT = ((key: string) => key) as ReturnType<typeof useT>["t"];

describe("authErrorMessage", () => {
  it("maps a 401 (invalid token) to the translated auth_error_invalid key", () => {
    expect(authErrorMessage(new ApiError("Invalid token", 401), identityT)).toBe(
      "auth_error_invalid"
    );
  });

  it("maps a 429 (rate limited) to the translated auth_error_rate_limited key", () => {
    expect(
      authErrorMessage(
        new ApiError("Too many login attempts. Try again in one minute.", 429),
        identityT
      )
    ).toBe("auth_error_rate_limited");
  });

  it("falls back to the raw detail text for a status the login screen doesn't special-case", () => {
    expect(authErrorMessage(new ApiError("Immich API unreachable", 502), identityT)).toBe(
      "Immich API unreachable"
    );
  });

  it("falls back to the error message for a non-ApiError failure (e.g. a network error)", () => {
    expect(authErrorMessage(new Error("Failed to fetch"), identityT)).toBe("Failed to fetch");
  });
});
