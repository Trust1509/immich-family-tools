import { describe, expect, it } from "vitest";
import React from "react";
import { renderToString } from "react-dom/server";
import {
  applyDocumentLang,
  detectBrowserLang,
  LANG_LABELS,
  LanguageProvider,
  readStoredLang,
  resolveLang,
  useT,
} from "./i18n";
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

describe("detectBrowserLang", () => {
  it("accepts every known language unchanged (exact match)", () => {
    // Same derivation-from-LANG_LABELS reasoning as the resolveLang test
    // above: a fourth shipped language that isn't detectable by its own
    // exact code should turn this red, not stay silently green.
    for (const lang of Object.keys(LANG_LABELS) as Lang[]) {
      expect(detectBrowserLang(lang)).toBe(lang);
    }
  });

  it("matches a bare language subtag to its shipped regional variant", () => {
    // "pt" alone (no region) is what some browsers report; pt-BR is the
    // only Portuguese we ship, so it's the only sane match.
    expect(detectBrowserLang("pt")).toBe("pt-BR");
  });

  it("matches an unshipped regional variant by its language prefix", () => {
    expect(detectBrowserLang("de-DE")).toBe("de");
    expect(detectBrowserLang("en-US")).toBe("en");
  });

  it("falls back to de for a language we don't ship at all", () => {
    expect(detectBrowserLang("xx")).toBe("de");
    expect(detectBrowserLang("fr-FR")).toBe("de");
  });

  it("falls back to de when no language is given", () => {
    expect(detectBrowserLang(null)).toBe("de");
    expect(detectBrowserLang(undefined)).toBe("de");
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

// Stubs `globalThis.navigator` for the duration of one call, the same
// restore-in-finally shape as `withStorage` above. `undefined` simulates an
// environment with no `navigator` at all (readStoredLang guards for that
// with a `typeof navigator === "undefined"` check).
function withNavigatorLanguage<T>(language: string | undefined, run: () => T): T {
  const original = Object.getOwnPropertyDescriptor(globalThis, "navigator");
  Object.defineProperty(globalThis, "navigator", {
    value: language === undefined ? undefined : ({ language } as Navigator),
    configurable: true,
    writable: true,
  });
  try {
    return run();
  } finally {
    if (original) {
      Object.defineProperty(globalThis, "navigator", original);
    } else {
      delete (globalThis as { navigator?: Navigator }).navigator;
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

  it("uses the browser language on first visit (nothing stored)", () => {
    withStorage(fakeStorage(null), () => {
      withNavigatorLanguage("pt-BR", () => {
        expect(readStoredLang()).toBe("pt-BR");
      });
    });
  });

  it("matches the browser language by prefix on first visit", () => {
    withStorage(fakeStorage(null), () => {
      withNavigatorLanguage("en-US", () => {
        expect(readStoredLang()).toBe("en");
      });
    });
  });

  it("still prefers an existing stored value over the browser language", () => {
    // This is the regression guard for the precedence rule in 1e: even a
    // browser language that resolves cleanly must never override a value
    // the user (or a previous session) already chose and saved.
    withStorage(fakeStorage("de"), () => {
      withNavigatorLanguage("pt-BR", () => {
        expect(readStoredLang()).toBe("de");
      });
    });
  });

  it("falls back to de when nothing is stored and the browser language is unknown", () => {
    withStorage(fakeStorage(null), () => {
      withNavigatorLanguage("fr-FR", () => {
        expect(readStoredLang()).toBe("de");
      });
    });
  });

  it("falls back to de when nothing is stored and there is no navigator at all", () => {
    withStorage(fakeStorage(null), () => {
      withNavigatorLanguage(undefined, () => {
        expect(readStoredLang()).toBe("de");
      });
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

  it("initialises from the browser language on first visit (nothing stored)", () => {
    withNavigatorLanguage("pt-BR", () => {
      expect(renderedLang(fakeStorage(null))).toBe("pt-BR");
    });
  });

  it("still prefers a stored value over the browser language", () => {
    withNavigatorLanguage("pt-BR", () => {
      expect(renderedLang(fakeStorage("en"))).toBe("en");
    });
  });
});

// ── applyDocumentLang ────────────────────────────────────────────────────
//
// Same reasoning as the storage stubs above: no jsdom here, so `document` is
// stubbed for the duration of one call rather than driven through a real
// React effect (renderToString, used everywhere else in this file, never
// runs effects at all).

interface FakeDocument {
  documentElement: { lang: string };
}

function fakeDocument(): FakeDocument {
  return { documentElement: { lang: "" } };
}

function withDocument<T>(doc: FakeDocument | undefined, run: () => T): T {
  const original = Object.getOwnPropertyDescriptor(globalThis, "document");
  Object.defineProperty(globalThis, "document", {
    value: doc,
    configurable: true,
    writable: true,
  });
  try {
    return run();
  } finally {
    if (original) {
      Object.defineProperty(globalThis, "document", original);
    } else {
      delete (globalThis as { document?: unknown }).document;
    }
  }
}

describe("applyDocumentLang", () => {
  it("writes the language to document.documentElement.lang", () => {
    const doc = fakeDocument();
    withDocument(doc, () => applyDocumentLang("pt-BR"));
    expect(doc.documentElement.lang).toBe("pt-BR");
  });

  it("does nothing when there is no document (SSR)", () => {
    expect(() => withDocument(undefined, () => applyDocumentLang("en"))).not.toThrow();
  });
});
