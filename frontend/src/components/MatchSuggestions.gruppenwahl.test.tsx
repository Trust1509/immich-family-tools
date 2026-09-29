// Die Gruppenwahl beim Anlegen (#81), geprueft am gerenderten Dialog.
//
// Warum am Bildschirm und nicht an der Funktion: Bei #78 hat genau diese
// Klasse zweimal ueberlebt — die Regel war geprueft, die VERDRAHTUNG nicht
// (`docs/agents/lehren.md` §39). Hier ist sie bereits beim Bauen aufgetreten:
// Der Mutations-Rueckruf nahm `force_new_group` nicht an, TypeScript erlaubte
// das trotzdem (ein Rueckruf darf weniger Felder annehmen als der Aufrufer
// schickt), und das Feld waere still verschwunden.
//
// Und der Zwischenzustand ist ein eigenes Verhalten (§40): Solange die
// Abfrage laeuft, darf nichts behauptet werden.
//
// Nacharbeit 1 zu #110 (28.09.2026, Fremd-/Blindpruefer): Owner-Entscheid
// aendert die Erstfassung — ein Fehlschlag der Vorschau gibt das Anlegen
// NICHT mehr frei ("Erneut pruefen"-Knopf statt Fail-open), und mehrere
// Proben unten pruefen Funde, die die erste Fassung nicht abdeckte.
import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import MatchSuggestions from "./MatchSuggestions";
import { LanguageProvider } from "../i18n";
import { SPEICHER_SCHLUESSEL } from "../test-konstanten";
import { QUERY_VORGABEN } from "../queryClient";

// Alle Daten erfunden; das Repo ist oeffentlich.
const MATCH = {
  id: "match-1",
  confidence: 0.9,
  reasons: ["name_similarity"],
  status: "pending",
  has_album: false,
  names_synced: false,
  person_a: {
    account_id: "konto-1",
    person_id: "p1",
    person_name: "Person A",
    account_name: "Konto Eins",
    account_color: "#111111",
  },
  person_b: {
    account_id: "konto-2",
    person_id: "p2",
    person_name: "Person A",
    account_name: "Konto Zwei",
    account_color: "#222222",
  },
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

const {
  matchesMock,
  kontenMock,
  albenMock,
  albumMock,
  vorschauMock,
  thumbMock,
  kontoAlbenMock,
  dismissMock,
  namesMock,
  refreshAlbumMock,
} = vi.hoisted(() => ({
  matchesMock: vi.fn(),
  kontenMock: vi.fn(),
  albenMock: vi.fn(),
  albumMock: vi.fn(),
  vorschauMock: vi.fn(),
  thumbMock: vi.fn(),
  kontoAlbenMock: vi.fn(),
  dismissMock: vi.fn(),
  namesMock: vi.fn(),
  refreshAlbumMock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  api: {
    matches: {
      list: matchesMock,
      refresh: matchesMock,
      dismiss: dismissMock,
    },
    accounts: { list: kontenMock, albums: kontoAlbenMock },
    sync: {
      albums: albenMock,
      album: albumMock,
      albumGroupPreview: vorschauMock,
      names: namesMock,
      refreshAlbum: refreshAlbumMock,
    },
    people: { thumbnailUrl: thumbMock },
  },
}));

function zeichne() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <LanguageProvider>
        <MatchSuggestions />
      </LanguageProvider>
    </QueryClientProvider>
  );
}

/** Oeffnet den Album-Dialog einer Vorschlagskarte. */
async function oeffneDialog() {
  zeichne();
  const knopf = await screen.findByText("Album verbinden");
  fireEvent.click(knopf);
  return await screen.findByPlaceholderText("Album-Name…");
}

/** Laesst alle bereits geplanten Mikro-/Makrotasks (bis 0ms) ablaufen, bevor
 *  eine Nicht-Aufruf-Zusicherung geprueft wird. Ohne das ist
 *  `expect(mock).not.toHaveBeenCalled()` direkt nach einem Klick IMMER gruen
 *  — `mutate()` ruft die Mutationsfunktion asynchron auf, also sagt die
 *  Zusicherung nichts aus, wenn man nicht erst zu Ende wartet (Blindpruefer,
 *  Nacharbeit 1, 28.09.2026). */
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
  matchesMock.mockResolvedValue([MATCH]);
  kontenMock.mockResolvedValue([
    { id: "konto-1", name: "Konto Eins", color: "#111111" },
    { id: "konto-2", name: "Konto Zwei", color: "#222222" },
  ]);
  albenMock.mockResolvedValue([]);
  albumMock.mockResolvedValue([]);
  thumbMock.mockReturnValue("");
  kontoAlbenMock.mockResolvedValue([]);
  vorschauMock.mockResolvedValue(GRUPPE);
  dismissMock.mockResolvedValue(undefined);
  namesMock.mockResolvedValue([]);
  refreshAlbumMock.mockResolvedValue([]);
});

