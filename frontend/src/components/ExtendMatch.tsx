import { useState, useMemo, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, User, Clock, Disc, CheckCircle, XCircle, ChevronRight, Plus } from "lucide-react";
import { api, ManagedAlbum, SyncLogEntry, Account, Person } from "../api/client";
import { useT } from "../i18n";

// ── Re-use groupAlbums logic ───────────────────────────────────────────────

interface AlbumGroup {
  album_name: string;
  albums: ManagedAlbum[];
  total_assets: number;
  last_synced_at: string | undefined;
  owner_name: string;
  person_refs: ManagedAlbum["person_refs"];
  primary_album: ManagedAlbum; // most recently synced
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
        if (!seen.has(key)) {
          seen.add(key);
          personRefs.push(ref);
        }
      }
    }
    const dates = group.map((a) => a.last_synced_at).filter(Boolean) as string[];
    const lastSync = dates.length ? dates.sort().reverse()[0] : undefined;
    const primary = [...group].sort((a, b) =>
      (b.last_synced_at ?? "").localeCompare(a.last_synced_at ?? "")
    )[0];
    const ownerRef = primary.person_refs.find((r) => r.account_id === primary.owner_account_id);
    const mostRecent = [...group].sort((a, b) =>
      (b.last_synced_at ?? "").localeCompare(a.last_synced_at ?? "")
    )[0];
    return {
      album_name: primary.album_name,
      albums: group,
      total_assets: mostRecent.total_assets,
      last_synced_at: lastSync,
      owner_name: ownerRef?.account_name ?? primary.owner_account_id,
      person_refs: personRefs,
      primary_album: primary,
    };
  });
}

