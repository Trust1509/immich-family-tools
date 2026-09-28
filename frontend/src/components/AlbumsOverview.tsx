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
import { api, ManagedAlbum, SyncLogEntry } from "../api/client";
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
  // gespeichert (Owner-Entscheid 28.09.2026, #99/#112). Betrifft IRGENDEIN
  // Album der Gruppe: Eine Gruppe buendelt je ein Album pro Konto, und schon
  // ein einziges verwaistes Album darin sperrt das Umbenennen der Gruppe —
  // WAS genau gesperrt wird, ist eine technische Entscheidung des
  // Hauptagenten (Nacharbeit 1), siehe `renameLocked` unten.
  ownerMissing: boolean;
  tooFewPeople: boolean;
}

function groupAlbums(albums: ManagedAlbum[]): AlbumGroup[] {
  return bucketByGroup(albums).map((group) => {
    const personRefs = mergePersonRefs(group);
    const dates = group.map((a) => a.last_synced_at).filter(Boolean) as string[];
    const lastSync = dates.length ? dates.sort().reverse()[0] : undefined;
    const first = group[0];
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
      tooFewPeople: group.some((a) => a.too_few_people),
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
}: {
  group: AlbumGroup;
  externalLogs?: SyncLogEntry[] | null; // results pushed from "Alle synchronisieren"
  externalSyncing?: boolean;
}) {
  const { t, lang, errorText } = useT();
  const qc = useQueryClient();
  const [localLogs, setLocalLogs] = React.useState<SyncLogEntry[] | null>(null);
  const [localSyncing, setLocalSyncing] = React.useState(false);
  const [deleting, setDeleting] = React.useState(false);
  const [renaming, setRenaming] = React.useState(false);
  const [renameValue, setRenameValue] = React.useState(group.album_name);
  const [renameError, setRenameError] = React.useState<string | null>(null);

  // Ein lokales Ergebnis ist NEUER als ein liegengebliebenes Sammelergebnis
  // (Fund des Fremdpruefers an #79). Vorher hatte `externalLogs` Vorrang,
  // solange der Eintrag aus „Alle synchronisieren“ im Zustand stand — ein
  // danach ausgeloestes Umbenennen zeigte sein Ergebnis dann nirgends, auch
  // ein fehlerhaftes nicht. Beim naechsten Sammellauf dreht sich der Vorrang
  // zurueck: `externalLogs` wechselt die Identitaet, der Effekt laeuft.
  const [lokalZuletzt, setLokalZuletzt] = React.useState(false);
  React.useEffect(() => {
    setLokalZuletzt(false);
  }, [externalLogs]);
  const displayLogs = !lokalZuletzt && externalLogs !== undefined ? externalLogs : localLogs;
  const syncing = externalSyncing || localSyncing;

  // Nacharbeit 1 (Hauptagent, technisch entschieden — KEIN Owner-Entscheid,
  // siehe `renameLocked` unten): Der Abgleich sperrt NICHT die ganze Gruppe.
  // Er laeuft wie der Auto-Sync nur fuer Alben mit lebendem Besitzer und
  // UEBERSPRINGT verwaiste — sonst erzeugte jeder Klick auf "Jetzt
  // synchronisieren" denselben `log_owner_account_missing`-Fehlereintrag,
  // den der Auto-Sync (`main._run_auto_sync`) genau deshalb nicht mehr
  // schreibt (`docs/agents/lehren.md` §45). Die Markierung weiter oben
  // bleibt der sichtbare Hinweis, warum ein Teil der Gruppe fehlt.
  const gesundeAlben = group.albums.filter((album) => !album.owner_account_missing);

  const handleRefresh = async () => {
    setLocalSyncing(true);
    setLocalLogs(null);
    const allLogs: SyncLogEntry[] = [];
    for (const album of gesundeAlben) {
      try {
        allLogs.push(...(await api.sync.refreshAlbum(album.id)));
      } catch (_) {}
    }
    setLocalLogs(allLogs);
    setLokalZuletzt(true);
    setLocalSyncing(false);
    qc.invalidateQueries({ queryKey: ["managed-albums"] });
    qc.invalidateQueries({ queryKey: ["sync-log"] });
  };

  const handleDelete = async () => {
    if (!confirm(t("album_remove_confirm", group.album_name, group.albums.length))) return;
    setDeleting(true);
    for (const album of group.albums) {
      try {
        await api.sync.deleteAlbum(album.id);
      } catch (_) {}
    }
    setDeleting(false);
    qc.invalidateQueries({ queryKey: ["managed-albums"] });
    qc.invalidateQueries({ queryKey: ["matches"] });
    // Entfernen aendert die Gruppe (weniger/keine Alben mehr) — eine
    // laufende Gruppenvorschau darf danach keine veraltete Antwort mehr
    // zeigen (#110, Nacharbeit 1, BLOCKER Fund 1).
    qc.invalidateQueries({ queryKey: ["album-group"] });
  };

  const handleRename = async () => {
    // Nacharbeit 1 (Gegenpruefer, gemessen): Ohne diese Pruefung HIER blieb
    // ein bereits GEOEFFNETES Eingabefeld offen, wenn die Sperre erst
    // WAEHREND des Bearbeitens eintrat (Konto in einem anderen Tab
    // geloescht, Liste neu geladen) — Enter benannte dann nur das gesunde
    // Album um, die Gruppe trug danach zwei Namen. Der Effekt unten schliesst
    // das Feld zusaetzlich von sich aus, sobald die Sperre eintritt; diese
    // Pruefung faengt das Fenster dazwischen (Klick/Enter, bevor der Effekt
    // gelaufen ist).
    if (renameLocked) {
      setRenaming(false);
      setRenameValue(group.album_name);
      return;
    }
    const nextName = renameValue.trim();
    // KEIN Abbruch bei „Name gleich dem Gruppennamen“: Der Gruppenname ist vom
    // ERSTEN Album abgeleitet (`groupAlbums`). Nach einem Teilfehler traegt das
    // erste Album schon den neuen Namen — mit dem alten Vergleich war der
    // zweite Versuch deshalb ein Nullvorgang, und das fehlgeschlagene Album
    // blieb fuer immer zurueck (Fund des Fremdpruefers an #79). Abgebrochen
    // wird nur, wenn ALLE Alben der Gruppe den Namen schon tragen.
    if (!nextName || group.albums.every((album) => album.album_name === nextName)) {
      setRenaming(false);
      setRenameValue(group.album_name);
      return;
    }
    setRenameError(null);
    setLocalSyncing(true);
    setLocalLogs(null);
    const logs: SyncLogEntry[] = [];
    try {
      for (const album of group.albums) {
        logs.push(...(await api.sync.renameAlbum(album.id, nextName)));
      }
      if (logs.every((entry) => entry.status === "success")) setRenaming(false);
    } catch (error) {
      setRenameError(errorText(error as ServerErrorLike));
    } finally {
      // Die schon gesammelten Eintraege gehoeren auch dann auf die Karte, wenn
      // eine SPAETERE Anfrage geworfen hat (Fund des Fremdpruefers an #79):
      // `setLocalLogs` und die Invalidierungen standen hinter der Schleife, ein
      // Wurf sprang ueber beides — der Nutzer sah nur den Fehlertext und nicht,
      // was vorher schon umbenannt worden war.
      if (logs.length) {
        setLocalLogs(logs);
        setLokalZuletzt(true);
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
  // NICHT Owner-Entscheid — technisch vom Hauptagenten entschieden
  // (Nacharbeit 1, #99/#112): Ein Album ohne lebenden Besitzer sperrt
  // UMBENENNEN der ganzen Gruppe (sonst eine halb umbenannte Gruppe mit
  // zwei Namen — jedes Album traegt seinen Namen einzeln, Umbenennen laeuft
  // in einer Schleife ueber `group.albums`). Der ABGLEICH sperrt NICHT:
  // er laeuft fuer die gesunden Alben weiter und ueberspringt die
  // verwaisten, siehe `gesundeAlben` oben. Entfernen bleibt in jedem Fall
  // moeglich. "Nur noch eine Person"/"keine Person mehr" sperrt fuer sich
  // allein nichts, wird aber ebenfalls sichtbar (Text, nicht nur Farbe).
  const renameLocked = group.ownerMissing;

  // Schliesst ein offenes Umbenennen-Feld, sobald die Sperre eintritt —
  // siehe die Pruefung am Kopf von `handleRename` fuer das Fenster davor.
  React.useEffect(() => {
    if (renameLocked) {
      setRenaming(false);
      setRenameValue(group.album_name);
      setRenameError(null);
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
                      setRenaming(false);
                      setRenameValue(group.album_name);
                    }
                  }}
                  aria-label={t("album_rename_action")}
                  autoFocus
                  disabled={localSyncing}
                />
                <button
                  className="p-1 text-emerald-400 hover:text-emerald-300"
                  onClick={handleRename}
                  disabled={localSyncing || !renameValue.trim()}
                  aria-label={t("save")}
                >
                  <Check size={15} />
                </button>
                <button
                  className="p-1 text-gray-500 hover:text-gray-300"
                  onClick={() => {
                    setRenaming(false);
                    setRenameValue(group.album_name);
                    setRenameError(null);
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
              {t("owner")}: {group.ownerMissing ? t("album_owner_missing_badge") : group.owner_name}
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
            {/* 0 und 1 verbleibende Person(en) sind unterschiedliche Texte
                (Nacharbeit 1, kleiner Fund): "Nur noch eine Person" waere bei
                null Personen falsch. */}
            {group.tooFewPeople &&
              (group.person_refs.length === 0
                ? t("album_no_people_badge")
                : t("album_too_few_people_badge"))}
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

      <SyncLogDisplay logs={displayLogs} syncing={syncing} />
      {renameError && <p className="text-xs text-red-400">{renameError}</p>}

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
            setRenameError(null);
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
          disabled={syncing || gesundeAlben.length === 0}
          title={
            group.ownerMissing && gesundeAlben.length > 0
              ? t("album_sync_skips_orphaned_hint")
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

  // bulkSyncState: per-group results from "Alle synchronisieren"
  // null = not started, undefined = currently running (show spinner), [] = done (show logs)
  const [bulkSyncState, setBulkSyncState] = React.useState<Map<string, SyncLogEntry[] | null>>(
    new Map()
  );
  const [refreshingAll, setRefreshingAll] = React.useState(false);

  const handleRefreshAll = async () => {
    setRefreshingAll(true);
    // Mark all groups as "syncing"
    setBulkSyncState(new Map(groups.map((g) => [g.group_id, null])));

    for (const group of groups) {
      const groupLogs: SyncLogEntry[] = [];
      // Nacharbeit 1: wie der einzelne "Jetzt synchronisieren"-Knopf und wie
      // der Auto-Sync — verwaiste Alben werden UEBERSPRUNGEN, nicht mit
      // demselben Fehlereintrag pro Klick bedacht (siehe `gesundeAlben` in
      // `AlbumGroupCard`).
      const gesunde = group.albums.filter((album) => !album.owner_account_missing);
      for (const album of gesunde) {
        try {
          groupLogs.push(...(await api.sync.refreshAlbum(album.id)));
        } catch (_) {}
      }
      // Update this group's results immediately, keep others in their current state
      setBulkSyncState((prev) => new Map(prev).set(group.group_id, groupLogs));
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
            // null in map = currently syncing; array = done with results
            const externalSyncing = bulkSyncState.has(group.group_id) && bulkEntry === null;
            // Ein LEERES Sammelergebnis ist kein Ergebnis (Fund des
            // Blindpruefers an der Nacharbeit): Werfen alle Auffrischungen
            // einer Gruppe, ist `bulkEntry` ein leeres Feld — nicht
            // `undefined`. Es bekam damit den Vorrang, `SyncLogDisplay` gibt
            // fuer ein leeres Feld nichts zurueck, und die Karte stand leer
            // da: das vorige Umbenenn-Ergebnis war spurlos weg. Der
            // Sammellauf schluckt seine Fehler ausserdem, es gab also auch
            // keine Meldung.
            const externalLogs = bulkEntry && bulkEntry.length ? bulkEntry : undefined;
            return (
              <AlbumGroupCard
                key={group.group_id}
                group={group}
                externalLogs={externalLogs}
                externalSyncing={externalSyncing}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
