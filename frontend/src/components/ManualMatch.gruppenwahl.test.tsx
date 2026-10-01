// Der ZWEITE Anlege-Weg: die Gruppenwahl im manuellen Abgleich (#81).
//
// Warum eigens geprueft, obwohl die Komponente `GruppenWahl` bereits Tests
// hat: Bei #78 ist genau diese Klasse zweimal durchgerutscht — die Regel war
// geprueft, die VERDRAHTUNG nicht (`docs/agents/lehren.md` §39). Und der
// Mutationslauf zu diesem Slice hat gezeigt, dass es hier wieder so war: Die
// Zeile, die `force_new_group` mitschickt, liess sich entfernen, ohne dass
// ein Test rot wurde.
//
// Nacharbeit 1 zu #110 (28.09.2026, Fremd-/Blindpruefer): Owner-Entscheid
// aendert die Erstfassung (kein Fail-open mehr) und mehrere Proben unten
// pruefen Funde, die die erste Fassung nicht abdeckte — insbesondere Fund 5
// (stiller Besitzerwechsel, nur in diesem Anlegeweg moeglich).
import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ManualMatch from "./ManualMatch";
import { LanguageProvider } from "../i18n";
import { SPEICHER_SCHLUESSEL } from "../test-konstanten";

const STARTKNOPF = "Namen sync + Album erstellen";

// Alle Daten erfunden; das Repo ist oeffentlich. "Konto Drei" nur fuer den
// Besitzerwechsel-Fund (5) gebraucht.
const KONTEN = [
  { id: "konto-1", name: "Konto Eins", color: "#111111" },
  { id: "konto-2", name: "Konto Zwei", color: "#222222" },
  { id: "konto-3", name: "Konto Drei", color: "#333333" },
];

const LEUTE: Record<
  string,
  { id: string; name: string; account_id: string; asset_count: number }[]
> = {
  "konto-1": [{ id: "p1", name: "Person A", account_id: "konto-1", asset_count: 3 }],
  "konto-2": [{ id: "p2", name: "Person A", account_id: "konto-2", asset_count: 4 }],
  "konto-3": [{ id: "p3", name: "Person C", account_id: "konto-3", asset_count: 1 }],
};

const GRUPPE = {
  group_id: "gruppe-1",
  album_names: ["Testalbum"],
  person_refs: [
    {
      account_id: "konto-1",
      person_id: "p8",
      person_name: "Person X",
      account_name: "Konto Eins",
      account_color: "#111111",
    },
  ],
};

const { kontenMock, leuteMock, namesMultiMock, vorschauMock, kontoAlbenMock } = vi.hoisted(() => ({
  kontenMock: vi.fn(),
  leuteMock: vi.fn(),
  namesMultiMock: vi.fn(),
  vorschauMock: vi.fn(),
  kontoAlbenMock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  api: {
    accounts: { list: kontenMock, albums: kontoAlbenMock },
    people: { byAccount: leuteMock, thumbnailUrl: () => "" },
    personLinks: { list: vi.fn().mockResolvedValue([]) },
    sync: { namesMulti: namesMultiMock, albumGroupPreview: vorschauMock },
  },
}));

function zeichne() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <LanguageProvider>
        <ManualMatch />
      </LanguageProvider>
    </QueryClientProvider>
  );
}

/** Waehlt in der Personensuche der Zeile `zeile` die Person `name`. */
async function waehlePerson(zeile: number, name: string) {
  const felder = await waitFor(() => {
    const treffer = screen.getAllByPlaceholderText("Person suchen…");
    if (treffer.length <= zeile) throw new Error("Personenfelder noch nicht da");
    return treffer;
  });
  fireEvent.focus(felder[zeile]);
  const umgebung = within(felder[zeile].parentElement as HTMLElement);
  const eintrag = await umgebung.findByText(name);
  fireEvent.mouseDown(eintrag);
}