function formatDate(iso?: string) {
  if (!iso) return "–";
  return new Date(iso).toLocaleString("de-AT", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ── Searchable Person Picker ───────────────────────────────────────────────

function SearchablePersonPicker({
  people,
  value,
  onChange,
  placeholder,
  disabled,
}: {
  people: Person[];
  value: string;
  onChange: (id: string) => void;
  placeholder: string;
  disabled?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const selectedPerson = people.find((p) => p.id === value);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return people
      .filter((p) => !q || (p.name ?? "").toLowerCase().includes(q))
      .sort((a, b) => {
        const na = a.name ?? "";
        const nb = b.name ?? "";
        if (na && !nb) return -1;
        if (!na && nb) return 1;
        return na.localeCompare(nb);
      })
      .slice(0, 50);
  }, [people, query]);

  const select = (p: Person) => {
    onChange(p.id);
    setQuery(p.name ?? "");
    setOpen(false);
  };

  return (
    <div ref={ref} className="relative">
      <input
        type="text"
        className={`w-full bg-immich-surface border border-immich-border rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-immich-primary ${disabled ? "opacity-40 pointer-events-none" : ""}`}
        placeholder={placeholder}
        value={open ? query : (selectedPerson?.name ?? (value ? value.slice(0, 8) + "…" : ""))}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          if (!e.target.value) onChange("");
        }}
        onFocus={() => {
          setQuery("");
          setOpen(true);
        }}
        disabled={disabled}
      />
      {open && filtered.length > 0 && (
        <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-immich-surface border border-immich-border rounded-lg shadow-xl max-h-56 overflow-y-auto">
          {filtered.map((p) => (
            <button
              key={p.id}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-200 hover:bg-immich-border text-left"
              onMouseDown={(e) => {
                e.preventDefault();
                select(p);
              }}
            >
              <img
                src={api.people.thumbnailUrl(p.account_id, p.id)}
                className="w-6 h-6 rounded-full object-cover shrink-0"
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = "none";
                }}
              />
              <span className="truncate flex-1">
                {p.name || <span className="text-gray-500 italic">Unbekannt</span>}
              </span>
              {p.asset_count > 0 && (
                <span className="text-xs text-gray-500 shrink-0">
                  {p.asset_count.toLocaleString()}
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Album Group Card (selectable) ─────────────────────────────────────────

function AlbumGroupCard({
  group,
  selected,
  onSelect,
}: {
  group: AlbumGroup;
  selected: boolean;
  onSelect: () => void;
}) {
  const { t } = useT();
  return (
    <button
      onClick={onSelect}
      className={`w-full text-left card space-y-3 transition-colors ${
        selected ? "border-immich-primary bg-immich-primary/10" : "hover:border-gray-500"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Disc size={16} className={selected ? "text-immich-primary" : "text-blue-400"} />
          <div>
            <p className="font-semibold text-sm">{group.album_name}</p>
            <p className="text-xs text-gray-500">
              {t("owner")}: {group.owner_name}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs text-gray-400">
            {group.total_assets.toLocaleString()} {t("photos")}
          </span>
          <ChevronRight
            size={14}
            className={`text-gray-500 transition-transform ${selected ? "rotate-90" : ""}`}
          />
        </div>
      </div>

      {/* Persons */}
      <div className="flex flex-wrap gap-1.5">
        {group.person_refs.map((ref, i) => (
          <div key={i} className="flex items-center gap-1 text-xs">
            <User size={10} className="text-gray-600" />
            <span className="text-gray-300">{ref.person_name}</span>
            <span
              className="badge"
              style={{ backgroundColor: ref.account_color, fontSize: "0.65rem", padding: "0 4px" }}
            >
              {ref.account_name}
            </span>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-1 text-xs text-gray-600">
        <Clock size={10} />
        <span>{t("last_sync", formatDate(group.last_synced_at))}</span>
      </div>
    </button>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function ExtendMatch() {
  const { t, logMessage } = useT();
  const qc = useQueryClient();

  const { data: rawAlbums = [], isLoading: loadingAlbums } = useQuery({
    queryKey: ["managed-albums"],
    queryFn: api.sync.albums,
    staleTime: 30_000,
  });

  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: api.accounts.list,
    staleTime: 30_000,
  });

  const groups = useMemo(() => groupAlbums(rawAlbums), [rawAlbums]);

  const [selectedGroupName, setSelectedGroupName] = useState<string | null>(null);
  const [newAccountId, setNewAccountId] = useState("");
  const [newPersonId, setNewPersonId] = useState("");
  const [syncName, setSyncName] = useState(true);
  const [result, setResult] = useState<SyncLogEntry[] | null>(null);

  const selectedGroup = groups.find((g) => g.album_name === selectedGroupName) ?? null;

  // Derived canonical name = album name (what existing people are named)
  const canonicalName = selectedGroup?.album_name ?? "";

  // Accounts not yet in the selected group
  const availableAccounts = useMemo<Account[]>(() => {
    if (!selectedGroup) return [];
    const usedIds = new Set(selectedGroup.person_refs.map((r) => r.account_id));
    return accounts.filter((a) => !usedIds.has(a.id));
  }, [selectedGroup, accounts]);

  // People for the chosen new account
  const { data: newAccountPeople = [], isFetching: loadingPeople } = useQuery({
    queryKey: ["people", newAccountId],
    queryFn: () => api.people.byAccount(newAccountId),
    enabled: !!newAccountId,
    staleTime: 60_000,
  });

  const selectedPerson = newAccountPeople.find((p) => p.id === newPersonId);

  // Reset form when album changes
  useEffect(() => {
    setNewAccountId("");
    setNewPersonId("");
    setResult(null);
  }, [selectedGroupName]);

  const mutation = useMutation({
    mutationFn: () =>
      api.sync.extend({
        managed_album_id: selectedGroup!.primary_album.id,
        account_id: newAccountId,
        person_id: newPersonId,
        person_name: selectedPerson?.name ?? undefined,
        canonical_name: syncName ? canonicalName : undefined,
      }),
    onSuccess: (data) => {
      setResult(data);
      qc.invalidateQueries({ queryKey: ["managed-albums"] });
      qc.invalidateQueries({ queryKey: ["sync-log"] });
      setNewPersonId("");
    },
  });

  const isValid = !!selectedGroup && !!newAccountId && !!newPersonId;

  return (
    <div className="p-6 max-w-2xl space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-100">{t("extend_title")}</h2>
        <p className="text-sm text-gray-400 mt-1">{t("extend_subtitle")}</p>
      </div>

      {/* Step 1: Album wählen */}
      <div className="space-y-2">
        <p className="text-xs text-gray-400 uppercase tracking-wide">{t("extend_pick_album")}</p>
        {loadingAlbums ? (
          <div className="flex justify-center py-8">
            <Loader2 size={24} className="animate-spin text-gray-500" />
          </div>
        ) : groups.length === 0 ? (
          <p className="text-sm text-gray-500">{t("extend_no_albums")}</p>
        ) : (
          <div className="space-y-2">
            {groups.map((g) => (
              <AlbumGroupCard
                key={g.album_name}
                group={g}
                selected={selectedGroupName === g.album_name}
                onSelect={() =>
                  setSelectedGroupName(selectedGroupName === g.album_name ? null : g.album_name)
                }
              />
            ))}
          </div>
        )}
      </div>

      {/* Step 2: Neuen Account + Person wählen */}
      {selectedGroup && (
        <div className="space-y-4 border-t border-immich-border pt-5">
          {availableAccounts.length === 0 && !result ? (
            <p className="text-sm text-amber-400 bg-amber-900/20 border border-amber-800 rounded px-3 py-2">
              {t("extend_no_accounts")}
            </p>
          ) : availableAccounts.length > 0 ? (
            <>
              {/* Account select */}
              <div className="space-y-1">
                <label className="text-xs text-gray-400 uppercase tracking-wide">
                  {t("extend_new_account")}
                </label>
                <select
                  className="w-full bg-immich-surface border border-immich-border rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-immich-primary"
                  value={newAccountId}
                  onChange={(e) => {
                    setNewAccountId(e.target.value);
                    setNewPersonId("");
                  }}
                >
                  <option value="">— {t("account_select_ph")} —</option>
                  {availableAccounts.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Person picker (searchable) */}
              <div className="space-y-1">
                <label className="text-xs text-gray-400 uppercase tracking-wide">
                  {t("extend_new_person")}
                </label>
                {loadingPeople ? (
                  <div className="flex items-center gap-2 text-sm text-gray-500 py-2">
                    <Loader2 size={14} className="animate-spin" /> {t("loading")}
                  </div>
                ) : (
                  <SearchablePersonPicker
                    people={newAccountPeople}
                    value={newPersonId}
                    onChange={setNewPersonId}
                    placeholder={newAccountId ? t("extend_search_person") : t("extend_new_account")}
                    disabled={!newAccountId}
                  />
                )}
              </div>

              {/* Namen synchronisieren Checkbox */}
              <label className="flex items-start gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={syncName}
                  onChange={(e) => setSyncName(e.target.checked)}
                  className="mt-0.5 rounded"
                />
                <div>
                  <span className="text-sm text-gray-300">{t("extend_sync_name")}</span>
                  {syncName && canonicalName && (
                    <p className="text-xs text-gray-500 mt-0.5">
                      {t("extend_sync_name_hint", canonicalName)}
                    </p>
                  )}
                </div>
              </label>

              {/* Submit */}
              <button
                onClick={() => {
                  setResult(null);
                  mutation.mutate();
                }}
                disabled={!isValid || mutation.isPending}
                className="flex items-center gap-2 px-5 py-2.5 bg-immich-primary text-white rounded-lg text-sm font-medium hover:bg-blue-600 disabled:opacity-40 transition-colors"
              >
                {mutation.isPending ? (
                  <Loader2 size={15} className="animate-spin" />
                ) : (
                  <Plus size={15} />
                )}
                {mutation.isPending ? t("running") : t("extend_submit")}
              </button>
            </>
          ) : null}

          {mutation.isError && (
            <p className="text-sm text-red-400">
              {t("error_prefix")} {(mutation.error as Error).message}
            </p>
          )}

          {/* Result — shown regardless of availableAccounts */}
          {result && (
            <div className="space-y-1.5">
              <p className="text-xs text-gray-400 uppercase tracking-wide">{t("result")}</p>
              {result.map((e) => (
                <div
                  key={e.id}
                  className={`flex items-start gap-2 p-2 rounded text-sm ${
                    e.status === "success"
                      ? "bg-green-900/20 text-green-300"
                      : "bg-red-900/20 text-red-300"
                  }`}
                >
                  {e.status === "success" ? (
                    <CheckCircle size={15} className="shrink-0 mt-0.5" />
                  ) : (
                    <XCircle size={15} className="shrink-0 mt-0.5" />
                  )}
                  <span>{logMessage(e)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
