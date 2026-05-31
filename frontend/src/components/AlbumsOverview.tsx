import React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw, Trash2, Disc, AlertTriangle, User, Clock } from "lucide-react";
import { api, ManagedAlbum, SyncLogEntry } from "../api/client";
import { useT } from "../i18n";

function formatDate(iso?: string) {
  if (!iso) return "–";
  return new Date(iso).toLocaleString("de-AT", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

interface AlbumGroup {
  album_name: string;
  albums: ManagedAlbum[];
  total_assets: number;
  last_synced_at: string | undefined;
  owner_name: string;
  person_refs: ManagedAlbum["person_refs"];
}

function groupAlbums(albums: ManagedAlbum[]): AlbumGroup[] {
  const map = new Map<string, ManagedAlbum[]>();
  for (const a of albums) {
    const key = a.album_name.trim().toLowerCase();
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(a);
  }

  return Array.from(map.values()).map((group) => {
    const seen = new Set<string>();
    const personRefs: ManagedAlbum["person_refs"] = [];
    for (const album of group) {
      for (const ref of album.person_refs) {
        const key = `${ref.account_id}::${ref.person_id}`;
        if (!seen.has(key)) { seen.add(key); personRefs.push(ref); }
      }
    }
    const dates = group.map((a) => a.last_synced_at).filter(Boolean) as string[];
    const lastSync = dates.length ? dates.sort().reverse()[0] : undefined;
    const first = group[0];
    const ownerRef = first.person_refs.find((r) => r.account_id === first.owner_account_id);
    // Use total_assets from the most recently synced entry (most accurate)
    const mostRecent = [...group].sort((a, b) =>
      (b.last_synced_at ?? "").localeCompare(a.last_synced_at ?? "")
    )[0];

    return {
      album_name: first.album_name,
      albums: group,
      total_assets: mostRecent.total_assets,
      last_synced_at: lastSync,
      owner_name: ownerRef?.account_name ?? first.owner_account_id,
      person_refs: personRefs,
    };
  });
}

function AlbumGroupCard({ group }: { group: AlbumGroup }) {
  const { t } = useT();
  const qc = useQueryClient();
  const [syncLogs, setSyncLogs] = React.useState<SyncLogEntry[] | null>(null);
  const [syncing, setSyncing] = React.useState(false);
  const [deleting, setDeleting] = React.useState(false);

  const handleRefresh = async () => {
    setSyncing(true);
    setSyncLogs(null);
    const allLogs: SyncLogEntry[] = [];
    for (const album of group.albums) {
      try { allLogs.push(...(await api.sync.refreshAlbum(album.id))); } catch (_) {}
    }
    setSyncLogs(allLogs);
    setSyncing(false);
    qc.invalidateQueries({ queryKey: ["managed-albums"] });
    qc.invalidateQueries({ queryKey: ["sync-log"] });
  };

  const handleDelete = async () => {
    if (!confirm(t("album_remove_confirm", group.album_name, group.albums.length))) return;
    setDeleting(true);
    for (const album of group.albums) {
      try { await api.sync.deleteAlbum(album.id); } catch (_) {}
    }
    setDeleting(false);
    qc.invalidateQueries({ queryKey: ["managed-albums"] });
    qc.invalidateQueries({ queryKey: ["matches"] });
  };

  const isDeleted = syncLogs?.some((e) => e.error_message === "ALBUM_DELETED");

  return (
    <div className={`card space-y-4 ${isDeleted ? "border-red-800" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Disc size={18} className={isDeleted ? "text-red-400" : "text-blue-400"} />
          <div>
            <h3 className="font-semibold">{group.album_name}</h3>
            <p className="text-xs text-gray-500">{t("owner")}: {group.owner_name}</p>
          </div>
        </div>
        <span className="text-sm font-medium text-gray-300 shrink-0">
          {group.total_assets.toLocaleString()} {t("photos")}
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
        <span>{t("last_sync", formatDate(group.last_synced_at))}</span>
      </div>

      {syncLogs && (
        <div className="space-y-1">
          {syncLogs.map((entry) => (
            <p key={entry.id} className={`text-xs border rounded px-2 py-1 ${
              entry.status === "success"
                ? "text-emerald-400 bg-emerald-900/20 border-emerald-800"
                : "text-red-400 bg-red-900/20 border-red-800"
            }`}>
              {entry.details}
            </p>
          ))}
        </div>
      )}

      {isDeleted && (
        <div className="flex items-center gap-2 text-xs text-amber-400 bg-amber-900/20 border border-amber-800 rounded px-3 py-2">
          <AlertTriangle size={13} />
          {t("album_deleted_warn")}
        </div>
      )}

      <div className="flex gap-2">
        <button className="btn-primary text-xs flex items-center gap-1.5" onClick={handleRefresh} disabled={syncing}>
          {syncing ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
          {syncing ? t("syncing") : t("sync_now")}
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

export default function AlbumsOverview() {
  const { t } = useT();
  const { data: albums = [], isLoading } = useQuery({
    queryKey: ["managed-albums"],
    queryFn: api.sync.albums,
    staleTime: 30_000,
  });
  const qc = useQueryClient();
  const groups = groupAlbums(albums);
  const [refreshingAll, setRefreshingAll] = React.useState(false);

  const handleRefreshAll = async () => {
    setRefreshingAll(true);
    for (const album of albums) {
      try { await api.sync.refreshAlbum(album.id); } catch (_) {}
    }
    setRefreshingAll(false);
    qc.invalidateQueries({ queryKey: ["managed-albums"] });
    qc.invalidateQueries({ queryKey: ["sync-log"] });
  };

  return (
    <div className="p-6 max-w-2xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold">{t("albums_title")}</h1>
          <p className="text-sm text-gray-500 mt-0.5">{t("albums_subtitle", groups.length)}</p>
        </div>
        {groups.length > 0 && (
          <button className="btn-primary text-sm flex items-center gap-1.5" onClick={handleRefreshAll} disabled={refreshingAll}>
            {refreshingAll ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            {t("sync_all")}
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16"><Loader2 size={28} className="animate-spin text-gray-500" /></div>
      ) : groups.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <Disc size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">{t("albums_empty")}</p>
          <p className="text-xs mt-1">{t("albums_empty_hint")}</p>
        </div>
      ) : (
        <div className="space-y-4">
          {groups.map((group) => <AlbumGroupCard key={group.album_name} group={group} />)}
        </div>
      )}
    </div>
  );
}