/** Zwei Personen auswaehlen und einen Namen setzen, bis abgeschickt werden kann. */
async function fuelleFormular() {
  zeichne();
  await waitFor(() => expect(kontenMock).toHaveBeenCalled());

  const kontoFelder = await screen.findAllByRole("combobox");
  fireEvent.change(kontoFelder[0], { target: { value: "konto-1" } });
  fireEvent.change(kontoFelder[1], { target: { value: "konto-2" } });

  await waitFor(() => expect(leuteMock).toHaveBeenCalled());

  // Je Zeile eine Person waehlen — sonst bleibt der Absendeknopf gesperrt.
  await waehlePerson(0, "Person A");
  await waehlePerson(1, "Person A");

  // Der gemeinsame Name traegt die Gruppenabfrage, wenn kein Albumname
  // gesetzt ist — genau die Verkettung, die hier gesichert werden soll.
  fireEvent.change(screen.getByPlaceholderText("z. B. Max Mustermann"), {
    target: { value: "Testalbum" },
  });
}

/** Laesst alle bereits geplanten Mikro-/Makrotasks (bis 0ms) ablaufen, bevor
 *  eine Nicht-Aufruf-Zusicherung geprueft wird (Blindpruefer, Nacharbeit 1,
 *  28.09.2026: `expect(mock).not.toHaveBeenCalled()` direkt nach einem Klick
 *  ist sonst IMMER gruen, weil `mutate()` asynchron aufruft). */
async function wartenAufRuhe() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

beforeEach(() => {
  // `resetAllMocks` statt `clearAllMocks`: Ein `mockResolvedValueOnce`/
  // `mockRejectedValueOnce`, den ein Test nie verbraucht, blieb sonst in der
  // Warteschlange und beantwortete den ERSTEN Aufruf des NAECHSTEN Tests —
  // gemessen bei der Rot-Beweis-Probe zu Fund 1/Nacharbeit 1 (28.09.2026).
  vi.resetAllMocks();
  try {
    localStorage.setItem(SPEICHER_SCHLUESSEL, "de");
  } catch {
    /* in dieser Umgebung nicht zwingend vorhanden */
  }
  kontenMock.mockResolvedValue(KONTEN);
  leuteMock.mockImplementation(async (id: string) => LEUTE[id] ?? []);
  namesMultiMock.mockResolvedValue([]);
  vorschauMock.mockResolvedValue(GRUPPE);
  kontoAlbenMock.mockResolvedValue([{ id: "immich-1", name: "Testalbum" }]);
});

describe("ManualMatch: Gruppenwahl", () => {
  it("zeigt die getroffene Gruppe, sobald ein Name feststeht", async () => {
    await fuelleFormular();

    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());
    expect(screen.getByText("Person X")).toBeTruthy();
  });

  it("bei mehrdeutigem Namen ('many') bleibt der Startknopf gesperrt, bis eine Gruppe gewaehlt ist (Nacharbeit 1, Blind W-5)", async () => {
    // Testluecke, Nacharbeit 1 zu #113/#119/#124 (Blind W-5): Die
    // "many"-Antwort war nur an der Einzelkomponente `GruppenWahl` geprueft,
    // nicht end-to-end im manuellen Abgleich — genau der Ort, an dem eine
    // fehlende Wahl trotzdem eine Anlage anstossen koennte.
    const MANY = {
      status: "many" as const,
      candidates: [
        {
          group_id: "gruppe-a",
          album_names: ["Testalbum"],
          person_refs: [
            {
              account_id: "konto-1",
              person_id: "p9",
              person_name: "Person Neun",
              account_name: "Konto Eins",
              account_color: "#111111",
            },
          ],
        },
        {
          group_id: "gruppe-b",
          album_names: ["Testalbum"],
          person_refs: [
            {
              account_id: "konto-1",
              person_id: "p10",
              person_name: "Person Zehn",
              account_name: "Konto Eins",
              account_color: "#111111",
            },
          ],
        },
      ],
    };
    vorschauMock.mockResolvedValue(MANY);

    await fuelleFormular();
    const knopf = () => screen.getByText(STARTKNOPF) as HTMLButtonElement;

    await waitFor(() => expect(screen.getByText("Person Neun")).toBeTruthy());
    expect(knopf().disabled).toBe(true);
    fireEvent.click(knopf());
    await wartenAufRuhe();
    expect(namesMultiMock).not.toHaveBeenCalled();

    // Eine Kandidaten-Gruppe waehlen — jetzt darf abgeschickt werden, MIT der
    // gewaehlten `group_id`.
    const radio = screen
      .getByText("Person Neun")
      .closest("label")
      ?.querySelector('input[type="radio"]') as HTMLInputElement;
    fireEvent.click(radio);
    await waitFor(() => expect(knopf().disabled).toBe(false));

    fireEvent.click(knopf());
    await waitFor(() => expect(namesMultiMock).toHaveBeenCalled());
    expect(namesMultiMock.mock.calls[0][0].group_id).toBe("gruppe-a");
  });

  it("schickt 'eigene Gruppe' wirklich mit", async () => {
    await fuelleFormular();
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());

    fireEvent.click(screen.getByLabelText("Eigene Gruppe anlegen"));
    fireEvent.click(screen.getByText(STARTKNOPF));

    await waitFor(() => expect(namesMultiMock).toHaveBeenCalled());
    expect(namesMultiMock.mock.calls[0][0].force_new_group).toBe(true);
  });
});

