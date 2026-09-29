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
    // ZWEI Personen als gesunder Regelfall (Nacharbeit 2: die Gruppen-Markierung
    // "zu wenige Personen" wird aus der ZUSAMMENGEFUEHRTEN Liste berechnet,
    // siehe `groupAlbums`/`tooFewPeople` — ein Standardalbum mit nur einer
    // Person haette jeden Test hier faelschlich als "zu wenige Personen"
    // markiert). Tests, die genau das pruefen wollen, ueberschreiben
    // `person_refs` gezielt.
    person_refs: [
      {
        account_id: "konto-lebt",
        person_id: "person-1",
        person_name: "Person Eins",
        account_name: "Konto Lebt",
        account_color: "#111111",
      },
      {
        account_id: "zwei",
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
  renameMock.mockResolvedValue([
    { id: "l", timestamp: "", action: "rename_album", details: "", status: "success" },
  ]);
  deleteMock.mockResolvedValue(undefined);
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
    albenMock.mockResolvedValue([
      album({
        owner_account_missing: false,
        too_few_people: true,
        person_refs: [
          {
            account_id: "konto-lebt",
            person_id: "person-1",
            person_name: "Person Eins",
            account_name: "Konto Lebt",
            account_color: "#111111",
          },
        ],
      }),
    ]);
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

  it("Umbenennen bleibt fuer die gemischte Gruppe moeglich (Owner-Entscheid 29.09.2026, #123)", async () => {
    // Rueckbau der Nacharbeit-2-Sperre: Der Knopf war hier bis #123 immer
    // deaktiviert, sobald IRGENDEIN Album der Gruppe verwaist war. Jetzt
    // sperrt nur noch eine GANZ verwaiste Gruppe (kein gesundes Album mehr),
    // siehe die eigene Beschreibung weiter unten.
    albenMock.mockResolvedValue(gemischteGruppe());
    await rendern("Gemischt");

    const umbenennenKnopf = screen.getByRole("button", {
      name: /Album umbenennen/i,
    }) as HTMLButtonElement;
    expect(umbenennenKnopf.disabled).toBe(false);
  });

  it("Umbenennen benennt nur das gesunde Album um und ueberspringt das verwaiste", async () => {
    // Nachweis (a) aus dem Bau-Brief zu #123: `renameAlbum` wird nur fuer
    // das Album mit lebendem Besitzer gerufen — das verwaiste wird gar
    // nicht erst angefahren (der Server wuerde es ohnehin mit 404
    // `err_owner_account_not_found` ablehnen, siehe
    // `test_umbenennen_fehlerwege.py`).
    albenMock.mockResolvedValue(gemischteGruppe());
    await rendern("Gemischt");

    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/i }));
    const feld = await screen.findByDisplayValue("Gemischt");
    fireEvent.change(feld, { target: { value: "Neuer Name" } });
    fireEvent.keyDown(feld, { key: "Enter" });

    await waitFor(() => expect(renameMock).toHaveBeenCalledTimes(1));
    expect(renameMock).toHaveBeenCalledWith("gesund", "Neuer Name");
    expect(renameMock).not.toHaveBeenCalledWith("verwaist", expect.anything());
  });

  it("laesst ein verwaistes Album einzeln entfernen, das gesunde bleibt (Owner-Entscheid 29.09.2026, #123)", async () => {
    // Nachweis (a): eine neue, EIGENE Zeile je verwaistem Album, mit
    // eigenem Knopf und eigener Rueckfrage — getrennt vom Gruppenknopf
    // "Verknuepfung entfernen" unten, der weiterhin die ganze Gruppe nimmt.
    albenMock.mockResolvedValue(gemischteGruppe());
    await rendern("Gemischt");

    const confirmSpy = vi.fn(() => true);
    vi.stubGlobal("confirm", confirmSpy);
    const einzelKnopf = screen.getByRole("button", {
      name: /Dieses verwaiste Album entfernen/i,
    }) as HTMLButtonElement;
    fireEvent.click(einzelKnopf);

    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining("Gemischt"));
    await waitFor(() => expect(deleteMock).toHaveBeenCalledWith("verwaist"));
    expect(deleteMock).not.toHaveBeenCalledWith("gesund");
    vi.unstubAllGlobals();
  });

  it("bricht die Einzelentfernung ohne Rueckfrage-Bestaetigung ab", async () => {
    albenMock.mockResolvedValue(gemischteGruppe());
    await rendern("Gemischt");

    vi.stubGlobal(
      "confirm",
      vi.fn(() => false)
    );
    fireEvent.click(screen.getByRole("button", { name: /Dieses verwaiste Album entfernen/i }));

    await new Promise((r) => setTimeout(r, 10));
    expect(deleteMock).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
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

    expect(
      screen.getByText(/Verwaiste Alben werden beim Abgleichen und Umbenennen übersprungen/)
    ).toBeTruthy();
  });

  it("laesst ein offenes Umbenennen-Feld OFFEN, wenn die Gruppe nur gemischt wird (Owner-Entscheid 29.09.2026, #123)", async () => {
    // Gegenstueck zum fruehereren Verhalten (Nacharbeit 1): Bis #123 schloss
    // dieser Uebergang das Feld, weil die Schleife damals JEDES Album der
    // Gruppe anfuhr und am verwaisten mit 404 scheiterte — eine Gruppe mit
    // zwei Namen drohte. Seit #123 faehrt die Schleife nur noch
    // `gesundeAlben` an; ein verwaistes Geschwister-Album kann das
    // gesunde nicht mehr gefaehrden, das Feld darf offen bleiben.
    const gesundeGruppe = [album({ id: "gesund", album_name: "Gemischt" })];
    albenMock.mockResolvedValue(gesundeGruppe);
    const qc = await rendern("Gemischt");

    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/i }));
    const feld = screen.getByRole("textbox", { name: /Album umbenennen/i }) as HTMLInputElement;
    fireEvent.change(feld, { target: { value: "Neuer Name" } });

    // Konto "verwaist" wird "in einem anderen Tab" geloescht — die Liste
    // liefert jetzt die gemischte Form, und die Abfrage wird ungueltig
    // gemacht. Das GESUNDE Album bleibt aber weiterhin gesund.
    albenMock.mockResolvedValue(gemischteGruppe());
    await act(async () => {
      await qc.invalidateQueries({ queryKey: ["managed-albums"] });
    });
    await waitFor(() =>
      expect(
        screen.getByText(/Verwaiste Alben werden beim Abgleichen und Umbenennen übersprungen/)
      ).toBeTruthy()
    );

    // Das Feld ist NICHT verschwunden — anders als vor #123.
    expect(screen.getByRole("textbox", { name: /Album umbenennen/i })).toBeTruthy();

    fireEvent.keyDown(feld, { key: "Enter" });
    await waitFor(() => expect(renameMock).toHaveBeenCalledTimes(1));
    expect(renameMock).toHaveBeenCalledWith("gesund", "Neuer Name");
    expect(renameMock).not.toHaveBeenCalledWith("verwaist", expect.anything());
  });

  it("schliesst ein offenes Umbenennen-Feld, sobald KEIN gesundes Album mehr uebrig ist", async () => {
    // Die Sperre selbst bleibt fuer den Fall, dass es fuer das Umbenennen
    // schlicht nichts mehr zu tun gibt (Owner-Entscheid 29.09.2026, #123:
    // `renameLocked = gesundeAlben.length === 0`) — nur ihr AUSLOESER hat
    // sich verengt: nicht mehr "irgendein verwaistes Geschwister", sondern
    // "gar kein gesundes Album mehr".
    const gesundeGruppe = [album({ id: "gesund", album_name: "Gemischt" })];
    albenMock.mockResolvedValue(gesundeGruppe);
    const qc = await rendern("Gemischt");

    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/i }));
    const feld = screen.getByRole("textbox", { name: /Album umbenennen/i }) as HTMLInputElement;
    fireEvent.change(feld, { target: { value: "Neuer Name" } });

    // Jetzt wird auch das bislang gesunde Konto entfernt — die Gruppe ist
    // GANZ verwaist.
    albenMock.mockResolvedValue([
      album({ id: "gesund", album_name: "Gemischt", owner_account_missing: true }),
    ]);
    await act(async () => {
      await qc.invalidateQueries({ queryKey: ["managed-albums"] });
    });
    await waitFor(() =>
      expect(screen.queryByRole("textbox", { name: /Album umbenennen/i })).toBeNull()
    );

    // Selbst wenn noch ein Enter auf dem alten Feld ankaeme, darf nichts
    // umbenannt worden sein.
    fireEvent.keyDown(feld, { key: "Enter" });
    await new Promise((r) => setTimeout(r, 10));
    expect(renameMock).not.toHaveBeenCalled();
  });

  it("REGRESSION Nacharbeit 2 (Gegenpruefer, Probe A3b): die Sperre schliesst nur das Feld, sie loescht nicht die Fehlermeldung des Servers", async () => {
    // Ausgangslage: BEIDE Alben gelten noch als gesund (owner_account_missing
    // fehlt) — das ist die Lage eines Clients mit veralteter Liste, bevor er
    // neu laedt. Das Umbenennen laeuft deshalb ungehindert fuer BEIDE Alben.
    albenMock.mockResolvedValue([
      album({ id: "gesund", album_name: "Gemischt" }),
      album({ id: "verwaist", album_name: "Gemischt", owner_account_id: "tot" }),
    ]);
    await rendern("Gemischt");

    renameMock.mockImplementation(async (id: string) => {
      if (id === "verwaist") {
        throw Object.assign(new Error("Owner-Account nicht gefunden"), {
          key: "err_owner_account_not_found",
        });
      }
      return [
        { id: "l1", timestamp: "", action: "rename_album", details: "ok", status: "success" },
      ];
    });
    // Die Neuladung, die `finally` ausloest, haengt — so laesst sich der
    // Zustand "Fehler steht schon, Neuladung noch nicht angekommen" pruefen.
    let freigeben: (v: unknown) => void = () => {};
    albenMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          freigeben = resolve;
        })
    );

    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/i }));
    const feld = screen.getByRole("textbox", { name: /Album umbenennen/i });
    fireEvent.change(feld, { target: { value: "Neu" } });
    fireEvent.keyDown(feld, { key: "Enter" });

    await waitFor(() => expect(screen.getByText(/Owner-Account nicht gefunden/)).toBeTruthy());

    // Die Neuladung kommt an: BEIDE Konten sind jetzt weg — die Gruppe ist
    // GANZ verwaist, nicht nur gemischt (sonst bliebe das Feld seit #123
    // absichtlich offen, siehe die Beschreibung zwei Faelle oben).
    await act(async () => {
      freigeben([
        album({ id: "gesund", album_name: "Neu", owner_account_missing: true }),
        album({
          id: "verwaist",
          album_name: "Gemischt",
          owner_account_id: "tot",
          owner_account_missing: true,
        }),
      ]);
    });

    // Die Sperre schliesst das Feld ...
    await waitFor(() =>
      expect(screen.queryByRole("textbox", { name: /Album umbenennen/i })).toBeNull()
    );
    // ... die Fehlermeldung des Servers bleibt trotzdem stehen. Die
    // fehlerhafte erste Fassung dieses Effekts loeschte sie hier mit.
    expect(screen.getByText(/Owner-Account nicht gefunden/)).toBeTruthy();
  });
});

