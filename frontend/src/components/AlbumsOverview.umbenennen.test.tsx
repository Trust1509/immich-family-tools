// Ein TEILAUSFALL beim Umbenennen muss sichtbar sein (#79, Auflage 1).
//
// Eine Kartenzeile kann fuer MEHRERE echte Alben stehen — eines je Konto.
// Das Umbenennen laeuft deshalb in einer Schleife, und das Backend gibt einen
// Fehlschlag NICHT als HTTP-Fehler zurueck, sondern als Protokolleintrag mit
// `status: "error"` in einer 200-Antwort. Die Schleife bricht also nicht ab.
//
// Beim Review des zugelieferten Zweigs (20.09.2026) haben wir das als offene
// Auflage notiert. NACHGEMESSEN auf dem rebasten Stand: Es ist gedeckt — der
// fehlgeschlagene Eintrag wird als Fehler dargestellt, und das Eingabefeld
// bleibt offen. Diese Datei nagelt beides fest, damit es nicht wieder
// verlorengeht.
//
// Die Darstellung unterscheidet Erfolg und Fehler heute allein ueber die
// FARBE (`SyncLogDisplay`, rot gegen gruen). Das ist eine Konvention der
// ganzen Anwendung, nicht etwas, das dieser Zweig eingefuehrt hat — als
// Grenze benannt, nicht hier behoben: Wer sie aendert, aendert sie ueberall.
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import AlbumsOverview from "./AlbumsOverview";
import { LanguageProvider } from "../i18n";
import { SPEICHER_SCHLUESSEL } from "../test-konstanten";

// Alle Daten erfunden; das Repo ist oeffentlich. ZWEI Alben in EINER Gruppe —
// nur so laeuft die Schleife mehr als einmal.
const GRUPPE = ["album-eins", "album-zwei"].map((id, nr) => ({
  id,
  match_id: `m-${nr}`,
  album_id: `immich-${nr}`,
  album_name: "Testalbum",
  group_id: "gruppe-1",
  owner_account_id: `konto-${nr}`,
  person_refs: [
    {
      account_id: `konto-${nr}`,
      person_id: `person-${nr}`,
      person_name: `Person ${nr}`,
      account_name: `Konto ${nr}`,
      account_color: "#111111",
    },
  ],
  linked_match_ids: [],
  created_at: "2026-01-01T00:00:00+00:00",
  last_synced_at: "2026-01-01T00:00:00+00:00",
  total_assets: 1,
}));

const { albenMock, autoSyncGet, renameMock } = vi.hoisted(() => ({
  albenMock: vi.fn(),
  autoSyncGet: vi.fn(),
  renameMock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  api: {
    sync: {
      albums: albenMock,
      refreshAlbum: vi.fn(),
      deleteAlbum: vi.fn(),
      renameAlbum: renameMock,
    },
    autoSync: { get: autoSyncGet, set: vi.fn() },
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
  try {
    localStorage.setItem(SPEICHER_SCHLUESSEL, "de");
  } catch {
    /* in dieser Umgebung nicht zwingend vorhanden */
  }
  albenMock.mockResolvedValue(GRUPPE);
  autoSyncGet.mockResolvedValue({ enabled: false, time: "01:00" });
});

async function umbenennen(neuerName: string) {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <LanguageProvider>
        <AlbumsOverview />
      </LanguageProvider>
    </QueryClientProvider>
  );
  await waitFor(() => expect(screen.getByText("Testalbum")).toBeTruthy());
  fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/ }));
  const feld = await screen.findByDisplayValue("Testalbum");
  fireEvent.change(feld, { target: { value: neuerName } });
  fireEvent.keyDown(feld, { key: "Enter" });
}

describe("Umbenennen einer Gruppe mit mehreren Alben", () => {
  it("macht einen Teilausfall sichtbar", async () => {
    // Das erste Album gelingt, das zweite scheitert — so, wie das Backend es
    // meldet: HTTP 200, `status: "error"`.
    // NEUTRALE Texte in der Attrappe. Die erste Fassung dieser Probe legte
    // das Wort "fehlgeschlagen" in den Mock und suchte es danach im
    // gerenderten Text — sie prueefte also den Mock, nicht die Anwendung.
    // Gemessen wird stattdessen, was die ANWENDUNG selbst erzeugt.
    renameMock.mockImplementation(async (albumId: string) => [
      {
        id: `log-${albumId}`,
        timestamp: "2026-01-03T00:00:00+00:00",
        action: "rename_album",
        details: `Eintrag zu ${albumId}`,
        status: albumId === "album-eins" ? "success" : "error",
        ...(albumId === "album-eins" ? {} : { error_message: "IMMICH_API_ERROR" }),
      },
    ]);

    await umbenennen("Neuer Name");

    await waitFor(() => expect(renameMock).toHaveBeenCalledTimes(2));

    // ERSTES SIGNAL: Der fehlgeschlagene Eintrag wird als Fehler dargestellt,
    // der gelungene als Erfolg. Die Anwendung unterscheidet sie heute allein
    // ueber die Farbe (`SyncLogDisplay`) — das ist ihre eigene Aussage, nicht
    // meine.
    const fehler = await screen.findByText("Eintrag zu album-zwei");
    expect(fehler.className).toMatch(/red/);
    const gelungen = screen.getByText("Eintrag zu album-eins");
    expect(gelungen.className).toMatch(/emerald/);

    // ZWEITES SIGNAL, unabhaengig vom ersten: Das Eingabefeld bleibt OFFEN.
    // Ein Nutzer, der nur auf die Karte schaut, sieht daran, dass der Vorgang
    // nicht durchgelaufen ist — auch ohne die Farbe zu deuten.
    expect(screen.queryByDisplayValue("Neuer Name")).toBeTruthy();
  });

  it("meldet nichts, wenn alle Alben gelingen", async () => {
    renameMock.mockImplementation(async (albumId: string) => [
      {
        id: `log-${albumId}`,
        timestamp: "2026-01-03T00:00:00+00:00",
        action: "rename_album",
        details: `Eintrag zu ${albumId}`,
        status: "success",
      },
    ]);

    await umbenennen("Neuer Name");
    await waitFor(() => expect(renameMock).toHaveBeenCalledTimes(2));

    // Beide Eintraege als Erfolg — und das Eingabefeld schliesst sich.
    const eins = await screen.findByText("Eintrag zu album-eins");
    expect(eins.className).toMatch(/emerald/);
    expect(eins.className).not.toMatch(/red/);
    await waitFor(() => expect(screen.queryByDisplayValue("Neuer Name")).toBeNull());
  });
});