describe("ManualMatch: Gruppenwahl beim VERKNUEPFEN", () => {
  it("zeigt die Gruppe auch im Modus 'Vorhandenes verknuepfen'", async () => {
    // Die erste Fassung schaltete die Anzeige dort ab (`wirksamerName` war
    // fest ""), waehrend das Backend weiter ueber den Namen verschmolz — ein
    // stiller Beitritt ohne jeden Hinweis. MatchSuggestions bot die Wahl in
    // genau diesem Modus an; die Asymmetrie war nirgends begruendet
    // (Blindpruefer und Zweitstimme 21.09.2026, unabhaengig).
    await fuelleFormular();

    fireEvent.click(screen.getByText("Vorhandenes verknüpfen"));
    await screen.findByText("Testalbum");
    const felder = screen.getAllByRole("combobox");
    fireEvent.change(felder[felder.length - 1], { target: { value: "immich-1" } });

    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());
    expect(screen.getByText("Person X")).toBeTruthy();
  });

  it("laedt die Albumliste neu, wenn der Server mit 'err_group_situation_changed' ablehnt (Nacharbeit 1, Gegen F8, KLEIN)", async () => {
    // Im Modus "Verknuepfen" bestimmt die Albumliste (`account-albums`) den
    // Namen, den die CLIENT-Vorschau prueft — der Server loest beim
    // Speichern den Namen frisch aus Immich auf. Aendert sich der
    // Immich-Name dazwischen, lehnt der Server mit
    // `err_group_situation_changed` ab; ohne Neuladen der Albumliste zeigt
    // die Vorschau beim naechsten Versuch denselben veralteten Namen wieder
    // — eine Ablehnungsschleife.
    // Enten-Typisierung wie im Komponentencode selbst (siehe Kommentar dort):
    // ein Objekt mit `key` reicht, eine echte `ApiError`-Instanz ist nicht
    // noetig — und waere hier ohnehin nicht zu bekommen, weil dieses Modul
    // komplett gemockt ist.
    namesMultiMock.mockRejectedValueOnce(
      Object.assign(new Error("Die Gruppenlage hat sich geaendert."), {
        key: "err_group_situation_changed",
      })
    );

    await fuelleFormular();
    fireEvent.click(screen.getByText("Vorhandenes verknüpfen"));
    await screen.findByText("Testalbum");
    const felder = screen.getAllByRole("combobox");
    fireEvent.change(felder[felder.length - 1], { target: { value: "immich-1" } });

    await waitFor(() => expect(kontoAlbenMock).toHaveBeenCalledTimes(1));
    const knopf = () => screen.getByText(STARTKNOPF) as HTMLButtonElement;
    await waitFor(() => expect(knopf().disabled).toBe(false));

    fireEvent.click(knopf());

    await waitFor(() => expect(namesMultiMock).toHaveBeenCalled());
    // Der eigentliche Fund: Die Albumliste wird nach GENAU dieser Ablehnung
    // neu geladen — ohne das blieb sie bei EINEM Aufruf stehen.
    await waitFor(() => expect(kontoAlbenMock.mock.calls.length).toBeGreaterThan(1));
  });
});

