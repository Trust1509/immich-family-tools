import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Loader2, RefreshCw, Check, X, Music, GitMerge, Zap,
  Search, SlidersHorizontal, CheckCircle, Disc, EyeOff,
} from "lucide-react";
import { api, Match, Account } from "../api/client";
import FaceCompare from "./FaceCompare";

// ── Album Dialog ───────────────────────────────────────────────────────────

function AlbumDialog({
  match, accounts, onSubmit, onCancel, isPending, error,
}: {
  match: Match;
  accounts: Account[];
  onSubmit: (body: { owner_account_id: string; album_name?: string; existing_album_id?: string }) => void;
  onCancel: () => void;
  isPending: boolean;
  error?: string;
}) {
  const defaultName = match.person_a.person_name || match.person_b.person_name || "Familie";
  const [mode, setMode] = useState<"new" | "existing">("new");
  const [albumName, setAlbumName] = useState(defaultName);
  const [ownerAccountId, setOwnerAccountId] = useState(match.person_a.account_id);
  const [existingAlbumId, setExistingAlbumId] = useState("");

  const { data: existingAlbums = [], isFetching: loadingAlbums } = useQuery({
    queryKey: ["account-albums", ownerAccountId],
    queryFn: () => api.accounts.albums(ownerAccountId),
    enabled: mode === "existing",
    staleTime: 30_000,
  });

  const handleSubmit = () => {
    if (mode === "new") {
      onSubmit({ owner_account_id: ownerAccountId, album_name: albumName });
    } else {
      const selected = existingAlbums.find((a) => a.id === existingAlbumId);
      onSubmit({
        owner_account_id: ownerAccountId,
        existing_album_id: existingAlbumId,
        album_name: selected?.name,
      });
    }
  };

  const canSubmit = mode === "new" ? !!albumName : !!existingAlbumId;

  return (
    <div className="space-y-3 bg-immich-bg border border-immich-border rounded-lg p-3">
      {/* Mode toggle */}
      <div className="flex gap-1 bg-immich-surface rounded-lg p-1">
        {(["new", "existing"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`flex-1 py-1.5 rounded text-xs font-medium transition-colors ${
              mode === m ? "bg-immich-primary text-white" : "text-gray-400 hover:text-gray-200"
            }`}
          >
            {m === "new" ? "Neues Album" : "Vorhandenes verknüpfen"}
          </button>
        ))}
      </div>

      {/* Owner */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500 w-16 shrink-0">Besitzer</span>
        <select
          className="input text-sm flex-1"
          value={ownerAccountId}
          onChange={(e) => { setOwnerAccountId(e.target.value); setExistingAlbumId(""); }}
        >
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>{a.name}</option>
          ))}
        </select>
      </div>

      {mode === "new" ? (
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500 w-16 shrink-0">Name</span>
          <input
            className="input text-sm flex-1"
            value={albumName}
            onChange={(e) => setAlbumName(e.target.value)}
            placeholder="Album-Name…"
            autoFocus
          />
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500 w-16 shrink-0">Album</span>
          {loadingAlbums ? (
            <Loader2 size={14} className="animate-spin text-gray-500" />
          ) : (
            <select
              className="input text-sm flex-1"
              value={existingAlbumId}
              onChange={(e) => setExistingAlbumId(e.target.value)}
            >
              <option value="">— Album wählen —</option>
              {existingAlbums.map((a) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          )}
        </div>
      )}

      <p className="text-xs text-gray-600">
        {mode === "new"
          ? "Neues Album wird erstellt, mit allen Accounts geteilt und Fotos automatisch hinzugefügt."
          : "Bestehendes Album wird mit allen Accounts geteilt und fehlende Fotos werden ergänzt."}
      </p>

      {error && <p className="text-xs text-red-400 bg-red-900/20 border border-red-800 rounded px-2 py-1">{error}</p>}

      <div className="flex gap-2">
        <button
          className="btn-primary text-sm flex items-center gap-1"
          onClick={handleSubmit}
          disabled={!canSubmit || isPending}
        >
          {isPending ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
          {isPending ? "Wird verarbeitet…" : mode === "new" ? "Album erstellen" : "Album verknüpfen"}
        </button>
        <button className="btn-ghost text-sm" onClick={onCancel}><X size={14} /></button>
      </div>
    </div>
  );
}

// ── Match Card ─────────────────────────────────────────────────────────────

interface ResultState { text: string; ok: boolean }

function MatchCard({ match, accounts, onDismiss, managedAlbumId }: {
  match: Match; accounts: Account[]; onDismiss: () => void; managedAlbumId?: string;
}) {
  const defaultName = match.person_a.person_name || match.person_b.person_name || "";
  const [syncName, setSyncName] = useState(defaultName);
  const [mode, setMode] = useState<null | "name" | "album">(null);
  const [result, setResult] = useState<ResultState | null>(null);
  const [albumError, setAlbumError] = useState<string | undefined>();
  const qc = useQueryClient();

  const isDismissed = match.status === "dismissed";

  const nameMutation = useMutation({
    mutationFn: () => api.sync.names(match.id, syncName),
    onSuccess: (entries) => {
      const ok = entries.every((e) => e.status === "success");
      setMode(null);
      setResult({ text: ok ? "Namen synchronisiert!" : "Teilweise fehlgeschlagen.", ok });
      if (ok) {
        qc.invalidateQueries({ queryKey: ["people"] });
        qc.invalidateQueries({ queryKey: ["matches"] });
        setTimeout(() => setResult(null), 3000);
      }
    },
  });

  const albumMutation = useMutation({
    mutationFn: (body: { owner_account_id: string; album_name?: string; existing_album_id?: string }) =>
      api.sync.album({ match_id: match.id, ...body }),
    onSuccess: (entries) => {
      const ok = entries.every((e) => e.status === "success");
      setMode(null);
      setAlbumError(undefined);
      setResult({ text: ok ? "Album verbunden!" : "Fehler beim Erstellen.", ok });
      qc.invalidateQueries({ queryKey: ["sync-log"] });
      qc.invalidateQueries({ queryKey: ["matches"] });
      qc.invalidateQueries({ queryKey: ["managed-albums"] });
      if (ok) setTimeout(() => setResult(null), 4000);
    },
    onError: (err: Error) => setAlbumError(err.message),
  });

  const refreshMutation = useMutation({
    mutationFn: () => api.sync.refreshAlbum(managedAlbumId!),
    onSuccess: (entries) => {
      const ok = entries.every((e) => e.status === "success");
      setResult({ text: ok ? "Album aktualisiert!" : "Teilweise fehlgeschlagen.", ok });
      qc.invalidateQueries({ queryKey: ["sync-log"] });
      if (ok) setTimeout(() => setResult(null), 4000);
    },
    onError: (err: Error) => setResult({ text: err.message, ok: false }),
  });

  return (
    <div className={`card space-y-3 ${isDismissed ? "opacity-50 border-dashed" : ""}`}>
      {isDismissed && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500 italic">Abgelehnt — nicht dieselbe Person</span>
          <button
            className="text-xs text-blue-400 hover:text-blue-300"
            onClick={() => {
              // undismiss via dismiss toggle (frontend will re-show after refresh)
              qc.invalidateQueries({ queryKey: ["matches"] });
            }}
          >
            Wiederherstellen
          </button>
        </div>
      )}

      <FaceCompare
        personA={match.person_a} personB={match.person_b}
        confidence={match.confidence} reasons={match.reasons}
      />

      {/* Status badges */}
      {(match.names_synced || match.has_album) && (
        <div className="flex gap-1.5 flex-wrap">
          {match.names_synced && (
            <span className="flex items-center gap-1 text-xs bg-emerald-900/30 border border-emerald-700 text-emerald-400 px-2 py-0.5 rounded-full">
              <Check size={10} /> Namen sync
            </span>
          )}
          {match.has_album && (
            <span className="flex items-center gap-1 text-xs bg-blue-900/30 border border-blue-700 text-blue-400 px-2 py-0.5 rounded-full">
              <Disc size={10} /> Album verbunden
            </span>
          )}
        </div>
      )}

      {result && (
        <div className={`flex items-start justify-between gap-2 text-xs border rounded px-3 py-2 ${result.ok ? "text-emerald-400 bg-emerald-900/20 border-emerald-800" : "text-red-400 bg-red-900/20 border-red-800"}`}>
          <span>{result.text}</span>
          {!result.ok && (
            <button onClick={() => setResult(null)} className="shrink-0 opacity-60 hover:opacity-100">
              <X size={12} />
            </button>
          )}
        </div>
      )}

      {mode === "name" && (
        <div className="flex gap-2">
          <input className="input text-sm" placeholder="Kanonischer Name…" value={syncName}
            onChange={(e) => setSyncName(e.target.value)} autoFocus />
          <button className="btn-primary text-sm shrink-0 flex items-center gap-1"
            onClick={() => nameMutation.mutate()} disabled={!syncName || nameMutation.isPending}>
            {nameMutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />} OK
          </button>
          <button className="btn-ghost text-sm" onClick={() => setMode(null)}><X size={14} /></button>
        </div>
      )}

      {mode === "album" && (
        <AlbumDialog
          match={match} accounts={accounts}
          onSubmit={(body) => albumMutation.mutate(body)}
          onCancel={() => { setMode(null); setAlbumError(undefined); }}
          isPending={albumMutation.isPending}
          error={albumError}
        />
      )}

      {mode === null && !isDismissed && (
        <div className="flex flex-wrap gap-2">
          <button className="btn-primary text-xs flex items-center gap-1.5" onClick={() => setMode("name")}>
            <Check size={13} />
            {match.names_synced ? "Namen erneut sync" : "Namen synchronisieren"}
          </button>
          {match.has_album && managedAlbumId ? (
            <button
              className="bg-immich-surface border border-blue-700 hover:border-blue-500 text-blue-400 hover:text-blue-300 px-3 py-1.5 rounded-lg text-xs flex items-center gap-1.5 transition-colors"
              onClick={() => refreshMutation.mutate()}
              disabled={refreshMutation.isPending}
            >
              {refreshMutation.isPending
                ? <Loader2 size={13} className="animate-spin" />
                : <RefreshCw size={13} />}
              Album aktualisieren
            </button>
          ) : (
            <button
              className="bg-immich-surface border border-immich-border hover:border-immich-primary text-gray-300 hover:text-white px-3 py-1.5 rounded-lg text-xs flex items-center gap-1.5 transition-colors"
              onClick={() => setMode("album")}>
              <Music size={13} />
              Album verbinden
            </button>
          )}
          <button className="btn-ghost text-xs flex items-center gap-1.5 text-red-400 hover:text-red-300" onClick={onDismiss}>
            <X size={13} /> Nicht dieselbe Person
          </button>
        </div>
      )}
    </div>
  );
}

