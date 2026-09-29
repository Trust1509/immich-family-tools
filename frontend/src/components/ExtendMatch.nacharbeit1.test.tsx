// Nacharbeit 1 zu #113/#119/#124 — Blind K-1: `isValid` kennt die Sperre
// eines waehrend der Auswahl VERWAISTEN Albums nicht. An die Sonde der
// Pruefstimme angelehnt
// (`scratchpad/welle4/blind/S2/sonden/ExtendMatch.sonde.test.tsx`), hier als
// fester, assertierender Test statt einer druckenden Sonde.
//
// Alle Daten erfunden; das Repo ist oeffentlich.
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ExtendMatch from "./ExtendMatch";
import { LanguageProvider } from "../i18n";
import { SPEICHER_SCHLUESSEL } from "../test-konstanten";

const album = (verwaist: boolean) => ({
  id: "album-gesund",
  match_id: "m-2",
  album_id: "immich-gesund",
  album_name: "Gesundes Album",
  group_id: "gruppe-gesund",
  owner_account_id: "konto-1",
  person_refs: [
    {
      account_id: "konto-1",
      person_id: "person-b",
      person_name: "Person B",
      account_name: "Konto Eins",
      account_color: "#111111",
    },
  ],
  linked_match_ids: [],
  created_at: "2026-01-02T00:00:00+00:00",
  last_synced_at: "2026-01-02T00:00:00+00:00",
  total_assets: 1,
  owner_account_missing: verwaist,
  too_few_people: true,
});

const { albenMock, kontenMock, extendMock, personenMock, byAccountMock } = vi.hoisted(() => ({
  albenMock: vi.fn(),
  kontenMock: vi.fn(),
  extendMock: vi.fn(),
  personenMock: vi.fn(),
  byAccountMock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  api: {
    sync: { albums: albenMock, extend: extendMock },
    accounts: { list: kontenMock },
    people: { list: personenMock, byAccount: byAccountMock, thumbnailUrl: () => "" },
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  try {
    localStorage.setItem(SPEICHER_SCHLUESSEL, "de");
  } catch {
    /* egal */
  }
  albenMock.mockResolvedValue([album(false)]);
  kontenMock.mockResolvedValue([
    { id: "konto-1", name: "Konto Eins", color: "#111111" },
    { id: "konto-2", name: "Konto Zwei", color: "#222222" },
  ]);
  personenMock.mockResolvedValue([]);
  byAccountMock.mockResolvedValue([
    { id: "person-neu", name: "Person Neu", account_id: "konto-2", asset_count: 1 },
  ]);
  extendMock.mockResolvedValue([]);
});

describe("Karte wird NACH der Auswahl verwaist (Blind K-1, Sonde FP4)", () => {
  it("der Knopf 'Zum Match hinzufügen' wird gesperrt, sobald die Karte verwaist", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <LanguageProvider>
          <ExtendMatch />
        </LanguageProvider>
      </QueryClientProvider>
    );
    await waitFor(() => expect(screen.getByText("Gesundes Album")).toBeTruthy());
    fireEvent.click(screen.getByText("Gesundes Album").closest("button")!);
    const kontoAuswahl = await screen.findByRole("combobox");
    fireEvent.change(kontoAuswahl, { target: { value: "konto-2" } });
    const feld = await screen.findByPlaceholderText("Person suchen…");
    fireEvent.focus(feld);
    fireEvent.mouseDown(await screen.findByText("Person Neu"));

    const knopf = () =>
      screen.getByText("Zum Match hinzufügen").closest("button") as HTMLButtonElement;
    await waitFor(() => expect(knopf().disabled).toBe(false));

    // Die Karte verwaist WAEHREND der Nutzer schon Konto und Person gewaehlt
    // hat (z.B. eine Invalidierung von `managed-albums`) — genau der Fall,
    // den `AlbumGroupCard`/`gesperrt` schon abdeckt, `isValid` aber nicht.
    albenMock.mockResolvedValue([album(true)]);
    await act(async () => {
      await qc.invalidateQueries();
    });
    await waitFor(() =>
      expect(
        screen.queryByText(
          "Dieses Album ist verwaist (Besitzerkonto fehlt) — kann nicht erweitert werden."
        )
      ).toBeTruthy()
    );

    expect(knopf().disabled).toBe(true);
    fireEvent.click(knopf());
    await act(async () => {
      await new Promise((r) => setTimeout(r, 20));
    });
    expect(extendMock).not.toHaveBeenCalled();
  });
});