describe("Gruppenwahl beim Anlegen", () => {
  it("zeigt, wem das neue Album beitreten wuerde", async () => {
    await oeffneDialog();

    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());
    // Wem — nicht nur dass. Ohne die Personen waere die Bestaetigung leer.
    expect(screen.getByText("Person X")).toBeTruthy();
  });

  it("behauptet nichts, solange die Abfrage laeuft", async () => {
    // §40: Der Zwischenzustand ist ein eigenes Verhalten und braucht eine
    // eigene Zusicherung. Die Abfrage wird hier ANGEHALTEN — sonst prueft der
    // Test nur die Entprellung und waere gruen, ohne je einen laufenden
    // Aufruf gesehen zu haben.
    vorschauMock.mockImplementation(() => new Promise(() => {}));

    await oeffneDialog();

    // Erst warten, bis die Abfrage wirklich LAEUFT.
    await waitFor(() => expect(vorschauMock).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText("Wird geprüft …")).toBeTruthy());

    expect(screen.queryByText("Tritt der bestehenden Gruppe bei")).toBeNull();
    expect(screen.queryByText("Eigene Gruppe anlegen")).toBeNull();
  });

  it("schickt ohne Wahl KEIN force_new_group — das bisherige Verhalten", async () => {
    await oeffneDialog();
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());

    fireEvent.click(screen.getByText("Album erstellen"));

    await waitFor(() => expect(albumMock).toHaveBeenCalled());
    expect(albumMock.mock.calls[0][0].force_new_group).toBeUndefined();
  });

  it("schickt expected_no_group mit, wenn die Vorschau keine Gruppe fand (#119)", async () => {
    // Die tragende Zusicherung von #119: Ohne Treffer wird das ANGEZEIGTE
    // "keine Gruppe" ausdruecklich mitgeschickt, statt gar nichts zu sagen —
    // nur damit kann der Server unter dem Namensschloss pruefen, ob sich die
    // Lage seit der Vorschau geaendert hat.
    vorschauMock.mockResolvedValue(null);
    await oeffneDialog();
    await waitFor(() =>
      expect((screen.getByText("Album erstellen") as HTMLButtonElement).disabled).toBe(false)
    );

    fireEvent.click(screen.getByText("Album erstellen"));

    await waitFor(() => expect(albumMock).toHaveBeenCalled());
    expect(albumMock.mock.calls[0][0].expected_no_group).toBe(true);
    expect(albumMock.mock.calls[0][0].group_id).toBeUndefined();
    expect(albumMock.mock.calls[0][0].force_new_group).toBeUndefined();
  });

  it("bei mehrdeutigem Namen ('many') bleibt 'Album erstellen' gesperrt, bis eine Gruppe gewaehlt ist (Nacharbeit 1, Blind W-5)", async () => {
    // Testluecke, Nacharbeit 1 zu #113/#119/#124 (Blind W-5): "many" war nur
    // an der Einzelkomponente `GruppenWahl` geprueft, nicht end-to-end an der
    // Vorschlagsliste.
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
    await oeffneDialog();
    const knopf = () => screen.getByText("Album erstellen") as HTMLButtonElement;

    await waitFor(() => expect(screen.getByText("Person Neun")).toBeTruthy());
    expect(knopf().disabled).toBe(true);
    fireEvent.click(knopf());
    await wartenAufRuhe();
    expect(albumMock).not.toHaveBeenCalled();

    const radio = screen
      .getByText("Person Neun")
      .closest("label")
      ?.querySelector('input[type="radio"]') as HTMLInputElement;
    fireEvent.click(radio);
    await waitFor(() => expect(knopf().disabled).toBe(false));

    fireEvent.click(knopf());
    await waitFor(() => expect(albumMock).toHaveBeenCalled());
    expect(albumMock.mock.calls[0][0].group_id).toBe("gruppe-a");
  });

  it("schickt die angezeigte Gruppe beim Beitritt mit", async () => {
    // Was ANGEZEIGT wird, wird auch GESCHICKT. Ohne diese Bindung liess die
    // App das Backend beim Bestaetigen erneut ueber den Namen raten — kommt
    // dazwischen ein zweites gleichnamiges Album, landet der Nutzer in einer
    // DRITTEN Gruppe, obwohl er einen Beitritt bestaetigt hat.
    await oeffneDialog();
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());

    fireEvent.click(screen.getByText("Album erstellen"));

    await waitFor(() => expect(albumMock).toHaveBeenCalled());
    expect(albumMock.mock.calls[0][0].group_id).toBe("gruppe-1");
  });

  it("behaelt die Wahl, wenn danach weitergetippt wird", async () => {
    // Gemessen vom Blindpruefer: Der Ruecksetzer feuerte bei JEDEM
    // Tastendruck, weil "wird gerade geprueft" mit "es gibt keine Gruppe" in
    // einer Bedingung lag. Der Haken verschwand still, und das Album landete
    // in genau der Gruppe, gegen die sich der Nutzer entschieden hatte.
    await oeffneDialog();
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());

    fireEvent.click(screen.getByLabelText("Eigene Gruppe anlegen"));
    fireEvent.change(screen.getByPlaceholderText("Album-Name…"), {
      target: { value: "Testalbum 2026" },
    });

    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());
    fireEvent.click(screen.getByText("Album erstellen"));

    await waitFor(() => expect(albumMock).toHaveBeenCalled());
    expect(albumMock.mock.calls[0][0].force_new_group).toBe(true);
  });

  it("schickt die Wahl 'eigene Gruppe' wirklich mit", async () => {
    // DIE tragende Zusicherung dieses Slices. Ohne sie waere die Oberflaeche
    // ein Schalter, der nichts tut — gemessen: der Mutations-Rueckruf nahm
    // das Feld anfangs nicht an, und `tsc` sagte nichts.
    await oeffneDialog();
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());

    fireEvent.click(screen.getByLabelText("Eigene Gruppe anlegen"));
    fireEvent.click(screen.getByText("Album erstellen"));

    await waitFor(() => expect(albumMock).toHaveBeenCalled());
    expect(albumMock.mock.calls[0][0].force_new_group).toBe(true);
  });
});

