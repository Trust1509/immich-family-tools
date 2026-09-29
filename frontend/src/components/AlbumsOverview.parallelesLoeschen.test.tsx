// Paralleles Entfernen einer Gruppe (#123, #121 Punkt 1, Owner-Entscheid
// 29.09.2026).
//
// `handleDelete` schleifte bisher NACHEINANDER ueber `group.albums`, mit
// `await` je Album. Seit #101 wartet `DELETE /api/sync/albums/{id}` am
// Albumschloss GENAU DIESES Albums (`sync_service._album_schloss`, ein
// Schloss je Album-ID, keins ueber die Gruppe) — ein sequenzieller Lauf lief
// deshalb einem laufenden Abgleich unnoetig hinterher: Haelt ein Refresh das
// Schloss von Album 2, wartete in der Schleife auch Album 1 VOR Album 2, und
// Alben 3/4 kamen erst danach dran, obwohl ihr eigenes Schloss die ganze Zeit
// frei war (Zeitmessung dazu in Issue #121, hier nicht wiederholt — nicht
// selbst nachgemessen, docs/agents/lehren.md §46).
//
// Diese Datei prueft NUR die Nebenlaeufigkeit selbst — dass alle DELETEs
// GESTARTET sind, bevor das erste antwortet (`docs/agents/lehren.md` §40: eine
// Probe, die nur auf das Endergebnis wartet, uebersieht den toten
// Zwischenzustand "laeuft parallel" und waere mit einer sequenziellen
// Schleife genauso gruen). Der Beweis braucht deshalb einen Mock, der HAENGT,
// bis der Test selbst freigibt.
//
// Alle Daten erfunden; das Repo ist oeffentlich.
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import AlbumsOverview from "./AlbumsOverview";
import { LanguageProvider } from "../i18n";
import { SPEICHER_SCHLUESSEL } from "../test-konstanten";

function album(overrides: Record<string, unknown>) {
  return {
    id: "album",
    match_id: "m",
    album_id: "immich",
    album_name: "Grossfamilie",
    group_id: "gruppe-gross",
    owner_account_id: "konto",
    person_refs: [],
    linked_match_ids: [],
    created_at: "2026-01-01T00:00:00+00:00",
    last_synced_at: "2026-01-01T00:00:00+00:00",
    total_assets: 1,
    ...overrides,
  };
}

// VIER Alben in EINER Gruppe — nur damit zeigt sich ein sequenzieller
// Rueckbau ueberhaupt: Bei zwei Alben waere "erst nach dem ersten kommt das
// zweite" kaum von "beide laufen gleichzeitig" zu unterscheiden.
const VIER_ALBEN = ["a1", "a2", "a3", "a4"].map((id) =>
  album({ id, owner_account_id: `konto-${id}` })
);

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

