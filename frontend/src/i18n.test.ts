import { describe, expect, it } from "vitest";
import readmeText from "../../README.md?raw";
import React from "react";
import { renderToString } from "react-dom/server";
import {
  applyDocumentLang,
  detectBrowserLang,
  formatDate,
  LANG_LABELS,
  LANG_LOCALES,
  LanguageProvider,
  readStoredLang,
  resolveLang,
  ERROR_PARAM_ORDER,
  translations,
  type ServerErrorLike,
  useT,
} from "./i18n";
import type { Lang } from "./i18n";

describe("resolveLang", () => {
  it("accepts every known language unchanged", () => {
    // Derived from LANG_LABELS (not hardcoded) so a fifth language that's
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

describe("LANG_LOCALES", () => {
  it("has exactly the same key set as LANG_LABELS", () => {
    // Same derivation reasoning as the resolveLang/detectBrowserLang tests
    // below: a fifth language added to LANG_LABELS but forgotten here
    // should turn this red, not stay silently green.
    expect(Object.keys(LANG_LOCALES).sort()).toEqual(Object.keys(LANG_LABELS).sort());
  });

  it("pins the exact, documented locale for each language", () => {
    // Exact values, not just "looks like a BCP-47 tag" — `LANG_LOCALES.de`
    // mutated to an invented tag like "zz-ZZ", or `.en` swapped from the
    // deliberately-chosen "en-GB" to "en-US", both still look like valid
    // locale strings. Only pinning the literal, documented value catches
    // either kind of mutation (previously: null coverage — the whole map
    // could be swapped for nonsense without a single test going red).
    expect(LANG_LOCALES).toEqual({
      de: "de-AT",
      en: "en-GB",
      "es-ES": "es-ES",
      "pt-BR": "pt-BR",
    });
  });
});

// ── formatDate ──────────────────────────────────────────────────────────
//
// `toLocaleString`'s hour/minute rendering reads the process time zone,
// which is whatever machine (or CI runner) happens to run the suite. This
// stub pins it to UTC for the duration of one call — same restore-in-finally
// shape as the storage/document stubs below — so the fixture timestamp
// `2026-03-04T14:30:00Z` reliably shows up as `14:30`, not a runner-dependent
// hour that would make the exact-string assertions below flaky.
// Accessed via `globalThis` (typed just enough for `.env.TZ`), not the bare
// `process` global: this project's tsconfig has `types: []` on purpose (a
// browser app has no Node globals), so a plain `process.env.TZ` reference
// would need `@types/node` — out of scope for a test-only helper.
function withTZ<T>(tz: string, run: () => T): T {
  const nodeProcess = (
    globalThis as unknown as { process: { env: Record<string, string | undefined> } }
  ).process;
  const original = nodeProcess.env.TZ;
  nodeProcess.env.TZ = tz;
  try {
    return run();
  } finally {
    if (original === undefined) {
      delete nodeProcess.env.TZ;
    } else {
      nodeProcess.env.TZ = original;
    }
  }
}

describe("formatDate", () => {
  // Invented fixture (Issue #71 Bau-Brief §7) — this repo is public, no real
  // sync timestamps in code or tests.
  const FIXTURE = "2026-03-04T14:30:00Z";

  it("returns the placeholder for an undefined timestamp", () => {
    expect(formatDate(undefined, LANG_LOCALES.de)).toBe("–");
  });

  it("returns the same placeholder for an unparseable timestamp instead of 'Invalid Date' (Fund 1c)", () => {
    // Real case, not theoretical: timestamps come from accounts.json (see
    // docs/agents/lehren.md's hand-recovered-storage incident), and an
    // unreadable-but-present value must not leak the English
    // `Invalid Date` string into a German, Spanish, or pt-BR UI.
    expect(formatDate("nicht-ein-datum", LANG_LOCALES.de)).toBe("–");
  });

  it("renders the exact, documented format for each shipped language", () => {
    // Pinned to the literal strings from Issue #71's Befund — a real `Intl`
    // run against the day:"numeric"/month:"short" options, not "looks about
    // right". This is the string a user actually sees.
    withTZ("UTC", () => {
      expect(formatDate(FIXTURE, LANG_LOCALES.de)).toBe("4. März 2026, 14:30");
      expect(formatDate(FIXTURE, LANG_LOCALES.en)).toBe("4 Mar 2026, 14:30");
      expect(formatDate(FIXTURE, LANG_LOCALES["es-ES"])).toBe("4 mar 2026, 14:30");
      expect(formatDate(FIXTURE, LANG_LOCALES["pt-BR"])).toBe("4 de mar. de 2026, 14:30");
    });
  });

  it("shows a month name, never a month number, in every shipped language", () => {
    // This is the guard the whole slice exists for: a numeric month must
    // never come back for any of the four locales, or the entire point of
    // the change could be silently reverted without a single test noticing.
    withTZ("UTC", () => {
      expect(formatDate(FIXTURE, LANG_LOCALES.de)).toContain("März");
      expect(formatDate(FIXTURE, LANG_LOCALES.en)).toContain("Mar");
      expect(formatDate(FIXTURE, LANG_LOCALES["es-ES"])).toContain("mar");
      expect(formatDate(FIXTURE, LANG_LOCALES["pt-BR"])).toContain("mar.");
      for (const locale of Object.values(LANG_LOCALES)) {
        // The old options rendered March as the two-digit token "03"; none
        // of the four outputs above contain it any more.
        expect(formatDate(FIXTURE, locale)).not.toContain("03");
      }
    });
  });
});

describe("detectBrowserLang", () => {
  it("accepts every known language unchanged (exact match)", () => {
    // Same derivation-from-LANG_LABELS reasoning as the resolveLang test
    // above: a fifth shipped language that isn't detectable by its own
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
    expect(detectBrowserLang("es-MX")).toBe("es-ES");
    // Zusatz beim v1.6.0-Notizenschreiben: Die Notiz verspricht "jede
    // spanische Variante". Geprueft statt behauptet — "es" ohne Region und
    // "es-AR" waren nicht abgedeckt.
    expect(detectBrowserLang("es")).toBe("es-ES");
    expect(detectBrowserLang("es-AR")).toBe("es-ES");
  });

  it("matches a browser locale with mixed-case subtags", () => {
    // Regression guard for the `.toLowerCase()` call in the prefix match:
    // it could be deleted without any test going red. "PT-br" (some
    // browsers report the region in lowercase, the language in upper) only
    // matches "pt-BR" if both sides are folded to the same case first.
    expect(detectBrowserLang("PT-br")).toBe("pt-BR");
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

  it("treats a stored empty string as an (invalid) stored value, not as 'nothing stored'", () => {
    // Regression guard for `if (stored !== null)`: swapping it for the
    // more casual-looking `if (stored)` behaves identically for every
    // *realistic* stored value, and only diverges for an empty string —
    // which is falsy, so `if (stored)` would fall through to the browser
    // language below instead of validating "" via resolveLang() and
    // landing on "de". Previously uncovered.
    withStorage(fakeStorage(""), () => {
      withNavigatorLanguage("pt-BR", () => {
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

// ── setLang <-> <html lang> wiring ───────────────────────────────────────
//
// A2: the Provider used to keep `<html lang>` in sync via a `useEffect`
// that nothing exercised — deleting the whole effect left every test in
// this file green (Fund 3/6), because `renderToString` never runs effects
// and no test called `applyDocumentLang` through the Provider at all. Now
// that the write happens synchronously inside `setLang` itself, a test can
// call `setLang` directly (the same way the "does not throw when
// persisting the language choice fails" test above already does) and
// assert on the stubbed `document` — this goes red if the
// `applyDocumentLang(l)` call inside `setLang` is deleted, not just if
// `applyDocumentLang` itself is altered.

function capturedContext(storage: Storage): ReturnType<typeof useT> {
  let captured: ReturnType<typeof useT> | undefined;
  function Capture() {
    captured = useT();
    return null;
  }
  withStorage(storage, () => {
    renderToString(React.createElement(LanguageProvider, null, React.createElement(Capture)));
  });
  return captured!;
}

describe("setLang keeps <html lang> in sync", () => {
  it("writes the new language to the document when the language changes", () => {
    const ctx = capturedContext(fakeStorage("de"));
    const doc = fakeDocument();
    withDocument(doc, () => {
      withStorage(fakeStorage("de"), () => {
        ctx.setLang("pt-BR");
      });
    });
    expect(doc.documentElement.lang).toBe("pt-BR");
  });

  it("does not throw when there is no document (SSR) while changing the language", () => {
    const ctx = capturedContext(fakeStorage("de"));
    expect(() =>
      withDocument(undefined, () => {
        withStorage(fakeStorage("de"), () => ctx.setLang("en"));
      })
    ).not.toThrow();
  });
});

// ── AuthGate translations ────────────────────────────────────────────────
//
// A2: the login screen is the one screen every user sees before anything
// else works, and its three static strings going back to German (or
// `auth_subtitle` silently pointing at the wrong translation key) would go
// unnoticed by every test above, since none of them render `t()` for a
// non-German language against these specific keys. Pinning the exact
// expected string per key/language — not just "differs from German" —
// catches both a hardcoded-German regression and a key mix-up (Fund
// "auth_subtitle auf den falschen Schlüssel").

function tFor(lang: Lang): ReturnType<typeof useT>["t"] {
  return capturedContext(fakeStorage(lang)).t;
}

describe("AuthGate translations", () => {
  it("renders the exact expected text for every login-screen key, in every language", () => {
    const expected: Record<
      "auth_title" | "auth_subtitle" | "auth_token_ph",
      Record<Lang, string>
    > = {
      auth_title: {
        de: "Family Tools entsperren",
        en: "Unlock Family Tools",
        "es-ES": "Desbloquear Family Tools",
        "pt-BR": "Desbloquear o Family Tools",
      },
      auth_subtitle: {
        de: "Gemeinsames Zugriffstoken eingeben",
        en: "Enter the shared access token",
        "es-ES": "Introduce el token de acceso compartido",
        "pt-BR": "Insira o token de acesso compartilhado",
      },
      auth_token_ph: {
        de: "Zugriffstoken",
        en: "Access token",
        "es-ES": "Token de acceso",
        "pt-BR": "Token de acesso",
      },
    };
    for (const lang of Object.keys(LANG_LABELS) as Lang[]) {
      const t = tFor(lang);
      for (const key of Object.keys(expected) as (keyof typeof expected)[]) {
        expect(t(key)).toBe(expected[key][lang]);
      }
    }
  });

  it("never shows the German login text for a non-German language", () => {
    const tDe = tFor("de");
    for (const lang of ["en", "es-ES", "pt-BR"] as Lang[]) {
      const t = tFor(lang);
      for (const key of ["auth_title", "auth_subtitle", "auth_token_ph"] as const) {
        expect(t(key)).not.toBe(tDe(key));
      }
    }
  });
});

describe("README", () => {
  it("lists every shipped language", () => {
    // Warum ein Test fuer eine Zeile Prosa: Die Sprachliste im README ist
    // eine Zusage an den Nutzer, und sie ist genau einmal still veraltet —
    // der pt-BR-Beitrag hat sie gepflegt, der es-ES-Beitrag nicht, und
    // gemerkt hat es erst eine Pruefstimme nach dem Merge. Eine Zusage, die
    // niemand nachhaelt, ist schlechter als keine.
    //
    // Geprueft wird gegen LANG_LABELS, den Eigentuemer der Sprachliste, und
    // zwar gegen den Text-Teil der Beschriftung ("DE", "PT-BR") statt gegen
    // Sprachnamen in Prosa — sonst braeuchte der Test eine zweite Zuordnung
    // und waere selbst eine Stelle, die driften kann.
    // ?raw statt node:fs: Dieses Projekt fuehrt bewusst KEINE @types/node
    // ("types": [] in der tsconfig), und eine Abhaengigkeit fuer einen Test
    // waere der falsche Preis. Vites ?raw-Import ist ueber vite/client
    // typisiert, das vite-env.d.ts schon einbindet.
    //
    // Gesucht wird die FETTE Form `**ES**`, nicht das blosse `ES`. Die erste
    // Fassung suchte den blossen Code — und blieb gruen, als ES aus der
    // Liste entfernt wurde, weil "ES" auch in REST, SESSION, CEST und
    // RESTORE steckt. Ein Waechter, der auf ein Wortfragment prueft, prueft
    // nichts. Gefunden nur, weil der Rot-Beweis gefahren wurde.
    const fehlend = (Object.values(LANG_LABELS) as string[])
      .map((label) => label.replace(/[^\x20-\x7E]/g, "").trim())
      .filter((code) => code.length > 0 && !readmeText.includes(`**${code}**`));
    expect(fehlend).toEqual([]);
  });
});

describe("translations shape", () => {
  // Der Typ `Record<Lang, Uebersetzungswert>` verbietet Unsinn im Wert
  // (undefined, Zahlen), aber er verlangt NICHT, dass alle Sprachen eines
  // Schluessels dieselbe Form haben. Genau das hat die adversariale
  // Panel-Stimme ausgenutzt: eine Funktion neben drei Zeichenketten liess
  // tsc und alle Tests gruen, und die spanische Oberflaeche zeigte
  // "Manual undefined".
  //
  // Dieser Test schliesst die Luecke von der Laufzeitseite. Er laeuft ueber
  // ALLE Schluessel, auch die, die derzeit nirgends aufgerufen werden — bei
  // denen greift die Aritaetspruefung des Compilers naemlich gar nicht,
  // weil es keine Aufrufstelle gibt, an der sie greifen koennte.
  const alleSchluessel = Object.keys(translations) as (keyof typeof translations)[];

  it("every language of a key has the same shape", () => {
    const abweichungen: string[] = [];
    for (const key of alleSchluessel) {
      const werte = translations[key] as Record<string, unknown>;
      const formen = new Map<string, string>();
      for (const lang of Object.keys(LANG_LABELS)) {
        formen.set(lang, typeof werte[lang]);
      }
      const verschiedene = new Set(formen.values());
      if (verschiedene.size !== 1) {
        abweichungen.push(`${String(key)}: ${[...formen].map(([l, f]) => `${l}=${f}`).join(" ")}`);
      }
    }
    expect(abweichungen).toEqual([]);
  });

  it("every language of a parameterised key takes the same number of arguments", () => {
    // Eine Sprache, die ein Argument weniger nimmt, rendert still einen
    // Platzhalter weniger — der Satz erscheint dann unvollstaendig, ohne
    // dass irgendetwas rot wird.
    const abweichungen: string[] = [];
    for (const key of alleSchluessel) {
      const werte = translations[key] as Record<string, unknown>;
      const stellen = Object.keys(LANG_LABELS)
        .map((lang) => werte[lang])
        .filter((v): v is (...a: never[]) => string => typeof v === "function")
        .map((f) => f.length);
      if (stellen.length > 0 && new Set(stellen).size !== 1) {
        abweichungen.push(`${String(key)}: ${stellen.join(" / ")}`);
      }
    }
    expect(abweichungen).toEqual([]);
  });

  it("no language value is an empty string", () => {
    const leere: string[] = [];
    for (const key of alleSchluessel) {
      const werte = translations[key] as Record<string, unknown>;
      for (const lang of Object.keys(LANG_LABELS)) {
        if (werte[lang] === "") leere.push(`${String(key)}/${lang}`);
      }
    }
    expect(leere).toEqual([]);
  });
});

describe("errorText", () => {
  // Der Server schickt Schluessel UND deutschen Klartext. Diese Gruppe
  // prueft vor allem den RUECKFALL — den Fall, in dem das Frontend den
  // Schluessel nicht kennt. Das ist kein Randfall: FastAPIs eigene
  // Validierungsfehler kommen ganz ohne Schluessel (gemessen an der
  // laufenden API), und jede kuenftige Meldung kommt zuerst ohne
  // Uebersetzung hier an.
  // Nimmt den vorhandenen Weg, die Sprache im Provider zu setzen, statt einen
  // eigenen zu erfinden. Die erste Fassung dieses Helfers nahm `lang`
  // entgegen und BENUTZTE ES NICHT — vier der sechs Tests blieben trotzdem
  // gruen, weil sie gar nicht von der Sprache abhaengen. Zwei sind
  // umgefallen, und nur deshalb ist es aufgefallen.
  const textFor = (lang: Lang, fehler: ServerErrorLike): string =>
    capturedContext(fakeStorage(lang)).errorText(fehler);

  it("translates a known key into the selected language", () => {
    expect(
      textFor("es-ES", { message: "Account nicht gefunden", key: "err_account_not_found" })
    ).toBe("Cuenta no encontrada");
    expect(
      textFor("pt-BR", { message: "Account nicht gefunden", key: "err_account_not_found" })
    ).toBe("Conta não encontrada");
  });

  it("falls back to the server's plain text for an unknown key", () => {
    // DER WICHTIGSTE TEST DIESES SLICES. Ohne den Rueckfall zeigt die
    // Oberflaeche "Error:" und nichts dahinter — ein Fehler, den niemand
    // bemerkt, weil er wie ein leeres Feld aussieht und nicht wie ein Absturz.
    expect(
      textFor("es-ES", { message: "Etwas ist schiefgegangen", key: "err_gibt_es_nicht" })
    ).toBe("Etwas ist schiefgegangen");
  });

  it("falls back when the server sends no key at all", () => {
    // Die Form von FastAPIs Validierungsfehlern.
    expect(textFor("pt-BR", { message: "Unprocessable Entity" })).toBe("Unprocessable Entity");
  });

  it("never returns an empty string, whatever the server sent", () => {
    // Die Zusicherung, auf die es ankommt: etwas Lesbares kommt immer.
    const faelle: ServerErrorLike[] = [
      { message: "HTTP 500" },
      { message: "HTTP 500", key: "" },
      { message: "HTTP 500", key: "err_unbekannt" },
      { message: "HTTP 500", key: "err_account_not_found" },
      { message: "HTTP 500", key: "err_account_id_not_found", params: {} },
    ];
    for (const lang of Object.keys(LANG_LABELS) as Lang[]) {
      for (const fall of faelle) {
        expect(textFor(lang, fall).length).toBeGreaterThan(0);
      }
    }
  });

  it("fills the server's values into a parameterised message", () => {
    expect(
      textFor("en", {
        message: "Account a1 nicht gefunden",
        key: "err_account_id_not_found",
        params: { id: "a1" },
      })
    ).toBe("Account a1 not found");
    expect(
      textFor("es-ES", {
        message: "...",
        key: "err_unsupported_immich_version",
        params: { major: "2", minor: "7" },
      })
    ).toContain("2.7");
  });

  it("falls back to the plain text when a parameterised message arrives without its values", () => {
    // Frueher stand hier "die Meldung wird dann lueckenhaft, aber sie
    // erscheint" — und die Zusicherung war entsprechend schwach
    // (`length > 0`). Die Panel-Stimme hat gezeigt, wie das aussieht:
    // «undefined» bzw. «» mitten im Satz. Lieber der deutsche Klartext des
    // Servers als ein Satz mit einer Luecke; der Test haelt jetzt genau das
    // fest, statt nur "irgendetwas kommt".
    expect(textFor("de", { message: "Rueckfall", key: "err_account_id_not_found" })).toBe(
      "Rueckfall"
    );
  });
});

describe("ERROR_PARAM_ORDER", () => {
  // Die Bruecke zwischen dem Woerterbuch, das der Server schickt, und den
  // positionellen Argumenten der Uebersetzungen. Sie ist die Stelle, an der
  // still eine leere oder falsche Zahl erscheint — und die erste Fassung war
  // nur zu zwei von fuenf Faellen abgedeckt: Eine Mutation, die zwei
  // Eintraege entfernte, liess alle 66 Tests gruen und zeigte «undefined»
  // auf der Oberflaeche. Von der blinden Panel-Stimme gefunden.
  const fehlerSchluessel = (Object.keys(translations) as string[]).filter((k) =>
    k.startsWith("err_")
  );

  it("has an entry for every parameterised error key, and only for those", () => {
    const mitFunktion = fehlerSchluessel.filter((k) => {
      const werte = (translations as Record<string, Record<string, unknown>>)[k];
      return typeof werte.de === "function";
    });
    expect(Object.keys(ERROR_PARAM_ORDER).sort()).toEqual(mitFunktion.sort());
  });

  it("names exactly as many parameters as the translation takes arguments", () => {
    const abweichungen: string[] = [];
    for (const [key, namen] of Object.entries(ERROR_PARAM_ORDER)) {
      const fn = (translations as Record<string, Record<string, unknown>>)[key]?.de;
      if (typeof fn !== "function") {
        abweichungen.push(`${key}: kein Funktionseintrag`);
        continue;
      }
      if ((fn as (...a: never[]) => string).length !== namen.length) {
        abweichungen.push(
          `${key}: ${namen.length} Namen, aber ${(fn as (...a: never[]) => string).length} Argumente`
        );
      }
    }
    expect(abweichungen).toEqual([]);
  });

  it("renders every parameterised error with its values, in every language", () => {
    // Alle fuenf, nicht zwei. Je Schluessel wird geprueft, dass JEDER Wert
    // im Ergebnis auftaucht — ein vertauschtes oder verschlucktes Argument
    // faellt damit auf.
    const werte: Record<string, Record<string, string>> = {
      err_account_id_not_found: { id: "WERT-A" },
      err_owner_account_id_not_found: { id: "WERT-B" },
      err_person_validation_failed: { account: "WERT-C" },
      err_match_album_exists: { album: "WERT-D" },
      err_unsupported_immich_version: { major: "WERT-E", minor: "WERT-F" },
    };
    expect(Object.keys(werte).sort()).toEqual(Object.keys(ERROR_PARAM_ORDER).sort());
    for (const lang of Object.keys(LANG_LABELS) as Lang[]) {
      for (const [key, params] of Object.entries(werte)) {
        const text = capturedContext(fakeStorage(lang)).errorText({
          message: "RUECKFALL",
          key,
          params,
        });
        expect(text).not.toBe("RUECKFALL");
        for (const wert of Object.values(params)) {
          expect(text).toContain(wert);
        }
      }
    }
  });

  it("falls back to the plain text when a value is missing", () => {
    // Lieber der deutsche Satz des Servers als ein Satz mit einer Luecke.
    for (const key of Object.keys(ERROR_PARAM_ORDER)) {
      expect(capturedContext(fakeStorage("es-ES")).errorText({ message: "RUECKFALL", key })).toBe(
        "RUECKFALL"
      );
    }
  });

  it("ignores a key that is not an error key at all", () => {
    // Ohne die err_-Schranke schlug ein Tippfehler im GESAMTEN Woerterbuch
    // nach und lieferte einen fremden Satz.
    expect(
      capturedContext(fakeStorage("de")).errorText({ message: "RUECKFALL", key: "nav_accounts" })
    ).toBe("RUECKFALL");
  });
});
