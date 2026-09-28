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

const { albenMock, autoSyncGet, renameMock, refreshMock } = vi.hoisted(() => ({
  albenMock: vi.fn(),
  autoSyncGet: vi.fn(),
  renameMock: vi.fn(),
  refreshMock: vi.fn(),
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

  it("schickt den getippten Namen an jedes Album der Gruppe", async () => {
    // Gemessen vom Blindpruefer: Zwischen Eingabefeld und HTTP-Koerper hielt
    // NICHTS. Der getippte Name durch einen Festwert ersetzt — und alle 118
    // Proben blieben gruen. Die Aufrufzahl allein prueft die Schleife, nicht
    // die Uebergabe.
    renameMock.mockResolvedValue([]);

    await umbenennen("Ein ganz neuer Name");
    await waitFor(() => expect(renameMock).toHaveBeenCalledTimes(2));

    expect(renameMock).toHaveBeenCalledWith("album-eins", "Ein ganz neuer Name");
    expect(renameMock).toHaveBeenCalledWith("album-zwei", "Ein ganz neuer Name");
  });

  it("schneidet Leerraum ab, bevor der Name hinausgeht", async () => {
    // Die Gegenprobe zum `trim()`: Sonst waere „ Fest " ein anderer Name als
    // „Fest", und die Gruppe zerfiele beim Umbenennen in zwei.
    renameMock.mockResolvedValue([]);

    await umbenennen("   Umrandeter Name   ");
    await waitFor(() => expect(renameMock).toHaveBeenCalledTimes(2));

    expect(renameMock).toHaveBeenCalledWith("album-eins", "Umrandeter Name");
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

// ---------------------------------------------------------------------------
// Drei Funde des Fremdpruefers an der gerebasten Fassung. Alle drei betreffen
// nicht das Umbenennen selbst, sondern was der Nutzer DANACH tun kann und
// sieht — genau die Stelle, an der eine Funktion "da" ist und trotzdem nicht
// benutzbar.
// ---------------------------------------------------------------------------

describe("Nach einem Teilausfall", () => {
  it("erreicht der zweite Versuch das zurueckgebliebene Album", async () => {
    // DER STAND NACH EINEM TEILAUSFALL: Album eins traegt den neuen Namen,
    // Album zwei noch den alten. Der Gruppenname wird vom ERSTEN Album
    // abgeleitet — mit dem alten Vergleich `nextName === group.album_name`
    // war der zweite Versuch deshalb ein Nullvorgang, und das
    // fehlgeschlagene Album liess sich NIE mehr nachziehen.
    albenMock.mockResolvedValue([{ ...GRUPPE[0], album_name: "Neuer Name" }, GRUPPE[1]]);
    renameMock.mockResolvedValue([]);

    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <LanguageProvider>
          <AlbumsOverview />
        </LanguageProvider>
      </QueryClientProvider>
    );
    await waitFor(() => expect(screen.getByText("Neuer Name")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/ }));
    // Der Nutzer bestaetigt denselben Namen noch einmal — die Wiederholung.
    const feld = await screen.findByDisplayValue("Neuer Name");
    fireEvent.keyDown(feld, { key: "Enter" });

    await waitFor(() => expect(renameMock).toHaveBeenCalledTimes(2));
    expect(renameMock.mock.calls.map((aufruf) => aufruf[0])).toContain("album-zwei");
  });

  it("bricht ab, wenn ALLE Alben den Namen schon tragen", async () => {
    // Die Gegenprobe zur Zeile darueber: Ohne sie waere die billigste Antwort
    // "immer umbenennen", und jedes Oeffnen-und-Bestaetigen des unveraenderten
    // Namens schickte zwei Anfragen nach Immich.
    albenMock.mockResolvedValue([
      { ...GRUPPE[0], album_name: "Gleicher Name" },
      { ...GRUPPE[1], album_name: "Gleicher Name" },
    ]);
    renameMock.mockResolvedValue([]);

    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <LanguageProvider>
          <AlbumsOverview />
        </LanguageProvider>
      </QueryClientProvider>
    );
    await waitFor(() => expect(screen.getByText("Gleicher Name")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/ }));
    const feld = await screen.findByDisplayValue("Gleicher Name");
    fireEvent.keyDown(feld, { key: "Enter" });

    // Das Feld schliesst sich, und NICHTS geht hinaus.
    await waitFor(() => expect(screen.queryByDisplayValue("Gleicher Name")).toBeNull());
    expect(renameMock).not.toHaveBeenCalled();
  });

  it("zeigt die schon gesammelten Eintraege, wenn ein spaeterer Aufruf wirft", async () => {
    // Ein WURF (HTTP-Fehler) ist etwas anderes als ein Fehler-Protokolleintrag:
    // Er springt aus der Schleife. Vorher standen `setLocalLogs` und die
    // Invalidierungen dahinter — der Nutzer sah nur den Fehlertext und nicht,
    // dass Album eins schon umbenannt WAR.
    //
    // Beispieltext: das zweite Album wurde zwischen Laden und Umbenennen
    // geloescht (404, `err_managed_album_not_found`) — ein Wurf, den es auch
    // nach #98 noch gibt. Die frühere Fassung nahm hier die Namenskollision
    // (409, `err_album_name_in_use`); die ist mit #98 entfernt und kann nicht
    // mehr auftreten.
    renameMock.mockImplementation(async (albumId: string) => {
      if (albumId === "album-zwei") {
        throw { message: "Managed Album nicht gefunden" };
      }
      return [
        {
          id: `log-${albumId}`,
          timestamp: "2026-01-03T00:00:00+00:00",
          action: "rename_album",
          details: `Eintrag zu ${albumId}`,
          status: "success",
        },
      ];
    });

    await umbenennen("Neuer Name");
    await waitFor(() => expect(renameMock).toHaveBeenCalledTimes(2));

    // BEIDES muss zu sehen sein: der Fehlertext UND der gelungene Eintrag.
    expect(await screen.findByText("Eintrag zu album-eins")).toBeTruthy();
    expect(screen.getByText(/Managed Album nicht gefunden/)).toBeTruthy();
  });
});

describe("Nach einem Sammellauf", () => {
  it("zeigt das Umbenennen sein eigenes Ergebnis", async () => {
    // Der Sammellauf legt fuer jede Gruppe ein Ergebnis ab, und das hatte
    // Vorrang, SOLANGE es im Zustand stand. Ein danach ausgeloestes
    // Umbenennen zeigte sein Ergebnis dadurch nirgends — auch kein
    // fehlerhaftes. Gemessen wird die Reihenfolge: erst sammeln, dann
    // umbenennen.
    // Je Album EIN Eintrag mit eigenem Text — zwei gleiche Texte waeren beim
    // Suchen nicht unterscheidbar, und die Karte steht fuer zwei Alben.
    refreshMock.mockImplementation(async (albumId: string) => [
      {
        id: `log-sammellauf-${albumId}`,
        timestamp: "2026-01-02T00:00:00+00:00",
        action: "refresh_album",
        details: `Sammellauf zu ${albumId}`,
        status: "success",
      },
    ]);
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

    fireEvent.click(screen.getByRole("button", { name: /Alle synchronisieren/ }));
    expect(await screen.findByText("Sammellauf zu album-eins")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/ }));
    const feld = await screen.findByDisplayValue("Testalbum");
    fireEvent.change(feld, { target: { value: "Neuer Name" } });
    fireEvent.keyDown(feld, { key: "Enter" });
    await waitFor(() => expect(renameMock).toHaveBeenCalledTimes(2));

    // DER KERN: Das Ergebnis des Umbenennens steht auf der Karte, samt dem
    // fehlgeschlagenen Eintrag.
    const fehler = await screen.findByText("Eintrag zu album-zwei");
    expect(fehler.className).toMatch(/red/);
    expect(screen.queryByText("Sammellauf zu album-eins")).toBeNull();
  });

  it("dreht der naechste Sammellauf den Vorrang zurueck", async () => {
    // Die Gegenprobe zur Zeile darueber, und der Waechter ueber die eigene
    // Loesung: „lokal hat ab jetzt immer Vorrang" waere die billigste Antwort
    // gewesen — und haette das Sammelergebnis fuer immer verdeckt. Gemessen
    // wird die umgekehrte Reihenfolge: erst umbenennen, dann sammeln.
    refreshMock.mockImplementation(async (albumId: string) => [
      {
        id: `log-sammellauf-${albumId}`,
        timestamp: "2026-01-04T00:00:00+00:00",
        action: "refresh_album",
        details: `Sammellauf zu ${albumId}`,
        status: "success",
      },
    ]);
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
    expect(await screen.findByText("Eintrag zu album-eins")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Alle synchronisieren/ }));

    expect(await screen.findByText("Sammellauf zu album-eins")).toBeTruthy();
    expect(screen.queryByText("Eintrag zu album-eins")).toBeNull();
  });

  it("zeigt auch ein einzelnes Synchronisieren sein eigenes Ergebnis", async () => {
    // Gemessen vom Blindprüfer an der ersten Nacharbeit: `setLokalZuletzt(true)`
    // aus `handleRefresh` entfernt → alle 125 Proben blieben grün. Der neue
    // Vorrang war ausschliesslich am Umbenennen gemessen, obwohl er für JEDE
    // lokale Handlung gilt.
    let lauf = 0;
    refreshMock.mockImplementation(async (albumId: string) => {
      lauf += 1;
      return [
        {
          id: `log-${lauf}-${albumId}`,
          timestamp: "2026-01-04T00:00:00+00:00",
          action: "refresh_album",
          details: lauf <= 2 ? `Sammellauf zu ${albumId}` : `Einzellauf zu ${albumId}`,
          status: "success",
        },
      ];
    });

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

    fireEvent.click(screen.getByRole("button", { name: /Alle synchronisieren/ }));
    expect(await screen.findByText("Sammellauf zu album-eins")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Jetzt synchronisieren/ }));

    expect(await screen.findByText("Einzellauf zu album-eins")).toBeTruthy();
    expect(screen.queryByText("Sammellauf zu album-eins")).toBeNull();
  });

  it("löscht ein gescheiterter Sammellauf das vorige Ergebnis nicht", async () => {
    // Werfen ALLE Auffrischungen einer Gruppe, ist der Sammel-Eintrag ein
    // LEERES Feld — nicht `undefined`. Es bekam damit den Vorrang, und
    // `SyncLogDisplay` zeigt für ein leeres Feld nichts: Die Karte stand leer
    // da, das Umbenenn-Ergebnis war spurlos weg (Fund des Blindprüfers). Dass
    // der Sammellauf seine Fehler schluckt, ist alt — das Löschen war neu.
    renameMock.mockImplementation(async (albumId: string) => [
      {
        id: `log-${albumId}`,
        timestamp: "2026-01-03T00:00:00+00:00",
        action: "rename_album",
        details: `Eintrag zu ${albumId}`,
        status: "success",
      },
    ]);
    refreshMock.mockRejectedValue(new Error("Immich antwortet nicht"));

    await umbenennen("Neuer Name");
    await waitFor(() => expect(renameMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Eintrag zu album-eins")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Alle synchronisieren/ }));

    // ZWEIMAL warten, und das ist der Beweis, nicht Umständlichkeit: Dass die
    // Attrappe zweimal gerufen wurde, heisst NICHT, dass der Sammellauf fertig
    // ist — `setBulkSyncState` und das Neuzeichnen kommen danach. Die
    // Zusicherung las sonst noch das Bild von vorher und blieb grün, obwohl
    // der Fehler drin war: gemessen 1 von 6 Läufen mit der Mutation
    // `bulkEntry ?? undefined`. Gewartet wird deshalb, bis der Knopf wieder
    // bedienbar ist — das passiert erst nach dem Ablegen des Ergebnisses.
    await waitFor(() => expect(refreshMock).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(
        (
          screen.getByRole("button", {
            name: /Alle synchronisieren/,
          }) as HTMLButtonElement
        ).disabled
      ).toBe(false)
    );

    // Die Karte behält, was sie hat, statt leer zu werden.
    expect(screen.getByText("Eintrag zu album-eins")).toBeTruthy();
  });
});