describe("Anlegen erst nach Antwort der Gruppenvorschau (#110)", () => {
  // Der zweite Anlegeweg: dieselbe Owner-Festlegung wie bei MatchSuggestions
  // (CONTEXT.md, Group Suggestion) — ein Vorschlag ist ein Vorschlag, nie
  // eine stille Zuordnung.
  it("sperrt den Startknopf, bis die Vorschau geantwortet hat, und gibt danach frei", async () => {
    let antworten!: (wert: typeof GRUPPE) => void;
    vorschauMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          antworten = resolve;
        })
    );

    await fuelleFormular();
    const knopf = () => screen.getByText(STARTKNOPF) as HTMLButtonElement;

    // Sofort klicken, bevor die Vorschau geantwortet hat: keine Anlage.
    expect(knopf().disabled).toBe(true);
    fireEvent.click(knopf());
    await wartenAufRuhe();
    expect(namesMultiMock).not.toHaveBeenCalled();

    // Erst warten, bis die Abfrage wirklich LAEUFT — sonst gibt es noch
    // keine Zusage-Funktion zum Aufloesen.
    await waitFor(() => expect(vorschauMock).toHaveBeenCalled());
    await act(async () => {
      antworten(GRUPPE);
    });
    await waitFor(() => expect(knopf().disabled).toBe(false));

    fireEvent.click(knopf());
    await waitFor(() => expect(namesMultiMock).toHaveBeenCalled());
  });

  it("sperrt den Startknopf ebenso im Modus 'Verknuepfen' (#110, Nacharbeit 1, Fund 7)", async () => {
    // Blindpruefer, Nacharbeit 1: die Sperre war fuer den Verknuepfen-Zweig
    // in BEIDEN Aufrufern ungetestet — eine Mutation dort blieb 135/135 gruen.
    let antworten!: (wert: typeof GRUPPE) => void;
    vorschauMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          antworten = resolve;
        })
    );

    await fuelleFormular();
    fireEvent.click(screen.getByText("Vorhandenes verknüpfen"));
    await screen.findByText("Testalbum");
    const felder = screen.getAllByRole("combobox");
    fireEvent.change(felder[felder.length - 1], { target: { value: "immich-1" } });

    const knopf = () => screen.getByText(STARTKNOPF) as HTMLButtonElement;
    await waitFor(() => expect(vorschauMock).toHaveBeenCalled());
    expect(knopf().disabled).toBe(true);

    fireEvent.click(knopf());
    await wartenAufRuhe();
    expect(namesMultiMock).not.toHaveBeenCalled();

    await act(async () => {
      antworten(GRUPPE);
    });
    await waitFor(() => expect(knopf().disabled).toBe(false));

    fireEvent.click(knopf());
    await waitFor(() => expect(namesMultiMock).toHaveBeenCalled());
    expect(namesMultiMock.mock.calls[0][0].existing_album_id).toBe("immich-1");
  });

  it("bleibt gesperrt bei fehlgeschlagener Vorschau und gibt erst nach 'Erneut pruefen' frei", async () => {
    // Owner-Entscheid 28.09.2026 (#110, Nacharbeit 1, ersetzt die Erstfassung):
    // kein Fail-open mehr.
    vorschauMock.mockRejectedValueOnce(new Error("netzwerk kaputt"));
    vorschauMock.mockResolvedValueOnce(GRUPPE);

    await fuelleFormular();
    const knopf = () => screen.getByText(STARTKNOPF) as HTMLButtonElement;

    await waitFor(() =>
      expect(screen.getByText("Prüfung fehlgeschlagen — Anlegen bleibt gesperrt.")).toBeTruthy()
    );
    expect(knopf().disabled).toBe(true);
    fireEvent.click(knopf());
    await wartenAufRuhe();
    expect(namesMultiMock).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText("Erneut prüfen"));

    await waitFor(() => expect(vorschauMock).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(knopf().disabled).toBe(false));
  });
});

