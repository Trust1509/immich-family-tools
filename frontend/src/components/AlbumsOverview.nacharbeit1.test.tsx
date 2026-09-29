// Nacharbeit 1 zu #123 — vier Funde des Panels (Gegenpruefer G1/G3,
// Blindpruefer W1/W2, alle drei Stimmen), jeweils mit eigenem Test:
//
// 1./2. `groupAlbums` nahm Anzeigename, Besitzerzeile UND die Vorbelegung des
//    Umbenennen-Feldes bislang immer vom ERSTEN Album der Gruppe — auch wenn
//    das ein verwaistes war. Nach einem erfolgreichen Umbenennen des
//    gesunden Geschwisters zeigte die Karte weiter den ALTEN Namen, und ein
//    Enter ohne jede Aenderung benannte lautlos zurueck. Jetzt wird das
//    ERSTE GESUNDE Album bevorzugt.
// 3. Die Umbenennen-Schleife lief bislang ueber `gesundeAlben`, einer beim
//    LADEN des Tabs berechneten Liste. Wird ein Konto zwischen Laden und
//    Klick in einem anderen Tab geloescht, lehnt der Server GENAU DIESES
//    Album mit `err_owner_account_not_found` ab — und die Schleife brach bis
//    hierher komplett ab, statt das eine Album zu ueberspringen.
// 4. Der Markierungstext "keine Person"/"eine Person" wurde aus der
//    ZUSAMMENGEFUEHRTEN Personenliste der Gruppe gewaehlt, nicht aus den
//    einzelnen markierten Alben — beide Texte konnten so verschwinden oder
//    den falschen anzeigen.
//
// Alle Daten erfunden; das Repo ist oeffentlich.
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import AlbumsOverview from "./AlbumsOverview";
import { LanguageProvider } from "../i18n";
import { SPEICHER_SCHLUESSEL } from "../test-konstanten";
import { ApiError } from "../api/client";

