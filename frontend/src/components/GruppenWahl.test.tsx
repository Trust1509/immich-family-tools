// Die Gruppenwahl-Komponente fuer sich (#81; Nacharbeit 1 zu #110,
// 28.09.2026: Fremd-/Blindpruefer-Funde am Bereitschafts-Signal).
//
// Der Zwischenzustand ist ein eigenes Verhalten (`docs/agents/lehren.md` §40):
// Ein Hinweis, der zu einer VERALTETEN Eingabe gehoert, ist schlimmer als
// keiner — der Nutzer bestaetigt dann eine Gruppe, die zu dem Namen, den er
// gerade tippt, gar nicht passt.
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { act, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider, onlineManager } from "@tanstack/react-query";
import React from "react";
import {
  GruppenWahl,
  gruppenBereitschaft,
  bestehendesAlbumGueltig,
  type GruppenAntwort,
} from "./GruppenWahl";
import { LanguageProvider } from "../i18n";
import { SPEICHER_SCHLUESSEL } from "../test-konstanten";
import { QUERY_VORGABEN } from "../queryClient";

// Alle Daten erfunden; das Repo ist oeffentlich.
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

const { vorschauMock } = vi.hoisted(() => ({ vorschauMock: vi.fn() }));

vi.mock("../api/client", () => ({
  api: { sync: { albumGroupPreview: vorschauMock } },
}));

function zeichne(albumName: string) {
  const antworten: GruppenAntwort[] = [];
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const baum = (name: string) => (
    <QueryClientProvider client={qc}>
      <LanguageProvider>
        <GruppenWahl
          albumName={name}
          eigeneGruppe={false}
          onEigeneGruppeChange={() => {}}
          onAntwort={(a) => antworten.push(a)}
        />
      </LanguageProvider>
    </QueryClientProvider>
  );
  const ergebnis = render(baum(albumName));
  return {
    ...ergebnis,
    antworten,
    /** Letzte Antwort gegen einen wirksamen Namen geprueft — genau das, was
     *  ein Aufrufer im eigenen Render tut. */
    letzteBereitschaft: (wirksamerName: string) =>
      gruppenBereitschaft(antworten[antworten.length - 1] ?? null, wirksamerName),
    neuZeichnen: (name: string) => ergebnis.rerender(baum(name)),
  };
}

beforeEach(() => {
  // `resetAllMocks` statt `clearAllMocks`: Ein `mockResolvedValueOnce`, den
  // ein Test (z.B. wegen einer Mutation) nie verbraucht, blieb sonst in der
  // Warteschlange und beantwortete den ERSTEN Aufruf des NAECHSTEN Tests —
  // gemessen bei der Rot-Beweis-Probe zu Fund 1/Nacharbeit 1 (28.09.2026):
  // ein liegengebliebenes `mockResolvedValueOnce(GRUPPE)` liess einen ganz
  // anderen Test rot werden. `resetAllMocks` leert auch die Warteschlange;
  // der Standard wird danach hier neu gesetzt.
  vi.resetAllMocks();
  try {
    localStorage.setItem(SPEICHER_SCHLUESSEL, "de");
  } catch {
    /* in dieser Umgebung nicht zwingend vorhanden */
  }
  vorschauMock.mockResolvedValue(GRUPPE);
});

afterEach(() => {
  // Nie offline aus einem Test in den naechsten durchsickern lassen.
  onlineManager.setOnline(true);
});