describe("Besitzerwechsel setzt eine gewaehlte Albumkennung zurueck (#110, Nacharbeit 1, Fund 5)", () => {
  it("sperrt den Startknopf, wenn der wirksame Besitzer still wechselt, waehrend eine bestehende Albumkennung gewaehlt ist", async () => {
    // Gemessen: "Konto Eins" hat "Testalbum", "Konto Drei" nicht. Wechselt
    // die ERSTE Personenzeile von Konto Eins auf Konto Drei, gehoert die
    // laengst gewaehlte Kennung "immich-1" zu einem FREMDEN Konto — ohne
    // dass ein `onChange` an der Albumauswahl das je meldet.
    kontoAlbenMock.mockImplementation(async (accountId: string) =>
      accountId === "konto-1" ? [{ id: "immich-1", name: "Testalbum" }] : []
    );

    await fuelleFormular();
    fireEvent.click(screen.getByText("Vorhandenes verknüpfen"));
    await screen.findByText("Testalbum");
    let felder = screen.getAllByRole("combobox");
    fireEvent.change(felder[felder.length - 1], { target: { value: "immich-1" } });

    const knopf = () => screen.getByText(STARTKNOPF) as HTMLButtonElement;
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());
    await waitFor(() => expect(knopf().disabled).toBe(false));

    // Erste Personenzeile auf ein DRITTES Konto umstellen — und dort auch
    // gleich eine Person waehlen, damit NUR die Albumkennung ungueltig wird
    // (sonst wuerde die allgemeine "alle Zeilen ausgefuellt"-Regel schon
    // allein sperren, und der Test bewiese gar nichts Spezifisches).
    felder = screen.getAllByRole("combobox");
    fireEvent.change(felder[0], { target: { value: "konto-3" } });
    // Erst warten, bis die Personenliste fuer Konto Drei WIRKLICH da ist —
    // sonst traegt Zeile 0 kurzzeitig den Lade-Platzhalter ("Lade…") statt
    // "Person suchen…", und `getAllByPlaceholderText` faende nur Zeile 1.
    await waitFor(() => expect(screen.queryByPlaceholderText("Lade…")).toBeNull());
    await waehlePerson(0, "Person C");

    // Sofort gesperrt: "immich-1" gehoert zu Konto Eins, nicht zu Konto Drei.
    // Vorher blieb `existingAlbumId` stehen und `wirksamerName` wurde leer —
    // "nichts zu pruefen" meldete faelschlich bereit (gemessen).
    expect(knopf().disabled).toBe(true);
    fireEvent.click(knopf());
    await wartenAufRuhe();
    expect(namesMultiMock).not.toHaveBeenCalled();

    // Die Albumliste fuer Konto Drei ist leer — es bleibt gesperrt, bis
    // wieder ein gueltiges Album zu einem passenden Konto gewaehlt wird.
    await waitFor(() => expect(screen.queryByText("Testalbum")).toBeNull());
    expect(knopf().disabled).toBe(true);
  });

  it("setzt die gewaehlte Albumkennung WIRKLICH zurueck, statt sich nur auf den Namens-Schutz zu verlassen", async () => {
    // Zugespitzter Fall, unabhaengig vom Namens-Schutz in `albumReady`:
    // Konto Drei hat ZUFAELLIG ebenfalls eine Kennung "immich-1" — aber ein
    // VOELLIG ANDERES Album dahinter. Bliebe `existingAlbumId` nach dem
    // Besitzerwechsel stehen (kein Reset), waere `wirksamerName` NICHT leer
    // ("Voellig anderes Album") — der Namens-Schutz allein wuerde das NICHT
    // fangen, weil er nur bei LEEREM Namen greift. Nur der Reset verhindert,
    // dass die App eine Kennung unter einem fremden Konto stillschweigend
    // weiterbenutzt.
    kontoAlbenMock.mockImplementation(async (accountId: string) => {
      if (accountId === "konto-1") return [{ id: "immich-1", name: "Testalbum" }];
      if (accountId === "konto-3") return [{ id: "immich-1", name: "Voellig anderes Album" }];
      return [];
    });

    await fuelleFormular();
    fireEvent.click(screen.getByText("Vorhandenes verknüpfen"));
    await screen.findByText("Testalbum");
    let felder = screen.getAllByRole("combobox");
    fireEvent.change(felder[felder.length - 1], { target: { value: "immich-1" } });

    const knopf = () => screen.getByText(STARTKNOPF) as HTMLButtonElement;
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());
    await waitFor(() => expect(knopf().disabled).toBe(false));

    felder = screen.getAllByRole("combobox");
    fireEvent.change(felder[0], { target: { value: "konto-3" } });
    await waitFor(() => expect(screen.queryByPlaceholderText("Lade…")).toBeNull());
    await waehlePerson(0, "Person C");

    // Ohne Reset wuerde "Voellig anderes Album" jetzt als wirksamer Name
    // gelten (nicht leer!) und nach etwas Zeit sogar wieder "bereit" werden —
    // der Startknopf muss trotzdem gesperrt bleiben, dauerhaft, nicht nur im
    // ersten Moment.
    expect(knopf().disabled).toBe(true);
    // Wiederholt pruefen statt einmal zu warten: die Entprellung setzt bei
    // jeder Zwischen-Aenderung von `wirksamerName` neu an (erst "", dann der
    // Name des zufaellig gleichen Albums) — gemessen schwankt der Zeitpunkt,
    // an dem die zweite Vorschau-Anfrage durchkommt, zwischen rund 0,7 s und
    // 1,5 s. Eine einzelne feste Wartezeit waere hier genau die Falle aus
    // `docs/agents/lehren.md` §44/45 (schon einmal geflattert) — drei
    // Sekunden in 300-ms-Schritten decken die gemessene Schwankung sicher ab.
    for (let vergangen = 0; vergangen < 3000; vergangen += 300) {
      await act(async () => {
        await new Promise((r) => setTimeout(r, 300));
      });
      expect(knopf().disabled).toBe(true);
    }

    fireEvent.click(knopf());
    await wartenAufRuhe();
    expect(namesMultiMock).not.toHaveBeenCalled();
  }, 15_000);
});

