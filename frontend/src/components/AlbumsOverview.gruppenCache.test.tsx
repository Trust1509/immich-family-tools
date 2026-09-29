// Gruppen-Cache nach Entfernen/Umbenennen (#110, Nacharbeit 2, Fund 3).
//
// Blindpruefer: die Invalidierung von `["album-group"]` in `AlbumsOverview.tsx`
// (Entfernen UND Umbenennen) war bislang ungetestet — direkter Nachweis wie
// bei den anderen drei Aufrufstellen (MatchSuggestions.tsx, ManualMatch.tsx,
// ExtendMatch.tsx).
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import AlbumsOverview from "./AlbumsOverview";
import { LanguageProvider } from "../i18n";
import { SPEICHER_SCHLUESSEL } from "../test-konstanten";

// Alle Daten erfunden; das Repo ist oeffentlich.
const ALBUM = {
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
};

const { albenMock, autoSyncGet, renameMock, refreshMock, deleteMock } = vi.hoisted(() => ({
  albenMock: vi.fn(),
  autoSyncGet: vi.fn(),
  renameMock: vi.fn(),
  refreshMock: vi.fn(),
  deleteMock: vi.fn(),
}));

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    api: {
      sync: {
        albums: albenMock,
        refreshAlbum: refreshMock,
        deleteAlbum: deleteMock,
        renameAlbum: renameMock,
      },
      autoSync: { get: autoSyncGet, set: vi.fn() },
    },
  };
});

function zeichne() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const spion = vi.spyOn(qc, "invalidateQueries");
  render(
    <QueryClientProvider client={qc}>
      <LanguageProvider>
        <AlbumsOverview />
      </LanguageProvider>
    </QueryClientProvider>
  );
  return spion;
}

/** Ob unter den bisherigen Aufrufen des Spions eine Invalidierung von
 *  `["album-group"]` war. */
function hatAlbumGroupInvalidiert(spion: { mock: { calls: unknown[][] } }): boolean {
  return spion.mock.calls.some(
    (call: unknown[]) =>
      call[0] &&
      typeof call[0] === "object" &&
      "queryKey" in call[0] &&
      (call[0] as { queryKey?: unknown[] }).queryKey?.[0] === "album-group"
  );
}

/** Dasselbe, fuer einen beliebigen Abfrageschluessel — Nacharbeit 1 (#123,
 *  Blindpruefer W4): `handleDeleteSingle` bekam bis hierher keinen eigenen
 *  Nachweis, dass es ueberhaupt neu laedt; eine Mutation, die alle drei
 *  `invalidateQueries`-Aufrufe darin entfernt, blieb gruen. */
function hatQueryInvalidiert(spion: { mock: { calls: unknown[][] } }, key: string): boolean {
  return spion.mock.calls.some(
    (call: unknown[]) =>
      call[0] &&
      typeof call[0] === "object" &&
      "queryKey" in call[0] &&
      (call[0] as { queryKey?: unknown[] }).queryKey?.[0] === key
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  try {
    localStorage.setItem(SPEICHER_SCHLUESSEL, "de");
  } catch {
    /* in dieser Umgebung nicht zwingend vorhanden */
  }
  albenMock.mockResolvedValue([ALBUM]);
  autoSyncGet.mockResolvedValue({ enabled: false, time: "01:00" });
  renameMock.mockResolvedValue([]);
  deleteMock.mockResolvedValue(undefined);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AlbumsOverview: Gruppen-Cache nach Entfernen", () => {
  it("invalidiert die Gruppenvorschau, sobald ein Album entfernt wurde", async () => {
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );
    const spion = zeichne();
    await waitFor(() => expect(screen.getByText("Testalbum")).toBeTruthy());

    fireEvent.click(screen.getByTitle("Verknüpfung entfernen"));

    await waitFor(() => expect(deleteMock).toHaveBeenCalled());
    await waitFor(() => expect(hatAlbumGroupInvalidiert(spion)).toBe(true));
  });
});

describe("AlbumsOverview: Gruppen-Cache nach Umbenennen", () => {
  it("invalidiert die Gruppenvorschau, sobald umbenannt wurde", async () => {
    const spion = zeichne();
    await waitFor(() => expect(screen.getByText("Testalbum")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/ }));
    const feld = await screen.findByDisplayValue("Testalbum");
    fireEvent.change(feld, { target: { value: "Neuer Name" } });
    fireEvent.keyDown(feld, { key: "Enter" });

    await waitFor(() => expect(renameMock).toHaveBeenCalled());
    await waitFor(() => expect(hatAlbumGroupInvalidiert(spion)).toBe(true));
  });

  it("invalidiert die Gruppenvorschau AUCH, wenn das Umbenennen wirft (#110, Nacharbeit 2, KLEIN Fund 4)", async () => {
    // `handleRename` invalidiert schon seit #79 im `finally`-Block — dieser
    // Test haelt genau das fest, statt es nur zu behaupten.
    renameMock.mockRejectedValue({ message: "Der Name gehört bereits zu einer anderen Gruppe." });
    const spion = zeichne();
    await waitFor(() => expect(screen.getByText("Testalbum")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/ }));
    const feld = await screen.findByDisplayValue("Testalbum");
    fireEvent.change(feld, { target: { value: "Neuer Name" } });
    fireEvent.keyDown(feld, { key: "Enter" });

    await waitFor(() => expect(renameMock).toHaveBeenCalled());
    await waitFor(() => expect(hatAlbumGroupInvalidiert(spion)).toBe(true));
  });
});

describe("AlbumsOverview: Cache nach EINZEL-Entfernen eines verwaisten Albums (Nacharbeit 1, #123, Blindpruefer W4)", () => {
  it("invalidiert managed-albums, matches UND die Gruppenvorschau, nicht nur die Gruppenvorschau allein", async () => {
    albenMock.mockResolvedValue([
      { ...ALBUM, id: "gesund", owner_account_id: "konto-1" },
      {
        ...ALBUM,
        id: "verwaist",
        album_name: "Testalbum (verwaist)",
        owner_account_id: "konto-tot",
        owner_account_missing: true,
      },
    ]);
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );
    const spion = zeichne();
    await waitFor(() => expect(screen.getByText("Testalbum")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: /Dieses verwaiste Album entfernen/i }));

    await waitFor(() => expect(deleteMock).toHaveBeenCalledWith("verwaist"));
    await waitFor(() => expect(hatQueryInvalidiert(spion, "managed-albums")).toBe(true));
    expect(hatQueryInvalidiert(spion, "matches")).toBe(true);
    expect(hatAlbumGroupInvalidiert(spion)).toBe(true);
  });
});
