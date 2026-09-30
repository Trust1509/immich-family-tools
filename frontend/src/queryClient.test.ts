// #119, Punkt 4 (KLEIN): `erzeugeAppQueryClient` von `QUERY_VORGABEN`
// abgekoppelt (z.B. eine zweite, hier hartkodierte Kopie der Zahlen) blieb
// bisher ungetestet gruen — kein Test rief `erzeugeAppQueryClient` je auf.
// Ohne diese Kopplung ist `QUERY_VORGABEN`s eigener Docstring ("main.tsx und
// jeder produktionsnahe Test teilen sich diese Konstante") eine unbewachte
// Behauptung.
import { describe, expect, it } from "vitest";
import { erzeugeAppQueryClient, QUERY_VORGABEN } from "./queryClient";

describe("erzeugeAppQueryClient", () => {
  it("benutzt WIRKLICH QUERY_VORGABEN, nicht eine zweite Kopie der Zahlen", () => {
    const client = erzeugeAppQueryClient();

    expect(client.getDefaultOptions().queries).toEqual(QUERY_VORGABEN);
  });

  it("traegt die produktionsnahen Werte, die die Gruppenvorschau-Tests voraussetzen", () => {
    // Diese beiden Zahlen sind der Grund, warum `QUERY_VORGABEN` ueberhaupt
    // existiert (#110, Nacharbeit 2, Fund 2) — ein produktionsnaher Test
    // baut seinen eigenen Client MIT diesen Vorgaben, nicht ohne.
    const client = erzeugeAppQueryClient();

    expect(client.getDefaultOptions().queries?.staleTime).toBe(30_000);
    expect(client.getDefaultOptions().queries?.retry).toBe(1);
  });
});