describe("AlbumsOverview: 'zu wenige Personen' je Album, nicht je Gruppe (Owner-Entscheid 29.09.2026, #123)", () => {
  // Nachweis (b) aus dem Bau-Brief zu #123 — der Rueckschritt aus
  // Nacharbeit 2 zu #99/#112: `tooFewPeople` wurde dort aus der
  // ZUSAMMENGEFUEHRTEN Personenliste der Gruppe berechnet
  // (`personRefs.length < 2`). Ein Album mit einer Person verlor seine
  // eigene Markierung, sobald ein Geschwister-Album in derselben Gruppe
  // weitere Personen beisteuerte — gemessen im Issue: HEAD `false`,
  // HEAD~1 `true`. #123 verlangt das Gegenteil: JEDES solche Album bleibt
  // markiert.
  it("zeigt die Markierung, wenn EIN Album der Gruppe zu wenige Personen hat — auch wenn die Gruppe insgesamt genug hat", async () => {
    albenMock.mockResolvedValue([
      album({
        id: "album-a",
        album_name: "Familie",
        owner_account_id: "konto-a",
        owner_account_missing: false,
        too_few_people: true,
        person_refs: [
          {
            account_id: "konto-a",
            person_id: "person-a",
            person_name: "Person A",
            account_name: "Konto A",
            account_color: "#111111",
          },
        ],
      }),
      album({
        id: "album-b",
        album_name: "Familie",
        owner_account_id: "konto-b",
        owner_account_missing: false,
        too_few_people: false,
        person_refs: [
          {
            account_id: "konto-b",
            person_id: "person-b1",
            person_name: "Person B1",
            account_name: "Konto B",
            account_color: "#222222",
          },
          {
            account_id: "konto-c",
            person_id: "person-c1",
            person_name: "Person C1",
            account_name: "Konto C",
            account_color: "#333333",
          },
        ],
      }),
    ]);
    await rendern("Familie");

    // Die zusammengefuehrte Liste traegt DREI Personen (A, B1, C1) — unter
    // der alten, aus Nacharbeit 2 zurueckgebauten Berechnung waere die
    // Gruppe damit NICHT markiert gewesen. Album A hat fuer sich allein nur
    // eine Person und bleibt markiert.
    expect(screen.getByText("Nur noch eine Person")).toBeTruthy();
  });

  it("zeigt KEINE Markierung, wenn kein Album der Gruppe fuer sich allein zu wenige Personen hat", async () => {
    albenMock.mockResolvedValue([
      album({
        id: "album-a",
        album_name: "Familie",
        too_few_people: false,
        person_refs: [
          {
            account_id: "konto-a",
            person_id: "person-a",
            person_name: "Person A",
            account_name: "Konto A",
            account_color: "#111111",
          },
          {
            account_id: "konto-b",
            person_id: "person-b",
            person_name: "Person B",
            account_name: "Konto B",
            account_color: "#222222",
          },
        ],
      }),
    ]);
    await rendern("Familie");

    expect(screen.queryByText("Nur noch eine Person")).toBeNull();
    expect(screen.queryByText("Keine Person mehr verknüpft")).toBeNull();
  });
});

