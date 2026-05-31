import { useState } from "react";
import { useQuery, useQueries } from "@tanstack/react-query";
import { Loader2, Search, UserX, User } from "lucide-react";
import { api, Person } from "../api/client";
import { useT } from "../i18n";

function PersonCard({ person }: { person: Person }) {
  const { t } = useT();
  const thumbUrl = api.people.thumbnailUrl(person.account_id, person.id);
  const [imgError, setImgError] = useState(false);

  return (
    <div className="card p-3 flex flex-col items-center gap-2 text-center group hover:border-immich-primary transition-colors">
      <div className="w-20 h-20 rounded-full overflow-hidden bg-immich-border flex items-center justify-center shrink-0">
        {!imgError ? (
          <img
            src={thumbUrl}
            alt={person.name ?? t("unknown")}
            className="w-full h-full object-cover"
            onError={() => setImgError(true)}
          />
        ) : (
          <User size={32} className="text-gray-600" />
        )}
      </div>
      <div className="w-full min-w-0">
        <p className="text-sm font-medium truncate">
          {person.name || <span className="text-gray-500 italic">{t("unknown")}</span>}
        </p>
        <p className="text-xs text-gray-500">
          {person.asset_count > 0
            ? `${person.asset_count.toLocaleString("de-AT")} ${t("photos")}`
            : "–"}
        </p>
        <span className="badge mt-1 inline-block" style={{ backgroundColor: person.account_color }}>
          {person.account_name}
        </span>
      </div>
    </div>
  );
}

type Filter = "all" | "named" | "unnamed";

export default function PeopleGrid() {
  const { t } = useT();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");

  // Step 1: load accounts
  const { data: accounts = [], isLoading: loadingAccounts } = useQuery({
    queryKey: ["accounts"],
    queryFn: api.accounts.list,
    staleTime: 60_000,
  });

  // Step 2: one query per account — results arrive independently
  const accountQueries = useQueries({
    queries: accounts.map((acc) => ({
      queryKey: ["people", acc.id],
      queryFn: () => api.people.byAccount(acc.id),
      staleTime: 60_000,
    })),
  });

  const loadedCount = accountQueries.filter((q) => q.isSuccess).length;
  const totalCount  = accounts.length;
  const anyLoading  = loadingAccounts || accountQueries.some((q) => q.isFetching);

  // Merge all loaded people so far
  const people: Person[] = accountQueries.flatMap((q) => q.data ?? []);

  const filtered = people.filter((p) => {
    if (filter === "named"   && !p.name) return false;
    if (filter === "unnamed" &&  p.name) return false;
    if (search && !(p.name ?? "").toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const namedCount   = people.filter((p) =>  p.name).length;
  const unnamedCount = people.filter((p) => !p.name).length;

  return (
    <div className="p-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-xl font-bold">{t("people_title")}</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {t("people_subtitle", people.length, namedCount, unnamedCount)}
          </p>
        </div>

        {/* Progress indicator while loading */}
        {anyLoading && totalCount > 0 && (
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <Loader2 size={14} className="animate-spin" />
            <span>
              {loadedCount}/{totalCount} {t("nav_accounts")}
            </span>
            {/* mini progress bar */}
            <div className="w-24 h-1.5 bg-immich-border rounded-full overflow-hidden">
              <div
                className="h-full bg-immich-primary rounded-full transition-all duration-300"
                style={{ width: `${totalCount > 0 ? (loadedCount / totalCount) * 100 : 0}%` }}
              />
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            className="input pl-8 w-48 text-sm"
            placeholder={t("search_name")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        {(["all", "named", "unnamed"] as Filter[]).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filter === f
                ? "bg-immich-primary text-white"
                : "bg-immich-surface border border-immich-border text-gray-400 hover:text-gray-100"
            }`}
          >
            {f === "all" ? t("filter_all") : f === "named" ? t("filter_named") : t("filter_unnamed")}
          </button>
        ))}
      </div>

      {/* Show spinner only if nothing loaded yet */}
      {loadingAccounts || (anyLoading && people.length === 0) ? (
        <div className="flex justify-center py-16">
          <Loader2 size={28} className="animate-spin text-gray-500" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <UserX size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">{t("people_empty")}</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
          {filtered.map((p) => <PersonCard key={`${p.account_id}:${p.id}`} person={p} />)}
        </div>
      )}
    </div>
  );
}
