import { useState, useMemo, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle, XCircle, Plus, Trash2, Play, AlertTriangle, Loader2 } from "lucide-react";
import { api, type Account, type Person, type SyncLogEntry } from "../api/client";
import { useT } from "../i18n";

interface PersonSelection {
  account_id: string;
  person_id: string;
}

// ── Searchable person picker ───────────────────────────────────────────────

function SearchablePersonPicker({
  people,
  loading,
  value,
  onChange,
  placeholder,
  disabled,
}: {
  people: Person[];
  loading?: boolean;
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
      .slice(0, 60);
  }, [people, query]);

  const select = (p: Person) => {
    onChange(p.id);
    setQuery(p.name ?? "");
    setOpen(false);
  };

  const displayValue = open
    ? query
    : selectedPerson
      ? `${selectedPerson.name || "?"}${selectedPerson.asset_count > 0 ? ` (${selectedPerson.asset_count.toLocaleString()})` : ""}`
      : "";

  return (
    <div ref={ref} className="relative flex-1">
      <input
        type="text"
        className={`w-full bg-immich-surface border border-immich-border rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-immich-primary ${disabled ? "opacity-40 pointer-events-none" : ""}`}
        placeholder={loading ? "Lade…" : placeholder}
        value={displayValue}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          if (!e.target.value) onChange("");
        }}
        onFocus={() => {
          setQuery("");
          setOpen(true);
        }}
        disabled={disabled || loading}
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

// ── Person row ─────────────────────────────────────────────────────────────

function PersonRow({
  accounts,
  usedAccountIds,
  selection,
  index,
  onUpdate,
  onRemove,
  canRemove,
}: {
  accounts: Account[];
  usedAccountIds: string[];
  selection: PersonSelection;
  index: number;
  onUpdate: (s: PersonSelection) => void;
  onRemove: () => void;
  canRemove: boolean;
}) {
  const { t } = useT();
  const { data: people = [], isFetching } = useQuery({
    queryKey: ["people", selection.account_id],
    queryFn: () => api.people.byAccount(selection.account_id),
    enabled: !!selection.account_id,
    staleTime: 60_000,
  });

  return (
    <div className="flex items-center gap-3 p-3 bg-immich-bg rounded-lg border border-immich-border">
      <span className="text-gray-500 text-sm w-5 shrink-0">{index + 1}.</span>
      <select
        className="w-36 shrink-0 bg-immich-surface border border-immich-border rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-immich-primary"
        value={selection.account_id}
        onChange={(e) => onUpdate({ account_id: e.target.value, person_id: "" })}
      >
        <option value="">{t("account_select_ph")}</option>
        {accounts.map((a) => {
          const taken = usedAccountIds.includes(a.id);
          return (
            <option key={a.id} value={a.id} disabled={taken}>
              {a.name}
              {taken ? " ✓" : ""}
            </option>
          );
        })}
      </select>
      <SearchablePersonPicker
        people={people}
        loading={isFetching}
        value={selection.person_id}
        onChange={(id) => onUpdate({ ...selection, person_id: id })}
        placeholder={selection.account_id ? t("extend_search_person") : t("person_select_ph")}
        disabled={!selection.account_id}
      />
      {selection.person_id && (
        <img
          src={api.people.thumbnailUrl(selection.account_id, selection.person_id)}
          alt=""
          className="w-9 h-9 rounded-full object-cover shrink-0 border border-immich-border"
        />
      )}
      <button
        onClick={onRemove}
        disabled={!canRemove}
        className="p-1.5 rounded text-gray-500 hover:text-red-400 disabled:opacity-30 transition-colors shrink-0"
      >
        <Trash2 size={15} />
      </button>
    </div>
  );
}

// ── Album section ──────────────────────────────────────────────────────────

