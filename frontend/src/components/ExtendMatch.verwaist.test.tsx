// #124 B8: `ExtendMatch.tsx` bot ein verwaistes `primary_album`
// (`owner_account_missing`) weiter zum Erweitern an, ohne jeden Hinweis.
// Erweitern haette dort ohnehin nur eine stille Fehlermeldung produziert
// (`sync_service._extend_match_unlocked`, `log_owner_account_missing`) —
// die Karte bleibt sichtbar, aber sichtbar gesperrt.
//
// Alle Daten erfunden; das Repo ist oeffentlich.
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ExtendMatch from "./ExtendMatch";
import { LanguageProvider } from "../i18n";
import { SPEICHER_SCHLUESSEL } from "../test-konstanten";

const ALBEN = [
  {
    id: "album-verwaist",
    match_id: "m-1",
    album_id: "immich-verwaist",
    album_name: "Verwaistes Album",
    group_id: "gruppe-verwaist",
    owner_account_id: "konto-geloescht",
    person_refs: [
      {
        account_id: "konto-1",
        person_id: "person-a",
        person_name: "Person A",
        account_name: "Konto Eins",
        account_color: "#111111",
      },
    ],
    linked_match_ids: [],
    created_at: "2026-01-01T00:00:00+00:00",
    last_synced_at: "2026-01-01T00:00:00+00:00",
    total_assets: 1,
    // Beim Lesen berechnet (#99, #112) — genau das Feld, das B8 auswertet.
    owner_account_missing: true,
    too_few_people: false,
  },
  {
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
    owner_account_missing: false,
    too_few_people: false,
  },
];

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

function zeichne() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <LanguageProvider>
        <ExtendMatch />
      </LanguageProvider>
    </QueryClientProvider>
  );
}

function karteMit(albumName: string): HTMLElement {
  const treffer = screen.getByText(albumName);
  const karte = treffer.closest("button");
  if (!karte) throw new Error(`keine Karte zu ${albumName}`);
  return karte;
}

beforeEach(() => {
  vi.clearAllMocks();
  try {
    localStorage.setItem(SPEICHER_SCHLUESSEL, "de");
  } catch {
    /* in dieser Umgebung nicht zwingend vorhanden */
  }
  albenMock.mockResolvedValue(ALBEN);
  // "konto-geloescht" ABSICHTLICH nicht im lebenden Bestand — genau das
  // macht album-verwaist zu einem verwaisten Album.
  kontenMock.mockResolvedValue([{ id: "konto-1", name: "Konto Eins", color: "#111111" }]);
  personenMock.mockResolvedValue([]);
  byAccountMock.mockResolvedValue([]);
  extendMock.mockResolvedValue([]);
});

describe("ExtendMatch: verwaistes Album bleibt sichtbar, aber gesperrt (#124 B8)", () => {
  it("zeigt einen Hinweis auf der verwaisten Karte", async () => {
    zeichne();

    await waitFor(() => expect(screen.getByText("Verwaistes Album")).toBeTruthy());
    expect(
      screen.getByText(
        "Dieses Album ist verwaist (Besitzerkonto fehlt) — kann nicht erweitert werden."
      )
    ).toBeTruthy();
  });

  it("laesst die verwaiste Karte NICHT auswaehlen", async () => {
    zeichne();
    await waitFor(() => expect(screen.getByText("Verwaistes Album")).toBeTruthy());

    fireEvent.click(karteMit("Verwaistes Album"));

    // Kein Schritt 2 (Konto-/Personenauswahl) darf erscheinen — die Karte
    // hat nie ausgewaehlt gegolten.
    expect(screen.queryByText("Neues Konto")).toBeNull();
    expect(karteMit("Verwaistes Album").className).not.toContain("border-immich-primary");
  });

  it("laesst die GESUNDE Karte daneben ganz normal auswaehlen", async () => {
    // Gegenprobe: die Sperre trifft NUR die verwaiste Karte, nicht die
    // ganze Ansicht.
    zeichne();
    await waitFor(() => expect(screen.getByText("Gesundes Album")).toBeTruthy());

    fireEvent.click(karteMit("Gesundes Album"));

    await waitFor(() =>
      expect(karteMit("Gesundes Album").className).toContain("border-immich-primary")
    );
    expect(screen.queryByText("Dieses Album ist verwaist")).toBeNull();
  });

  it("setzt `disabled` auf dem Knopf der verwaisten Karte", async () => {
    // Rot-beweisbarer Nachweis der SICHTBAREN Sperre, unabhaengig vom
    // Klick-Verhalten oben: ein Screenreader/Tastatur-Nutzer sieht das
    // ueber die Knopf-Eigenschaft, nicht nur ueber die Optik.
    zeichne();
    await waitFor(() => expect(screen.getByText("Verwaistes Album")).toBeTruthy());

    expect((karteMit("Verwaistes Album") as HTMLButtonElement).disabled).toBe(true);
    expect((karteMit("Gesundes Album") as HTMLButtonElement).disabled).toBe(false);
  });
});