describe("ManualMatch: die angezeigte Gruppe wird auch geschickt", () => {
  it("schickt group_id beim Beitritt mit", async () => {
    // Gemessen vom Gegenpruefer: Das Entfernen des `group_id`-Zweigs hier
    // ueberlebte die volle Suite — geprueft war nur force_new_group.
    await fuelleFormular();
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());

    fireEvent.click(screen.getByText(STARTKNOPF));

    await waitFor(() => expect(namesMultiMock).toHaveBeenCalled());
    expect(namesMultiMock.mock.calls[0][0].group_id).toBe("gruppe-1");
  });

  it("schickt expected_no_group mit, wenn die Vorschau keine Gruppe fand (#119)", async () => {
    vorschauMock.mockResolvedValue(null);
    await fuelleFormular();
    const knopf = () => screen.getByText(STARTKNOPF) as HTMLButtonElement;
    await waitFor(() => expect(knopf().disabled).toBe(false));

    fireEvent.click(knopf());

    await waitFor(() => expect(namesMultiMock).toHaveBeenCalled());
    expect(namesMultiMock.mock.calls[0][0].expected_no_group).toBe(true);
    expect(namesMultiMock.mock.calls[0][0].group_id).toBeUndefined();
    expect(namesMultiMock.mock.calls[0][0].force_new_group).toBeUndefined();
  });

  it("schickt beim Verknuepfen keinen stehengebliebenen Albumnamen", async () => {
    // Das Namensfeld gehoert dem Anlege-Modus und wird beim Umschalten nur
    // AUSGEBLENDET. Mitgeschickt entschied sein Wert ueber die Gruppe,
    // waehrend die Vorschau nach dem Namen des IMMICH-Albums gefragt hatte —
    // ein stiller Beitritt zu einer fremden Gruppe (beide Stimmen, gemessen).
    await fuelleFormular();
    fireEvent.change(screen.getByPlaceholderText("Album-Name"), {
      target: { value: "Stehengeblieben" },
    });

    fireEvent.click(screen.getByText("Vorhandenes verknüpfen"));
    await screen.findByText("Testalbum");
    const felder = screen.getAllByRole("combobox");
    fireEvent.change(felder[felder.length - 1], { target: { value: "immich-1" } });

    // Seit #110 sperrt der Startknopf, bis die Vorschau zur AKTUELLEN
    // Eingabe geantwortet hat — hier "Testalbum" (der Name des gewaehlten
    // Albums), nicht mehr "Stehengeblieben".
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());
    fireEvent.click(screen.getByText(STARTKNOPF));

    await waitFor(() => expect(namesMultiMock).toHaveBeenCalled());
    expect(namesMultiMock.mock.calls[0][0].album_name).toBeUndefined();
    expect(namesMultiMock.mock.calls[0][0].existing_album_id).toBe("immich-1");
  });
});

