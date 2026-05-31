import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw, Trash2, Disc, AlertTriangle, User, Clock } from "lucide-react";
import { api, ManagedAlbum } from "../api/client";

function formatDate(iso?: string) {
  if (!iso) return "nie";
  return new Date(iso).toLocaleString("de-AT", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

function AlbumCard({ album }: { album: ManagedAlbum }) {
  const qc = useQueryClient();

  const refreshMutation = useMutation({
    mutationFn: () => api.sync.refreshAlbum(album.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["managed-albums"] });
      qc.invalidateQueries({ queryKey: ["sync-log"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.sync.deleteAlbum(album.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["managed-albums"] });
      qc.invalidateQueries({ queryKey: ["matches"] });
    },
  });

  const lastSyncLog = refreshMutation.data;
  const hasError = lastSyncLog?.some((e) => e.status === "error");
  const isDeleted = lastSyncLog?.some((e) => e.error_message === "ALBUM_DELETED");

  return (
    <div className={`card space-y-4 ${isDeleted ? "border-red-800" : ""}`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Disc size={18} className={isDeleted ? "text-red-400" : "text-blue-400"} />
          <div>
            <h3 className="font-semibold">{album.album_name}</h3>
            <p className="text-xs text-gray-500">
              Besitzer: {
                // Find account name from person_refs
                album.person_refs.find((r) => r.account_id === album.owner_account_id)?.account_name
                ?? album.owner_account_id
              }
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-sm font-medium text-gray-300">
            {album.total_assets.toLocaleString()} Fotos
          </span>
        </div>
      </div>

      {/* Persons */}
      <div className="space-y-1.5">
        <p className="text-xs text-gray-500 font-medium">Verknüpfte Personen</p>
        {album.person_refs.map((ref, i) => (
          <div key={i} className="flex items-center gap-2">
            <User size={12} className="text-gray-600 shrink-0" />
            <span className="text-sm">
              {ref.person_name || <span className="text-gray-500 italic">Unbekannt</span>}
            </span>
            <span
              className="badge text-xs"
              style={{ backgroundColor: "#6366f1" }}
            >
              {ref.account_name ?? ref.account_id}
            </span>
          </div>
        ))}
      </div>

      {/* Last sync */}
      <div className="flex items-center gap-1.5 text-xs text-gray-500">
        <Clock size={12} />
        <span>Letzter Sync: {formatDate(album.last_synced_at)}</span>
      </div>

      {/* Status from last refresh */}
      {lastSyncLog && (
        <div className="space-y-1">
          {lastSyncLog.map((entry) => (
            <p
              key={entry.id}
              className={`text-xs border rounded px-2 py-1 ${
                entry.status === "success"
                  ? "text-emerald-400 bg-emerald-900/20 border-emerald-800"
                  : "text-red-400 bg-red-900/20 border-red-800"
              }`}
            >
              {entry.details}
            </p>
          ))}
        </div>
      )}

      {isDeleted && (
        <div className="flex items-center gap-2 text-xs text-amber-400 bg-amber-900/20 border border-amber-800 rounded px-3 py-2">
          <AlertTriangle size={13} />
          Album wurde in Immich gelöscht. Eintrag hier entfernen?
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        <button
          className="btn-primary text-xs flex items-center gap-1.5"
          onClick={() => refreshMutation.mutate()}
          disabled={refreshMutation.isPending}
        >
          {refreshMutation.isPending
            ? <Loader2 size={13} className="animate-spin" />
            : <RefreshCw size={13} />}
          {refreshMutation.isPending ? "Synchronisiert…" : "Jetzt synchronisieren"}
        </button>
        <button
          className="btn-ghost text-xs flex items-center gap-1.5 text-red-400 hover:text-red-300"
          onClick={() => {
            if (confirm(`Eintrag für Album "${album.album_name}" entfernen?\n\nDas Album in Immich bleibt erhalten, wird aber nicht mehr synchronisiert.`))
              deleteMutation.mutate();
          }}
          disabled={deleteMutation.isPending}
          title="Verknüpfung entfernen (Album in Immich bleibt erhalten)"
        >
          {deleteMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
          Verknüpfung entfernen
        </button>
      </div>
    </div>
  );
}

export default function AlbumsOverview() {
  const { data: albums = [], isLoading } = useQuery({
    queryKey: ["managed-albums"],
    queryFn: api.sync.albums,
    staleTime: 30_000,
  });

  const qc = useQueryClient();

  const refreshAllMutation = useMutation({
    mutationFn: async () => {
      for (const album of albums) {
        await api.sync.refreshAlbum(album.id);
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["managed-albums"] });
      qc.invalidateQueries({ queryKey: ["sync-log"] });
    },
  });

  return (
    <div className="p-6 max-w-2xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold">Verwaltete Alben</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {albums.length} Album{albums.length !== 1 ? "en" : ""} mit automatischer Synchronisation
          </p>
        </div>
        {albums.length > 0 && (
          <button
            className="btn-primary text-sm flex items-center gap-1.5"
            onClick={() => refreshAllMutation.mutate()}
            disabled={refreshAllMutation.isPending}
          >
            {refreshAllMutation.isPending
              ? <Loader2 size={14} className="animate-spin" />
              : <RefreshCw size={14} />}
            Alle synchronisieren
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 size={28} className="animate-spin text-gray-500" />
        </div>
      ) : albums.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <Disc size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">Noch keine verwalteten Alben.</p>
          <p className="text-xs mt-1">
            Erstelle ein Album über einen Match-Vorschlag.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {albums.map((album) => (
            <AlbumCard key={album.id} album={album} />
          ))}
        </div>
      )}
    </div>
  );
}