describe("Anlegen erst nach Antwort der Gruppenvorschau (#110)", () => {
  // Die Owner-Festlegung in CONTEXT.md (Group Suggestion): ein Vorschlag ist
  // ein Vorschlag, nie eine stille Zuordnung — wer sofort klickt, darf keine
  // Anlage anstossen, bevor die Vorschau zur AKTUELLEN Eingabe geantwortet
  // hat. Vorher wartete nur `GruppenWahl` selbst darauf, der Anlege-Knopf
  // nicht (Befund im Bau-Brief).
  it("sperrt 'Album erstellen', bis die Vorschau geantwortet hat, und gibt danach frei", async () => {
    let antworten!: (wert: typeof GRUPPE) => void;
    vorschauMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          antworten = resolve;
        })
    );

    await oeffneDialog();
    const knopf = () => screen.getByText("Album erstellen") as HTMLButtonElement;

    // Sofort klicken, bevor die Vorschau geantwortet hat: keine Anlage.
    expect(knopf().disabled).toBe(true);
    fireEvent.click(knopf());
    await wartenAufRuhe();
    expect(albumMock).not.toHaveBeenCalled();

    // Erst warten, bis die Abfrage wirklich LAEUFT — sonst gibt es noch
    // keine Zusage-Funktion zum Aufloesen.
    await waitFor(() => expect(vorschauMock).toHaveBeenCalled());
    await act(async () => {
      antworten(GRUPPE);
    });
    await waitFor(() => expect(knopf().disabled).toBe(false));

    fireEvent.click(knopf());
    await waitFor(() => expect(albumMock).toHaveBeenCalled());
  });

  it("bleibt gesperrt, wenn waehrend einer laufenden Abfrage weitergetippt wird", async () => {
    // Die Antwort, die gerade eintrifft, gehoert dann zu einer AELTEREN
    // Eingabe — genau der Fall, den `gruppenBereitschaft` per Namensvergleich
    // abfaengt.
    await oeffneDialog();
    const knopf = () => screen.getByText("Album erstellen") as HTMLButtonElement;
    await waitFor(() => expect(knopf().disabled).toBe(false));

    fireEvent.change(screen.getByPlaceholderText("Album-Name…"), {
      target: { value: "Noch ein Name" },
    });
    expect(knopf().disabled).toBe(true);

    fireEvent.click(knopf());
    await wartenAufRuhe();
    expect(albumMock).not.toHaveBeenCalled();

    await waitFor(() => expect(knopf().disabled).toBe(false));
  });

  it("bleibt WAEHREND einer echt laufenden Abfrage gesperrt, wenn dabei weitergetippt wird", async () => {
    // Schaerfer als der Test oben: hier wird waehrend eine Anfrage noch
    // UNBEANTWORTET ist weitergetippt, nicht erst NACH ihrer Antwort.
    let ersteAntwort!: (wert: typeof GRUPPE) => void;
    vorschauMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          ersteAntwort = resolve;
        })
    );

    await oeffneDialog();
    const knopf = () => screen.getByText("Album erstellen") as HTMLButtonElement;
    await waitFor(() => expect(vorschauMock).toHaveBeenCalledTimes(1));
    expect(knopf().disabled).toBe(true);

    fireEvent.change(screen.getByPlaceholderText("Album-Name…"), {
      target: { value: "Zweiter Name" },
    });
    expect(knopf().disabled).toBe(true);

    // Die ERSTE (jetzt veraltete) Anfrage antwortet — darf den Knopf fuer
    // "Zweiter Name" nicht freigeben.
    await act(async () => {
      ersteAntwort(GRUPPE);
    });
    expect(knopf().disabled).toBe(true);
    fireEvent.click(knopf());
    await wartenAufRuhe();
    expect(albumMock).not.toHaveBeenCalled();

    await waitFor(() => expect(knopf().disabled).toBe(false));
  });

  it("bleibt gesperrt bei fehlgeschlagener Vorschau, mit Hinweis und 'Erneut pruefen'", async () => {
    // Owner-Entscheid 28.09.2026 (#110, Nacharbeit 1, ersetzt die Erstfassung):
    // kein Fail-open mehr — die Vorschau laeuft gegen denselben Server wie
    // das Anlegen.
    vorschauMock.mockRejectedValue(new Error("netzwerk kaputt"));

    await oeffneDialog();
    const knopf = () => screen.getByText("Album erstellen") as HTMLButtonElement;

    await waitFor(() =>
      expect(screen.getByText("Prüfung fehlgeschlagen — Anlegen bleibt gesperrt.")).toBeTruthy()
    );
    expect(knopf().disabled).toBe(true);

    fireEvent.click(knopf());
    await wartenAufRuhe();
    expect(albumMock).not.toHaveBeenCalled();
  });

  it("'Erneut pruefen' gibt nach Erfolg den Knopf frei", async () => {
    vorschauMock.mockRejectedValueOnce(new Error("netzwerk kaputt"));
    vorschauMock.mockResolvedValueOnce(GRUPPE);

    await oeffneDialog();
    const knopf = () => screen.getByText("Album erstellen") as HTMLButtonElement;
    await waitFor(() => expect(screen.getByText("Erneut prüfen")).toBeTruthy());
    expect(knopf().disabled).toBe(true);

    fireEvent.click(screen.getByText("Erneut prüfen"));

    await waitFor(() => expect(vorschauMock).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(knopf().disabled).toBe(false));

    fireEvent.click(knopf());
    await waitFor(() => expect(albumMock).toHaveBeenCalled());
  });
});