function album(overrides: Record<string, unknown>) {
  return {
    id: "album",
    match_id: "m",
    album_id: "immich",
    album_name: "Gruppe",
    group_id: "gruppe-1",
    owner_account_id: "konto",
    person_refs: [
      {
        account_id: "konto",
        person_id: "person-1",
        person_name: "Person Eins",
        account_name: "Konto Eins",
        account_color: "#111111",
      },
      {
        account_id: "konto-zwei",
        person_id: "person-2",
        person_name: "Person Zwei",
        account_name: "Konto Zwei",
        account_color: "#222222",
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

const { albenMock, autoSyncGet, refreshMock, renameMock, deleteMock } = vi.hoisted(() => ({
  albenMock: vi.fn(),
  autoSyncGet: vi.fn(),
  refreshMock: vi.fn(),
  renameMock: vi.fn(),
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

beforeEach(() => {
  vi.clearAllMocks();
  try {
    localStorage.setItem(SPEICHER_SCHLUESSEL, "de");
  } catch {
    /* in dieser Umgebung nicht zwingend vorhanden */
  }
  autoSyncGet.mockResolvedValue({ enabled: false, time: "01:00" });
  refreshMock.mockResolvedValue([]);
  deleteMock.mockResolvedValue(undefined);
  renameMock.mockResolvedValue([
    { id: "l", timestamp: "", action: "rename_album", details: "", status: "success" },
  ]);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function rendern(text: string) {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <LanguageProvider>
        <AlbumsOverview />
      </LanguageProvider>
    </QueryClientProvider>
  );
  await waitFor(() => expect(screen.getAllByText(text).length).toBeGreaterThan(0));
}

describe("AlbumsOverview: Anzeigename/Besitzerzeile/Vorbelegung vom ERSTEN GESUNDEN Album (Nacharbeit 1, #123, Gegenpruefer G1, Blindpruefer W1, WICHTIG)", () => {
  function verwaistesAlbumZuerst() {
    return [
      album({
        id: "verwaist",
        album_name: "Alt",
        owner_account_id: "konto-tot",
        owner_account_missing: true,
        person_refs: [],
      }),
      album({
        id: "gesund",
        album_name: "Neu",
        owner_account_id: "konto-lebt",
        owner_account_missing: false,
        person_refs: [
          {
            account_id: "konto-lebt",
            person_id: "person-x",
            person_name: "Person X",
            account_name: "Konto Lebt",
            account_color: "#333333",
          },
        ],
      }),
    ];
  }

  it("zeigt Titel und Besitzer des GESUNDEN Albums, obwohl das verwaiste in der Liste vorn steht", async () => {
    albenMock.mockResolvedValue(verwaistesAlbumZuerst());
    await rendern("Neu");

    // Die KARTENUEBERSCHRIFT traegt den Namen des gesunden Albums — "Alt"
    // darf dort nicht stehen. ("Alt" taucht durchaus noch woanders auf: in
    // der Einzelentfernungs-Zeile fuer das verwaiste Album, die zurecht
    // dessen EIGENEN Namen zeigt — deshalb hier gezielt die Ueberschrift,
    // nicht `queryByText`.)
    expect(screen.getByRole("heading", { name: "Neu" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Alt" })).toBeNull();
    // Die Besitzer-ZEILE nennt den lebenden Besitzer, nicht die Markierung.
    expect(screen.getAllByText(/Konto Lebt/).length).toBeGreaterThan(0);
  });

  it("legt das Umbenennen-Feld mit dem Namen des GESUNDEN Albums vor, nicht des verwaisten", async () => {
    albenMock.mockResolvedValue(verwaistesAlbumZuerst());
    await rendern("Neu");

    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/i }));
    expect(screen.getByDisplayValue("Neu")).toBeTruthy();
    expect(screen.queryByDisplayValue("Alt")).toBeNull();
  });

  it("Enter OHNE Aenderung benennt NICHT zurueck (Folgefund Blindpruefer W2)", async () => {
    albenMock.mockResolvedValue(verwaistesAlbumZuerst());
    await rendern("Neu");

    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/i }));
    const feld = await screen.findByDisplayValue("Neu");
    fireEvent.keyDown(feld, { key: "Enter" });

    await new Promise((r) => setTimeout(r, 10));
    expect(renameMock).not.toHaveBeenCalled();
  });
});

describe("AlbumsOverview: Umbenennen ueberspringt ein ZWISCHENZEITLICH verwaistes Album, statt abzubrechen (Nacharbeit 1, #123, Gegenpruefer G3, WICHTIG)", () => {
  function dreiAlben() {
    return [
      album({ id: "a", album_name: "Album A", owner_account_id: "konto-a" }),
      album({ id: "b", album_name: "Album B", owner_account_id: "konto-b" }),
      album({ id: "c", album_name: "Album C", owner_account_id: "konto-c" }),
    ];
  }

  it("benennt A und C um, ueberspringt B (404 err_owner_account_not_found) und nennt B im Hinweis", async () => {
    albenMock.mockResolvedValue(dreiAlben());
    renameMock.mockImplementation(async (id: string) => {
      if (id === "b") {
        throw new ApiError("Owner-Account nicht gefunden", 404, "err_owner_account_not_found");
      }
      return [
        { id: `log-${id}`, timestamp: "", action: "rename_album", details: "", status: "success" },
      ];
    });

    await rendern("Album A");
    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/i }));
    const feld = await screen.findByDisplayValue("Album A");
    fireEvent.change(feld, { target: { value: "Neuer Name" } });
    fireEvent.keyDown(feld, { key: "Enter" });

    // Die Schleife laeuft trotz des Fehlschlags bei B bis zum Ende: ALLE
    // DREI Alben werden angefahren, nicht nur A.
    await waitFor(() => expect(renameMock).toHaveBeenCalledTimes(3));
    expect(renameMock).toHaveBeenCalledWith("a", "Neuer Name");
    expect(renameMock).toHaveBeenCalledWith("c", "Neuer Name");

    // Der sichtbare Hinweis nennt eine ANZAHL, nicht mehr die Namen
    // (Nacharbeit 2, #123, Blindpruefer K8, Gegenpruefer K6: Albumnamen
    // innerhalb einer Gruppe sind meist gleich, "A, A" sagt nichts) — hier
    // 1 von 3 angefahrenen (gesunden) Alben.
    await waitFor(() =>
      expect(
        screen.getByText(
          "Übersprungen, weil das Besitzerkonto inzwischen gelöscht ist: 1 von 3 Alben."
        )
      ).toBeTruthy()
    );

    // A und C sind erfolgreich, das Feld schliesst sich.
    await waitFor(() => expect(screen.queryByDisplayValue("Neuer Name")).toBeNull());
  });

  it("bricht bei einem ANDEREN Fehler weiterhin ab (kein Ueberspringen)", async () => {
    // Nacharbeit 2 (#123, Blindpruefer K1, Gegenpruefer K4): Die vorige
    // Fassung nutzte hier `err_album_name_in_use` (409) — einen Schluessel,
    // den der Server seit #98 nicht mehr erzeugt (`rename_managed_album`
    // prueft die Namenskollision nicht mehr). Ein REAL erzeugter Schluessel
    // gehoert hierher, und zwar bewusst einer, der ebenfalls ein 404 ist:
    // `err_managed_album_not_found` — damit die Probe eine Mutation faengt,
    // die faelschlich JEDEN 404 uebersprringt (etwa `error.status === 404`
    // statt des Schluesselvergleichs `error.key ===
    // "err_owner_account_not_found"`). Ohne diesen Test waere so eine
    // Mutation unsichtbar, weil beide Schluessel denselben HTTP-Status
    // tragen.
    albenMock.mockResolvedValue(dreiAlben());
    renameMock.mockImplementation(async (id: string) => {
      if (id === "b") {
        throw new ApiError("Verwaltetes Album nicht gefunden", 404, "err_managed_album_not_found");
      }
      return [
        { id: `log-${id}`, timestamp: "", action: "rename_album", details: "", status: "success" },
      ];
    });

    await rendern("Album A");
    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/i }));
    const feld = await screen.findByDisplayValue("Album A");
    fireEvent.change(feld, { target: { value: "Neuer Name" } });
    fireEvent.keyDown(feld, { key: "Enter" });

    // A gelingt, B wirft einen ANDEREN Fehler als
    // `err_owner_account_not_found` (auch wenn es ebenfalls ein 404 ist) —
    // die Schleife bricht ab, C wird gar nicht mehr angefahren.
    await waitFor(() => expect(renameMock).toHaveBeenCalledTimes(2));
    expect(renameMock).not.toHaveBeenCalledWith("c", expect.anything());
    expect(screen.getByText(/Verwaltetes Album nicht gefunden/)).toBeTruthy();
  });
});

