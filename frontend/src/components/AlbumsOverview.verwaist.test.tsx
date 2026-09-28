// Owner-Entscheid 28.09.2026 (#99, #112): ein Album ohne lebenden Besitzer
// wird SICHTBAR markiert (Text, nicht nur Farbe) und sperrt Umbenennen und
// Abgleichen der GANZEN Gruppe — Entfernen bleibt moeglich. "Nur noch eine
// Person" markiert, sperrt aber fuer sich allein nichts.
//
// Alle Daten erfunden; das Repo ist oeffentlich.
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import AlbumsOverview from "./AlbumsOverview";
import { LanguageProvider } from "../i18n";
import { SPEICHER_SCHLUESSEL } from "../test-konstanten";

function album(overrides: Record<string, unknown>) {
  return {
    id: "album-verwaist",
    match_id: "m-1",
    album_id: "immich-1",
    album_name: "Verwaistes Album",
    group_id: "gruppe-verwaist",
    owner_account_id: "konto-tot",
    person_refs: [
      {
        account_id: "konto-lebt",
        person_id: "person-1",
        person_name: "Person Eins",
        account_name: "Konto Lebt",
        account_color: "#111111",
      },
    ],
    linked_match_ids: [],
    created_at: "2026-01-01T00:00:00+00:00",
    last_synced_at: "2026-01-01T00:00:00+00:00",
    total_assets: 1,
    owner_account_missing: false,
    too_few_people: false,
    ...overrides,
  };
}

const { albenMock, autoSyncGet } = vi.hoisted(() => ({
  albenMock: vi.fn(),
  autoSyncGet: vi.fn(),
}));

vi.mock("../api/client", () => ({
  api: {
    sync: { albums: albenMock, refreshAlbum: vi.fn(), deleteAlbum: vi.fn(), renameAlbum: vi.fn() },
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
  autoSyncGet.mockResolvedValue({ enabled: false, time: "01:00" });
});

async function rendern() {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <LanguageProvider>
        <AlbumsOverview />
      </LanguageProvider>
    </QueryClientProvider>
  );
  await waitFor(() => expect(screen.getByText("Verwaistes Album")).toBeTruthy());
}

describe("AlbumsOverview: verwaistes Album", () => {
  it("zeigt die Markierung als TEXT und sperrt Umbenennen und Abgleichen", async () => {
    albenMock.mockResolvedValue([album({ owner_account_missing: true })]);
    await rendern();

    expect(screen.getByText("Besitzerkonto gelöscht")).toBeTruthy();

    const umbenennenKnopf = screen.getByRole("button", {
      name: /Album umbenennen/i,
    }) as HTMLButtonElement;
    const syncKnopf = screen.getByRole("button", {
      name: /Jetzt synchronisieren/i,
    }) as HTMLButtonElement;
    expect(umbenennenKnopf.disabled).toBe(true);
    expect(syncKnopf.disabled).toBe(true);
  });

  it("laesst Entfernen weiterhin zu", async () => {
    albenMock.mockResolvedValue([album({ owner_account_missing: true })]);
    await rendern();

    const entfernenKnopf = screen.getByRole("button", {
      name: /Verknüpfung entfernen/i,
    }) as HTMLButtonElement;
    expect(entfernenKnopf.disabled).toBe(false);
  });

  it("sperrt NICHT bei lebendem Besitzer, auch mit nur einer Person", async () => {
    albenMock.mockResolvedValue([album({ owner_account_missing: false, too_few_people: true })]);
    await rendern();

    expect(screen.getByText("Nur noch eine Person")).toBeTruthy();
    const umbenennenKnopf = screen.getByRole("button", {
      name: /Album umbenennen/i,
    }) as HTMLButtonElement;
    const syncKnopf = screen.getByRole("button", {
      name: /Jetzt synchronisieren/i,
    }) as HTMLButtonElement;
    expect(umbenennenKnopf.disabled).toBe(false);
    expect(syncKnopf.disabled).toBe(false);
  });

  it("zeigt keine Markierung, wenn nichts fehlt", async () => {
    albenMock.mockResolvedValue([album({})]);
    await rendern();

    expect(screen.queryByText("Besitzerkonto gelöscht")).toBeNull();
    expect(screen.queryByText("Nur noch eine Person")).toBeNull();
  });
});
