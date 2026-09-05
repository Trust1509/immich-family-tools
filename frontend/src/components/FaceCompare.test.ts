import { describe, expect, it } from "vitest";
import type { useT } from "../i18n";
import { reasonLabel } from "./FaceCompare";

// `reasonLabel` takes `t` as a parameter rather than calling `useT()`
// itself (same pattern as `authErrorMessage` in AuthGate.tsx), so it can be
// tested with a trivial identity stub instead of rendering a
// LanguageProvider — an identity `t` returns the translation key unchanged,
// which is enough to prove *which* key each `reason` maps to.
const identityT = ((key: string) => key) as ReturnType<typeof useT>["t"];

describe("reasonLabel", () => {
  it("maps every known backend reason to its own, distinct translation key", () => {
    // Regression guard for "ein Grund auf das falsche Label": each case
    // must resolve to its *own* key, not a neighbour's. Asserting the
    // literal key (via the identity stub) — not just "is a string" — is
    // what catches a case wired to the wrong key.
    expect(reasonLabel(identityT, "name_similarity")).toBe("reason_name_similarity");
    expect(reasonLabel(identityT, "embedding_similarity")).toBe("reason_embedding_similarity");
    expect(reasonLabel(identityT, "manual")).toBe("reason_manual");
  });

  it("falls back to the raw reason string for an unknown reason, not an empty string", () => {
    // Regression guard for the default case being mutated from
    // `return reason;` to `return "";` — a plausible-looking mutant that
    // nothing previously exercised.
    expect(reasonLabel(identityT, "some_future_reason_code")).toBe("some_future_reason_code");
  });
});
