import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type GroupCandidate } from "../api/client";
import { useT } from "../i18n";

/**
 * Die Antwort der Gruppenvorschau zu EINEM (entprellten, getrimmten) Namen —
 * mit dem Namen selbst, zu dem sie gehoert.
 *
 * Nacharbeit 1 zu #110 (Fremd-/Blindpruefer, 28.09.2026): Die vorherige
 * Fassung leitete in `GruppenWahl` selbst eine fertige Buchung ("bereit":
 * boolean) ab und schickte NUR die per Effekt nach oben. Zwischen einem
 * Tastendruck im Elternteil (neue Eingabe, im SELBEN Render) und dem Effekt,
 * der die Buchung im Kind nachzieht (einen Render SPAETER), lag ein Commit
 * mit neuer Eingabe und alter Buchung — nicht in jedem Test sichtbar (RTLs
 * `act()` verschluckt genau diesen Spalt), aber im echten Browser real.
 * Jetzt traegt die Antwort NUR Rohdaten (Name, Erfolg, Gruppe); der
 * Vergleich "gehoert diese Antwort noch zur aktuellen Eingabe" passiert erst
 * beim Aufrufer, in DESSEN eigenem Render, gegen dessen eigenen aktuellen
 * wirksamen Namen (`gruppenBereitschaft` unten) — die Buchung darf
 * nachlaufen, der VERGLEICH nicht.
 */
export interface GruppenAntwort {
  /** Der (entprellte, getrimmte) Name, zu dem diese Antwort gehoert. */
  name: string;
  /**
   * true nur, wenn zu `name` eine ERFOLGREICHE, ABGESCHLOSSENE Antwort
   * vorliegt — nicht: laeuft noch, nicht: pausiert (offline), nicht:
   * fehlgeschlagen. Owner-Entscheid 28.09.2026 (#110, Nacharbeit 1, ersetzt
   * die Erstfassung): Ein Fehlschlag der Vorschau gibt das Anlegen NICHT
   * frei — die Vorschau laeuft gegen denselben Server wie das Anlegen
   * selbst, ein Fail-open waere ein Griff ins Ungewisse.
   */
  ok: boolean;
  /** Die Gruppe, der beigetreten wuerde — bei "keine Gruppe" oder "eigene
   *  Gruppe" (auch innerhalb einer Mehrdeutigkeit) immer `null`. */
  groupId: string | null;
  /**
   * #113: true nur, wenn der Name MEHRDEUTIG ist (mehrere Gruppen tragen
   * ihn) UND der Nutzer noch KEINE der Kandidaten und auch nicht "eigene
   * Gruppe" gewaehlt hat. Optional statt eines Pflichtfelds, damit ein
   * Aufrufer, der die alte, flache `GruppenAntwort`-Form konstruiert (siehe
   * `GruppenWahl.test.tsx`), unveraendert kompiliert — `undefined` zaehlt
   * wie `false`. Der Aufrufer sperrt sein Anlegen zusaetzlich darauf.
   */
  wahlAusstehend?: boolean;
}

/**
 * Ob zu `wirksamerName` (roh, ungetrimmt erlaubt) JETZT eine gueltige
 * Antwort vorliegt, und welche Gruppe dann zu senden ist.
 *
 * Reine Funktion, extra herausgezogen, damit BEIDE Anlege-Wege dieselbe
 * Regel im eigenen Render aufrufen, statt sie zweimal nachzubauen — zwei
 * Kopien derselben Regel waren bei #78 mit ein Grund, dass ein Defekt so
 * lange unentdeckt blieb (`docs/agents/lehren.md` §39). Dieselbe
 * Normalisierung (trim) wie in `GruppenWahl` selbst.
 */
export function gruppenBereitschaft(
  antwort: GruppenAntwort | null,
  wirksamerName: string
): { bereit: boolean; gruppeId: string | null } {
  const name = wirksamerName.trim();
  // Nichts einzugeben heisst nichts zu pruefen — ein leeres Feld sperrt
  // nicht, unabhaengig davon, was eine fruehere Antwort behauptete.
  if (!name) return { bereit: true, gruppeId: null };
  // #113: bei Mehrdeutigkeit bleibt es gesperrt, bis der Nutzer eine der
  // Kandidaten (oder "eigene Gruppe") gewaehlt hat — `ok` allein (die
  // Vorschau selbst war erfolgreich) reicht dafuer nicht.
  if (!antwort || antwort.name !== name || !antwort.ok || antwort.wahlAusstehend) {
    return { bereit: false, gruppeId: null };
  }
  return { bereit: true, gruppeId: antwort.groupId };
}