describe("Gruppenwahl beim VERKNUEPFEN eines bestehenden Albums", () => {
  it("schickt die Wahl auch im Verknuepfen-Zweig mit", async () => {
    // Gemessen vom Blindpruefer: Das Entfernen von `...gruppenwahl` in genau
    // diesem Zweig ueberlebte die volle Suite — der Pfad "Wahl + bestehendes
    // Album" war end-to-end ungedeckt.
    kontoAlbenMock.mockResolvedValue([{ id: "immich-1", name: "Testalbum" }]);
    await oeffneDialog();

    fireEvent.click(screen.getByText("Vorhandenes verknüpfen"));

    // Erst warten, bis die Albumliste wirklich da ist — sonst waehlt der
    // Test in ein leeres Feld und prueft nichts.
    await screen.findByText("Testalbum");
    const felder = screen.getAllByRole("combobox");
    fireEvent.change(felder[felder.length - 1], { target: { value: "immich-1" } });

    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());
    fireEvent.click(screen.getByLabelText("Eigene Gruppe anlegen"));
    fireEvent.click(screen.getByText("Album verknüpfen"));

    await waitFor(() => expect(albumMock).toHaveBeenCalled());
    expect(albumMock.mock.calls[0][0].force_new_group).toBe(true);
    expect(albumMock.mock.calls[0][0].existing_album_id).toBe("immich-1");
  });

  it("sperrt 'Album verknuepfen' ebenso, bis die Vorschau geantwortet hat (#110, Nacharbeit 1, Fund 7)", async () => {
    // Blindpruefer, Nacharbeit 1: die Sperre war fuer den Verknuepfen-Zweig
    // in BEIDEN Aufrufern ungetestet — eine Mutation dort blieb 135/135 gruen.
    kontoAlbenMock.mockResolvedValue([{ id: "immich-1", name: "Testalbum" }]);
    let antworten!: (wert: typeof GRUPPE) => void;
    vorschauMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          antworten = resolve;
        })
    );

    await oeffneDialog();
    fireEvent.click(screen.getByText("Vorhandenes verknüpfen"));
    await screen.findByText("Testalbum");
    const felder = screen.getAllByRole("combobox");
    fireEvent.change(felder[felder.length - 1], { target: { value: "immich-1" } });

    const knopf = () => screen.getByText("Album verknüpfen") as HTMLButtonElement;
    await waitFor(() => expect(vorschauMock).toHaveBeenCalled());
    expect(knopf().disabled).toBe(true);

    fireEvent.click(knopf());
    await wartenAufRuhe();
    expect(albumMock).not.toHaveBeenCalled();

    await act(async () => {
      antworten(GRUPPE);
    });
    await waitFor(() => expect(knopf().disabled).toBe(false));

    fireEvent.click(knopf());
    await waitFor(() => expect(albumMock).toHaveBeenCalled());
    expect(albumMock.mock.calls[0][0].existing_album_id).toBe("immich-1");
  });
});

