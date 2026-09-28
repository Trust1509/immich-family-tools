import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
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
  /** Die Gruppe bei Erfolg, sonst immer `null`. */
  groupId: string | null;
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
  if (!antwort || antwort.name !== name || !antwort.ok) {
    return { bereit: false, gruppeId: null };
  }
  return { bereit: true, gruppeId: antwort.groupId };
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
    // hatte nie etwas zu tun. Entfernt, `npm test` bleibt 158/158 gruen.
    staleTime: 0,
  });

  const passt = entprellt === gesucht;

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
  const zeigeGruppe = zustand === "erfolg" && !!gruppe;
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

  // Die Antwort traegt IMMER den Namen, zu dem sie gehoert — der Aufrufer
  // vergleicht selbst (`gruppenBereitschaft`), statt einer vorverdauten
  // Buchung zu vertrauen (Fund 3, Nacharbeit 1).
  const antwortOk = zustand === "erfolg";
  const antwortGruppeId = antwortOk ? (gruppe?.group_id ?? null) : null;
  useEffect(() => {
    onAntwort({ name: entprellt, ok: antwortOk, groupId: antwortGruppeId });
  }, [entprellt, antwortOk, antwortGruppeId, onAntwort]);

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
  if (!zeigeGruppe || !gruppe) return null;

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