describe("Gruppen-Cache nach Aenderungen (#110, Nacharbeit 1, BLOCKER Fund 1)", () => {
  it("invalidiert die Gruppenvorschau, sobald names-multi erfolgreich war", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const spion = vi.spyOn(qc, "invalidateQueries");
    render(
      <QueryClientProvider client={qc}>
        <LanguageProvider>
          <ManualMatch />
        </LanguageProvider>
      </QueryClientProvider>
    );
    await waitFor(() => expect(kontenMock).toHaveBeenCalled());
    const kontoFelder = await screen.findAllByRole("combobox");
    fireEvent.change(kontoFelder[0], { target: { value: "konto-1" } });
    fireEvent.change(kontoFelder[1], { target: { value: "konto-2" } });
    await waitFor(() => expect(leuteMock).toHaveBeenCalled());
    await waehlePerson(0, "Person A");
    await waehlePerson(1, "Person A");
    fireEvent.change(screen.getByPlaceholderText("z. B. Max Mustermann"), {
      target: { value: "Testalbum" },
    });
    const knopf = () => screen.getByText(STARTKNOPF) as HTMLButtonElement;
    await waitFor(() => expect(knopf().disabled).toBe(false));

    fireEvent.click(knopf());

    await waitFor(() =>
      expect(
        spion.mock.calls.some(
          (call) =>
            call[0] &&
            typeof call[0] === "object" &&
            "queryKey" in call[0] &&
            (call[0] as { queryKey?: unknown[] }).queryKey?.[0] === "album-group"
        )
      ).toBe(true)
    );
  });

  it("die Invalidierung wirkt WIRKLICH — nicht nur der Aufruf mit der richtigen Form (#119, Punkt 2)", async () => {
    // Derselbe Fund wie bei MatchSuggestions: `queryKey[0] === "album-group"`
    // allein beweist nicht, dass die WIRKLICHE Abfrage ["album-group",
    // "Testalbum"] getroffen wird — ein `exact: true` saehe im Spion oben
    // genauso aus. Hier wird ein zweiter echter Vorschau-Aufruf verlangt.
    await fuelleFormular();
    await waitFor(() => expect(vorschauMock).toHaveBeenCalledTimes(1));
    const knopf = () => screen.getByText(STARTKNOPF) as HTMLButtonElement;
    await waitFor(() => expect(knopf().disabled).toBe(false));

    fireEvent.click(knopf());

    await waitFor(() => expect(namesMultiMock).toHaveBeenCalled());
    await waitFor(() => expect(vorschauMock).toHaveBeenCalledTimes(2));
  });

  it("invalidiert die Gruppenvorschau AUCH, wenn names-multi fehlschlaegt (#119, Punkt 3, onSettled)", async () => {
    // `onSettled` statt nur `onSuccess`: ein Teil-Schreibvorgang kann schon
    // eine Gruppe veraendert haben, auch wenn die Anfrage insgesamt als
    // Fehler zurueckkommt. Bisher ungetestet.
    namesMultiMock.mockRejectedValueOnce(new Error("netzwerk kaputt"));
    await fuelleFormular();
    await waitFor(() => expect(vorschauMock).toHaveBeenCalledTimes(1));
    const knopf = () => screen.getByText(STARTKNOPF) as HTMLButtonElement;
    await waitFor(() => expect(knopf().disabled).toBe(false));

    fireEvent.click(knopf());

    await waitFor(() => expect(namesMultiMock).toHaveBeenCalled());
    // Das Formular bleibt nach einem Fehlschlag offen (kein Reset), also
    // bleibt GruppenWahl beobachtet — der automatische Refetch ist der
    // sichtbare Nachweis.
    await waitFor(() => expect(vorschauMock).toHaveBeenCalledTimes(2));
  });
});

