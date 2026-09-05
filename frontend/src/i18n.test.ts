import { describe, expect, it } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import { LANG_LABELS, LanguageProvider, readStoredLang, resolveLang, useT } from "./i18n";
import type { Lang } from "./i18n";

describe("resolveLang", () => {
  it("accepts every known language unchanged", () => {
    // Derived from LANG_LABELS (not hardcoded) so a fourth language that's
    // added there but not wired through resolveLang turns this test red
    // instead of leaving it silently green.
    for (const lang of Object.keys(LANG_LABELS) as Lang[]) {
      expect(resolveLang(lang)).toBe(lang);
    }
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

// ── Storage stubs ────────────────────────────────────────────────────────
//
// This repo has no jsdom, so we can't rely on a browser-shaped global. We
// stand a minimal `Storage`-like object in for `globalThis.localStorage` for
// the duration of one call and restore whatever was there before (nothing,
// in plain Node) — see `withStorage` below.

function fakeStorage(value: string | null): Storage {
  return {
    getItem: () => value,
    setItem: () => {},
    removeItem: () => {},
    clear: () => {},
    key: () => null,
    length: 0,
  };
}

function throwingStorage(): Storage {
  const boom = () => {
    throw new Error("storage access blocked");
  };
  return {
    getItem: boom,
    setItem: boom,
    removeItem: () => {},
    clear: () => {},
    key: () => null,
    length: 0,
  };
}

function withStorage<T>(stub: Storage, run: () => T): T {
  const original = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  Object.defineProperty(globalThis, "localStorage", {
    value: stub,
    configurable: true,
    writable: true,
  });
  try {
    return run();
  } finally {
    if (original) {
      Object.defineProperty(globalThis, "localStorage", original);
    } else {
      delete (globalThis as { localStorage?: Storage }).localStorage;
    }
  }
}

// Distinct from `throwingStorage` above: that stub throws when `.getItem()`
// is *called*. This one throws on the `localStorage` *property access*
// itself (a getter on `globalThis`), before any method is ever reached —
// the case the `readStoredLang` JSDoc claims its try/catch also covers.
// Same restore mechanism as `withStorage` (finally + descriptor reset).
function withThrowingLocalStorageAccess<T>(run: () => T): T {
  const original = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  Object.defineProperty(globalThis, "localStorage", {
    get(): Storage {
      throw new Error("localStorage property access blocked");
    },
    configurable: true,
  });
  try {
    return run();
  } finally {
    if (original) {
      Object.defineProperty(globalThis, "localStorage", original);
    } else {
      delete (globalThis as { localStorage?: Storage }).localStorage;
    }
  }
}

describe("readStoredLang", () => {
  it("resolves a valid stored value via resolveLang", () => {
    withStorage(fakeStorage("pt-BR"), () => {
      expect(readStoredLang()).toBe("pt-BR");
    });
  });

  it("falls back to de for an invalid stored value", () => {
    withStorage(fakeStorage("xx"), () => {
      expect(readStoredLang()).toBe("de");
    });
  });

  it("falls back to de when localStorage access itself throws (locked storage)", () => {
    withStorage(throwingStorage(), () => {
      expect(readStoredLang()).toBe("de");
    });
  });

  it("falls back to de when the localStorage property access itself throws", () => {
    withThrowingLocalStorageAccess(() => {
      expect(readStoredLang()).toBe("de");
    });
  });
});

describe("LanguageProvider wiring", () => {
  // No jsdom/@testing-library here — `react-dom/server`'s `renderToString`
  // runs a real component render (hooks included) without touching the DOM,
  // which is exactly enough to prove the Provider actually calls
  // `readStoredLang()` instead of reading storage on its own.

  function renderedLang(stub: Storage): string {
    let probed = "";
    function Probe() {
      const { lang } = useT();
      probed = lang;
      return null;
    }
    withStorage(stub, () => {
      renderToString(React.createElement(LanguageProvider, null, React.createElement(Probe)));
    });
    return probed;
  }

  it("initialises the actual context value through readStoredLang, not just in isolation", () => {
    // This is the regression guard for the mutant the panel found: the old
    // test proved `resolveLang("xx") === "de"` but never proved the
    // Provider *uses* that validation. Sabotaging the Provider's
    // `useState` line back to a naked `localStorage.getItem(...) as Lang`
    // cast makes this assert "xx" instead of "de" and turns this test red.
    expect(renderedLang(fakeStorage("xx"))).toBe("de");
  });

  it("still renders (does not go blank) when localStorage access throws", () => {
    expect(() => renderedLang(throwingStorage())).not.toThrow();
    expect(renderedLang(throwingStorage())).toBe("de");
  });

  it("does not throw when persisting the language choice fails", () => {
    let captured: ReturnType<typeof useT> | undefined;
    function Capture() {
      captured = useT();
      return null;
    }
    withStorage(fakeStorage("de"), () => {
      renderToString(React.createElement(LanguageProvider, null, React.createElement(Capture)));
    });

    withStorage(throwingStorage(), () => {
      expect(() => captured!.setLang("en")).not.toThrow();
    });
  });
});