describe("Gruppen-Cache nach Aenderungen (#110, Nacharbeit 1, BLOCKER Fund 1)", () => {
  it("invalidiert die Gruppenvorschau, sobald das Anlegen erfolgreich war", async () => {
    // Direkter Nachweis der Invalidierung (unabhaengig von `refetchOnMount`,
    // das denselben Fall beim Neu-Oeffnen des Dialogs zusaetzlich abdeckt):
    // ohne diese Zeile bliebe eine bereits gemountete zweite Beobachtung
    // derselben Anfrage (z.B. eine zweite offene Karte) auf der alten
    // Antwort sitzen.
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const spion = vi.spyOn(qc, "invalidateQueries");
    render(
      <QueryClientProvider client={qc}>
        <LanguageProvider>
          <MatchSuggestions />
        </LanguageProvider>
      </QueryClientProvider>
    );
    const knopf = await screen.findByText("Album verbinden");
    fireEvent.click(knopf);
    await screen.findByPlaceholderText("Album-Name…");
    await waitFor(() =>
      expect((screen.getByText("Album erstellen") as HTMLButtonElement).disabled).toBe(false)
    );

    fireEvent.click(screen.getByText("Album erstellen"));

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
    // Der Spion oben prueft nur `queryKey[0] === "album-group"` — ein
    // `invalidateQueries({queryKey: ["album-group", name], exact: true})`
    // saehe FORMAL genauso aus (der Spion sieht den Aufruf), traefe aber die
    // echte Abfrage `["album-group", "Person A"]` NICHT mehr. Hier wird
    // deshalb die WIRKUNG geprueft: der Zustand der konkreten Abfrage nach
    // der Mutation.
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <LanguageProvider>
          <MatchSuggestions />
        </LanguageProvider>
      </QueryClientProvider>
    );
    fireEvent.click(await screen.findByText("Album verbinden"));
    await screen.findByPlaceholderText("Album-Name…");
    await waitFor(() =>
      expect((screen.getByText("Album erstellen") as HTMLButtonElement).disabled).toBe(false)
    );

    await waitFor(() => expect(vorschauMock).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByText("Album erstellen"));

    await waitFor(() => expect(albumMock).toHaveBeenCalled());
    // Ein `invalidateQueries({queryKey: ["album-group", name], exact: true})`
    // saehe im Spion oben GENAUSO aus wie der echte Aufruf, traefe die
    // laufende Beobachtung `["album-group", "Person A"]` aber NICHT — dann
    // bliebe es bei GENAU einem Aufruf. Hier wird die WIRKUNG gemessen: ein
    // ZWEITER echter Vorschau-Aufruf, ausgeloest vom automatischen Refetch
    // einer wirklich invalidierten, noch beobachteten Abfrage.
    await waitFor(() => expect(vorschauMock).toHaveBeenCalledTimes(2));
  });

  it("invalidiert die Gruppenvorschau AUCH, wenn das Anlegen fehlschlaegt (#119, Punkt 3, onSettled)", async () => {
    // `onSettled` statt nur `onSuccess`: ein Teil-Schreibvorgang kann in
    // Immich schon eine Gruppe veraendert haben, auch wenn die Anfrage
    // insgesamt als Fehler zurueckkommt. Bisher ungetestet — eine Mutation,
    // die `onSettled` durch `onSuccess` ersetzt, blieb hier gruen.
    albumMock.mockRejectedValueOnce(new Error("netzwerk kaputt"));
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <LanguageProvider>
          <MatchSuggestions />
        </LanguageProvider>
      </QueryClientProvider>
    );
    fireEvent.click(await screen.findByText("Album verbinden"));
    await screen.findByPlaceholderText("Album-Name…");
    await waitFor(() =>
      expect((screen.getByText("Album erstellen") as HTMLButtonElement).disabled).toBe(false)
    );

    fireEvent.click(screen.getByText("Album erstellen"));

    await waitFor(() => expect(albumMock).toHaveBeenCalled());
    // Der Fehlschlag haelt den Dialog OFFEN (kein `setMode(null)` bei
    // `onError`) — GruppenWahl bleibt gemountet und beobachtet die Abfrage
    // weiter, also ist hier der REFETCH der sichtbare Nachweis.
    await waitFor(() => expect(vorschauMock).toHaveBeenCalledTimes(2));
  });

  it("zeigt nach dem Anlegen keine veraltete 'keine Gruppe'-Antwort mehr, auch nicht unter dem PRODUKTIONS-Client", async () => {
    // End-zu-Ende-Nachweis des sichtbaren Verhaltens: erst "keine Gruppe",
    // dann angelegt, dann derselbe Name erneut abgefragt — jetzt MIT Gruppe.
    //
    // Nacharbeit 2, Fund 2 (Blindpruefer, gemessen): Diese Probe lief bisher
    // ueber `oeffneDialog()`/`zeichne()`, deren Test-Client KEINE eigene
    // `staleTime` setzt — TanStacks Bibliotheks-Standard ist dort ebenfalls
    // 0, also bewies ein gruener Lauf nichts gegen die ECHTEN 30 Sekunden aus
    // `main.tsx`. Jetzt baut dieser Test seinen EIGENEN Client mit
    // `QUERY_VORGABEN` (derselben Quelle wie `main.tsx`) — ein Mutationslauf,
    // der GruppenWahls `staleTime: 0` entfernt, muss HIER rot werden.
    vorschauMock.mockResolvedValueOnce(null);
    vorschauMock.mockResolvedValue(GRUPPE);

    const qc = new QueryClient({
      defaultOptions: { queries: { ...QUERY_VORGABEN, retry: false } },
    });
    render(
      <QueryClientProvider client={qc}>
        <LanguageProvider>
          <MatchSuggestions />
        </LanguageProvider>
      </QueryClientProvider>
    );
    fireEvent.click(await screen.findByText("Album verbinden"));
    await screen.findByPlaceholderText("Album-Name…");

    await waitFor(() => expect(vorschauMock).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect((screen.getByText("Album erstellen") as HTMLButtonElement).disabled).toBe(false)
    );

    fireEvent.click(screen.getByText("Album erstellen"));
    await waitFor(() => expect(albumMock).toHaveBeenCalledTimes(1));

    const wiederOeffnen = await screen.findByText("Album verbinden");
    fireEvent.click(wiederOeffnen);
    await screen.findByPlaceholderText("Album-Name…");

    // Ohne Invalidierung UND ohne GruppenWahls eigenes `staleTime: 0` wuerde
    // der Cache (30 Sekunden, `QUERY_VORGABEN`) die alte "keine Gruppe"-
    // Antwort weiter servieren, ohne die Vorschau erneut zu fragen.
    await waitFor(() => expect(vorschauMock).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());
  });

  it("sperrt 'Album verknuepfen', wenn das gewaehlte Album aus der Liste verschwindet (#110, Nacharbeit 2, WICHTIG Fund 1)", async () => {
    // Blindpruefer, Nacharbeit 2, Probe P5: Die Albumliste laedt neu (z.B.
    // Fokus-Refetch nach `staleTime`) und enthaelt die gewaehlte Kennung nicht
    // mehr — `wirksamerName` wird leer, `gruppenBereitschaft` haelt das
    // faelschlich fuer "nichts zu pruefen", der Knopf war frei. Gemessen:
    // gesendet wurde `{match_id, owner_account_id, existing_album_id}` ohne
    // Namen und ohne Gruppe.
    kontoAlbenMock.mockResolvedValue([{ id: "immich-1", name: "Testalbum" }]);
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <LanguageProvider>
          <MatchSuggestions />
        </LanguageProvider>
      </QueryClientProvider>
    );
    fireEvent.click(await screen.findByText("Album verbinden"));
    await screen.findByPlaceholderText("Album-Name…");
    fireEvent.click(screen.getByText("Vorhandenes verknüpfen"));
    await screen.findByText("Testalbum");
    const felder = screen.getAllByRole("combobox");
    fireEvent.change(felder[felder.length - 1], { target: { value: "immich-1" } });

    const knopf = () => screen.getByText("Album verknüpfen") as HTMLButtonElement;
    await waitFor(() => expect(knopf().disabled).toBe(false));

    // Die Liste laedt neu und enthaelt "immich-1" nicht mehr — die Kennung
    // im Zustand bleibt trotzdem stehen (niemand hat sie explizit geaendert).
    kontoAlbenMock.mockResolvedValue([]);
    await act(async () => {
      await qc.invalidateQueries({ queryKey: ["account-albums"] });
    });
    await waitFor(() => expect(screen.queryByText("Testalbum")).toBeNull());

    expect(knopf().disabled).toBe(true);
    fireEvent.click(knopf());
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(albumMock).not.toHaveBeenCalled();
  });
});