describe("Gewaehltes Album verschwindet bei GLEICHEM Besitzer (#110, Nacharbeit 2, WICHTIG Fund 3d)", () => {
  it("sperrt den Startknopf, wenn die Albumliste neu laedt und die Kennung nicht mehr enthaelt", async () => {
    // Blindpruefer, Nacharbeit 2, Probe P7: ANDERS als Fund 5 (Nacharbeit 1)
    // wechselt hier NICHT der Besitzer — dieselbe Kennung wird bei DEMSELBEN
    // Konto einfach ungueltig (z.B. Fokus-Refetch der Albumliste, Album in
    // Immich geloescht). Das prueft, ob der Namens-Schutz in `albumReady`
    // wirklich an JEDER Quelle greift, die die Liste veraendert — nicht nur
    // an einem Besitzerwechsel.
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <LanguageProvider>
          <ManualMatch />
        </LanguageProvider>
      </QueryClientProvider>
    );
    await waitFor(() => expect(kontenMock).toHaveBeenCalled());
    const kontoFelder = await screen.findAllByRole("combobox");
    fireEvent.change(kontoFelder[0], { target: { value: "konto-1" } });
    fireEvent.change(kontoFelder[1], { target: { value: "konto-2" } });
    await waitFor(() => expect(leuteMock).toHaveBeenCalled());
    await waehlePerson(0, "Person A");
    await waehlePerson(1, "Person A");
    fireEvent.change(screen.getByPlaceholderText("z. B. Max Mustermann"), {
      target: { value: "Testalbum" },
    });

    fireEvent.click(screen.getByText("Vorhandenes verknüpfen"));
    await screen.findByText("Testalbum");
    const felder = screen.getAllByRole("combobox");
    fireEvent.change(felder[felder.length - 1], { target: { value: "immich-1" } });

    const knopf = () => screen.getByText(STARTKNOPF) as HTMLButtonElement;
    await waitFor(() => expect(knopf().disabled).toBe(false));

    // Dieselbe Kennung, DASSELBE Konto — die Liste laedt neu und enthaelt
    // "immich-1" nicht mehr.
    kontoAlbenMock.mockResolvedValue([]);
    await act(async () => {
      await qc.invalidateQueries({ queryKey: ["account-albums"] });
    });
    await waitFor(() => expect(screen.queryByText("Testalbum")).toBeNull());

    expect(knopf().disabled).toBe(true);
    fireEvent.click(knopf());
    await wartenAufRuhe();
    expect(namesMultiMock).not.toHaveBeenCalled();
  });
});

describe("Kleinfunde (#119, Punkt 4)", () => {
  it("zeigt einen Hinweis, wenn das gewaehlte bestehende Album keinen Namen traegt", async () => {
    kontoAlbenMock.mockResolvedValue([{ id: "immich-leer", name: "" }]);
    await fuelleFormular();
    fireEvent.click(screen.getByText("Vorhandenes verknüpfen"));

    await waitFor(() => expect(kontoAlbenMock).toHaveBeenCalled());
    // 2 Personen-Konto-Auswahlen + Besitzer-Auswahl (immer da) + die
    // Album-Auswahl, die erst im Modus "Verknuepfen" hinzukommt.
    await waitFor(() => expect(screen.getAllByRole("combobox").length).toBeGreaterThan(3));
    const felder = screen.getAllByRole("combobox");
    fireEvent.change(felder[felder.length - 1], { target: { value: "immich-leer" } });

    await waitFor(() =>
      expect(
        screen.getByText(
          "Dieses Album hat in Immich keinen Namen — bitte dort erst einen Namen vergeben."
        )
      ).toBeTruthy()
    );
    expect((screen.getByText(STARTKNOPF) as HTMLButtonElement).disabled).toBe(true);
  });
});
