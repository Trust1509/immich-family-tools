// Ein Album ohne lebenden Besitzer wird SICHTBAR markiert (Text, nicht nur
// Farbe) — die Markierung selbst ist Owner-Entscheid 28.09.2026 (#99, #112).
//
// WAS DIE SPERRE TUT, ist dagegen eine TECHNISCHE Entscheidung des
// Hauptagenten (Nacharbeit 1, nicht der Owner — eine fruehere Fassung dieser
// Datei nannte sie faelschlich "Owner-Entscheid"): UMBENENNEN sperrt die
// GANZE Gruppe (sonst eine halb umbenannte Gruppe mit zwei Namen). Der
// ABGLEICH sperrt NICHT — er laeuft wie der Auto-Sync nur fuer Alben mit
// lebendem Besitzer und UEBERSPRINGT die verwaisten, mit einem sichtbaren
// Hinweis statt eines Fehlereintrags je Klick. Entfernen bleibt immer
// moeglich. "Nur noch eine Person"/"keine Person mehr" markiert, sperrt aber
// fuer sich allein nichts.
//
// Alle Daten erfunden; das Repo ist oeffentlich.
import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
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

const { albenMock, autoSyncGet, refreshMock, renameMock } = vi.hoisted(() => ({
  albenMock: vi.fn(),
  autoSyncGet: vi.fn(),
  refreshMock: vi.fn(),
  renameMock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  api: {
    sync: {
      albums: albenMock,
      refreshAlbum: refreshMock,
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
  autoSyncGet.mockResolvedValue({ enabled: false, time: "01:00" });
  refreshMock.mockResolvedValue([]);
  renameMock.mockResolvedValue([
    { id: "l", timestamp: "", action: "rename_album", details: "", status: "success" },
  ]);
});

async function rendern(text: string, qc?: QueryClient) {
  const client = qc ?? new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <LanguageProvider>
        <AlbumsOverview />
      </LanguageProvider>
    </QueryClientProvider>
  );
  await waitFor(() => expect(screen.getAllByText(text).length).toBeGreaterThan(0));
  return client;
}

describe("AlbumsOverview: einzelnes verwaistes Album (nichts Gesundes uebrig)", () => {
  it("zeigt die Markierung als TEXT und sperrt Umbenennen", async () => {
    albenMock.mockResolvedValue([album({ owner_account_missing: true })]);
    await rendern("Verwaistes Album");

    expect(screen.getByText("Besitzerkonto gelöscht")).toBeTruthy();

    const umbenennenKnopf = screen.getByRole("button", {
      name: /Album umbenennen/i,
    }) as HTMLButtonElement;
    expect(umbenennenKnopf.disabled).toBe(true);
  });

  it("der Abgleich-Knopf ist deaktiviert, weil kein gesundes Album uebrig ist", async () => {
    // Nicht "gesperrt" im Sinne der Regel — es gibt schlicht nichts, das der
    // Klick abgleichen koennte. Der Unterschied zaehlt: Bei einer GEMISCHTEN
    // Gruppe bleibt derselbe Knopf aktiv (naechste Beschreibung unten).
    albenMock.mockResolvedValue([album({ owner_account_missing: true })]);
    await rendern("Verwaistes Album");

    const syncKnopf = screen.getByRole("button", {
      name: /Jetzt synchronisieren/i,
    }) as HTMLButtonElement;
    expect(syncKnopf.disabled).toBe(true);
  });

  it("laesst Entfernen weiterhin zu", async () => {
    albenMock.mockResolvedValue([album({ owner_account_missing: true })]);
    await rendern("Verwaistes Album");

    const entfernenKnopf = screen.getByRole("button", {
      name: /Verknüpfung entfernen/i,
    }) as HTMLButtonElement;
    expect(entfernenKnopf.disabled).toBe(false);
  });

  it("sperrt NICHT bei lebendem Besitzer, auch mit nur einer Person", async () => {
    albenMock.mockResolvedValue([album({ owner_account_missing: false, too_few_people: true })]);
    await rendern("Verwaistes Album");

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

  it("zeigt bei NULL verbleibenden Personen einen eigenen Text", async () => {
    albenMock.mockResolvedValue([
      album({ owner_account_missing: false, too_few_people: true, person_refs: [] }),
    ]);
    await rendern("Verwaistes Album");

    expect(screen.getByText("Keine Person mehr verknüpft")).toBeTruthy();
    expect(screen.queryByText("Nur noch eine Person")).toBeNull();
  });

  it("zeigt keine Markierung, wenn nichts fehlt", async () => {
    albenMock.mockResolvedValue([album({})]);
    await rendern("Verwaistes Album");

    expect(screen.queryByText("Besitzerkonto gelöscht")).toBeNull();
    expect(screen.queryByText("Nur noch eine Person")).toBeNull();
  });
});

describe("AlbumsOverview: gemischte Gruppe (ein gesundes, ein verwaistes Album)", () => {
  // Nacharbeit 1 (Blindpruefer): Diese Form war bis hierher UNGETESTET — ein
  // `every` statt `some` beim Sperren, oder eine Pruefung, die nur das ERSTE
  // Album der Gruppe ansieht, waeren hier still gruen geblieben.
  function gemischteGruppe() {
    return [
      album({ id: "gesund", album_name: "Gemischt", owner_account_id: "konto-lebt" }),
      album({
        id: "verwaist",
        album_name: "Gemischt",
        owner_account_id: "konto-tot",
        owner_account_missing: true,
      }),
    ];
  }

  it("Umbenennen bleibt fuer die GANZE Gruppe gesperrt", async () => {
    albenMock.mockResolvedValue(gemischteGruppe());
    await rendern("Gemischt");

    const umbenennenKnopf = screen.getByRole("button", {
      name: /Album umbenennen/i,
    }) as HTMLButtonElement;
    expect(umbenennenKnopf.disabled).toBe(true);
  });

  it("Abgleichen bleibt aktiv und ruft NUR das gesunde Album auf", async () => {
    albenMock.mockResolvedValue(gemischteGruppe());
    await rendern("Gemischt");

    const syncKnopf = screen.getByRole("button", {
      name: /Jetzt synchronisieren/i,
    }) as HTMLButtonElement;
    expect(syncKnopf.disabled).toBe(false);

    fireEvent.click(syncKnopf);
    await waitFor(() => expect(refreshMock).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 10));

    expect(refreshMock).toHaveBeenCalledWith("gesund");
    expect(refreshMock).not.toHaveBeenCalledWith("verwaist");
    expect(refreshMock).toHaveBeenCalledTimes(1);
  });

  it("'Alle synchronisieren' ruft ebenfalls NUR das gesunde Album auf", async () => {
    albenMock.mockResolvedValue(gemischteGruppe());
    await rendern("Gemischt");

    fireEvent.click(screen.getByRole("button", { name: /Alle synchronisieren/i }));
    await waitFor(() => expect(refreshMock).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 10));

    expect(refreshMock).toHaveBeenCalledWith("gesund");
    expect(refreshMock).not.toHaveBeenCalledWith("verwaist");
    expect(refreshMock).toHaveBeenCalledTimes(1);
  });

  it("zeigt einen Hinweis, dass verwaiste Alben uebersprungen werden", async () => {
    albenMock.mockResolvedValue(gemischteGruppe());
    await rendern("Gemischt");

    expect(screen.getByText(/Verwaiste Alben werden beim Abgleich übersprungen/)).toBeTruthy();
  });

  it("schliesst ein offenes Umbenennen-Feld, sobald die Sperre eintritt", async () => {
    // Gegenpruefer-Fund (Nacharbeit 1): Ohne diesen Schutz blieb ein bereits
    // geoeffnetes Eingabefeld offen, wenn das Konto in einem anderen Tab
    // geloescht wurde und die Liste neu laedt — Enter benannte dann nur das
    // gesunde Album um, die Gruppe hatte danach zwei Namen.
    const gesundeGruppe = [album({ id: "gesund", album_name: "Gemischt" })];
    albenMock.mockResolvedValue(gesundeGruppe);
    const qc = await rendern("Gemischt");

    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/i }));
    const feld = screen.getByRole("textbox", { name: /Album umbenennen/i }) as HTMLInputElement;
    fireEvent.change(feld, { target: { value: "Neuer Name" } });

    // Konto wird "in einem anderen Tab" geloescht — die Liste liefert jetzt
    // die verwaiste Form, und die Abfrage wird ungueltig gemacht.
    albenMock.mockResolvedValue(gemischteGruppe());
    await act(async () => {
      await qc.invalidateQueries({ queryKey: ["managed-albums"] });
    });
    // Der Abgleich-Hinweis ist eindeutig (nur EIN Element traegt ihn), anders
    // als "Besitzerkonto gelöscht", das jetzt sowohl in der Markierung als
    // auch in der Besitzer-Zeile steht.
    await waitFor(() =>
      expect(screen.getByText(/Verwaiste Alben werden beim Abgleich übersprungen/)).toBeTruthy()
    );

    expect(screen.queryByRole("textbox", { name: /Album umbenennen/i })).toBeNull();

    // Selbst wenn noch ein Enter auf dem alten Feld ankaeme, darf nichts
    // umbenannt worden sein.
    fireEvent.keyDown(feld, { key: "Enter" });
    await new Promise((r) => setTimeout(r, 10));
    expect(renameMock).not.toHaveBeenCalled();
  });
});