// ── Filter Bar ─────────────────────────────────────────────────────────────

interface Filters {
  search: string;
  minConfidence: number;
  showNamesSynced: boolean;
  showAlbumLinked: boolean;
  showDismissed: boolean;
}

function FilterBar({ filters, onChange, total, visible }: {
  filters: Filters; onChange: (f: Filters) => void; total: number; visible: number;
}) {
  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch });
  return (
    <div className="space-y-2 mb-4">
      <div className="flex flex-wrap gap-2">
        <div className="relative">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input className="input pl-8 w-44 text-sm" placeholder="Name suchen…"
            value={filters.search} onChange={(e) => set({ search: e.target.value })} />
        </div>
        <div className="flex items-center gap-2 bg-immich-surface border border-immich-border rounded-lg px-3 py-1.5">
          <SlidersHorizontal size={13} className="text-gray-500" />
          <span className="text-xs text-gray-400">min.</span>
          <input type="range" min={0} max={100} step={5} value={filters.minConfidence}
            onChange={(e) => set({ minConfidence: Number(e.target.value) })}
            className="w-20 accent-immich-primary" />
          <span className="text-xs text-gray-300 w-8 text-right">{filters.minConfidence}%</span>
        </div>
        {[
          { key: "showNamesSynced" as const, label: "Namen sync", icon: <CheckCircle size={12} /> },
          { key: "showAlbumLinked" as const, label: "Album verbunden", icon: <Disc size={12} /> },
          { key: "showDismissed" as const, label: "Abgelehnte", icon: <EyeOff size={12} /> },
        ].map(({ key, label, icon }) => (
          <button key={key} onClick={() => set({ [key]: !filters[key] })}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs border transition-colors ${
              filters[key] ? "bg-immich-primary border-immich-primary text-white" : "bg-immich-surface border-immich-border text-gray-400 hover:text-gray-100"
            }`}>
            {icon} {label}
          </button>
        ))}
      </div>
      {visible < total && (
        <p className="text-xs text-gray-600">{visible} von {total} Vorschlägen sichtbar</p>
      )}
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function MatchSuggestions() {
  const qc = useQueryClient();
  const [filters, setFilters] = useState<Filters>({
    search: "", minConfidence: 0,
    showNamesSynced: true, showAlbumLinked: true, showDismissed: false,
  });

  const { data: matches = [], isLoading, isFetching } = useQuery({
    queryKey: ["matches"],
    queryFn: api.matches.list,
    staleTime: 5 * 60_000,
  });

  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: api.accounts.list,
  });

  const { data: managedAlbums = [] } = useQuery({
    queryKey: ["managed-albums"],
    queryFn: api.sync.albums,
    staleTime: 30_000,
  });

  const refreshMutation = useMutation({
    mutationFn: api.matches.refresh,
    onSuccess: (data) => qc.setQueryData(["matches"], data),
  });

  const dismissMutation = useMutation({
    mutationFn: (matchId: string) => api.matches.dismiss(matchId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["matches"] }),
  });

  const pending = matches.filter((m) => m.status === "pending");
  const dismissed = matches.filter((m) => m.status === "dismissed");
  const highConf = pending.filter((m) => m.confidence >= 0.85 && !m.names_synced);

  const bulkSyncMutation = useMutation({
    mutationFn: async () => {
      for (const m of highConf) {
        const name = m.person_a.person_name || m.person_b.person_name;
        if (name) await api.sync.names(m.id, name);
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["matches"] });
      qc.invalidateQueries({ queryKey: ["people"] });
    },
  });

  const displayed = useMemo(() => {
    const pool = filters.showDismissed ? matches : pending;
    return pool.filter((m) => {
      if (Math.round(m.confidence * 100) < filters.minConfidence) return false;
      if (!filters.showNamesSynced && m.names_synced) return false;
      if (!filters.showAlbumLinked && m.has_album) return false;
      if (filters.search) {
        const q = filters.search.toLowerCase();
        const na = (m.person_a.person_name ?? "").toLowerCase();
        const nb = (m.person_b.person_name ?? "").toLowerCase();
        if (!na.includes(q) && !nb.includes(q)) return false;
      }
      return true;
    });
  }, [matches, pending, filters]);

  return (
    <div className="p-6 max-w-2xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold">Match-Vorschläge</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {pending.length} offen · {dismissed.length} abgelehnt · {highConf.length} hochkonfident (&ge;85%)
          </p>
        </div>
        <div className="flex gap-2">
          {highConf.length > 0 && (
            <button className="btn-primary text-sm flex items-center gap-1.5"
              onClick={() => { if (confirm(`Alle ${highConf.length} hochkonfidenten Matches synchronisieren?`)) bulkSyncMutation.mutate(); }}
              disabled={bulkSyncMutation.isPending}>
              <Zap size={14} /> Bulk-Sync ({highConf.length})
            </button>
          )}
          <button className="btn-ghost flex items-center gap-1.5 text-sm"
            onClick={() => refreshMutation.mutate()} disabled={refreshMutation.isPending || isFetching}>
            <RefreshCw size={14} className={(refreshMutation.isPending || isFetching) ? "animate-spin" : ""} />
            Neu berechnen
          </button>
        </div>
      </div>

      <FilterBar filters={filters} onChange={setFilters} total={pending.length + (filters.showDismissed ? dismissed.length : 0)} visible={displayed.length} />

      {isLoading ? (
        <div className="flex justify-center py-16"><Loader2 size={28} className="animate-spin text-gray-500" /></div>
      ) : displayed.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <GitMerge size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">{pending.length === 0 ? "Keine offenen Vorschläge." : "Kein Vorschlag passt zu den Filtern."}</p>
        </div>
      ) : (
        <div className="space-y-4">
          {displayed.map((m) => (
            <MatchCard key={m.id} match={m} accounts={accounts}
              managedAlbumId={managedAlbums.find((a) => a.match_id === m.id)?.id}
              onDismiss={() => dismissMutation.mutate(m.id)} />
          ))}
        </div>
      )}
    </div>
  );
}
