import { describe, expect, it } from "vitest";
import { resolveLang } from "./i18n";

describe("resolveLang", () => {
  it("accepts every known language unchanged", () => {
    expect(resolveLang("de")).toBe("de");
    expect(resolveLang("en")).toBe("en");
    expect(resolveLang("pt-BR")).toBe("pt-BR");
  });

  it("falls back to de for a stale pre-rename value", () => {
    // "br" was the (incorrect) code used before the pt-BR rename; anyone who
    // tried the pr65 branch before the fix has this persisted in localStorage.
    expect(resolveLang("br")).toBe("de");
  });

  it("falls back to de for any other unknown value", () => {
    expect(resolveLang("xx")).toBe("de");
  });

  it("falls back to de when nothing is stored", () => {
    expect(resolveLang(null)).toBe("de");
  });
});
