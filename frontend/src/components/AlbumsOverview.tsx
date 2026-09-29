import React from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import {
  Loader2,
  RefreshCw,
  Trash2,
  Disc,
  AlertTriangle,
  User,
  Clock,
  Timer,
  X,
  Pencil,
  Check,
} from "lucide-react";
import { api, ApiError, ManagedAlbum, SyncLogEntry } from "../api/client";
import { formatDate, LANG_LOCALES, useT, type ServerErrorLike } from "../i18n";
import { bucketByGroup, mergePersonRefs } from "../lib/albumGroups";

interface AlbumGroup {
  // Die IDENTITAET der Gruppe. Der Name ist Anzeigetext und seit #78
  // nicht mehr eindeutig — zwei Gruppen duerfen gleich heissen.
  group_id: string;
  album_name: string;
  albums: ManagedAlbum[];
  total_assets: number;
  last_synced_at: string | undefined;
  owner_name: string;
  person_refs: ManagedAlbum["person_refs"];
  // Markierungen aus GET /api/sync/albums — beim Lesen berechnet, nicht
  // gespeichert (Owner-Entscheid 28.09.2026, #99/#112). `ownerMissing`
  // betrifft IRGENDEIN Album der Gruppe: Eine Gruppe buendelt je ein Album
  // pro Konto. Bis Nacharbeit 2 zu #99/#112 sperrte schon ein einziges
  // verwaistes Album das Umbenennen der GANZEN Gruppe, server-seitig
  // durchgesetzt ueber `errors.group_member_owner_missing`. Diese Sperre ist
  // mit Owner-Entscheid 29.09.2026 (#123) ersatzlos entfernt: Umbenennen
  // bedient jetzt die gesunden Alben und ueberspringt die verwaisten — wie
  // der Abgleich, siehe `gesundeAlben` unten. `ownerMissing` bleibt die
  // Grundlage der sichtbaren MARKIERUNG (Text auf der Karte), nicht mehr
  // einer Sperre.
  ownerMissing: boolean;
  // `displayedOwnerMissing` ist ENGER: nur, ob der ANGEZEIGTE Besitzer (der
  // des ersten Albums, `owner_name` unten) selbst fehlt — nicht irgendein
  // Geschwister-Album. Nacharbeit 2 (Gegen-/Blindpruefer, gemessen): Eine
  // gemischte Gruppe zeigte vorher "Besitzerkonto gelöscht" in der
  // Besitzer-Zeile, obwohl der dort GENANNTE Besitzer noch lebte.
  displayedOwnerMissing: boolean;
  // Ob MINDESTENS EIN Album der Gruppe fuer sich allein zu wenige Personen
  // hat — ein ODER ueber `too_few_people` je Album (Owner-Entscheid
  // 29.09.2026, #123, Rueckschritt aus Nacharbeit 2 zu #99/#112 zurueckgebaut).
  //
  // Nacharbeit 2 hatte das stattdessen aus der ZUSAMMENGEFUEHRTEN Personenliste
  // der Gruppe berechnet (`personRefs.length < 2`) — mit der Begruendung, das
  // ODER ueber einzelne Alben zeige "Nur noch eine Person" faelschlich auch
  // dann, wenn die Gruppe insgesamt schon drei Personen fuehrt. Genau das ist
  // aber die vom Owner gewollte Markierung: Ein Album mit einer Person in
  // einer Gruppe mit weiteren Personen VERLOR seine Markierung unter der
  // zusammengefuehrten Berechnung (gemessen, #123: HEAD `false`, HEAD~1
  // `true`, bei Album A mit 1 Person neben Album B mit 2 Personen in
  // derselben Gruppe) — Issue #123 verlangt das Gegenteil: jedes solche
  // Album bleibt markiert.
  tooFewPeople: boolean;
  // Welcher TEXT gezeigt wird, ist eine eigene Frage von `tooFewPeople`
  // (Nacharbeit 1 zu #123, alle drei Stimmen): Bisher waehlte die Karte den
  // Satz ueber `group.person_refs.length` — die ZUSAMMENGEFUEHRTE Liste,
  // dieselbe Quelle, die Nacharbeit 2 fuer die Markierung SELBST schon
  // verworfen hatte. Ein Album mit 0 Personen neben einem mit 2 zeigte so
  // "Nur noch eine Person" (falsch, es sind ja gar keine mehr) oder, je nach
  // Ueberlappung, gar nichts. Jetzt direkt aus den ALBEN DER GRUPPE
  // abgeleitet: `hasZeroPeopleAlbum`, wenn eines von ihnen leer ist,
  // `hasOnePersonAlbum`, wenn eines genau eine Person fuehrt — beides kann
  // gleichzeitig zutreffen, dann erscheinen beide Texte.
  hasZeroPeopleAlbum: boolean;
  hasOnePersonAlbum: boolean;
}

function groupAlbums(albums: ManagedAlbum[]): AlbumGroup[] {
  return bucketByGroup(albums).map((group) => {
    const personRefs = mergePersonRefs(group);
    const dates = group.map((a) => a.last_synced_at).filter(Boolean) as string[];
    const lastSync = dates.length ? dates.sort().reverse()[0] : undefined;
    // Nacharbeit 1 (#123, Gegenpruefer G1, Blindpruefer W1, WICHTIG): `first`
    // bestimmt Anzeigename, Besitzerzeile UND die Vorbelegung des
    // Umbenennen-Feldes (`renameValue` unten). Bis hierher war das immer
    // `group[0]` — steht das verwaiste Album einer gemischten Gruppe vorn
    // (die Ladereihenfolge des Servers ist nicht garantiert), zeigte die
    // Karte nach einem erfolgreichen Umbenennen weiter den ALTEN Namen, und
    // ein erneut geoeffnetes Eingabefeld war mit dem alten statt dem neuen
    // Namen vorbelegt — ein Enter ohne jede Aenderung benannte dann
    // stillschweigend zurueck (Folgefund, Blindpruefer W2). Bevorzugt wird
    // jetzt das ERSTE GESUNDE Album; nur wenn die ganze Gruppe verwaist ist,
    // bleibt es beim ersten ueberhaupt — unveraendertes Verhalten fuer
    // diesen Fall, und `displayedOwnerMissing` unten bleibt darueber korrekt:
    // Ist das gewaehlte `first` gesund, ist es automatisch `false`.
    const first = group.find((a) => !a.owner_account_missing) ?? group[0];
    const ownerRef = first.person_refs.find((r) => r.account_id === first.owner_account_id);
    // Use total_assets from the most recently synced entry (most accurate)
    const mostRecent = [...group].sort((a, b) =>
      (b.last_synced_at ?? "").localeCompare(a.last_synced_at ?? "")
    )[0];

    return {
      group_id: first.group_id,
      album_name: first.album_name,
      albums: group,
      total_assets: mostRecent.total_assets,
      last_synced_at: lastSync,
      owner_name: ownerRef?.account_name ?? first.owner_account_id,
      person_refs: personRefs,
      ownerMissing: group.some((a) => a.owner_account_missing),
      displayedOwnerMissing: !!first.owner_account_missing,
      tooFewPeople: group.some((a) => a.too_few_people),
      hasZeroPeopleAlbum: group.some((a) => a.person_refs.length === 0),
      hasOnePersonAlbum: group.some((a) => a.person_refs.length === 1),
    };
  });
}

function SyncLogDisplay({ logs, syncing }: { logs: SyncLogEntry[] | null; syncing: boolean }) {
  const { t, logMessage } = useT();
  if (syncing)
    return (
      <div className="flex items-center gap-2 text-xs text-gray-500 py-1">
        <Loader2 size={12} className="animate-spin" />
        <span>{t("syncing")}</span>
      </div>
    );
  if (!logs || logs.length === 0) return null;
  return (
    <div className="space-y-1">
      {logs.map((entry) => (
        <p
          key={entry.id}
          className={`text-xs border rounded px-2 py-1 ${
            entry.status === "success"
              ? "text-emerald-400 bg-emerald-900/20 border-emerald-800"
              : "text-red-400 bg-red-900/20 border-red-800"
          }`}
        >
          {logMessage(entry)}
        </p>
      ))}
    </div>
  );
}