describe("GruppenWahl", () => {
  it("zeigt gar nichts, solange kein Name eingegeben ist", () => {
    zeichne("   ");

    expect(screen.queryByText("Wird geprüft …")).toBeNull();
    expect(screen.queryByText("Tritt der bestehenden Gruppe bei")).toBeNull();
    expect(vorschauMock).not.toHaveBeenCalled();
  });

  it("nimmt die Antwort zurueck, sobald der Name nicht mehr dazu passt", async () => {
    // Genau der Fall, den ein Test mit einer haengenden Abfrage NICHT trifft:
    // Die Antwort ist da, sie gehoert nur zu einem aelteren Namen.
    const { neuZeichnen } = zeichne("Testalbum");
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());

    neuZeichnen("Ganz anderer Name");

    // SOFORT weg — nicht erst, wenn die neue Abfrage geantwortet hat.
    expect(screen.queryByText("Tritt der bestehenden Gruppe bei")).toBeNull();
    expect(screen.getByText("Wird geprüft …")).toBeTruthy();
  });

  it("nimmt die Antwort auch zurueck, wenn das Feld GELEERT wird", async () => {
    // Ein eigener Fall, kein Sonderfall des vorigen: Bei leerem Feld wird
    // NICHT gesucht, also greift der Pruefzustand nicht — die alte Antwort
    // haengt aber noch am vorigen Schluessel. Gemessen: Ohne die zweite
    // Schranke behauptete die App rund eine Drittelsekunde etwas ueber einen
    // Namen, den es nicht mehr gab.
    const { neuZeichnen } = zeichne("Testalbum");
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());

    neuZeichnen("");

    expect(screen.queryByText("Tritt der bestehenden Gruppe bei")).toBeNull();
    expect(screen.queryByText("Wird geprüft …")).toBeNull();
  });
});

describe("gruppenBereitschaft (reine Funktion, #110 Nacharbeit 1 Fund 3)", () => {
  // Der Vergleich "gehoert diese Antwort noch zur aktuellen Eingabe" liegt
  // seit der Nacharbeit HIER, nicht mehr in einer Buchung, die `GruppenWahl`
  // per Effekt nach oben schiebt — deshalb reine, direkt pruefbare Funktion.
  it("ist bereit, wenn nichts einzugeben ist — unabhaengig von einer alten Antwort", () => {
    const alt: GruppenAntwort = { name: "Alter Name", ok: true, groupId: "g1" };
    expect(gruppenBereitschaft(alt, "   ")).toEqual({ bereit: true, gruppeId: null });
  });

  it("ist NICHT bereit ohne jede Antwort", () => {
    expect(gruppenBereitschaft(null, "Testalbum")).toEqual({ bereit: false, gruppeId: null });
  });

  it("ist NICHT bereit, wenn die Antwort zu einem ANDEREN Namen gehoert", () => {
    const antwort: GruppenAntwort = { name: "Anderer Name", ok: true, groupId: "g1" };
    expect(gruppenBereitschaft(antwort, "Testalbum")).toEqual({ bereit: false, gruppeId: null });
  });

  it("ist NICHT bereit bei einer fehlgeschlagenen Antwort, auch zum RICHTIGEN Namen", () => {
    // Owner-Entscheid 28.09.2026 (#110, Nacharbeit 1): kein Fail-open mehr.
    const antwort: GruppenAntwort = { name: "Testalbum", ok: false, groupId: null };
    expect(gruppenBereitschaft(antwort, "Testalbum")).toEqual({ bereit: false, gruppeId: null });
  });

  it("ist bereit UND nennt die Gruppe bei Erfolg zum RICHTIGEN Namen (getrimmt)", () => {
    const antwort: GruppenAntwort = { name: "Testalbum", ok: true, groupId: "g1" };
    expect(gruppenBereitschaft(antwort, "  Testalbum  ")).toEqual({ bereit: true, gruppeId: "g1" });
  });
});