/**
 * Typ-Wache fuer die "many"-Antwort (#113) — als eigene, benannte Funktion
 * statt eines Inline-`"status" in gruppe`-Checks an jeder Stelle, DAMIT
 * TypeScript `gruppe` an jeder Aufrufstelle wirklich EINENGT (auch ueber
 * eine `const mehrdeutig = ...`-Zwischenvariable hinweg — TS engt seit 4.4
 * durch "aliased conditions" hindurch ein). Eine Form-Heuristik ohne
 * Typ-Wache waere hier ein stilles Sicherheitsloch: `gruppe.person_refs`
 * existiert auf der "many"-Form nicht.
 */
function mehrdeutigeAntwort(
  g: GroupCandidate | { status: "many"; candidates: GroupCandidate[] } | null | undefined
): g is { status: "many"; candidates: GroupCandidate[] } {
  return !!g && "status" in g && g.status === "many";
}

/**
 * Ob eine gewaehlte BESTEHENDE Albumkennung gerade noch gueltig ist — d.h.
 * ob sich zu ihr JETZT ein Name aufloesen laesst.
 *
 * Reine Funktion, aus demselben Grund herausgezogen wie `gruppenBereitschaft`
 * (#78, `docs/agents/lehren.md` §39): `MatchSuggestions.tsx` (Modus
 * "Verknuepfen") UND `ManualMatch.tsx` (Modus "Verknuepfen") pruefen dieselbe
 * Regel. Nacharbeit 1 hatte sie nur in `ManualMatch.tsx` — Nacharbeit 2, Fund
 * 1 (Blindpruefer, Probe P5): dieselbe Luecke traf `MatchSuggestions.tsx`
 * genauso, nur ueber einen anderen Ausloeser (die Albumliste laedt neu und
 * enthaelt die gewaehlte Kennung nicht mehr — z.B. `invalidateQueries(
 * ["account-albums"])`, nicht nur ein Kontowechsel). Fehlt der Name (Liste
 * neu geladen, Konto gewechselt, Album in Immich geloescht), ist die Kennung
 * wertlos, auch wenn sie noch im Zustand steht — ohne diese Pruefung meldet
 * `gruppenBereitschaft` faelschlich "nichts zu pruefen" fuer einen LEEREN
 * Namen, und der leere Zustand sieht wie "bereit" aus.
 */
export function bestehendesAlbumGueltig(existingAlbumId: string, wirksamerName: string): boolean {
  return !!existingAlbumId && !!wirksamerName.trim();
}

/**
 * Zeigt, welcher Gruppe ein neues Album beitreten wuerde — und laesst den
 * Nutzer widersprechen (#81).
 *
 * Eine Komponente fuer BEIDE Anlege-Wege (Vorschlagsliste und manueller
 * Abgleich). Zwei Kopien derselben Regel waren bei #78 mit ein Grund, dass
 * der Defekt so lange unentdeckt blieb (`docs/agents/lehren.md` §39).
 *
 * Erscheint nur, wenn der Name wirklich eine Gruppe trifft: Bei einem neuen
 * Namen bleibt der Ablauf unveraendert, ohne zusaetzlichen Klick.
 *
 * Meldet ueber `onAntwort` JEDE Antwort zu JEDEM (entprellten) Namen — der
 * Aufrufer entscheidet per `gruppenBereitschaft`, ob sie noch aktuell ist,
 * und sperrt sein Anlegen darauf (#110): Wer sofort klickt, darf keine
 * Anlage anstossen, bevor eine gueltige Antwort zur AKTUELLEN Eingabe da ist.
 */