describe("AlbumsOverview: Anzeige-Korrekturen aus Nacharbeit 2 zu #99/#112, jetzt mit eigenen Tests (#123)", () => {
  it("Besitzerzeile zeigt den lebenden Besitzer des ERSTEN Albums, nicht die Markierung des Geschwisters", async () => {
    // `displayedOwnerMissing` ist enger als `ownerMissing`: Eine gemischte
    // Gruppe, deren ERSTES (angezeigtes) Album einen lebenden Besitzer hat,
    // darf in der Besitzer-Zeile nicht "Besitzerkonto gelöscht" zeigen —
    // auch wenn irgendein Geschwister-Album verwaist ist.
    albenMock.mockResolvedValue([
      album({
        id: "gesund",
        album_name: "Gemischt",
        owner_account_id: "konto-lebt",
        owner_account_missing: false,
        person_refs: [
          {
            account_id: "konto-lebt",
            person_id: "person-1",
            person_name: "Person Eins",
            account_name: "Konto Lebt",
            account_color: "#111111",
          },
        ],
      }),
      album({
        id: "verwaist",
        album_name: "Gemischt",
        owner_account_id: "konto-tot",
        owner_account_missing: true,
        // Bewusst LEER, nicht der Standard aus der Fabrik oben — sonst
        // ueberschneidet sich der Standard-Eintrag "konto-lebt"/"person-1"
        // zufaellig mit dem des gesunden Albums, und der Test haengt an
        // einer Koinzidenz statt an einer Aussage.
        person_refs: [],
      }),
    ]);
    await rendern("Gemischt");

    // Die Besitzer-Zeile nennt den lebenden Besitzer beim Namen — er taucht
    // auch als Personen-Badge auf, deshalb hier `getAllByText` statt
    // `getByText`.
    expect(screen.getAllByText(/Konto Lebt/).length).toBeGreaterThan(0);
    // "Besitzerkonto gelöscht" steht nur noch in der Markierung darunter,
    // GENAU EINMAL — nicht zusaetzlich in der Besitzer-Zeile (die zeigt den
    // lebenden Besitzer). Regex statt exaktem String: Die Markierung traegt
    // in dieser (gemischten) Gruppe zusaetzlich den Abgleich-Hinweis im
    // selben Element, der exakte Textinhalt ist also laenger.
    expect(screen.getAllByText(/Besitzerkonto gelöscht/)).toHaveLength(1);
  });

  it("zeigt den Hinweis 'ganz verwaist' am Abgleich-Knopf, wenn KEIN Album mehr gesund ist", async () => {
    // Nacharbeit 2 (Blindpruefer, kleiner Fund): Eine ganz verwaiste Gruppe
    // deaktivierte "Jetzt synchronisieren" bis dahin ohne jeden Grund im
    // Titel. Bisher ungetestet — dieser Test nagelt ihn fest.
    albenMock.mockResolvedValue([
      album({ id: "a", album_name: "Ganz verwaist", owner_account_missing: true }),
      album({
        id: "b",
        album_name: "Ganz verwaist",
        owner_account_id: "konto-tot-2",
        owner_account_missing: true,
      }),
    ]);
    await rendern("Ganz verwaist");

    const syncKnopf = screen.getByRole("button", {
      name: /Jetzt synchronisieren/i,
    }) as HTMLButtonElement;
    expect(syncKnopf.disabled).toBe(true);
    expect(syncKnopf.title).toBe("Kein Album dieser Gruppe hat noch ein lebendes Besitzerkonto.");
  });
});
