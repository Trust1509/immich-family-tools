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

  // Fund 1b: the error path used to read `detail` off whatever `res.json()`
  // resolved to without checking it was even an object first. Each of these
  // is a real shape a backend error response can take; every one of them
  // must still surface an `ApiError` carrying the status code and a
  // non-empty message — never a `TypeError` that pre-empts `ApiError`, and
  // never an empty string `AuthGate` would render as nothing at all.
  it("falls back to statusText when the body is null", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      statusText: "Bad Gateway",
      json: async () => null,
    });
    vi.stubGlobal("fetch", fetchMock);

    const err = await api.auth.login("x").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(502);
    expect((err as ApiError).message).toBe("Bad Gateway");
  });

  it("falls back to statusText when the body is an empty object", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: async () => ({}),
    });
    vi.stubGlobal("fetch", fetchMock);

    const err = await api.auth.login("x").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(500);
    expect((err as ApiError).message).toBe("Internal Server Error");
  });

  it("falls back to statusText when detail is an empty string", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: "Bad Request",
      json: async () => ({ detail: "" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const err = await api.auth.login("x").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(400);
    expect((err as ApiError).message).toBe("Bad Request");
  });

  it("falls back to statusText when detail is not a string", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      statusText: "Unprocessable Entity",
      json: async () => ({ detail: 42 }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const err = await api.auth.login("x").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(422);
    expect((err as ApiError).message).toBe("Unprocessable Entity");
  });

  it("falls back to the status code when both detail and statusText are empty", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      statusText: "",
      json: async () => ({ detail: "" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const err = await api.auth.login("x").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(503);
    expect((err as ApiError).message).toBe("HTTP 503");
  });

  it("still throws an ApiError with the status code when reading the body itself fails", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 504,
      statusText: "Gateway Timeout",
      json: async () => {
        throw new SyntaxError("Unexpected end of JSON input");
      },
    });
    vi.stubGlobal("fetch", fetchMock);

    const err = await api.auth.login("x").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(504);
    expect((err as ApiError).message).toBe("Gateway Timeout");
  });
});

/** Die Naht zwischen HTTP-Antwort und `ApiError` fuer die Fehler-Schluessel.
 *
 *  WARUM DIESE GRUPPE EXISTIERT: Die `errorText`-Tests in `i18n.test.ts`
 *  bauen ihr Fehlerobjekt selbst. Sie pruefen damit die Uebersetzung, aber
 *  nicht, dass der Schluessel ueberhaupt aus der Antwort geholt wird. Ein
 *  Mutationslauf hat genau das gezeigt: Die Zeile in `client.ts`, die
 *  `error_key` liest, liess sich ersatzlos entfernen — alle Tests blieben
 *  gruen, und jede Meldung waere still wieder deutsch gewesen. Also genau der
 *  Fehler, den dieser Slice beseitigt, ohne ein einziges rotes Gate.
 *
 *  Dieselbe Bauart wie die Gruppe darueber (vi.stubGlobal auf fetch), damit
 *  der Weg durch `request()` und das Werfen des `ApiError` echt bleibt. */
describe("Fehler-Schluessel aus der Antwort", () => {
  // Rueckgabetyp ausdruecklich ApiError: `list()` liefert sonst die Union
  // `Account[] | ApiError`, und `.message` gibt es darauf nicht. Genau daran
  // ist der Typcheck im Pre-Commit-Hook gescheitert — der Hook hat also
  // getan, wofuer er da ist.
  const antwort = async (status: number, koerper: unknown): Promise<ApiError> => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status,
        statusText: "Fehler",
        json: async () => koerper,
      })
    );
    return (await api.accounts.list().catch((e) => e)) as ApiError;
  };

  it("nimmt Schluessel und Werte mit", async () => {
    const err = await antwort(404, {
      detail: "Account a1 nicht gefunden",
      error_key: "err_account_id_not_found",
      error_params: { id: "a1" },
    });
    expect(err).toBeInstanceOf(ApiError);
    expect(err.message).toBe("Account a1 nicht gefunden");
    expect(err.key).toBe("err_account_id_not_found");
    expect(err.params).toEqual({ id: "a1" });
  });

  it("kommt ohne Schluessel aus und behaelt den Klartext", async () => {
    // Die Form von FastAPIs eigenen Validierungsfehlern: `detail` ist eine
    // Liste, ein Schluessel fehlt ganz. Gemessen an der laufenden API.
    const err = await antwort(422, { detail: [{ msg: "Field required" }] });
    expect(err.key).toBeUndefined();
    expect(err.message.length).toBeGreaterThan(0);
  });

  it("verwirft einen Schluessel, der keine nicht-leere Zeichenkette ist", async () => {
    for (const schluessel of ["", 42, null, {}, []]) {
      const err = await antwort(400, { detail: "Klartext", error_key: schluessel });
      expect(err.key).toBeUndefined();
      expect(err.message).toBe("Klartext");
    }
  });

  it("nimmt nur Werte mit, die sich anzeigen lassen", async () => {
    const err = await antwort(409, {
      detail: "x",
      error_key: "err_match_album_exists",
      error_params: { album: "Urlaub", anzahl: 3, unsinn: { tief: true }, leer: null },
    });
    expect(err.params).toEqual({ album: "Urlaub", anzahl: "3" });
  });

  it("kommt mit error_params zurecht, die gar kein Objekt sind", async () => {
    for (const werte of ["nein", 42, [1, 2], null]) {
      const err = await antwort(500, { detail: "x", error_key: "err_x", error_params: werte });
      expect(err.message).toBe("x");
    }
  });
});