export function GruppenWahl({
  albumName,
  eigeneGruppe,
  onEigeneGruppeChange,
  onAntwort,
}: {
  /** Der Name, um den es beim Gruppieren geht — leer schaltet die Abfrage ab. */
  albumName: string;
  eigeneGruppe: boolean;
  onEigeneGruppeChange: (wert: boolean) => void;
  /** Jede Antwort, mit dem Namen, zu dem sie gehoert (siehe `GruppenAntwort`). */
  onAntwort: (antwort: GruppenAntwort) => void;
}) {
  const { t } = useT();
  const [entprellt, setEntprellt] = useState("");
  const gesucht = albumName.trim();

  // Entprellt: waehrend des Tippens nicht bei jedem Zeichen fragen.
  useEffect(() => {
    const zeit = setTimeout(() => setEntprellt(gesucht), 300);
    return () => clearTimeout(zeit);
  }, [gesucht]);

  const {
    data: gruppe,
    status,
    fetchStatus,
    refetch,
  } = useQuery({
    queryKey: ["album-group", entprellt],
    queryFn: () => {
      // Zeitgrenze (#110, Nacharbeit 1, Fund 6): ohne sie wuerde eine
      // haengende Anfrage `fetchStatus` nie wieder "idle" werden lassen —
      // die Sperre bliebe fuer immer stehen, mit oder ohne Fail-open.
      return api.sync.albumGroupPreview(entprellt, AbortSignal.timeout(10_000));
    },
    enabled: !!entprellt,
    // Cache nie vertrauen (#110, Nacharbeit 1, BLOCKER): Die Vorschau laeuft
    // gegen denselben Server wie das Anlegen — ein zweiter Dialog fuer
    // denselben Namen, Sekunden nach einer Anlage, die genau diesen Namen
    // gruppiert hat, darf keine mit `staleTime: 30_000` (`queryClient.ts`,
    // main.tsx) beliebig alte "keine Gruppe"-Antwort servieren. `staleTime: 0`
    // HIER, je Abfrage, ist die zweite Verteidigungslinie; die erste ist die
    // Invalidierung nach jeder gruppen-aendernden Mutation (fuenf
    // Aufrufstellen: Anlegen/Verknuepfen, names-multi, Umbenennen, Entfernen,
    // Erweitern — #110, Nacharbeit 1, BLOCKER Fund 1).
    //
    // BEWUSST OHNE `refetchOnMount: "always"` (stand hier bis Nacharbeit 2):
    // Gemessen (Blindpruefer, 28.09.2026) und selbst nachvollzogen — die
    // Option greift nur beim REACT-Mount-Moment der Komponente, und GENAU
    // DANN ist der Schluessel wegen der Entprellung noch "" und die Abfrage
    // `enabled: false`. Bis der Schluessel (300ms spaeter) einen echten Namen
    // traegt, ist es kein neuer Mount mehr aus TanStacks Sicht — die Option
    // hatte nie etwas zu tun. Entfernt; `npm test` bleibt gruen (Zahl hier
    // bewusst weggelassen — sie veraltet mit jedem neuen Test, siehe
    // `docs/agents/lehren.md`, "Belegen statt annehmen").
    staleTime: 0,
  });

  const passt = entprellt === gesucht;

  // #113: "many" ist an einem eigenen Feld erkennbar, das der eindeutige
  // Treffer NIE traegt (dessen Form ist unveraendert flach, siehe
  // `api/client.ts`, `AlbumGroupPreview`) — kein Raten anhand der Form.
  const mehrdeutig = mehrdeutigeAntwort(gruppe);
  const kandidaten: GroupCandidate[] = mehrdeutig ? gruppe.candidates : [];

  // Welchen Kandidaten der Nutzer bei Mehrdeutigkeit gewaehlt hat — lebt NUR
  // hier, nicht beim Aufrufer: `onAntwort` traegt das Ergebnis (`groupId`)
  // ohnehin schon nach oben, genau wie beim eindeutigen Treffer. Eine
  // Auswahl gehoert zu GENAU EINER Eingabe; wechselt der Name, ist sie
  // wertlos (derselbe Grundsatz wie bei der Antwort selbst).
  const [gewaehlterKandidat, setGewaehlterKandidat] = useState<string | null>(null);
  useEffect(() => {
    setGewaehlterKandidat(null);
  }, [entprellt]);
  // Verteidigt gegen eine Auswahl, die nach einer Invalidierung nicht mehr
  // unter den frischen Kandidaten steht (die gewaehlte Gruppe ist
  // inzwischen wirklich verschwunden) — dieselbe Klasse wie der
  // Ruecksetzer fuer "eigene Gruppe" unten, nur fuer die vielen Kandidaten.
  useEffect(() => {
    if (gewaehlterKandidat && !kandidaten.some((k) => k.group_id === gewaehlterKandidat)) {
      setGewaehlterKandidat(null);
    }
  }, [kandidaten, gewaehlterKandidat]);

  // VIER Zustaende (Nacharbeit 1 erweitert die vorherigen drei um
  // "pausiert/offline", das vorher faelschlich als abgeschlossen zaehlte):
  //
  //   leer   — nichts einzugeben, nichts zu pruefen
  //   laeuft — Entprellung, aktives Holen ODER pausiert (offline) — noch
  //            keine verwertbare Antwort
  //   erfolg — abgeschlossen (`fetchStatus === "idle"`), erfolgreich, zur
  //            AKTUELLEN Eingabe
  //   fehler — abgeschlossen, fehlgeschlagen, zur AKTUELLEN Eingabe
  //
  // "pausiert" zaehlt zu "laeuft", nicht zu "fehler": TanStack setzt eine
  // pausierte Abfrage automatisch fort, sobald die Verbindung zurueckkommt —
  // eine Fehlermeldung mit "erneut pruefen" waere hier eine falsche
  // Aufforderung. Die Erstfassung pruefte nur `isFetching` (das bei
  // "paused" false ist) und meldete offline faelschlich als "bereit" (Fund
  // 2, Nacharbeit 1, Fremdpruefer BLOCKER).
  const zustand: "leer" | "laeuft" | "erfolg" | "fehler" = !gesucht
    ? "leer"
    : !passt || fetchStatus !== "idle"
      ? "laeuft"
      : status === "success"
        ? "erfolg"
        : status === "error"
          ? "fehler"
          : "laeuft";

  const laeuft = zustand === "laeuft";
  // Die EIN-GRUPPE-Anzeige (unten) gilt nur, wenn es wirklich genau eine
  // ist — bei Mehrdeutigkeit zeigt eine eigene Auswahl (#113).
  const zeigeGruppe = zustand === "erfolg" && !!gruppe && !mehrdeutig;
  // NUR bei ERFOLG mit leerem Ergebnis gilt "sicher keine Gruppe" — ein
  // Fehlschlag ist keine Auskunft ueber die Gruppe und darf eine bereits
  // gewaehlte "eigene Gruppe" nicht zuruecksetzen (Fund 4, Nacharbeit 1:
  // die Erstfassung reagierte auf JEDES `!laeuft && !zeigeGruppe`,
  // Fehlschlag eingeschlossen, und schickte damit einen unsichtbaren Haken
  // ab, oder verwarf einen gesetzten).
  const keineGruppeErfolg = zustand === "erfolg" && !gruppe;

  useEffect(() => {
    if (keineGruppeErfolg && eigeneGruppe) onEigeneGruppeChange(false);
  }, [keineGruppeErfolg, eigeneGruppe, onEigeneGruppeChange]);

  // #113: solange der Name mehrdeutig ist UND weder eine bestehende Gruppe
  // noch "eigene Gruppe" gewaehlt wurde, bleibt die Wahl AUSSTEHEND — der
  // Aufrufer sperrt sein Anlegen zusaetzlich darauf (`gruppenBereitschaft`).
  const wahlAusstehend = mehrdeutig && !eigeneGruppe && !gewaehlterKandidat;

  // Die Antwort traegt IMMER den Namen, zu dem sie gehoert — der Aufrufer
  // vergleicht selbst (`gruppenBereitschaft`), statt einer vorverdauten
  // Buchung zu vertrauen (Fund 3, Nacharbeit 1).
  const antwortOk = zustand === "erfolg";
  const antwortGruppeId = !antwortOk
    ? null
    : mehrdeutig
      ? eigeneGruppe
        ? null
        : gewaehlterKandidat
      : gruppe && "group_id" in gruppe
        ? gruppe.group_id
        : null;
  useEffect(() => {
    onAntwort({
      name: entprellt,
      ok: antwortOk,
      groupId: antwortGruppeId,
      wahlAusstehend: antwortOk && wahlAusstehend,
    });
  }, [entprellt, antwortOk, antwortGruppeId, wahlAusstehend, onAntwort]);

  if (laeuft) return <p className="text-xs text-gray-600">{t("group_checking")}</p>;

  if (zustand === "fehler")
    return (
      <p className="text-xs text-amber-500 flex items-center gap-2 flex-wrap">
        <span>{t("group_check_failed")}</span>
        <button
          type="button"
          className="underline decoration-dotted hover:text-amber-400"
          onClick={() => refetch()}
        >
          {t("group_check_retry")}
        </button>
      </p>
    );

  // Ein geleertes Namensfeld ist KEIN Grund, die alte Antwort weiter zu
  // zeigen: `zustand` ist dann "leer" (nichts zu suchen), `gruppe` haengt
  // aber noch am vorigen Schluessel. Ohne diese Schranke behauptete die App
  // rund eine Drittelsekunde etwas ueber einen Namen, den es nicht mehr gibt.
  // `zeigeGruppe` deckt nur den EIN-Treffer-Fall; `mehrdeutig` (das die
  // Auswahl unten rendert) ist seit #113 der zweite gueltige Grund.
  if (!zeigeGruppe && !mehrdeutig) return null;
  if (!gruppe) return null; // reine Typ-Schranke fuer TS — mehrdeutig/zeigeGruppe schliessen das schon aus

  // #113: mehrdeutig — ALLE Kandidaten anbieten, dieselbe Form wie der
  // eindeutige Treffer, PLUS "eigene Gruppe". Ohne Vorauswahl (Owner-
  // Entscheid 29.09.2026, #113): weder ein Radiobutton noch "eigene Gruppe"
  // ist zu Beginn markiert.
  if (mehrdeutig) {
    return (
      <div className="space-y-1.5 bg-immich-surface border border-immich-border rounded-lg p-2">
        <p className="text-xs text-amber-400">{t("group_choice_needed")}</p>
        <div className="space-y-1.5">
          {kandidaten.map((k) => (
            <label
              key={k.group_id}
              className="flex items-start gap-2 text-xs text-gray-300 cursor-pointer"
            >
              <input
                type="radio"
                name="gruppenwahl-kandidat"
                className="mt-0.5"
                checked={!eigeneGruppe && gewaehlterKandidat === k.group_id}
                onChange={() => {
                  setGewaehlterKandidat(k.group_id);
                  if (eigeneGruppe) onEigeneGruppeChange(false);
                }}
              />
              <span className="space-y-1">
                <span className="flex flex-wrap gap-1.5">
                  {k.person_refs.map((ref) => (
                    <span
                      key={`${ref.account_id}::${ref.person_id}`}
                      className="badge"
                      style={{
                        backgroundColor: ref.account_color,
                        fontSize: "0.65rem",
                        padding: "0 4px",
                      }}
                    >
                      {ref.person_name}
                    </span>
                  ))}
                </span>
                {(k.owner_account_missing || k.too_few_people) && (
                  <span className="block text-amber-500">
                    {k.owner_account_missing && <span>{t("group_marker_owner_missing")} </span>}
                    {k.too_few_people && <span>{t("group_marker_too_few_people")}</span>}
                  </span>
                )}
              </span>
            </label>
          ))}
          <label className="flex items-center gap-2 text-xs text-gray-300 cursor-pointer pt-1">
            <input
              type="radio"
              name="gruppenwahl-kandidat"
              checked={eigeneGruppe}
              onChange={() => {
                setGewaehlterKandidat(null);
                onEigeneGruppeChange(true);
              }}
            />
            {t("group_own")}
          </label>
        </div>
        {eigeneGruppe && <p className="text-xs text-gray-500">{t("group_own_hint")}</p>}
      </div>
    );
  }

  return (
    <div className="space-y-1.5 bg-immich-surface border border-immich-border rounded-lg p-2">
      <p className="text-xs text-gray-400">{t("group_joins")}</p>
      <div className="flex flex-wrap gap-1.5">
        {gruppe.person_refs.map((ref) => (
          <span
            key={`${ref.account_id}::${ref.person_id}`}
            className="badge"
            style={{ backgroundColor: ref.account_color, fontSize: "0.65rem", padding: "0 4px" }}
          >
            {ref.person_name}
          </span>
        ))}
      </div>
      {(gruppe.owner_account_missing || gruppe.too_few_people) && (
        <p className="text-xs text-amber-500">
          {gruppe.owner_account_missing && <span>{t("group_marker_owner_missing")} </span>}
          {gruppe.too_few_people && <span>{t("group_marker_too_few_people")}</span>}
        </p>
      )}
      <label className="flex items-center gap-2 text-xs text-gray-300 pt-1">
        <input
          type="checkbox"
          checked={eigeneGruppe}
          onChange={(e) => onEigeneGruppeChange(e.target.checked)}
        />
        {t("group_own")}
      </label>
      {eigeneGruppe && <p className="text-xs text-gray-500">{t("group_own_hint")}</p>}
    </div>
  );
}