function AlbumGroupCard({
  group,
  externalLogs,
  externalSyncing,
  externalError,
  externalNummer,
  vergebeNummer,
}: {
  group: AlbumGroup;
  externalLogs?: SyncLogEntry[] | null; // results pushed from "Alle synchronisieren"
  externalSyncing?: boolean;
  // #102: uebersetzte Fehlerzeile, wenn der SAMMEL-Abgleich fuer diese
  // Gruppe (teilweise) fehlgeschlagen ist — getrennt vom Protokoll.
  externalError?: string;
  // Welle 4, S1, Nacharbeit 2 (#124/#102, LETZTE Runde): ersetzt
  // `externalRunSeq` + `lokalZuletzt` + die Objekt-Identitaetspruefung. Der
  // Blindpruefer hatte 6fae875 widerlegt: Ein vollstaendig gescheiterter
  // Sammellauf blieb ohne Fehlerzeile, wenn eine LOKALE Aktion VOR seinem
  // Start begann und DANACH endete — `lokalZuletzt` wurde erst am ENDE der
  // lokalen Aktion `true`, ueberschrieb damit die (juengere!) Sammel-
  // Fehlerzeile, obwohl der Sammellauf spaeter STARTETE.
  //
  // Jede Aktion (jede lokale Aktion einer Karte, der Sammellauf als Ganzes)
  // zieht jetzt beim EIGENEN START eine Nummer aus DEMSELBEN, in
  // `AlbumsOverview` gefuehrten Zaehler (`vergebeNummer` unten) — Startzeit
  // statt Endzeit entscheidet, wer "juenger" ist. Die Karte zeigt
  // Fehlerzeile/eigene Hinweise der Aktion mit der HOECHSTEN Nummer, die fuer
  // SIE etwas getan hat (`lokalGewinnt` unten); das Protokoll folgt separat
  // dem juengsten ERFOLGREICHEN Ergebnis, gleich ob lokal oder Sammel
  // (`letztesProtokoll`, Befund W1/Q3 — ein spaeterer Totalausfall darf ein
  // frueheres Erfolgsprotokoll nicht verdraengen).
  //
  // `0` heisst "kein gezaehlter Sammellauf fuer diese Gruppe" — ein
  // Sammellauf, der fuer die Gruppe keine einzige Anfrage gestellt hat (die
  // Gruppe ist inzwischen ganz verwaist), zaehlt fuer sie NICHT und bekommt
  // hier nie eine Nummer gestempelt (siehe `AlbumsOverview`, `betroffene`) —
  // er verdraengt deshalb auch kein juengeres Protokoll (Q3b).
  externalNummer: number;
  vergebeNummer: () => number;
}) {
  const { t, lang, errorText } = useT();
  const qc = useQueryClient();
  const [localLogs, setLocalLogs] = React.useState<SyncLogEntry[] | null>(null);
  const [localSyncing, setLocalSyncing] = React.useState(false);
  const [deleting, setDeleting] = React.useState(false);
  // KLEIN (Sonde Q5b): ZAHLEN/NAME statt eines fertig gerenderten Strings —
  // wie `localRefreshErrorInfo` unten wird erst beim RENDERN, mit der dann
  // aktuellen Sprache, uebersetzt (`deleteErrorText` unten). Vorher stand ein
  // einmal (in der zum Zeitpunkt des Fehlschlags aktuellen Sprache)
  // gerenderter String im Zustand; ein spaeterer Sprachwechsel liess die
  // Zeile in der alten Sprache stehen.
  const [deleteErrorInfo, setDeleteErrorInfo] = React.useState<
    | { art: "gruppe"; fehlgeschlagen: number; gesamt: number }
    | { art: "einzel"; albumName: string }
    | null
  >(null);
  const [renaming, setRenaming] = React.useState(false);
  const [renameValue, setRenameValue] = React.useState(group.album_name);
  // Feldwert BEIM OEFFNEN (#124, Fund B11) — die Grundlage fuer den
  // Nullvorgang bei Enter ohne Aenderung ist DIESER Wert, nicht "der Name
  // irgendeines Albums der Gruppe" (Albumnamen innerhalb einer Gruppe duerfen
  // seit #97 voneinander abweichen). Gesetzt, wenn das Feld geoeffnet wird
  // (Knopf-Klick unten); `handleRename` vergleicht `nextName` nur gegen
  // diesen eingefrorenen Wert.
  //
  // Nacharbeit 1 (#124, KLEIN, Sonde P5): GETRIMMT eingefroren — `nextName`
  // ist immer `renameValue.trim()`, ein untrimmter Oeffnungswert ("Urlaub ")
  // war deshalb nie gleich, und ein unveraendertes Enter benannte trotzdem
  // um (auf den getrimmten Namen).
  const [renameOpenedValue, setRenameOpenedValue] = React.useState(group.album_name.trim());
  // Nacharbeit 1 (#124, WICHTIG 3): Ob seit dem OEFFNEN schon ein echter
  // Umbenennen-VERSUCH lief — siehe `handleRename` unten. Nullvorgang gilt
  // nur, solange das hier `false` ist.
  const [renameAttempted, setRenameAttempted] = React.useState(false);
  // KLEIN (Sonde Q5b): der ROHE Fehler statt eines fertig gerenderten
  // Strings — `renameErrorText` unten ruft `errorText()` erst beim RENDERN
  // auf, mit der dann aktuellen Sprache (wie `errorText` es an der
  // Aufrufstelle unten in `handleRename` schon vorher tat, nur jetzt bei
  // JEDEM Rendern statt einmalig beim Fehlschlag).
  const [renameErrorInfo, setRenameErrorInfo] = React.useState<ServerErrorLike | null>(null);
  // W3/K3 (Sonde Q6, Nacharbeit 2, LETZTE Runde, Mutation M28): Nach einem
  // bereits gelaufenen ECHTEN Versuch ist ein Enter auf einem leeren/nur aus
  // Leerzeichen bestehenden Feld kein stiller Nullvorgang mehr — der Nutzer
  // hat auf DIESEM Feld schon einen Fehler gesehen. `handleRename` schickt in
  // diesem Fall weiterhin NICHTS an den Server, schliesst das Feld aber nicht
  // mehr lautlos: dieser Hinweis bleibt stehen, bis das Feld neu geoeffnet
  // oder ein echter (nicht-leerer) Versuch gestartet wird.
  const [renameEmptyHint, setRenameEmptyHint] = React.useState(false);
  // Album-Namen, die das UMBENENNEN in diesem Durchlauf uebersprungen hat,
  // weil der Server sie einzeln mit `err_owner_account_not_found` ablehnte
  // (Nacharbeit 1, #123, Gegenpruefer G3 — siehe `handleRename` unten).
  const [renameSkipped, setRenameSkipped] = React.useState<string[]>([]);
  // Gesamtzahl der beim DURCHLAUF angefahrenen (gesunden) Alben, zum
  // Zeitpunkt des Durchlaufs selbst (#124, Fund A1, WICHTIG). `gesundeAlben`
  // unten wird bei JEDEM Rendern aus der aktuell geladenen Liste berechnet —
  // laedt die Liste zwischen dem Durchlauf und der Anzeige des Hinweises neu
  // (ein Konto wurde in einem anderen Tab geloescht), ist das uebersprungene
  // Album dort inzwischen verwaist und faellt aus `gesundeAlben` heraus. Der
  // Hinweis wuerde dann eine falsche Gesamtzahl nennen ("1 von 2" statt
  // "1 von 3", im Extremfall "2 von 0"). Der Wert wird deshalb im `finally`
  // von `handleRename` MIT `renameSkipped` zusammen eingefroren.
  const [renameSkippedTotal, setRenameSkippedTotal] = React.useState(0);
  // Wie `renameSkipped`/`renameSkippedTotal`, aber fuer eine ANDERE Ursache
  // (#124, Fund A7): der Server lehnt ein Album mit
  // `err_managed_album_not_found` ab, wenn es INZWISCHEN ENTFERNT wurde (ein
  // anderer Tab hat es oder die ganze Gruppe geloescht) — das ist etwas
  // anderes als ein verwaistes Besitzerkonto, und bekommt deshalb einen
  // eigenen Grund im Hinweis statt denselben Text mit der falschen Erklaerung.
  const [renameSkippedRemoved, setRenameSkippedRemoved] = React.useState<string[]>([]);
  const [renameSkippedRemovedTotal, setRenameSkippedRemovedTotal] = React.useState(0);
  // #102: Eine EIGENE Fehlerzeile fuer einen (teilweise) gescheiterten
  // EINZEL-Abgleich (`handleRefresh` unten) — getrennt vom Protokoll
  // (`SyncLogDisplay`), das nur den Verlauf des SERVERS zeigt.
  //
  // Nacharbeit 1 (#124, KLEIN): Schluessel + Zahlen statt eines fertigen
  // Strings — der String wurde bis hierher EINMAL mit der zum Zeitpunkt des
  // Abgleichs aktuellen Sprache gerendert (`t(...)`) und dann UNVERAENDERT
  // gespeichert; ein spaeterer Sprachwechsel liess die Zeile in der alten
  // Sprache stehen (Sonde P9). `localRefreshErrorText` unten uebersetzt bei
  // JEDEM Rendern neu, wie `SyncLogDisplay`/`logMessage` es fuer das
  // Protokoll bereits tun.
  const [localRefreshErrorInfo, setLocalRefreshErrorInfo] = React.useState<{
    fehlgeschlagen: number;
    gesamt: number;
  } | null>(null);
  const localRefreshErrorText = localRefreshErrorInfo
    ? t(
        "album_refresh_failed_hint",
        localRefreshErrorInfo.fehlgeschlagen,
        localRefreshErrorInfo.gesamt
      )
    : null;
  const renameErrorText = renameErrorInfo ? errorText(renameErrorInfo) : null;
  const deleteErrorText = deleteErrorInfo
    ? deleteErrorInfo.art === "gruppe"
      ? t("album_remove_partial_failed", deleteErrorInfo.fehlgeschlagen, deleteErrorInfo.gesamt)
      : t("album_remove_single_failed", deleteErrorInfo.albumName)
    : null;

  // Welle 4, S1, Nacharbeit 2 (LETZTE Runde): die Startnummer der Aktion, die
  // GERADE die lokalen Hinweiszustaende oben besetzt (`0` = "auf dieser Karte
  // lief noch nie eine lokale Aktion") — vergeben von `vergebeNummer` (Prop
  // aus `AlbumsOverview`, EIN gemeinsamer Zaehler fuer alle Karten UND den
  // Sammellauf). `lokalGewinnt`: die lokale Aktion ist juenger als der
  // zuletzt fuer diese Gruppe GEZAEHLTE Sammellauf — Ties sind ausgeschlossen,
  // der Zaehler vergibt jeden Wert genau einmal.
  const [localAktionsNummer, setLocalAktionsNummer] = React.useState(0);
  const lokalGewinnt = localAktionsNummer > externalNummer;
  const syncing = externalSyncing || localSyncing;
  // Die Fehlerzeile/eigenen Hinweise gehoeren der Aktion mit der hoeheren
  // Startnummer. Beide Seiten raeumen ihre EIGENEN Hinweise synchron bei
  // IHREM eigenen Start ab (`resetFremdeHinweise` unten fuer lokal,
  // `setBulkSyncErrors(new Map())` in `AlbumsOverview` fuer den Sammellauf) —
  // ein zusaetzliches "blende aus, solange die Gewinner-Aktion noch laeuft"
  // ist deshalb NICHT noetig: Startet die jeweils juengere Seite, ist ihr
  // eigener Hinweis in genau demselben Moment schon wieder leer.
  const displayRefreshError = lokalGewinnt ? localRefreshErrorText : externalError;

  // Das juengste ERFOLGREICHE Protokoll der Karte, gleich ob lokal oder aus
  // "Alle synchronisieren" (Befund W1/Q3): Ein Sammellauf, der NACH einem
  // erfolgreichen lokalen Abgleich komplett scheitert, darf dessen Protokoll
  // nicht durch ein AELTERES Sammelergebnis ersetzen — und umgekehrt gilt
  // dasselbe fuer einen lokalen Fehlschlag nach einem juengeren, guten
  // Sammellauf. Ausgewaehlt wird ausschliesslich nach STARTNUMMER, nie nach
  // Abschlusszeit (das war exakt der 6fae875-Bug, siehe `externalNummer`
  // oben), und nur ein NICHT-LEERES Ergebnis aktualisiert den Speicher — ein
  // Totalausfall traegt keine Eintraege und loescht das vorige Protokoll
  // deshalb nicht (unveraendert seit #102/WICHTIG 1, jetzt nur nicht mehr
  // sammellauf-exklusiv).
  const [letztesProtokoll, setLetztesProtokoll] = React.useState<{
    nummer: number;
    logs: SyncLogEntry[];
  } | null>(null);
  React.useEffect(() => {
    if (!externalNummer || !externalLogs || externalLogs.length === 0) return;
    setLetztesProtokoll((bisher) =>
      externalNummer > (bisher?.nummer ?? 0)
        ? { nummer: externalNummer, logs: externalLogs }
        : bisher
    );
  }, [externalNummer, externalLogs]);
  const displayLogs = letztesProtokoll?.logs ?? null;

  // Nacharbeit 1 (Hauptagent, technisch entschieden — KEIN Owner-Entscheid,
  // siehe `renameLocked` unten): Der Abgleich sperrt NICHT die ganze Gruppe.
  // Er laeuft wie der Auto-Sync nur fuer Alben mit lebendem Besitzer und
  // UEBERSPRINGT verwaiste — sonst erzeugte jeder Klick auf "Jetzt
  // synchronisieren" denselben `log_owner_account_missing`-Fehlereintrag,
  // den der Auto-Sync (`main._run_auto_sync`) genau deshalb nicht mehr
  // schreibt (`docs/agents/lehren.md` §45). Die Markierung weiter oben
  // bleibt der sichtbare Hinweis, warum ein Teil der Gruppe fehlt.
  const gesundeAlben = group.albums.filter((album) => !album.owner_account_missing);

  // Nacharbeit 2 (#123, Blindpruefer K3) + #124 Fund A3: Ein stehengebliebener
  // Hinweis aus einer FRUEHEREN lokalen Aktion auf dieser Karte darf nicht
  // ueberleben, bis eine neue lokale Aktion ihn zufaellig ueberschreibt oder
  // nie. Jede der vier lokalen Aktionen (Abgleichen, ein ECHTER
  // Umbenennen-Versuch, Entfernen, Einzel-Entfernen) setzt deshalb beim
  // START ALLE fremden Hinweiszustaende zurueck. Ein neuer Sammellauf
  // braucht dafuer KEINEN eigenen Reset mehr (anders als bis 6fae875, wo
  // `resetFremdeHinweise` zusaetzlich an einen Effekt auf `externalRunSeq`
  // gehaengt war): Ueberholt der Sammellauf die lokale Aktion an Nummer,
  // wird `lokalGewinnt` oben `false`, und die hier gesetzten lokalen Hinweise
  // werden schlicht nicht mehr ANGEZEIGT — unabhaengig davon, ob sie noch im
  // Zustand stehen (getestet: M02/M27* dieser Runde).
  const resetFremdeHinweise = () => {
    setDeleteErrorInfo(null);
    setRenameErrorInfo(null);
    setRenameEmptyHint(false);
    setRenameSkipped([]);
    setRenameSkippedRemoved([]);
    setLocalRefreshErrorInfo(null);
  };

  const handleRefresh = async () => {
    const dieseNummer = vergebeNummer();
    resetFremdeHinweise();
    setLocalAktionsNummer(dieseNummer);
    setLocalSyncing(true);
    setLocalLogs(null);
    const allLogs: SyncLogEntry[] = [];
    let fehlgeschlagen = 0;
    for (const album of gesundeAlben) {
      try {
        allLogs.push(...(await api.sync.refreshAlbum(album.id)));
      } catch (_) {
        fehlgeschlagen++;
      }
    }
    setLocalLogs(allLogs);
    // #102: Ein (teilweise) gescheiterter Abgleich darf nicht schweigen —
    // die erfolgreichen Eintraege (falls welche) bleiben im Protokoll
    // sichtbar, UND diese eigene Zeile macht den Fehlschlag sichtbar.
    if (fehlgeschlagen > 0) {
      setLocalRefreshErrorInfo({ fehlgeschlagen, gesamt: gesundeAlben.length });
    }
    // Welle 4, S1, Nacharbeit 2: das juengste ERFOLGREICHE Protokoll der
    // Karte aktualisieren (nur ein NICHT-LEERES Ergebnis zaehlt, siehe
    // `letztesProtokoll` oben) — ein Totalausfall (leeres `allLogs`) loescht
    // das vorige Protokoll deshalb nicht.
    if (allLogs.length) {
      setLetztesProtokoll((bisher) =>
        dieseNummer > (bisher?.nummer ?? 0) ? { nummer: dieseNummer, logs: allLogs } : bisher
      );
    }
    setLocalSyncing(false);
    qc.invalidateQueries({ queryKey: ["managed-albums"] });
    qc.invalidateQueries({ queryKey: ["sync-log"] });
  };

  const handleDelete = async () => {
    if (!confirm(t("album_remove_confirm", group.album_name, group.albums.length))) return;
    const dieseNummer = vergebeNummer();
    setDeleting(true);
    resetFremdeHinweise();
    setLocalAktionsNummer(dieseNummer);
    // PARALLEL statt nacheinander (Owner-Entscheid 29.09.2026, #123, #121
    // Punkt 1): Seit #101 wartet `DELETE /api/sync/albums/{id}` am
    // Albumschloss dieses EINEN Albums (`sync_service._album_schloss`) — ein
    // Schloss je Album-ID, keins ueber die Gruppe. Ein sequenzieller Lauf
    // lief deshalb einem laufenden Abgleich unnoetig hinterher: Haelt ein
    // Refresh das Schloss von Album 2, wartete Album 1 in der Schleife
    // trotzdem VOR Album 2 — Alben 3 und 4 kamen erst danach an die Reihe,
    // obwohl ihr eigenes Schloss die ganze Zeit frei war (Zeitmessung dazu
    // in Issue #121, hier nicht wiederholt — nicht selbst nachgemessen,
    // docs/agents/lehren.md §46). `Promise.all` startet alle DELETEs sofort; nur das
    // Album mit dem gerade gehaltenen Schloss wartet noch.
    //
    // Nacharbeit 1 (#123, alle drei Stimmen): Ein Fehlschlag verschwand bis
    // hierher spurlos — jeder DELETE trug sein eigenes `.catch(() => {})`,
    // und `Promise.all` selbst kann dann gar nicht mehr ablehnen. Der Nutzer
    // sah "fertig", auch wenn ein Album weiterhin verwaltet blieb.
    // `Promise.allSettled` behaelt beide Faelle auseinander, ohne die
    // Parallelitaet oder die Invalidierungen (auch `["album-group"]`, #110)
    // aufzugeben — ein Fehlschlag wird jetzt gezaehlt und sichtbar gemacht.
    //
    // Nacharbeit 2 (#123, Gegenpruefer K1/K2, Blindpruefer K4): Der Schluessel
    // `err_managed_album_not_found` (ein 404 dieser konkreten Fehlerklasse)
    // heisst "das Album ist schon weg" — ein anderer Tab hat es (oder die
    // ganze Gruppe) bereits entfernt, WAEHREND dieser Klick unterwegs war.
    // Das ist der gewuenschte Endzustand, kein Fehlschlag: Vorher zaehlte
    // dieser Fall trotzdem mit ("1 von 2 ... nicht entfernt"), obwohl am Ende
    // genau das da ist, was der Klick wollte. Jeder ANDERE Fehler (Netzwerk,
    // 500, Schloss-Zeitueberschreitung ...) bleibt ein echter Fehlschlag.
    // Nacharbeit 1 (#124, KLEIN Punkt b): Geprueft wird NUR der Schluessel —
    // ein 404 OHNE diesen Schluessel (Proxy, falsche Route) zaehlt als
    // Fehlschlag, siehe `#124 Fund A2` in `AlbumsOverview.karte124.test.tsx`.
    const ergebnisse = await Promise.allSettled(
      group.albums.map((album) => api.sync.deleteAlbum(album.id))
    );
    const fehlgeschlagen = ergebnisse.filter(
      (r) =>
        r.status === "rejected" &&
        !(r.reason instanceof ApiError && r.reason.key === "err_managed_album_not_found")
    ).length;
    setDeleting(false);
    if (fehlgeschlagen > 0) {
      setDeleteErrorInfo({ art: "gruppe", fehlgeschlagen, gesamt: group.albums.length });
    }
    qc.invalidateQueries({ queryKey: ["managed-albums"] });
    qc.invalidateQueries({ queryKey: ["matches"] });
    // Entfernen aendert die Gruppe (weniger/keine Alben mehr) — eine
    // laufende Gruppenvorschau darf danach keine veraltete Antwort mehr
    // zeigen (#110, Nacharbeit 1, BLOCKER Fund 1).
    qc.invalidateQueries({ queryKey: ["album-group"] });
  };

  // Einzelentfernung eines VERWAISTEN Albums (Owner-Entscheid 29.09.2026,
  // #123): `handleDelete` oben nimmt immer die GANZE Gruppe — fuer ein
  // gemischtes Album gibt es damit bis hierher keinen Weg, nur das verwaiste
  // Mitglied loszuwerden, ohne das gesunde mitzureissen. Eigene Funktion,
  // eigene Rueckfrage (`album_remove_single_confirm`, nennt das EINE Album),
  // eigener Schreibpfad — derselbe Endpunkt wie oben, nur mit einer einzigen
  // ID statt der ganzen Gruppe.
  const handleDeleteSingle = async (album: ManagedAlbum) => {
    if (!confirm(t("album_remove_single_confirm", album.album_name))) return;
    const dieseNummer = vergebeNummer();
    setDeleting(true);
    resetFremdeHinweise();
    setLocalAktionsNummer(dieseNummer);
    // Nacharbeit 1 (#123, alle drei Stimmen): derselbe stille Fehlschlag wie
    // bei `handleDelete` oben, hier fuer die Einzelentfernung.
    //
    // Nacharbeit 2 (#123, Gegenpruefer K1/K2, Blindpruefer K4): derselbe
    // Schluesselvergleich wie oben — das Album ist schon weg (anderer Tab),
    // das ist der gewuenschte Endzustand, keine Fehlermeldung noetig. Auch
    // hier nur der Schluessel, nicht zusaetzlich der Status (KLEIN Punkt b).
    try {
      await api.sync.deleteAlbum(album.id);
    } catch (error) {
      if (error instanceof ApiError && error.key === "err_managed_album_not_found") {
        // Schon weg - kein Fehlschlag, keine Meldung.
      } else {
        setDeleteErrorInfo({ art: "einzel", albumName: album.album_name });
      }
    }
    setDeleting(false);
    qc.invalidateQueries({ queryKey: ["managed-albums"] });
    qc.invalidateQueries({ queryKey: ["matches"] });
    qc.invalidateQueries({ queryKey: ["album-group"] });
  };

  const handleRename = async () => {
    // Nacharbeit 1 (#124, KLEIN — "Ein Nullvorgang loescht eine noch
    // gueltige Abgleich-Fehlerzeile"): die fremden Hinweise (`deleteErrorInfo`,
    // `localRefreshErrorInfo`, ...) werden NICHT MEHR hier am Anfang
    // zurueckgesetzt, sondern erst weiter unten, NACHDEM feststeht, dass es
    // sich um einen ECHTEN Versuch handelt (nicht um einen der Nullvorgang-
    // Zweige). Vorher raeumte schon das blosse Oeffnen-und-unveraendert-
    // Bestaetigen einen noch gueltigen Abgleichs-Hinweis einer ANDEREN Aktion
    // weg.
    // Nacharbeit 1 (#124, KLEIN Punkt „h"): Waehrend ein Entfernen fuer diese
    // Karte laeuft, darf ein offen gebliebenes Umbenennen-Feld nicht mehr
    // per Enter feuern — bis hierher sperrte nur der KNOPF zum OEFFNEN des
    // Feldes (`disabled={... || deleting || ...}` unten), ein bereits
    // offenes Feld erreichte `handleRename` trotzdem (Sonde P7). Das Feld
    // selbst ist unten zusaetzlich `disabled={localSyncing || deleting}`;
    // dieser Wächter greift zusaetzlich, unabhaengig davon, ob die
    // Browser-Umgebung ein Tastaturereignis an ein deaktiviertes Feld
    // weiterreicht.
    if (deleting) return;
    const nextName = renameValue.trim();
    if (!nextName) {
      // W3/K3 (Sonde Q6, Nacharbeit 2, LETZTE Runde, Mutation M28): Ein
      // leeres/nur-Leerzeichen-Feld ist kein gueltiger Name — bis hierher
      // schloss das Feld dabei IMMER still (wie ein Nullvorgang), auch NACH
      // einem bereits gelaufenen echten Versuch. Genau dann ist Stille
      // falsch: Der Nutzer hat schon eine Fehlermeldung gesehen, ein Enter
      // auf dem jetzt geleerten Feld darf sie nicht kommentarlos wegwischen.
      // Kein Serveraufruf in BEIDEN Zweigen — nur der zweite laesst das Feld
      // offen und zeigt einen eigenen Hinweis statt sich zu schliessen. Der
      // Text eines VORIGEN Fehlschlags (`renameErrorInfo`) macht diesem
      // eigenen Hinweis Platz, statt zwei rote Zeilen uebereinander zu
      // zeigen — das leere Feld ist jetzt das eigentliche Problem.
      if (renameAttempted) {
        setRenameErrorInfo(null);
        setRenameEmptyHint(true);
        return;
      }
      setRenaming(false);
      setRenameValue(group.album_name);
      setRenameErrorInfo(null);
      setRenameEmptyHint(false);
      setRenameSkipped([]);
      setRenameSkippedRemoved([]);
      return;
    }
    // #124 Fund B11 (Nacharbeit zu #79/#123, zwei Pruefstimmen gemessen):
    // Nullvorgang bedeutet "der Feldwert ist derselbe wie BEIM OEFFNEN des
    // Feldes" (`renameOpenedValue`) — NICHT "alle gesunden Alben der Gruppe
    // tragen diesen Namen bereits". Die alte Fassung verglich gegen
    // `gesundeAlben.every(...)`, und das hatte zwei Ausloeser: (a) Tragen die
    // gesunden Alben einer Gruppe verschiedene Namen (erlaubt seit #97, siehe
    // `groupAlbums`), war ein unveraendertes Enter KEIN Nullvorgang mehr,
    // sondern glich alle auf den vorbelegten Namen an. (b) War das
    // angezeigte (erste gesunde) Album bei einem FRUEHEREN Umbenennen
    // gescheitert, trug es noch seinen alten Namen — das `.every()` war dann
    // `false`, obwohl das Feld unveraendert war, und Enter benannte die
    // bereits erfolgreich umbenannten Geschwister-Alben lautlos ZURUECK.
    // `renameOpenedValue` ist der einzige Vergleichswert, den der Nutzer
    // tatsaechlich SIEHT (der vorbelegte Feldinhalt).
    //
    // Diese TECHNISCHE Vorgabe des Orchestrators (KEIN Owner-Entscheid, siehe
    // die Korrektur in `AlbumsOverview.umbenennen.test.tsx`) hatte bis
    // hierher noch eine LUECKE (Nacharbeit 1, #124, WICHTIG 3): Nach einem
    // ECHTEN Versuch, der scheitert (Feld bleibt offen, z. B. Sonde P4: a
    // gelingt, b wirft einen harten Fehler), tippt der Nutzer den
    // Oeffnungswert zurueck und bestaetigt — das waere bisher WIEDER ein
    // Nullvorgang gewesen, das Feld schloss sich still, und die Gruppe blieb
    // gemischt liegen, ohne dass ein weiterer Versuch je ankam. Nullvorgang
    // gilt deshalb jetzt NUR, solange seit dem Oeffnen noch KEIN Versuch
    // lief (`renameAttempted`) — nach jedem Versuch ist jeder weitere Enter
    // ein ECHTER Versuch, unabhaengig davon, ob der Text zufaellig wieder dem
    // Oeffnungswert entspricht.
    //
    // Verbleibender, bewusst nicht behobener Fall (wird ein Folge-Issue):
    // Bricht der Nutzer stattdessen ab (Escape/X) und oeffnet das Feld NEU,
    // friert der Oeffnen-Knopf `renameOpenedValue` erneut auf den dann
    // AKTUELLEN (moeglicherweise immer noch gemischten) Gruppennamen ein —
    // ein unveraendertes Enter ist dann wieder ein Nullvorgang, ohne dass
    // die Mischung behoben wird.
    if (!renameAttempted && nextName === renameOpenedValue) {
      setRenaming(false);
      setRenameValue(group.album_name);
      setRenameErrorInfo(null);
      setRenameEmptyHint(false);
      setRenameSkipped([]);
      setRenameSkippedRemoved([]);
      return;
    }
    const dieseNummer = vergebeNummer();
    setRenameAttempted(true);
    // Ein ECHTER Versuch ist die juengere Aktion auf dieser Karte (siehe
    // `localAktionsNummer`/`lokalGewinnt` oben) — anders als die beiden
    // Nullvorgang-Zweige oben, die bewusst NICHTS an fremden Hinweisen
    // aendern.
    resetFremdeHinweise();
    setLocalAktionsNummer(dieseNummer);
    setLocalSyncing(true);
    setLocalLogs(null);
    const logs: SyncLogEntry[] = [];
    // Nacharbeit 1 (#123, Gegenpruefer G3, WICHTIG) + #124 Fund A7: `gesundeAlben`
    // stammt aus der Liste, die beim LADEN des Tabs galt — steckt darin ein
    // Konto, das seither (in einem anderen Tab) geloescht wurde, faehrt die
    // Schleife dessen Album trotzdem an. Zwei Ablehnungen sind moeglich, mit
    // VERSCHIEDENER Ursache:
    // - `err_owner_account_not_found`: das Besitzerkonto dieses Albums wurde
    //   geloescht (`routers/albums.py::rename_managed_album`).
    // - `err_managed_album_not_found` (#124, Fund A7): das Album SELBST wurde
    //   inzwischen entfernt — ein anderer Tab hat es oder die ganze Gruppe
    //   geloescht, WAEHREND dieses Umbenennen lief.
    // Bis hierher (Fund A7) riss NUR die erste Ursache nicht die Schleife ab;
    // die zweite lief weiter in den `catch`-Block unten und brach ALLE
    // weiteren Alben ab, sichtbar nur als "Verwaltetes Album nicht gefunden".
    // Beide gelten jetzt als UEBERSPRUNGEN, aber in getrennten Listen — der
    // Hinweis nennt fuer jede ihren EIGENEN Grund (`album_rename_skipped_hint`
    // vs. `album_rename_skipped_removed_hint`), statt fuer beide denselben,
    // teils falschen Satz zu zeigen. Jeder ANDERE Fehler verhaelt sich
    // unveraendert: Er bricht ab, sein Text erscheint in `renameErrorInfo`,
    // und die bis dahin gesammelten Eintraege bleiben sichtbar (#79).
    const uebersprungen: string[] = [];
    const uebersprungenEntfernt: string[] = [];
    try {
      for (const album of gesundeAlben) {
        try {
          logs.push(...(await api.sync.renameAlbum(album.id, nextName)));
        } catch (error) {
          if (error instanceof ApiError && error.key === "err_owner_account_not_found") {
            uebersprungen.push(album.album_name);
            continue;
          }
          if (error instanceof ApiError && error.key === "err_managed_album_not_found") {
            uebersprungenEntfernt.push(album.album_name);
            continue;
          }
          throw error;
        }
      }
      // Nacharbeit 2 (#123, Blindpruefer K2): `logs.length &&` ist absichtlich
      // hier — nicht nur eine Absicherung gegen ein leeres `.every()` (das
      // waere auf einem leeren Feld ohnehin `true`, ein leeres Feld haette
      // das Eingabefeld sonst STILL geschlossen). Sind ALLE gesunden Alben
      // uebersprungen (jedes einzelne mit `err_owner_account_not_found` oder
      // `err_managed_album_not_found`), bleibt `logs` leer — ohne diese
      // Bedingung wuerde das Feld trotzdem verschwinden, obwohl KEIN
      // einziges Album tatsaechlich umbenannt wurde. Das Feld bleibt offen,
      // und die Hinweise (im `finally` unten) machen sichtbar, warum nichts
      // passiert ist.
      //
      // #124 Fund A1-Folge: Dieser Test-/Code-Pfad gilt fuer eine
      // UNVERAENDERTE Liste. Der realistischere Ablauf, wenn WIRKLICH alle
      // Alben uebersprungen wurden (jedes einzelne Konto inzwischen
      // geloescht), ist ein ANDERER: `handleRename` laedt im `finally` unten
      // `["managed-albums"]` neu — kommt die Gruppe dabei komplett verwaist
      // zurueck, greift der `renameLocked`-Effekt weiter unten und schliesst
      // das Feld VON SICH AUS, unabhaengig von diesem `if`. Das "Feld bleibt
      // offen"-Verhalten hier ist also der Sonderfall einer Liste, die sich
      // zwischen Durchlauf und Neuzeichnen nicht aendert (z. B. weil der
      // Server-Refetch noch nicht zurueck ist) — nicht der Regelfall.
      if (logs.length && logs.every((entry) => entry.status === "success")) setRenaming(false);
    } catch (error) {
      setRenameErrorInfo(error as ServerErrorLike);
    } finally {
      // Die schon gesammelten Eintraege gehoeren auch dann auf die Karte, wenn
      // eine SPAETERE Anfrage geworfen hat (Fund des Fremdpruefers an #79):
      // `setLocalLogs` und die Invalidierungen standen hinter der Schleife, ein
      // Wurf sprang ueber beides — der Nutzer sah nur den Fehlertext und nicht,
      // was vorher schon umbenannt worden war.
      if (logs.length) {
        setLocalLogs(logs);
        // Welle 4, S1, Nacharbeit 2: das juengste ERFOLGREICHE Protokoll der
        // Karte aktualisieren (siehe `letztesProtokoll` oben) — auch ein
        // TEILWEISE erfolgreicher Versuch (manche Eintraege `status:
        // "error"`) zaehlt hier als "nicht leer", unveraendert seit #79.
        setLetztesProtokoll((bisher) =>
          dieseNummer > (bisher?.nummer ?? 0) ? { nummer: dieseNummer, logs } : bisher
        );
      }
      // #124 Fund A1: Die Gesamtzahl wird HIER, zum Zeitpunkt des
      // Durchlaufs, eingefroren (`gesundeAlben.length` in diesem Moment) —
      // nicht erst beim Rendern aus der (moeglicherweise laengst neu
      // geladenen) aktuellen Liste berechnet.
      if (uebersprungen.length) {
        setRenameSkipped(uebersprungen);
        setRenameSkippedTotal(gesundeAlben.length);
      }
      if (uebersprungenEntfernt.length) {
        setRenameSkippedRemoved(uebersprungenEntfernt);
        setRenameSkippedRemovedTotal(gesundeAlben.length);
      }
      setLocalSyncing(false);
      qc.invalidateQueries({ queryKey: ["managed-albums"] });
      qc.invalidateQueries({ queryKey: ["sync-log"] });
      qc.invalidateQueries({ queryKey: ["matches"] });
      // Umbenennen aendert den Namen, ueber den die Vorschau spaeter sucht —
      // eine Vorschau fuer den ALTEN oder den NEUEN Namen darf danach keine
      // veraltete Antwort mehr zeigen (#110, Nacharbeit 1, BLOCKER Fund 1).
      qc.invalidateQueries({ queryKey: ["album-group"] });
    }
  };

  const isDeleted = displayLogs?.some((e) => e.error_message === "ALBUM_DELETED");
  // Owner-Entscheid 29.09.2026 (#123): UMBENENNEN sperrt nicht mehr schon bei
  // einem einzelnen verwaisten Album der Gruppe — es sperrt nur noch, wenn
  // KEIN gesundes Album mehr uebrig ist, genau wie der ABGLEICH-Knopf
  // (`gesundeAlben.length === 0`, siehe `disabled` beim "Jetzt
  // synchronisieren"-Knopf unten). Eine gemischte Gruppe bleibt bedienbar:
  // `handleRename` benennt die gesunden Alben um und ueberspringt die
  // verwaisten, mit demselben sichtbaren Hinweis wie beim Abgleichen
  // (`album_sync_skips_orphaned_hint`). Die fruehere gruppenweite
  // Server-Sperre (`errors.group_member_owner_missing`) ist dafuer
  // ersatzlos entfernt — der Server lehnt nur noch das verwaiste Album
  // SELBST ab (`errors.owner_account_not_found`), und die Schleife oben
  // faehrt das verwaiste Album gar nicht erst an. Entfernen bleibt in jedem
  // Fall moeglich, je Gruppe (`handleDelete`) oder je verwaistem Album
  // einzeln (`handleDeleteSingle`). "Nur noch eine Person"/"keine Person
  // mehr" sperrt fuer sich allein nichts, wird aber ebenfalls sichtbar
  // (Text, nicht nur Farbe).
  const renameLocked = gesundeAlben.length === 0;

  // Schliesst ein offenes Umbenennen-Feld, sobald die Sperre eintritt (Konto
  // in einem anderen Tab geloescht, Liste neu geladen) — NUR das Feld.
  //
  // Nacharbeit 2 (Gegenpruefer, gemessen): Die erste Fassung loeschte hier
  // zusaetzlich `renameError` — nach einem erfolgreichen Umbenennen laedt
  // `handleRename` im `finally` die Liste neu; kommt sie verwaist zurueck,
  // sprang `renameLocked` auf true, und dieser Effekt loeschte die gerade
  // erst gesetzte Fehlermeldung des Servers. Auf der Karte stand danach nur
  // "ok" und der neue Name — kein Hinweis, dass ein Album des alten Namens
  // (oder der Ablehnungsgrund) verlorenging. `renameError` gehoert allein
  // dem Erfolg/Fehlschlag des naechsten Versuchs, nicht dieser Sperre.
  React.useEffect(() => {
    if (renameLocked) {
      setRenaming(false);
      setRenameValue(group.album_name);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [renameLocked]);

  return (
    <div className={`card space-y-4 ${isDeleted ? "border-red-800" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Disc size={18} className={isDeleted ? "text-red-400" : "text-blue-400"} />
          <div>
            {renaming ? (
              <div className="flex items-center gap-1.5">
                <input
                  className="input py-1 text-sm"
                  value={renameValue}
                  onChange={(event) => setRenameValue(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") handleRename();
                    if (event.key === "Escape") {
                      // Nacharbeit 2 (#123, Blindpruefer K3): dasselbe
                      // Zuruecksetzen wie beim X-Knopf unten — sonst blieb
                      // ein Hinweis aus einem VORIGEN Versuch stehen, obwohl
                      // das Feld gerade neu geoeffnet wurde.
                      setRenaming(false);
                      setRenameValue(group.album_name);
                      setRenameErrorInfo(null);
                      setRenameEmptyHint(false);
                      setRenameSkipped([]);
                      setRenameSkippedRemoved([]);
                    }
                  }}
                  aria-label={t("album_rename_action")}
                  autoFocus
                  // Nacharbeit 1 (#124, KLEIN Punkt „h", Sonde P7): waehrend
                  // ein Entfernen fuer diese Karte laeuft, darf das schon
                  // offene Feld nicht mehr bedienbar sein — das gerade
                  // entfernte Album sonst „anfahren" (siehe `handleRename`).
                  disabled={localSyncing || deleting}
                />
                <button
                  className="p-1 text-emerald-400 hover:text-emerald-300"
                  onClick={handleRename}
                  disabled={localSyncing || deleting || !renameValue.trim()}
                  aria-label={t("save")}
                >
                  <Check size={15} />
                </button>
                <button
                  className="p-1 text-gray-500 hover:text-gray-300"
                  onClick={() => {
                    setRenaming(false);
                    setRenameValue(group.album_name);
                    setRenameErrorInfo(null);
                    setRenameEmptyHint(false);
                    setRenameSkipped([]);
                    setRenameSkippedRemoved([]);
                  }}
                  aria-label={t("cancel")}
                >
                  <X size={15} />
                </button>
              </div>
            ) : (
              <h3 className="font-semibold">{group.album_name}</h3>
            )}
            <p className="text-xs text-gray-500">
              {t("owner")}:{" "}
              {group.displayedOwnerMissing ? t("album_owner_missing_badge") : group.owner_name}
            </p>
          </div>
        </div>
        <span className="text-sm font-medium text-gray-300 shrink-0">
          {group.total_assets.toLocaleString(LANG_LOCALES[lang])} {t("photos")}
        </span>
      </div>

      <div className="space-y-1.5">
        <p className="text-xs text-gray-500 font-medium">{t("linked_people")}</p>
        {group.person_refs.map((ref, i) => (
          <div key={i} className="flex items-center gap-2">
            <User size={12} className="text-gray-600 shrink-0" />
            <span className="text-sm">{ref.person_name}</span>
            <span className="badge text-xs" style={{ backgroundColor: ref.account_color }}>
              {ref.account_name}
            </span>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-1.5 text-xs text-gray-500">
        <Clock size={12} />
        <span>{t("last_sync", formatDate(group.last_synced_at, LANG_LOCALES[lang]))}</span>
      </div>

      {(group.ownerMissing || group.tooFewPeople) && (
        <div className="flex items-center gap-2 text-xs text-amber-400 bg-amber-900/20 border border-amber-800 rounded px-3 py-2">
          <AlertTriangle size={13} />
          <span>
            {group.ownerMissing && t("album_owner_missing_badge")}
            {group.ownerMissing && group.tooFewPeople && " · "}
            {/* Nacharbeit 1 zu #123 (alle drei Stimmen): Der Text wurde bis
                hierher aus der ZUSAMMENGEFUEHRTEN Personenliste der Gruppe
                gewaehlt (`group.person_refs.length === 0 ? no_people :
                too_few_people`, Stand 03db7ea) — genau die Quelle, die
                Nacharbeit 2 zu #99/#112 fuer die Markierung SELBST schon
                verworfen hatte (`tooFewPeople` oben, `group.some`).
                Nacharbeit 2 zu #123 (Blindpruefer K7, dieser Kommentar
                stimmte vorher nicht): Ein Album mit 0 Personen neben einem
                mit 2 zeigte so faelschlich "Nur noch eine Person" — die
                zusammengefuehrte Liste zaehlt 2, nicht 0, und der Vergleich
                oben traf nur genau 0. Ein Album mit 0 Personen neben einem
                mit 1 weiteren zeigte aus demselben Grund NUR "Nur noch eine
                Person" und nie den Null-Text, obwohl eines der beiden Alben
                wirklich leer war (zusammengefuehrt: 1, nicht 0) — nicht "gar
                nichts", wie hier fälschlich stand. Jetzt direkt aus den
                ALBEN DER GRUPPE abgeleitet: 0 Personen -> "keine Person",
                genau 1 -> "eine Person", beides gleichzeitig moeglich ->
                beide Texte. */}
            {group.hasZeroPeopleAlbum && t("album_no_people_badge")}
            {group.hasZeroPeopleAlbum && group.hasOnePersonAlbum && " · "}
            {group.hasOnePersonAlbum && t("album_too_few_people_badge")}
            {/* Sichtbarer Hinweis, dass der Abgleich verwaiste Alben
                UEBERSPRINGT statt sie zu sperren (Nacharbeit 1) — nur wenn
                noch mindestens ein gesundes Album da ist; sind alle
                verwaist, sagt schon der Markierungstext oben alles. */}
            {group.ownerMissing && gesundeAlben.length > 0 && (
              <>
                {" · "}
                {t("album_sync_skips_orphaned_hint")}
              </>
            )}
          </span>
        </div>
      )}

      {/* Einzelentfernung eines verwaisten Albums (Owner-Entscheid
          29.09.2026, #123) — nur bei einer GEMISCHTEN oder mehrfach
          verwaisten Gruppe (mehr als ein Album insgesamt): Bei genau einem
          Album IST der Gruppenknopf "Entfernen" unten schon die
          Einzelentfernung, eine zweite Zeile dafuer waere doppelt. */}
      {group.ownerMissing && group.albums.length > 1 && (
        <div className="space-y-1">
          {group.albums
            .filter((album) => album.owner_account_missing)
            .map((album) => (
              <div
                key={album.id}
                className="flex items-center justify-between gap-2 text-xs text-amber-300 bg-amber-900/10 border border-amber-800/60 rounded px-2 py-1"
              >
                <span className="truncate">{album.album_name}</span>
                <button
                  className="p-1 text-red-400 hover:text-red-300 shrink-0"
                  onClick={() => handleDeleteSingle(album)}
                  disabled={deleting}
                  aria-label={t("album_remove_single_action")}
                  title={t("album_remove_single_action")}
                >
                  <X size={13} />
                </button>
              </div>
            ))}
        </div>
      )}

      <SyncLogDisplay logs={displayLogs} syncing={syncing} />
      {/* #102: eine EIGENE Zeile fuer einen (teilweise) gescheiterten
          Abgleich, getrennt vom Protokoll oben. Welle 4 S1 Nacharbeit 2:
          `displayRefreshError` traegt die Vorrang-Entscheidung (lokal vs.
          Sammellauf, per Startnummer) schon in sich — die uebrigen vier
          Hinweise sind reine LOKALE Konzepte (kein Sammellauf erzeugt sie)
          und werden deshalb explizit an `lokalGewinnt` gebunden: Ueberholt
          ein juengerer Sammellauf die lokale Aktion, verschwinden sie aus
          der Anzeige, ohne dass ein neuer lokaler Vorgang sie erst raeumen
          muesste (M02/M27* dieser Runde). */}
      {displayRefreshError && <p className="text-xs text-red-400">{displayRefreshError}</p>}
      {lokalGewinnt && renameErrorText && <p className="text-xs text-red-400">{renameErrorText}</p>}
      {lokalGewinnt && renameEmptyHint && (
        <p className="text-xs text-red-400">{t("album_rename_empty_hint")}</p>
      )}
      {lokalGewinnt && renameSkipped.length > 0 && (
        <p className="text-xs text-amber-400">
          {t("album_rename_skipped_hint", renameSkipped.length, renameSkippedTotal)}
        </p>
      )}
      {lokalGewinnt && renameSkippedRemoved.length > 0 && (
        <p className="text-xs text-amber-400">
          {t(
            "album_rename_skipped_removed_hint",
            renameSkippedRemoved.length,
            renameSkippedRemovedTotal
          )}
        </p>
      )}
      {lokalGewinnt && deleteErrorText && <p className="text-xs text-red-400">{deleteErrorText}</p>}

      {isDeleted && (
        <div className="flex items-center gap-2 text-xs text-amber-400 bg-amber-900/20 border border-amber-800 rounded px-3 py-2">
          <AlertTriangle size={13} />
          {t("album_deleted_warn")}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          className="btn-ghost text-xs flex items-center gap-1.5"
          onClick={() => {
            setRenameValue(group.album_name);
            // #124 Fund B11: der Vergleichswert fuer den Nullvorgang wird
            // beim OEFFNEN eingefroren, siehe `handleRename`. Getrimmt
            // (Nacharbeit 1, KLEIN, Sonde P5) — `nextName` ist immer
            // `renameValue.trim()`.
            setRenameOpenedValue(group.album_name.trim());
            // Nacharbeit 1 (#124, WICHTIG 3): jede neue Oeffnen-Session
            // startet ohne einen bereits gelaufenen Versuch.
            setRenameAttempted(false);
            setRenameErrorInfo(null);
            setRenameEmptyHint(false);
            setRenameSkipped([]);
            setRenameSkippedRemoved([]);
            setRenaming(true);
          }}
          disabled={syncing || deleting || renaming || renameLocked}
          title={renameLocked ? t("album_locked_owner_missing_hint") : undefined}
        >
          <Pencil size={13} />
          {t("album_rename_action")}
        </button>
        <button
          className="btn-primary text-xs flex items-center gap-1.5"
          onClick={handleRefresh}
          // #121 (Nachlese #101, Punkt „Klein"): Ein haengendes Entfernen
          // (`deleting`) liess „Jetzt synchronisieren" weiter bedienbar —
          // ein waehrenddessen ausgeloester Abgleich faehrt dann ein Album
          // an, dessen Entfernen der Server gerade noch bearbeitet.
          disabled={syncing || deleting || gesundeAlben.length === 0}
          title={
            // Nacharbeit 2 (Blindpruefer, gemessen): eine GANZ verwaiste
            // Gruppe deaktivierte den Knopf zuvor ohne jeden Hinweis im
            // Titel — der Hinweistext oben setzt "mindestens ein gesundes
            // Album" voraus (siehe die Bedingung dort) und erschien hier
            // nie.
            group.ownerMissing && gesundeAlben.length > 0
              ? t("album_sync_skips_orphaned_hint")
              : gesundeAlben.length === 0
                ? t("album_sync_disabled_all_orphaned_hint")
                : undefined
          }
        >
          {localSyncing ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
          {t("sync_now")}
        </button>
        <button
          className="btn-ghost text-xs flex items-center gap-1.5 text-red-400 hover:text-red-300"
          onClick={handleDelete}
          disabled={deleting}
          title={t("remove_link")}
        >
          {deleting ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
          {t("remove_link")}
        </button>
      </div>
    </div>
  );
}

function AutoSyncControl() {
  const { t } = useT();

  const { data: cfg } = useQuery({
    queryKey: ["autosync-config"],
    queryFn: api.autoSync.get,
    staleTime: 30_000,
  });

  const qc = useQueryClient();
  const mutation = useMutation({
    mutationFn: ({ enabled, time }: { enabled: boolean; time: string }) =>
      api.autoSync.set(enabled, time),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["autosync-config"] }),
  });

  const enabled = cfg?.enabled ?? false;
  const time = cfg?.time ?? "01:00";

  // Compute next sync label (client-side, server local time ≈ user local time)
  const nextSyncLabel = React.useMemo(() => {
    if (!enabled || !cfg) return null;
    const [h, m] = time.split(":").map(Number);
    const now = new Date();
    const candidate = new Date(now);
    candidate.setHours(h, m, 0, 0);
    if (candidate <= now) candidate.setDate(candidate.getDate() + 1);
    const isToday = candidate.getDate() === now.getDate();
    const day = isToday ? t("auto_sync_today") : t("auto_sync_tomorrow");
    return t("auto_sync_next", time, day);
  }, [enabled, time, cfg, t]);

  if (!cfg) return null;

  return (
    <div className="flex items-center gap-3 bg-immich-surface border border-immich-border rounded-lg px-3 py-2">
      <Timer size={14} className={enabled ? "text-immich-primary" : "text-gray-500"} />
      <span className="text-sm text-gray-300 font-medium">{t("auto_sync_label")}</span>

      {/* Toggle */}
      <button
        onClick={() => mutation.mutate({ enabled: !enabled, time })}
        className={`relative inline-flex h-5 w-9 shrink-0 rounded-full transition-colors focus:outline-none ${
          enabled ? "bg-immich-primary" : "bg-immich-border"
        }`}
        disabled={mutation.isPending}
      >
        <span
          className={`inline-block h-4 w-4 mt-0.5 rounded-full bg-white shadow transition-transform ${
            enabled ? "translate-x-4" : "translate-x-0.5"
          }`}
        />
      </button>

      {/* Time picker — only active when enabled */}
      <input
        type="time"
        value={time}
        disabled={!enabled}
        onChange={(e) => mutation.mutate({ enabled, time: e.target.value })}
        className="bg-immich-bg border border-immich-border rounded px-2 py-0.5 text-sm text-gray-200 disabled:opacity-40 focus:outline-none focus:border-immich-primary"
      />

      {/* Next sync info */}
      {nextSyncLabel && (
        <span className="text-xs text-gray-500 hidden sm:block">{nextSyncLabel}</span>
      )}
    </div>
  );
}

export default function AlbumsOverview() {
  const { t } = useT();
  const { data: albums = [], isLoading } = useQuery({
    queryKey: ["managed-albums"],
    queryFn: api.sync.albums,
    staleTime: 30_000,
  });
  const qc = useQueryClient();
  const groups = groupAlbums(albums);

  // Welle 4, S1, Nacharbeit 2 (#124/#102, LETZTE Runde): EIN fortlaufender
  // Zaehler fuer ALLE Aktionen dieser Seite — jede lokale Aktion einer Karte
  // (in `AlbumGroupCard`, ueber die Prop `vergebeNummer` unten) UND der
  // Sammellauf hier ziehen ihre Startnummer aus DEMSELBEN Zaehler. Ein Ref
  // genuegt: Der Zaehler selbst muss kein Rendern ausloesen, nur EINDEUTIGE,
  // STEIGENDE Werte liefern — das Rendern loesen die States aus, die eine
  // vergebene Nummer dann TRAGEN (`bulkSyncNummer` unten,
  // `localAktionsNummer` in `AlbumGroupCard`). Ersetzt `bulkSyncRunSeq` +
  // `lokalZuletzt` + `bulkSyncLastGood` — Einzelheiten und der Fehler, den
  // das alte Modell hatte, stehen bei `externalNummer` in `AlbumGroupCard`.
  const naechsteNummer = React.useRef(0);
  const vergebeNummer = () => ++naechsteNummer.current;

  // bulkSyncState: Ergebnis je Gruppe des LAUFENDEN/letzten GEZAEHLTEN
  // Sammellaufs. Schluessel fehlt = fuer diese Gruppe noch nie ein gezaehlter
  // Lauf; Wert `null` = dieser Lauf haelt die Gruppe gerade fuer syncend
  // (Spinner); Wert ein Feld = dieser Lauf ist fuer die Gruppe fertig (leer,
  // wenn ALLE Anfragen geworfen haben). "Gezaehlt" heisst: der Lauf hat fuer
  // die Gruppe mindestens ein gesundes Album angefahren — eine Gruppe ohne
  // gesundes Album wird von einem Lauf gar nicht erst hier eingetragen
  // (Q3b/WICHTIG 1 unten).
  //
  // #103 Punkt 5: Zwei Kommentare an verschiedenen Stellen dieser Datei
  // beschrieben diese drei Zustaende WIDERSPRUECHLICH — einer sagte "null =
  // not started, undefined = currently running", der Code (und der zweite
  // Kommentar unten, bei der tatsaechlichen Verwendung) tut das Gegenteil:
  // `undefined` ist "kein Eintrag da, also nie gelaufen", `null` ist "dieser
  // Lauf haelt die Gruppe gerade". Dieser Kommentar ist jetzt der einzige
  // Eigentuemer der Beschreibung (`docs/agents/lehren.md` §14); die
  // Verwendungsstelle weiter unten verweist nur noch.
  const [bulkSyncState, setBulkSyncState] = React.useState<Map<string, SyncLogEntry[] | null>>(
    new Map()
  );
  // Die Startnummer des GEZAEHLTEN Sammellaufs je Gruppe (s.o.) — die
  // "Last-Good"-Bewahrung ueber einen spaeteren Totalausfall hinweg lebt
  // seit dieser Runde nicht mehr hier (vormals `bulkSyncLastGood`), sondern
  // im gemeinsamen `letztesProtokoll`-Speicher jeder Karte (siehe dort):
  // Der Speicher muss auch lokale Erfolge aufnehmen koennen, nicht nur
  // Sammel-Erfolge (Befund W1/Q3).
  const [bulkSyncNummer, setBulkSyncNummer] = React.useState<Map<string, number>>(new Map());
  // #102: Fehlerzahlen je Gruppe fuer den LETZTEN gezaehlten Sammellauf,
  // getrennt vom Protokoll — ein Teil- oder Volltreffer OHNE Fehlschlag
  // raeumt den Eintrag der Gruppe wieder ab (siehe die Schleife unten).
  //
  // Nacharbeit 1 (#124, KLEIN): ZAHLEN statt eines fertigen Strings — wie
  // `localRefreshErrorInfo` in `AlbumGroupCard` wird erst beim RENDERN
  // (unten, in der Gruppenliste) mit der dann aktuellen Sprache uebersetzt;
  // vorher haette ein gespeicherter String einen Sprachwechsel nicht
  // mitgemacht (Sonde P9).
  const [bulkSyncErrors, setBulkSyncErrors] = React.useState<
    Map<string, { fehlgeschlagen: number; gesamt: number }>
  >(new Map());
  const [refreshingAll, setRefreshingAll] = React.useState(false);

  const handleRefreshAll = async () => {
    const laufNummer = vergebeNummer();
    setRefreshingAll(true);
    // Q3b/WICHTIG 1 (Nacharbeit 2, LETZTE Runde): nur Gruppen mit MINDESTENS
    // einem gesunden Album werden von DIESEM Lauf ueberhaupt beruehrt — eine
    // ganz verwaiste Gruppe bekommt weder einen Spinner noch eine gestempelte
    // Nummer, damit ein 0-Anfragen-Lauf kein juengeres lokales (oder ein
    // frueheres Sammel-)Protokoll verdraengen kann.
    const betroffene = groups.filter((g) => g.albums.some((a) => !a.owner_account_missing));
    setBulkSyncState((prev) => {
      const next = new Map(prev);
      for (const g of betroffene) next.set(g.group_id, null);
      return next;
    });
    setBulkSyncNummer((prev) => {
      const next = new Map(prev);
      for (const g of betroffene) next.set(g.group_id, laufNummer);
      return next;
    });
    // Nacharbeit 1 (#124, WICHTIG 2): ein neuer Sammellauf raeumt die
    // Fehlerzeilen des VORIGEN Laufs sofort beim START ab, statt sie stehen
    // zu lassen, bis diese Gruppe in der Schleife unten an der Reihe war —
    // bis hierher stand eine alte Fehlerzeile waehrend eines haengenden
    // neuen Laufs weiter da (Sonde P3b).
    setBulkSyncErrors(new Map());

    for (const group of groups) {
      // Nacharbeit 1: wie der einzelne "Jetzt synchronisieren"-Knopf und wie
      // der Auto-Sync — verwaiste Alben werden UEBERSPRUNGEN, nicht mit
      // demselben Fehlereintrag pro Klick bedacht (siehe `gesundeAlben` in
      // `AlbumGroupCard`).
      //
      // Nacharbeit 1 (#124, KLEIN Punkt „h", bewusst NICHT behoben): Ein
      // Album, dessen Karte GERADE (`deleting`) ein Entfernen laufen hat,
      // wird hier NICHT uebersprungen — "Alle synchronisieren" faehrt es
      // trotzdem an (Sonde P7: `alleSyncWaehrendEntfernen` bleibt > 0). Der
      // `deleting`-Zustand lebt ausschliesslich lokal in `AlbumGroupCard`;
      // ihn hierher sichtbar zu machen braucht einen NEUEN, ueber beide
      // Komponenten GETEILTEN Zustand (z. B. ein Set laufender Loesch-IDs in
      // `AlbumsOverview`, nach unten UND von `AlbumGroupCard` nach oben
      // gereicht) — das ist mehr als dieser Nacharbeit-Slice an Umfang
      // vorsieht (`Umfang nicht erweitern`). Gemeldet, nicht gebaut.
      const gesunde = group.albums.filter((album) => !album.owner_account_missing);
      // Q3b/WICHTIG 1: ein Lauf ohne gesundes Album zaehlt fuer diese Gruppe
      // nicht (s.o.) — er stellt weder `bulkSyncState` noch `bulkSyncErrors`
      // fuer sie um.
      if (gesunde.length === 0) continue;
      const groupLogs: SyncLogEntry[] = [];
      let fehlgeschlagen = 0;
      for (const album of gesunde) {
        try {
          groupLogs.push(...(await api.sync.refreshAlbum(album.id)));
        } catch (_) {
          fehlgeschlagen++;
        }
      }
      // Update this group's results immediately, keep others in their current state
      setBulkSyncState((prev) => new Map(prev).set(group.group_id, groupLogs));
      // Nacharbeit 1 (#124, WICHTIG 4: vormals M29 — das fehlende
      // Abraeumen einer Gruppen-Fehlerzeile bei einem spaeteren guten
      // Sammellauf blieb ungeprueft): Ein eigenes `else { next.delete(...) }`
      // HIER waere seit dem `setBulkSyncErrors(new Map())` am START dieses
      // Laufs (oben, WICHTIG 2) toter Code — die Map ist zu Beginn JEDES
      // Laufs leer, ein `delete` traefe also nie einen Schluessel, den
      // dieser Lauf selbst gesetzt hat. Das Abraeumen einer Gruppe, die
      // diesmal wieder erfolgreich lief, passiert deshalb bereits durch das
      // Leeren am Anfang, nicht durch einen (nie erreichten) `else`-Zweig
      // hier.
      setBulkSyncErrors((prev) => {
        const next = new Map(prev);
        if (fehlgeschlagen > 0) {
          next.set(group.group_id, { fehlgeschlagen, gesamt: gesunde.length });
        }
        return next;
      });
    }

    setRefreshingAll(false);
    qc.invalidateQueries({ queryKey: ["managed-albums"] });
    qc.invalidateQueries({ queryKey: ["sync-log"] });
  };

  return (
    <div className="p-6 max-w-2xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold">{t("albums_title")}</h1>
          <p className="text-sm text-gray-500 mt-0.5">{t("albums_subtitle", groups.length)}</p>
        </div>
        {groups.length > 0 && (
          <button
            className="btn-primary text-sm flex items-center gap-1.5"
            onClick={handleRefreshAll}
            disabled={refreshingAll}
          >
            {refreshingAll ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <RefreshCw size={14} />
            )}
            {t("sync_all")}
          </button>
        )}
      </div>

      {/* Auto-sync control */}
      <div className="mb-6">
        <AutoSyncControl />
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 size={28} className="animate-spin text-gray-500" />
        </div>
      ) : groups.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <Disc size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">{t("albums_empty")}</p>
          <p className="text-xs mt-1">{t("albums_empty_hint")}</p>
        </div>
      ) : (
        <div className="space-y-4">
          {groups.map((group) => {
            const bulkEntry = bulkSyncState.get(group.group_id);
            // Bedeutung von `bulkEntry`: siehe die Erklaerung bei
            // `bulkSyncState` oben (einziger Eigentuemer dieser Beschreibung,
            // #103 Punkt 5) — kurz: `null` = dieser Lauf haelt die Gruppe
            // gerade fuer syncend.
            const externalSyncing = bulkEntry === null;
            // Welle 4, S1, Nacharbeit 2 (LETZTE Runde): rohe Daten des
            // aktuellen (gezaehlten) Laufs — KEIN Rueckfall auf ein
            // "letztes gutes Ergebnis" mehr hier (vormals `bulkSyncLastGood`):
            // dieses Gedaechtnis lebt jetzt in `letztesProtokoll` der Karte
            // selbst, weil es auch lokale Erfolge aufnehmen muss (Befund
            // W1/Q3). Ein Volltausfall bleibt trotzdem sichtbar erhalten —
            // nur eben in der Karte, nicht mehr hier.
            const externalLogs = bulkEntry ?? undefined;
            const externalNummer = bulkSyncNummer.get(group.group_id) ?? 0;
            const externalErrorInfo = bulkSyncErrors.get(group.group_id);
            // Nacharbeit 1 (#124, KLEIN): erst HIER, beim Rendern, mit der
            // aktuellen Sprache uebersetzen (siehe `bulkSyncErrors` oben) —
            // damit wechselt die Zeile mit, wenn `lang` sich aendert.
            const externalError = externalErrorInfo
              ? t(
                  "album_refresh_failed_hint",
                  externalErrorInfo.fehlgeschlagen,
                  externalErrorInfo.gesamt
                )
              : undefined;
            return (
              <AlbumGroupCard
                key={group.group_id}
                group={group}
                externalLogs={externalLogs}
                externalSyncing={externalSyncing}
                externalError={externalError}
                externalNummer={externalNummer}
                vergebeNummer={vergebeNummer}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