describe("Kleinfunde (#119, Punkt 4)", () => {
  it("ein Name aus reinem Leerraum gibt den Knopf NICHT frei", async () => {
    // `!!albumName` allein war truthy fuer "   " — der Knopf war frei, obwohl
    // GruppenWahl darunter nichts anzeigte (der Name faellt bei ihr auf
    // "leer" zurueck) und der Server einen solchen Namen ohnehin ablehnt.
    await oeffneDialog();
    fireEvent.change(screen.getByPlaceholderText("Album-Name…"), {
      target: { value: "   " },
    });

    expect((screen.getByText("Album erstellen") as HTMLButtonElement).disabled).toBe(true);

    fireEvent.click(screen.getByText("Album erstellen"));
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
    expect(albumMock).not.toHaveBeenCalled();
  });

  it("zeigt einen Hinweis, wenn das gewaehlte bestehende Album keinen Namen traegt", async () => {
    kontoAlbenMock.mockResolvedValue([{ id: "immich-leer", name: "" }]);
    await oeffneDialog();
    fireEvent.click(screen.getByText("Vorhandenes verknüpfen"));

    // Kein Text zum Warten (der Albumname ist leer) — stattdessen auf das
    // geladene <select> selbst warten (Owner-Auswahl + Album-Auswahl).
    await waitFor(() => expect(kontoAlbenMock).toHaveBeenCalled());
    await waitFor(() => expect(screen.getAllByRole("combobox").length).toBeGreaterThan(1));
    const felder = screen.getAllByRole("combobox");
    fireEvent.change(felder[felder.length - 1], { target: { value: "immich-leer" } });

    await waitFor(() =>
      expect(
        screen.getByText(
          "Dieses Album hat in Immich keinen Namen — bitte dort erst einen Namen vergeben."
        )
      ).toBeTruthy()
    );
    expect((screen.getByText("Album verknüpfen") as HTMLButtonElement).disabled).toBe(true);
  });
});