describe("AlbumsOverview: Markierungstext aus den ALBEN SELBST, nicht aus der zusammengefuehrten Liste (Nacharbeit 1, #123, alle drei Stimmen)", () => {
  it("(0 Personen + 2 Personen): zeigt NUR 'Keine Person mehr verknüpft'", async () => {
    albenMock.mockResolvedValue([
      album({
        id: "leer",
        album_name: "Sippe",
        owner_account_id: "k1",
        too_few_people: true,
        person_refs: [],
      }),
      album({
        id: "voll",
        album_name: "Sippe",
        owner_account_id: "k2",
        too_few_people: false,
        person_refs: [
          {
            account_id: "k2",
            person_id: "p1",
            person_name: "P1",
            account_name: "K2",
            account_color: "#111",
          },
          {
            account_id: "k3",
            person_id: "p2",
            person_name: "P2",
            account_name: "K3",
            account_color: "#222",
          },
        ],
      }),
    ]);
    await rendern("Sippe");

    expect(screen.getByText("Keine Person mehr verknüpft")).toBeTruthy();
    expect(screen.queryByText("Nur noch eine Person")).toBeNull();
  });

  it("(0 Personen + 1 Person): zeigt BEIDE Texte", async () => {
    albenMock.mockResolvedValue([
      album({
        id: "leer",
        album_name: "Sippe",
        owner_account_id: "k1",
        too_few_people: true,
        person_refs: [],
      }),
      album({
        id: "eins",
        album_name: "Sippe",
        owner_account_id: "k2",
        too_few_people: true,
        person_refs: [
          {
            account_id: "k2",
            person_id: "p1",
            person_name: "P1",
            account_name: "K2",
            account_color: "#111",
          },
        ],
      }),
    ]);
    await rendern("Sippe");

    // BEIDE Texte stehen im selben Markierungs-`<span>`, durch " · " getrennt
    // — deshalb hier ein RegExp-Matcher (Teiltreffer) statt der exakten
    // Zeichenkette, die nur bei EINEM der beiden Texte allein passt.
    expect(screen.getByText(/Keine Person mehr verknüpft/)).toBeTruthy();
    expect(screen.getByText(/Nur noch eine Person/)).toBeTruthy();
  });
});