function AlbumSection({
  accounts,
  ownerAccountId,
  onOwnerChange,
  albumMode,
  onAlbumModeChange,
  albumName,
  onAlbumNameChange,
  existingAlbumId,
  onExistingAlbumIdChange,
}: {
  accounts: Account[];
  ownerAccountId: string;
  onOwnerChange: (id: string) => void;
  albumMode: "new" | "existing";
  onAlbumModeChange: (m: "new" | "existing") => void;
  albumName: string;
  onAlbumNameChange: (v: string) => void;
  existingAlbumId: string;
  onExistingAlbumIdChange: (id: string) => void;
}) {
  const { t } = useT();

  const { data: existingAlbums = [], isFetching: loadingAlbums } = useQuery({
    queryKey: ["account-albums", ownerAccountId],
    queryFn: () => api.accounts.albums(ownerAccountId),
    enabled: albumMode === "existing" && !!ownerAccountId,
    staleTime: 30_000,
  });

  return (
    <div className="space-y-3">
      <label className="text-xs text-gray-400 uppercase tracking-wide">
        {t("create_shared_album")}
      </label>
      <div className="space-y-3">
        {/* Mode toggle */}
        <div className="flex gap-1 bg-immich-surface rounded-lg p-1 w-fit">
          {(["new", "existing"] as const).map((m) => (
            <button
              key={m}
              onClick={() => onAlbumModeChange(m)}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                albumMode === m
                  ? "bg-immich-primary text-white"
                  : "text-gray-400 hover:text-gray-200"
              }`}
            >
              {m === "new" ? t("album_new") : t("album_link_existing")}
            </button>
          ))}
        </div>

        {/* Owner */}
        <div className="space-y-1">
          <label className="text-xs text-gray-500">{t("manual_album_owner")}</label>
          <select
            className="w-full bg-immich-surface border border-immich-border rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-immich-primary"
            value={ownerAccountId}
            onChange={(e) => {
              onOwnerChange(e.target.value);
              onExistingAlbumIdChange("");
            }}
          >
            <option value="">— {t("account_select_ph")} —</option>
            {accounts.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </div>

        {/* New album name */}
        {albumMode === "new" && (
          <input
            type="text"
            placeholder={t("album_name_label")}
            value={albumName}
            onChange={(e) => onAlbumNameChange(e.target.value)}
            className="w-full bg-immich-surface border border-immich-border rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-immich-primary"
          />
        )}

        {/* Existing album picker */}
        {albumMode === "existing" &&
          (loadingAlbums ? (
            <div className="flex items-center gap-2 text-sm text-gray-500 py-1">
              <Loader2 size={13} className="animate-spin" /> {t("loading")}
            </div>
          ) : (
            <select
              className="w-full bg-immich-surface border border-immich-border rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-immich-primary disabled:opacity-40"
              value={existingAlbumId}
              disabled={!ownerAccountId}
              onChange={(e) => onExistingAlbumIdChange(e.target.value)}
            >
              <option value="">{t("album_select_ph")}</option>
              {existingAlbums.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          ))}

        <p className="text-xs text-gray-600">
          {albumMode === "new" ? t("album_new_desc") : t("album_existing_desc")}
        </p>
      </div>
    </div>
  );
}

function LogEntryRow({ entry }: { entry: SyncLogEntry }) {
  const { logMessage } = useT();
  return (
    <div
      className={`flex items-start gap-2 p-2 rounded text-sm ${
        entry.status === "success" ? "bg-green-900/20 text-green-300" : "bg-red-900/20 text-red-300"
      }`}
    >
      {entry.status === "success" ? (
        <CheckCircle size={15} className="shrink-0 mt-0.5" />
      ) : (
        <XCircle size={15} className="shrink-0 mt-0.5" />
      )}
      <span>{logMessage(entry)}</span>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function ManualMatch() {
  const { t } = useT();
  const queryClient = useQueryClient();

  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: api.accounts.list,
    staleTime: 30_000,
  });

  const [selections, setSelections] = useState<PersonSelection[]>([
    { account_id: "", person_id: "" },
    { account_id: "", person_id: "" },
  ]);
  const [canonicalName, setCanonicalName] = useState("");
  const [albumMode, setAlbumMode] = useState<"new" | "existing">("new");
  const [albumName, setAlbumName] = useState("");
  const [ownerAccountId, setOwnerAccountId] = useState("");
  const [existingAlbumId, setExistingAlbumId] = useState("");
  const [result, setResult] = useState<SyncLogEntry[] | null>(null);

  // Default owner to first fully-selected row
  const firstFilledAccountId = selections.find((s) => s.account_id)?.account_id ?? "";
  const effectiveOwner = ownerAccountId || firstFilledAccountId;

  const mutation = useMutation({
    mutationFn: () =>
      api.sync.namesMulti({
        persons: selections.map((s) => ({ account_id: s.account_id, person_id: s.person_id })),
        canonical_name: canonicalName.trim(),
        owner_account_id: effectiveOwner || undefined,
        ...(albumMode === "new"
          ? { album_name: albumName.trim() || canonicalName.trim() }
          : { existing_album_id: existingAlbumId, album_name: albumName.trim() || undefined }),
      }),
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ["sync-log"] });
      queryClient.invalidateQueries({ queryKey: ["managed-albums"] });
    },
  });

  const addRow = () => setSelections((prev) => [...prev, { account_id: "", person_id: "" }]);
  const updateRow = (i: number, s: PersonSelection) =>
    setSelections((prev) => prev.map((x, idx) => (idx === i ? s : x)));
  const removeRow = (i: number) => setSelections((prev) => prev.filter((_, idx) => idx !== i));

  const albumReady =
    albumMode === "new"
      ? true // album_name falls back to canonicalName
      : !!existingAlbumId;

  const isValid =
    canonicalName.trim().length > 0 &&
    selections.length >= 2 &&
    selections.every((s) => s.account_id && s.person_id) &&
    albumReady;

  return (
    <div className="p-6 max-w-2xl space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-100">{t("manual_title")}</h2>
        <p className="text-sm text-gray-400 mt-1">{t("manual_subtitle")}</p>
      </div>

      {/* Hinweis */}
      <div className="flex items-start gap-2 text-xs text-amber-400 bg-amber-900/20 border border-amber-800 rounded px-3 py-2">
        <AlertTriangle size={13} className="shrink-0 mt-0.5" />
        <span>{t("manual_hint")}</span>
      </div>

      {/* Personen */}
      <div className="space-y-2">
        <label className="text-xs text-gray-400 uppercase tracking-wide">
          {t("manual_people")}
        </label>
        {selections.map((sel, i) => (
          <PersonRow
            key={i}
            accounts={accounts}
            usedAccountIds={selections
              .filter((_, idx) => idx !== i)
              .map((s) => s.account_id)
              .filter(Boolean)}
            selection={sel}
            index={i}
            onUpdate={(s) => updateRow(i, s)}
            onRemove={() => removeRow(i)}
            canRemove={selections.length > 2}
          />
        ))}
        <button
          onClick={addRow}
          className="flex items-center gap-2 text-sm text-immich-primary hover:text-blue-300 transition-colors mt-1"
        >
          <Plus size={15} />
          {t("add_person")}
        </button>
      </div>

      {/* Gemeinsamer Name */}
      <div className="space-y-1">
        <label className="text-xs text-gray-400 uppercase tracking-wide">{t("shared_name")}</label>
        <input
          type="text"
          placeholder={t("shared_name_ph")}
          value={canonicalName}
          onChange={(e) => {
            setCanonicalName(e.target.value);
            if (albumMode === "new" && !albumName) setAlbumName(e.target.value);
          }}
          className="w-full bg-immich-surface border border-immich-border rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-immich-primary"
        />
      </div>

      {/* Album */}
      <AlbumSection
        accounts={accounts}
        ownerAccountId={effectiveOwner}
        onOwnerChange={setOwnerAccountId}
        albumMode={albumMode}
        onAlbumModeChange={setAlbumMode}
        albumName={albumName}
        onAlbumNameChange={setAlbumName}
        existingAlbumId={existingAlbumId}
        onExistingAlbumIdChange={setExistingAlbumId}
      />

      {/* Submit */}
      <button
        onClick={() => {
          setResult(null);
          mutation.mutate();
        }}
        disabled={!isValid || mutation.isPending}
        className="flex items-center gap-2 px-5 py-2.5 bg-immich-primary text-white rounded-lg text-sm font-medium hover:bg-blue-600 disabled:opacity-40 transition-colors"
      >
        <Play size={15} />
        {mutation.isPending ? t("running") : t("run_btn")}
      </button>

      {mutation.isError && (
        <p className="text-sm text-red-400">
          {t("error_prefix")} {(mutation.error as Error).message}
        </p>
      )}

      {result && (
        <div className="space-y-1.5">
          <p className="text-xs text-gray-400 uppercase tracking-wide">{t("result")}</p>
          {result.map((e) => (
            <LogEntryRow key={e.id} entry={e} />
          ))}
        </div>
      )}
    </div>
  );
}