describe("bestehendesAlbumGueltig (reine Funktion, #110 Nacharbeit 2 Fund 1)", () => {
  // Dieselbe Regel, die MatchSuggestions.tsx UND ManualMatch.tsx im Modus
  // "Verknuepfen" aufrufen — EINE Quelle statt zweier Kopien.
  it("ist NICHT gueltig ohne jede Kennung", () => {
    expect(bestehendesAlbumGueltig("", "Testalbum")).toBe(false);
  });

  it("ist NICHT gueltig, wenn sich zur Kennung KEIN Name mehr aufloesen laesst", () => {
    // Genau der Fall, wenn die Albumliste neu laedt und die Kennung nicht
    // mehr enthaelt: die Kennung selbst steht noch, der Name ist weg.
    expect(bestehendesAlbumGueltig("immich-1", "")).toBe(false);
    expect(bestehendesAlbumGueltig("immich-1", "   ")).toBe(false);
  });

  it("ist gueltig, wenn beides vorliegt", () => {
    expect(bestehendesAlbumGueltig("immich-1", "Testalbum")).toBe(true);
  });
});

describe("GruppenWahl: Antwort-Meldung (#110, Nacharbeit 1)", () => {
  // Der Aufrufer sperrt sein Anlegen auf `gruppenBereitschaft(antwort, ...)`
  // — diese Tests pruefen das ROHE SIGNAL (`onAntwort`), nicht die Sperre
  // selbst (die steht bei den Konsumenten: MatchSuggestions.gruppenwahl.
  // test.tsx, ManualMatch.gruppenwahl.test.tsx).
  it("meldet sofort eine bereite Antwort, solange kein Name eingegeben ist", () => {
    const { letzteBereitschaft } = zeichne("   ");

    expect(letzteBereitschaft("   ").bereit).toBe(true);
  });

  it("meldet unbereit, solange geprueft wird, und bereit danach", async () => {
    let antworten!: (wert: typeof GRUPPE) => void;
    vorschauMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          antworten = resolve;
        })
    );

    const { letzteBereitschaft } = zeichne("Testalbum");

    // Schon VOR dem ersten Aufruf unbereit — die Entprellung selbst zaehlt
    // schon als "noch keine Antwort".
    expect(letzteBereitschaft("Testalbum").bereit).toBe(false);
    await waitFor(() => expect(vorschauMock).toHaveBeenCalled());
    expect(letzteBereitschaft("Testalbum").bereit).toBe(false);

    antworten(GRUPPE);
    await waitFor(() => expect(letzteBereitschaft("Testalbum").bereit).toBe(true));
    expect(letzteBereitschaft("Testalbum").gruppeId).toBe("gruppe-1");
  });

  it("wird beim Weitertippen waehrend einer laufenden Abfrage wieder unbereit", async () => {
    const { letzteBereitschaft, neuZeichnen } = zeichne("Testalbum");
    await waitFor(() => expect(letzteBereitschaft("Testalbum").bereit).toBe(true));

    neuZeichnen("Ganz anderer Name");

    // Sofort unbereit fuer den NEUEN Namen, nicht erst nach der neuen
    // Antwort — sonst koennte ein Klick zwischen Tastendruck und Antwort
    // noch durchrutschen.
    expect(letzteBereitschaft("Ganz anderer Name").bereit).toBe(false);
    await waitFor(() => expect(letzteBereitschaft("Ganz anderer Name").bereit).toBe(true));
  });

  it("bleibt WAEHREND einer echt laufenden Abfrage unbereit fuer den NEUEN Namen, auch wenn eine aeltere Antwort noch eintrifft", async () => {
    // Die Regressionsklasse, die die Nacharbeit schliesst: eine Antwort, die
    // zu einer AELTEREN Eingabe gehoert, darf den NEUEN Namen nie freigeben —
    // unabhaengig davon, wann genau sie eintrifft.
    let ersteAntwort!: (wert: typeof GRUPPE) => void;
    vorschauMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          ersteAntwort = resolve;
        })
    );

    const { letzteBereitschaft, neuZeichnen } = zeichne("Testalbum");
    await waitFor(() => expect(vorschauMock).toHaveBeenCalledTimes(1));
    expect(letzteBereitschaft("Testalbum").bereit).toBe(false);

    neuZeichnen("Zweiter Name");
    expect(letzteBereitschaft("Zweiter Name").bereit).toBe(false);

    // Die ERSTE (jetzt veraltete) Anfrage antwortet — darf "Zweiter Name"
    // nicht freigeben.
    ersteAntwort(GRUPPE);
    await new Promise((r) => setTimeout(r, 0));
    expect(letzteBereitschaft("Zweiter Name").bereit).toBe(false);

    // Erst die Antwort zur NEUEN Eingabe gibt frei.
    await waitFor(() => expect(letzteBereitschaft("Zweiter Name").bereit).toBe(true));
  });

  it("serviert beim Wiedereinhaengen fuer denselben Namen NIE eine gecachte Antwort, auch nicht unter dem PRODUKTIONS-Client (#110, Nacharbeit 1 Fund 1 / Nacharbeit 2 Fund 2)", async () => {
    // Anders als die Invalidierungs-Proben bei den Konsumenten: hier laeuft
    // KEINE Mutation und KEINE Invalidierung — nur GruppenWahls eigenes
    // `staleTime: 0` (je Abfrage) kann hier ueberhaupt greifen.
    //
    // Nacharbeit 2, Fund 2 (Blindpruefer, gemessen): Diese Probe lief bisher
    // mit einem Test-Client OHNE eigene `staleTime` — TanStacks Bibliotheks-
    // Standard ist dort ebenfalls 0, also bewies ein gruener Lauf nichts
    // gegen die ECHTEN 30 Sekunden aus `main.tsx`/`queryClient.ts`. Ein
    // Mutationslauf, der GruppenWahls `staleTime: 0` entfernte, blieb unter
    // dem alten Test-Client gruen. Jetzt teilt sich dieser Test
    // `QUERY_VORGABEN` mit `main.tsx` — ein produktionsnaher Client mit
    // `staleTime: 30_000` als AUSGANGSPUNKT, den GruppenWahls eigene
    // `staleTime: 0` je Abfrage erst UEBERSCHREIBEN muss.
    vorschauMock.mockResolvedValueOnce(null);
    const qc = new QueryClient({
      defaultOptions: { queries: { ...QUERY_VORGABEN, retry: false } },
    });
    const antworten: GruppenAntwort[] = [];
    const baum = (mountKey: number) => (
      <QueryClientProvider client={qc}>
        <LanguageProvider>
          <GruppenWahl
            key={mountKey}
            albumName="Testalbum"
            eigeneGruppe={false}
            onEigeneGruppeChange={() => {}}
            onAntwort={(a) => antworten.push(a)}
          />
        </LanguageProvider>
      </QueryClientProvider>
    );
    const { rerender } = render(baum(1));
    await waitFor(() => expect(vorschauMock).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(gruppenBereitschaft(antworten[antworten.length - 1] ?? null, "Testalbum").bereit).toBe(
        true
      )
    );

    // Andere Antwort bereitstellen und NEU MOUNTEN (anderer `key`, GLEICHER
    // QueryClient/Cache) — wie das Schliessen und erneute Oeffnen desselben
    // Dialogs fuer denselben Namen.
    vorschauMock.mockResolvedValueOnce(GRUPPE);
    rerender(baum(2));

    await waitFor(() => expect(vorschauMock).toHaveBeenCalledTimes(2));
    await waitFor(() => {
      const bereitschaft = gruppenBereitschaft(
        antworten[antworten.length - 1] ?? null,
        "Testalbum"
      );
      expect(bereitschaft.bereit && bereitschaft.gruppeId).toBe("gruppe-1");
    });
  });

  it("bleibt gesperrt und zeigt eine Meldung samt 'Erneut pruefen', wenn die Abfrage fehlschlaegt", async () => {
    // Owner-Entscheid 28.09.2026 (#110, Nacharbeit 1, ersetzt die Erstfassung):
    // Ein Fehlschlag gibt das Anlegen NICHT frei — die Vorschau laeuft gegen
    // denselben Server wie das Anlegen selbst.
    vorschauMock.mockRejectedValue(new Error("netzwerk kaputt"));

    const { letzteBereitschaft } = zeichne("Testalbum");

    await waitFor(() =>
      expect(screen.getByText("Prüfung fehlgeschlagen — Anlegen bleibt gesperrt.")).toBeTruthy()
    );
    expect(screen.getByText("Erneut prüfen")).toBeTruthy();
    expect(letzteBereitschaft("Testalbum").bereit).toBe(false);
  });

  it("'Erneut pruefen' fragt neu nach und gibt bei Erfolg frei", async () => {
    vorschauMock.mockRejectedValueOnce(new Error("netzwerk kaputt"));
    vorschauMock.mockResolvedValueOnce(GRUPPE);

    const { letzteBereitschaft } = zeichne("Testalbum");
    await waitFor(() => expect(screen.getByText("Erneut prüfen")).toBeTruthy());

    fireEvent.click(screen.getByText("Erneut prüfen"));

    await waitFor(() => expect(vorschauMock).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(letzteBereitschaft("Testalbum").bereit).toBe(true));
    expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy();
  });

  it("eine haengende Anfrage endet nach der Zeitgrenze als Fehler, nicht auf ewig gesperrt (#110, Nacharbeit 2, WICHTIG Fund 3c)", async () => {
    // Ungetestet bis Nacharbeit 2 (Blindpruefer Probe P4): Der Mock haengt
    // NICHT an einer festen Anzahl Millisekunden, sondern am ABBRUCH-SIGNAL
    // selbst — genau das, was `AbortSignal.timeout(10_000)` in GruppenWahl
    // uebergibt. Eine Mutation, die die Zeitgrenze entfernt, wuerde hier
    // niemals abbrechen; diese Probe wartet deshalb wirklich die vollen
    // ~10 echten Sekunden ab, statt sie zu simulieren.
    vorschauMock.mockImplementation(
      (_name: string, signal?: AbortSignal) =>
        new Promise((_resolve, reject) => {
          signal?.addEventListener("abort", () => reject(signal.reason));
        })
    );

    const { letzteBereitschaft } = zeichne("Testalbum");

    await waitFor(() => expect(screen.getByText(/Prüfung fehlgeschlagen/)).toBeTruthy(), {
      timeout: 12_000,
    });
    expect(letzteBereitschaft("Testalbum").bereit).toBe(false);
  }, 15_000);

  it("zaehlt 'pausiert' (offline) NICHT als Antwort — weder bereit noch Fehlermeldung", async () => {
    // Fund 2, Nacharbeit 1 (Fremdpruefer BLOCKER): Die Erstfassung pruefte
    // nur `isFetching` (bei "paused" false) und meldete offline faelschlich
    // als bereit. TanStack haelt eine pausierte Anfrage automatisch an, bis
    // die Verbindung zurueckkommt — sie loest weder "erfolg" noch "fehler"
    // aus, solange sie pausiert ist.
    onlineManager.setOnline(false);

    const { letzteBereitschaft } = zeichne("Testalbum");
    await waitFor(() => expect(screen.getByText("Wird geprüft …")).toBeTruthy());
    expect(vorschauMock).not.toHaveBeenCalled();
    expect(letzteBereitschaft("Testalbum").bereit).toBe(false);
    expect(screen.queryByText(/Prüfung fehlgeschlagen/)).toBeNull();

    onlineManager.setOnline(true);

    await waitFor(() => expect(vorschauMock).toHaveBeenCalled());
    await waitFor(() => expect(letzteBereitschaft("Testalbum").bereit).toBe(true));
  });

  it("gibt NICHT frei, wenn eine Invalidierung offline auf eine VORHANDENE Erfolgsantwort trifft (#110, Nacharbeit 2, WICHTIG Fund 3b)", async () => {
    // Schaerfer als der Test oben: hier gibt es schon eine erfolgreiche
    // Antwort (`status: "success"`), BEVOR die Verbindung wegfaellt. Eine
    // Mutation, die `fetchStatus !== "idle"` durch `fetchStatus === "fetching"`
    // ersetzt, uebersieht "paused" und laesst die ALTE Erfolgsantwort stehen —
    // gemessen vom Blindpruefer (Probe P3): dieser Fall trat im Test oben
    // NIE auf, weil dort nie zuvor erfolgreich geantwortet wurde.
    vorschauMock.mockResolvedValue(GRUPPE);
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const antworten: GruppenAntwort[] = [];
    render(
      <QueryClientProvider client={qc}>
        <LanguageProvider>
          <GruppenWahl
            albumName="Testalbum"
            eigeneGruppe={false}
            onEigeneGruppeChange={() => {}}
            onAntwort={(a) => antworten.push(a)}
          />
        </LanguageProvider>
      </QueryClientProvider>
    );
    await waitFor(() =>
      expect(gruppenBereitschaft(antworten[antworten.length - 1] ?? null, "Testalbum").bereit).toBe(
        true
      )
    );

    onlineManager.setOnline(false);
    await act(async () => {
      await qc.invalidateQueries({ queryKey: ["album-group"] });
    });
    await new Promise((r) => setTimeout(r, 50));

    expect(qc.getQueryState(["album-group", "Testalbum"])?.fetchStatus).toBe("paused");
    expect(gruppenBereitschaft(antworten[antworten.length - 1] ?? null, "Testalbum").bereit).toBe(
      false
    );
  });

  it("zeigt bei einem Fehlschlag NICHT die noch vorhandene ALTE Gruppe — Fehler bleibt Fehler, auch mit Resten (#110, Nacharbeit 1, Fund 4)", async () => {
    // Genauer Fund 4: nicht "schlaegt von Anfang an fehl" (das deckt der
    // Test oben ab), sondern "war erfolgreich, ein spaeterer Refetch
    // schlaegt fehl, TanStack behaelt `data` vom letzten Erfolg". Die
    // Erstfassung entschied ueber `!laeuft && !zeigeGruppe`, was bei einem
    // Fehlschlag griff, aber `data` konnte noch die ALTE Gruppe zeigen und
    // wurde unsichtbar mitgeschickt. Der Fix haengt an `status`, nicht an
    // `data` — bleibt also auch dann korrekt, wenn `data` haengen bleibt.
    vorschauMock.mockResolvedValueOnce(GRUPPE);
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const antworten: GruppenAntwort[] = [];
    const baum = (mountKey: number) => (
      <QueryClientProvider client={qc}>
        <LanguageProvider>
          <GruppenWahl
            key={mountKey}
            albumName="Testalbum"
            eigeneGruppe={false}
            onEigeneGruppeChange={() => {}}
            onAntwort={(a) => antworten.push(a)}
          />
        </LanguageProvider>
      </QueryClientProvider>
    );
    const { rerender } = render(baum(1));
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());

    // Neu mounten (wie ein erneut geoeffneter Dialog) — `refetchOnMount:
    // "always"` fragt trotz vorhandener Erfolgs-Antwort erneut, und DIESMAL
    // schlaegt es fehl.
    vorschauMock.mockRejectedValueOnce(new Error("netzwerk kaputt"));
    rerender(baum(2));

    await waitFor(() =>
      expect(screen.getByText("Prüfung fehlgeschlagen — Anlegen bleibt gesperrt.")).toBeTruthy()
    );
    expect(screen.queryByText("Tritt der bestehenden Gruppe bei")).toBeNull();
    expect(screen.queryByText("Person X")).toBeNull();
    const letzte = gruppenBereitschaft(antworten[antworten.length - 1] ?? null, "Testalbum");
    expect(letzte).toEqual({ bereit: false, gruppeId: null });
  });
});

