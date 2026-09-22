import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useT } from "../i18n";

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
 */
export function GruppenWahl({
  albumName,
  eigeneGruppe,
  onEigeneGruppeChange,
  onGruppeChange,
}: {
  /** Der Name, um den es beim Gruppieren geht — leer schaltet die Abfrage ab. */
  albumName: string;
  eigeneGruppe: boolean;
  onEigeneGruppeChange: (wert: boolean) => void;
  /** Die angezeigte Gruppe — genau die wird beim Bestaetigen auch geschickt. */
  onGruppeChange: (groupId: string | null) => void;
}) {
  const { t } = useT();
  const [entprellt, setEntprellt] = useState("");
  const gesucht = albumName.trim();

  // Entprellt: waehrend des Tippens nicht bei jedem Zeichen fragen.
  useEffect(() => {
    const zeit = setTimeout(() => setEntprellt(gesucht), 300);
    return () => clearTimeout(zeit);
  }, [gesucht]);

  const { data: gruppe, isFetching } = useQuery({
    queryKey: ["album-group", entprellt],
    queryFn: () => api.sync.albumGroupPreview(entprellt),
    enabled: !!entprellt,
    staleTime: 10_000,
  });

  // Nur behaupten, was zur AKTUELLEN Eingabe gehoert. Solange die Abfrage
  // laeuft oder der entprellte Name der Eingabe hinterherhinkt, wird NICHTS
  // gezeigt — ein Hinweis, der sich eine Sekunde spaeter widerruft, ist
  // schlimmer als keiner (`docs/agents/lehren.md` §40).
  // DREI Zustaende, und sie sind nicht dasselbe:
  //
  //   passt       — die vorliegende Antwort gehoert zur aktuellen Eingabe
  //   laeuft      — es wird noch gesucht (nur bei nicht-leerer Eingabe)
  //   keineGruppe — es ist gesucht worden und es gibt sicher keine
  //
  // Die erste Fassung hatte `laeuft` und "keine Gruppe" in EINE Bedingung
  // gezogen. Das las sich sparsamer und war ein Defekt: Der Ruecksetzer unten
  // feuerte dann bei JEDEM Tastendruck, und der Haken "eigene Gruppe"
  // verschwand still — das Album landete in genau der Gruppe, gegen die sich
  // der Nutzer entschieden hatte (Blindpruefer 21.09.2026, gemessen).
  const passt = entprellt === gesucht;
  const laeuft = !!gesucht && (isFetching || !passt);

  // EIN Ausdruck regiert Anzeige UND Meldung. Die Fassung davor hatte zwei
  // (`zeigeGruppe` und `angezeigt`), die dasselbe sagen sollten — und
  // enthielt `passt` doppelt: einmal direkt, einmal ueber `laeuft`. Gemessen:
  // Die Mutation, die das direkte `passt` entfernt, war ein NO-OP und sah wie
  // eine Deckungsluecke aus (Gegenpruefer 21.09.2026). Zwei Ausdruecke fuer
  // eine Aussage laufen frueher oder spaeter auseinander; einer kann das nicht.
  const zeigeGruppe = !laeuft && !!gesucht && !!gruppe;
  const keineGruppe = !laeuft && !zeigeGruppe;

  // Nur zuruecksetzen, wenn SICHER keine Gruppe mehr da ist — nicht, solange
  // noch gesucht wird.
  useEffect(() => {
    if (keineGruppe && eigeneGruppe) onEigeneGruppeChange(false);
  }, [keineGruppe, eigeneGruppe, onEigeneGruppeChange]);

  // Was ANGEZEIGT wird, wird auch GESCHICKT. Ohne diese Bindung zeigte die
  // App eine Gruppe an und liess das Backend beim Bestaetigen erneut ueber
  // den Namen raten — kommt dazwischen ein zweites gleichnamiges Album, wird
  // der Name mehrdeutig und der Nutzer landet in einer DRITTEN Gruppe,
  // obwohl er einen Beitritt bestaetigt hat (Blindpruefer 21.09.2026).
  const angezeigt = zeigeGruppe ? (gruppe?.group_id ?? null) : null;
  useEffect(() => {
    onGruppeChange(angezeigt);
  }, [angezeigt, onGruppeChange]);

  if (laeuft) return <p className="text-xs text-gray-600">{t("group_checking")}</p>;
  // Ein geleertes Namensfeld ist KEIN Grund, die alte Antwort weiter zu
  // zeigen: `laeuft` ist dann falsch (nichts zu suchen), `gruppe` haengt aber
  // noch am vorigen Schluessel. Ohne diese Schranke behauptete die App rund
  // eine Drittelsekunde etwas ueber einen Namen, den es nicht mehr gibt.
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