beforeEach(() => {
  vi.clearAllMocks();
  try {
    localStorage.setItem(SPEICHER_SCHLUESSEL, "de");
  } catch {
    /* in dieser Umgebung nicht zwingend vorhanden */
  }
  albenMock.mockResolvedValue(VIER_ALBEN);
  autoSyncGet.mockResolvedValue({ enabled: false, time: "01:00" });
  renameMock.mockResolvedValue([]);
  refreshMock.mockResolvedValue([]);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function rendern() {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <LanguageProvider>
        <AlbumsOverview />
      </LanguageProvider>
    </QueryClientProvider>
  );
}

describe("AlbumsOverview: handleDelete entfernt eine Gruppe PARALLEL", () => {
  it("startet alle vier DELETEs, bevor auch nur eines geantwortet hat", async () => {
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );

    // Jeder Aufruf haengt an seiner EIGENEN, noch nicht aufgeloesten Zusage.
    // Eine sequenzielle Schleife (`for...of` mit `await`) koennte den ZWEITEN
    // Aufruf gar nicht erst absetzen, solange der erste haengt — genau das
    // ist der tote Zwischenzustand, den diese Probe erzwingt statt bloss
    // abzuwarten (§40/§44 aus `docs/agents/lehren.md`).
    const geloest: Array<() => void> = [];
    deleteMock.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          geloest.push(() => resolve());
        })
    );

    await rendern();
    await waitFor(() => expect(screen.getByText("Grossfamilie")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: /Verknüpfung entfernen/i }));

    // Alle VIER DELETEs sind angekommen, OHNE dass einer beantwortet wurde —
    // das waere mit einer sequenziellen Schleife nicht der Fall: Dort stuende
    // hier genau EIN Aufruf, weil der `await` im Schleifenkoerper den
    // naechsten erst nach der Antwort des vorigen absetzt.
    await waitFor(() => expect(deleteMock).toHaveBeenCalledTimes(4));
    expect(deleteMock).toHaveBeenCalledWith("a1");
    expect(deleteMock).toHaveBeenCalledWith("a2");
    expect(deleteMock).toHaveBeenCalledWith("a3");
    expect(deleteMock).toHaveBeenCalledWith("a4");

    // Erst jetzt loesen wir alle vier auf — der Knopf darf danach wieder
    // bedienbar sein (Beweis, dass `handleDelete` wirklich zu Ende kommt,
    // nicht nur, dass es startet).
    geloest.forEach((fn) => fn());
    await waitFor(() =>
      expect(
        (
          screen.getByRole("button", {
            name: /Verknüpfung entfernen/i,
          }) as HTMLButtonElement
        ).disabled
      ).toBe(false)
    );
  });

  it("wartet trotzdem auf ALLE Antworten, bevor die Liste neu geladen wird", async () => {
    // Gegenprobe zur Parallelitaet: `Promise.all` darf nicht vorzeitig
    // zurueckkehren, nur weil EIN DELETE schon fertig ist.
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );

    let spaetesFreigeben: () => void = () => {};
    deleteMock.mockImplementation((id: string) => {
      if (id === "a4") {
        return new Promise<void>((resolve) => {
          spaetesFreigeben = resolve;
        });
      }
      return Promise.resolve();
    });

    await rendern();
    await waitFor(() => expect(screen.getByText("Grossfamilie")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: /Verknüpfung entfernen/i }));
    await waitFor(() => expect(deleteMock).toHaveBeenCalledTimes(4));

    // Drei von vier sind fertig, das vierte haengt noch — der Knopf zeigt
    // weiterhin "wird geloescht", die Liste ist noch nicht neu geladen
    // (`albenMock` blieb bei einem Aufruf: dem allerersten Laden).
    await new Promise((r) => setTimeout(r, 20));
    expect(
      (screen.getByRole("button", { name: /Verknüpfung entfernen/i }) as HTMLButtonElement).disabled
    ).toBe(true);
    expect(albenMock).toHaveBeenCalledTimes(1);

    spaetesFreigeben();
    await waitFor(() => expect(albenMock.mock.calls.length).toBeGreaterThan(1));
  });

  it("entfernt die drei uebrigen Alben trotzdem, UND macht den einen Fehlschlag sichtbar (Nacharbeit 1, #123, alle drei Stimmen)", async () => {
    // Wie schon bei der sequenziellen Fassung: ein einzelner Fehlschlag darf
    // die anderen drei nicht verhindern — `Promise.allSettled`, nicht ein
    // `try` um den ganzen Block. NEU seit Nacharbeit 1: Der Fehlschlag darf
    // dabei nicht mehr STILL verschluckt werden (er war es bis hierher, siehe
    // `.catch(() => {})` je Aufruf in der Vorfassung von `handleDelete`) — er
    // muss als sichtbarer, uebersetzter Text auf der Karte stehen.
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );
    deleteMock.mockImplementation((id: string) =>
      id === "a2" ? Promise.reject(new Error("kaputt")) : Promise.resolve()
    );

    await rendern();
    await waitFor(() => expect(screen.getByText("Grossfamilie")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: /Verknüpfung entfernen/i }));

    await waitFor(() => expect(deleteMock).toHaveBeenCalledTimes(4));
    await waitFor(() =>
      expect(
        (
          screen.getByRole("button", {
            name: /Verknüpfung entfernen/i,
          }) as HTMLButtonElement
        ).disabled
      ).toBe(false)
    );

    // Die sichtbare Meldung: 1 von 4 Eintraegen konnte nicht entfernt werden.
    expect(screen.getByText("1 von 4 Einträgen konnten nicht entfernt werden.")).toBeTruthy();
  });

  it("zeigt KEINE Fehlermeldung, wenn alle vier DELETEs gelingen", async () => {
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );
    deleteMock.mockResolvedValue(undefined);

    await rendern();
    await waitFor(() => expect(screen.getByText("Grossfamilie")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: /Verknüpfung entfernen/i }));

    await waitFor(() => expect(deleteMock).toHaveBeenCalledTimes(4));
    await waitFor(() =>
      expect(
        (
          screen.getByRole("button", {
            name: /Verknüpfung entfernen/i,
          }) as HTMLButtonElement
        ).disabled
      ).toBe(false)
    );

    expect(screen.queryByText(/konnte.*nicht entfernt werden/)).toBeNull();
  });
});