/** Zeichnet die Komponente MIT Zustand — sonst laesst sich der Ruecksetzer
 *  nicht beobachten, und genau der war ungedeckt. */
function zeichneMitZustand(start: string) {
  const antworten: GruppenAntwort[] = [];
  function Huelle({ name }: { name: string }) {
    const [eigen, setEigen] = React.useState(false);
    return (
      <>
        <span data-testid="wahl">{String(eigen)}</span>
        <GruppenWahl
          albumName={name}
          eigeneGruppe={eigen}
          onEigeneGruppeChange={setEigen}
          onAntwort={(a) => antworten.push(a)}
        />
      </>
    );
  }
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const baum = (name: string) => (
    <QueryClientProvider client={qc}>
      <LanguageProvider>
        <Huelle name={name} />
      </LanguageProvider>
    </QueryClientProvider>
  );
  const e = render(baum(start));
  return { antworten, neuZeichnen: (n: string) => e.rerender(baum(n)) };
}

describe("GruppenWahl: die Wahl und ihre Meldung", () => {
  it("setzt die Wahl zurueck, wenn die Gruppe wirklich verschwindet", async () => {
    // Die Zeile liess sich ersatzlos streichen, ohne dass ein Test rot wurde
    // (Blindpruefer 21.09.2026) — obwohl genau dieses Verhalten der Fund war.
    const { neuZeichnen } = zeichneMitZustand("Testalbum");
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());

    fireEvent.click(screen.getByLabelText("Eigene Gruppe anlegen"));
    expect(screen.getByTestId("wahl").textContent).toBe("true");

    vorschauMock.mockResolvedValue(null);
    neuZeichnen("Kennt keine Gruppe");

    await waitFor(() => expect(screen.getByTestId("wahl").textContent).toBe("false"));
  });

  it("setzt eine gewaehlte eigene Gruppe NICHT zurueck, wenn die Vorschau nur fehlschlaegt", async () => {
    // Fund 4, Nacharbeit 1 (gemessen): Die Erstfassung reagierte auf JEDES
    // "keine Antwort mehr, die eine Gruppe zeigt" — Fehlschlag eingeschlossen
    // — und verwarf damit eine bereits gewaehlte "eigene Gruppe" nach einem
    // reinen Netzwerkfehler. Ein Fehlschlag ist keine Auskunft ueber die
    // Gruppe.
    const { neuZeichnen } = zeichneMitZustand("Testalbum");
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());

    fireEvent.click(screen.getByLabelText("Eigene Gruppe anlegen"));
    expect(screen.getByTestId("wahl").textContent).toBe("true");

    vorschauMock.mockRejectedValue(new Error("netzwerk kaputt"));
    neuZeichnen("Testalbum geaendert");

    await waitFor(() =>
      expect(screen.getByText("Prüfung fehlgeschlagen — Anlegen bleibt gesperrt.")).toBeTruthy()
    );
    expect(screen.getByTestId("wahl").textContent).toBe("true");
  });

  it("meldet keine Gruppe, solange die Antwort nicht zur Eingabe passt", async () => {
    const { antworten, neuZeichnen } = zeichneMitZustand("Testalbum");
    await waitFor(() =>
      expect(
        antworten.some((a) => a.name === "Testalbum" && a.ok && a.groupId === "gruppe-1")
      ).toBe(true)
    );

    neuZeichnen("Anderer Name");

    // Die zuletzt gemeldete Antwort darf nicht mehr "Testalbum" freigeben —
    // sonst schickt der Aufrufer eine Gruppe mit, die zur Eingabe nicht mehr
    // gehoert.
    await waitFor(() => {
      const letzte = antworten[antworten.length - 1];
      expect(letzte.ok && letzte.name === "Testalbum").toBe(false);
    });
  });
});
