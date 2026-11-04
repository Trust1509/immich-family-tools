import { useState } from "react";
import { useQuery, useQueries } from "@tanstack/react-query";
import { Loader2, Search, UserX, User, Link2, Images } from "lucide-react";
import { api, LinkedPerson, Person } from "../api/client";
import { LANG_LOCALES, useT } from "../i18n";

function PersonCard({ person }: { person: Person }) {
  const { t, lang } = useT();
  const thumbUrl = api.people.thumbnailUrl(person.account_id, person.id);
  const [imgError, setImgError] = useState(false);

  // Lazy count fallback: Immich API often returns assetCount=0 in list responses
  const { data: countData } = useQuery({
    queryKey: ["person-count", person.account_id, person.id],
    queryFn: () => api.people.count(person.account_id, person.id),
    enabled: person.asset_count === 0,
    staleTime: 5 * 60_000,
  });

  const photoCount = person.asset_count > 0 ? person.asset_count : (countData?.count ?? 0);

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
          {photoCount > 0 ? `${photoCount.toLocaleString(LANG_LOCALES[lang])} ${t("photos")}` : "–"}
        </p>
        <span className="badge mt-1 inline-block" style={{ backgroundColor: person.account_color }}>
          {person.account_name}
        </span>
      </div>
    </div>
  );
}

function personKey(accountId: string, personId: string): string {
  return `${accountId}:${personId}`;
}

export function linkedDisplayNames(link: LinkedPerson, people: Person[]): string[] {
  const peopleByKey = new Map(
    people.map((person) => [personKey(person.account_id, person.id), person])
  );
  return Array.from(
    new Set(
      link.person_refs
        .map(
          (ref) =>
            peopleByKey.get(personKey(ref.account_id, ref.person_id))?.name ?? ref.person_name
        )
        .filter((name): name is string => Boolean(name))
    )
  );
}

function LinkedPersonCard({ link, people }: { link: LinkedPerson; people: Person[] }) {
  const { t, lang } = useT();
  const peopleByKey = new Map(
    people.map((person) => [personKey(person.account_id, person.id), person])
  );
  const profiles = link.person_refs.map((ref) => ({
    ref,
    person: peopleByKey.get(personKey(ref.account_id, ref.person_id)),
  }));
  const countQueries = useQueries({
    queries: profiles.map(({ ref, person }) => ({
      queryKey: ["person-count", ref.account_id, ref.person_id],
      queryFn: () => api.people.count(ref.account_id, ref.person_id),
      enabled: !person || person.asset_count === 0,
      staleTime: 5 * 60_000,
    })),
  });
  const names = linkedDisplayNames(link, people);
  const totalPhotos = profiles.reduce((total, { person }, index) => {
    const count =
      person?.asset_count && person.asset_count > 0
        ? person.asset_count
        : (countQueries[index]?.data?.count ?? 0);
    return total + count;
  }, 0);
  const countsLoading = countQueries.some((query) => query.isFetching);

  return (
    <article className="card p-3 flex flex-col items-center gap-2 text-center border-violet-900/60 hover:border-violet-500 transition-colors">
      <div className="h-20 flex items-center justify-center -space-x-5" aria-hidden="true">
        {profiles.slice(0, 3).map(({ ref, person }) => (
          <div
            key={personKey(ref.account_id, ref.person_id)}
            className="w-16 h-16 rounded-full overflow-hidden bg-immich-border border-2 border-immich-surface shrink-0"
          >
            <img
              src={api.people.thumbnailUrl(ref.account_id, ref.person_id)}
              alt=""
              className="w-full h-full object-cover"
              onError={(event) => {
                event.currentTarget.style.visibility = "hidden";
              }}
            />
          </div>
        ))}
        {profiles.length > 3 && (
          <span className="w-10 h-10 rounded-full border-2 border-immich-surface bg-violet-900 flex items-center justify-center text-xs font-semibold text-violet-200 shrink-0">
            +{profiles.length - 3}
          </span>
        )}
      </div>

      <div className="w-full min-w-0">
        <div className="flex items-center justify-center gap-1.5 min-w-0">
          <Link2 size={13} className="text-violet-300 shrink-0" />
          <h3 className="text-sm font-medium truncate">
            {names.length > 0 ? names.join(" · ") : link.display_name}
          </h3>
        </div>
        {names.length > 1 && (
          <p className="text-xs text-gray-500 truncate">{t("linked_different_names")}</p>
        )}
        <p className="text-xs text-gray-500 flex items-center justify-center gap-1 mt-1">
          <Images size={12} />
          {t(
            "linked_photo_total",
            countsLoading ? "…" : totalPhotos.toLocaleString(LANG_LOCALES[lang])
          )}
        </p>
        <div className="flex flex-wrap justify-center gap-1 mt-1.5 max-h-12 overflow-hidden">
          {profiles.map(({ ref, person }) => (
            <span
              key={personKey(ref.account_id, ref.person_id)}
              className="badge text-xs inline-block"
              style={{ backgroundColor: person?.account_color || ref.account_color }}
            >
              {person?.account_name || ref.account_name}
            </span>
          ))}
        </div>
      </div>
    </article>
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
  const totalCount = accounts.length;
  const anyLoading = loadingAccounts || accountQueries.some((q) => q.isFetching);

  // Merge all loaded people so far
  const people: Person[] = accountQueries.flatMap((q) => q.data ?? []);

  const filtered = people.filter((p) => {
    if (filter === "named" && !p.name) return false;
    if (filter === "unnamed" && p.name) return false;
    if (search && !(p.name ?? "").toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const namedCount = people.filter((p) => p.name).length;
  const unnamedCount = people.filter((p) => !p.name).length;
  const { data: linkedPeople = [] } = useQuery({
    queryKey: ["person-links"],
    queryFn: api.personLinks.list,
    staleTime: 30_000,
  });
  const filteredLinkedPeople = linkedPeople.filter((link) => {
    const names = linkedDisplayNames(link, people);
    if (filter === "named" && names.length === 0) return false;
    if (filter === "unnamed" && names.length > 0) return false;
    if (search) {
      const query = search.toLowerCase();
      if (
        !link.display_name.toLowerCase().includes(query) &&
        !names.some((name) => name.toLowerCase().includes(query))
      )
        return false;
    }
    return true;
  });

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
            {f === "all"
              ? t("filter_all")
              : f === "named"
                ? t("filter_named")
                : t("filter_unnamed")}
          </button>
        ))}
      </div>

      {filteredLinkedPeople.length > 0 && (
        <section className="mb-6 space-y-3">
          <div>
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <Link2 size={15} className="text-violet-300" />
              {t("linked_people_title")}
            </h2>
            <p className="text-xs text-gray-500 mt-1">
              {t("linked_people_subtitle", filteredLinkedPeople.length)}
            </p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
            {filteredLinkedPeople.map((link) => (
              <LinkedPersonCard key={link.id} link={link} people={people} />
            ))}
          </div>
        </section>
      )}

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
          {filtered.map((p) => (
            <PersonCard key={`${p.account_id}:${p.id}`} person={p} />
          ))}
        </div>
      )}
    </div>
  );
}
