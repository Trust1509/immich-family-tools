// Zwei Gruppen gleichen Namens muessen als ZWEI Karten erscheinen.
//
// Warum (#78, Nacharbeit): `key={group.album_name}` und ein `bulkSyncState`,
// der ueber `group.album_name` verschluesselt ist, waren sicher, solange der
// Name der Gruppenschluessel WAR. Der Slice hebt das auf. Gemessen vom Panel
// an der ersten Fassung: zwei Gruppen, ein Eintrag im bulkSyncState, doppelte
// React-Keys — Ergebnisse der einen Gruppe erschienen bei der anderen.
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import AlbumsOverview from "./AlbumsOverview";
import { LanguageProvider } from "../i18n";
import { SPEICHER_SCHLUESSEL } from "../test-konstanten";

// Alle Daten erfunden; das Repo ist oeffentlich.
const ALBEN = [
  {
    id: "album-eins",
    match_id: "m-1",
    album_id: "immich-eins",
    album_name: "Testalbum",
    group_id: "gruppe-1",
    owner_account_id: "konto-1",
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
  },
  {
    id: "album-zwei",
    match_id: "m-2",
    album_id: "immich-zwei",
    album_name: "Testalbum",
    group_id: "gruppe-2",
    owner_account_id: "konto-2",
    person_refs: [
      {
        account_id: "konto-2",
        person_id: "person-b",
        person_name: "Person B",
        account_name: "Konto Zwei",
        account_color: "#222222",
      },
    ],
    linked_match_ids: [],
    created_at: "2026-01-02T00:00:00+00:00",
    last_synced_at: "2026-01-02T00:00:00+00:00",
    total_assets: 1,
  },
];

const { albenMock, autoSyncGet, refreshMock } = vi.hoisted(() => ({
  albenMock: vi.fn(),
  autoSyncGet: vi.fn(),
  refreshMock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  api: {
    sync: { albums: albenMock, refreshAlbum: refreshMock, deleteAlbum: vi.fn() },
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
  albenMock.mockResolvedValue(ALBEN);
  autoSyncGet.mockResolvedValue({ enabled: false, time: "01:00" });
  // Je Album ein unterscheidbarer Protokolleintrag — nur so faellt auf, wenn
  // das Ergebnis der einen Gruppe bei der anderen landet.
  refreshMock.mockImplementation(async (albumId: string) => [
    {
      id: `log-${albumId}`,
      timestamp: "2026-01-03T00:00:00+00:00",
      action: "album_sync",
      details: `Ergebnis fuer ${albumId}`,
      status: "success",
    },
  ]);
});

describe("AlbumsOverview", () => {
  it("zeigt zwei gleichnamige Gruppen als zwei Karten", async () => {
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <LanguageProvider>
          <AlbumsOverview />
        </LanguageProvider>
      </QueryClientProvider>
    );

    await waitFor(() => expect(screen.getAllByText("Testalbum")).toHaveLength(2));
    // Beide Gruppen behalten ihre eigenen Personen — wuerden sie ueber den
    // Namen zusammengelegt, stuenden beide auf einer Karte.
    expect(screen.getByText("Person A")).toBeTruthy();
    expect(screen.getByText("Person B")).toBeTruthy();
  });

  it("vergibt eindeutige Schluessel, auch bei gleichem Namen", async () => {
    // Dieselbe Tuer wie in ExtendMatch, und sie war offen: Die Mutation
    // `key={group.album_name}` ueberlebte die volle Suite (Gegenpruefer
    // 21.09.2026). Ein doppelter Schluessel rendert trotzdem zwei Karten —
    // zaehlen faengt ihn nicht. Hier haelt React zwei Karten fuer dieselbe,
    // und an dieser Ansicht haengen der Sammel-Spinner und der
    // "Alle synchronisieren"-Knopf.
    const warnungen: string[] = [];
    const echt = console.error;
    console.error = (...args: unknown[]) => {
      warnungen.push(args.map(String).join(" "));
    };
    const passendeWarnung = (w: string) => /same key|unique "key"|duplicate key/i.test(w);
    try {
      render(
        <QueryClientProvider
          client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
        >
          <LanguageProvider>
            <AlbumsOverview />
          </LanguageProvider>
        </QueryClientProvider>
      );
      await waitFor(() => expect(screen.getAllByText("Testalbum")).toHaveLength(2));
      expect(warnungen.filter(passendeWarnung)).toEqual([]);

      // SELBSTPROBE: zeigt, dass der Kanal ueberhaupt lebt.
      const probe: string[] = [];
      console.error = (...args: unknown[]) => {
        probe.push(args.map(String).join(" "));
      };
      render(
        <ul>
          {["x", "x"].map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      );
      expect(probe.filter(passendeWarnung).length).toBeGreaterThan(0);
    } finally {
      console.error = echt;
    }
  });
});

describe("AlbumsOverview: Sammel-Synchronisierung", () => {
  it("zeigt jeder Gruppe ihr EIGENES Ergebnis", async () => {
    // Der Blocker der zweiten Nacharbeit: Die Saat-Zeile von bulkSyncState
    // schluesselte noch auf album_name, gelesen wurde mit group_id — der
    // Sammel-Spinner war tot, und bei gleichnamigen Gruppen ueberschrieb das
    // Ergebnis der einen das der anderen. Vier von fuenf Stellen umgestellt,
    // die fuenfte uebersehen; die volle Suite blieb gruen.
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <LanguageProvider>
          <AlbumsOverview />
        </LanguageProvider>
      </QueryClientProvider>
    );
    await waitFor(() => expect(screen.getAllByText("Testalbum")).toHaveLength(2));

    fireEvent.click(screen.getByText("Alle synchronisieren"));

    await waitFor(() => {
      expect(screen.getByText("Ergebnis fuer album-eins")).toBeTruthy();
      expect(screen.getByText("Ergebnis fuer album-zwei")).toBeTruthy();
    });

    // Und jedes bei SEINER Karte, nicht beides bei einer.
    const karteA = screen.getByText("Person A").closest(".card");
    const karteB = screen.getByText("Person B").closest(".card");
    expect(karteA?.textContent).toContain("Ergebnis fuer album-eins");
    expect(karteA?.textContent).not.toContain("Ergebnis fuer album-zwei");
    expect(karteB?.textContent).toContain("Ergebnis fuer album-zwei");
    expect(karteB?.textContent).not.toContain("Ergebnis fuer album-eins");
  });
});

describe("AlbumsOverview: Spinner der Sammel-Synchronisierung", () => {
  it("markiert BEIDE Gruppen als laufend, solange der Abgleich laeuft", async () => {
    // DER eigentliche Blocker: bulkSyncState wurde mit album_name GESAET und
    // mit group_id GELESEN. Das Ergebnis kam trotzdem an (es wird mit
    // group_id geschrieben) — tot war nur der Spinner dazwischen. Ein Test,
    // der auf das Ergebnis wartet, uebersieht das: gemessen, er blieb gruen.
    let freigeben: (() => void) | undefined;
    refreshMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          freigeben = () => resolve([]);
        })
    );

    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <LanguageProvider>
          <AlbumsOverview />
        </LanguageProvider>
      </QueryClientProvider>
    );
    await waitFor(() => expect(screen.getAllByText("Testalbum")).toHaveLength(2));

    fireEvent.click(screen.getByText("Alle synchronisieren"));

    // Beide Karten stehen auf "laufend", bevor irgendein Abgleich fertig ist.
    await waitFor(() => expect(screen.getAllByText("Synchronisiert…")).toHaveLength(2));

    freigeben?.();
  });
});
