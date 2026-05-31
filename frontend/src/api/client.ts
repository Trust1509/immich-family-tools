const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const secret = localStorage.getItem("ift_secret") ?? "";
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(secret ? { Authorization: `Bearer ${secret}` } : {}),
      ...(options?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Types ──────────────────────────────────────────────────────────────────

export interface Account {
  id: string;
  name: string;
  immich_url: string;
  api_key: string;
  color: string;
  user_id?: string;
}

export interface AccountStatus {
  id: string;
  name: string;
  color: string;
  reachable: boolean;
  error?: string;
  user_name?: string;
  user_email?: string;
}

export interface Person {
  id: string;
  name: string | null;
  thumbnail_path: string | null;
  asset_count: number;
  is_hidden: boolean;
  account_id: string;
  account_name: string;
  account_color: string;
}

export interface PersonRef {
  person_id: string;
  person_name: string | null;
  account_id: string;
  account_name: string;
  account_color: string;
}

export interface Match {
  id: string;
  person_a: PersonRef;
  person_b: PersonRef;
  confidence: number;
  reasons: string[];
  status: "pending" | "confirmed" | "dismissed";
  has_album: boolean;
  names_synced: boolean;
}

export interface ManagedAlbum {
  id: string;
  match_id: string;
  album_id: string;
  album_name: string;
  owner_account_id: string;
  person_refs: { account_id: string; person_id: string; person_name: string; account_name: string; account_color: string }[];
  linked_match_ids: string[];
  created_at: string;
  last_synced_at?: string;
  total_assets: number;
}

export interface SyncLogEntry {
  id: string;
  timestamp: string;
  action: string;
  details: string;
  status: "success" | "error";
  error_message?: string;
  undo_data?: Record<string, unknown>;
}

export interface HealthStatus {
  status: string;
  accounts: number;
  thumbnail_cache_entries: number;
  thumbnail_cache_bytes: number;
}

// ── API ────────────────────────────────────────────────────────────────────

export const api = {
  accounts: {
    list: () => request<Account[]>("/accounts"),
    add: (data: { name: string; immich_url: string; api_key: string }) =>
      request<Account>("/accounts", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: { name?: string; immich_url?: string; api_key?: string; color?: string }) =>
      request<Account>(`/accounts/${id}`, { method: "PUT", body: JSON.stringify(data) }),
    remove: (id: string) => request<void>(`/accounts/${id}`, { method: "DELETE" }),
    status: (id: string) => request<AccountStatus>(`/accounts/${id}/status`),
    albums: (accountId: string) =>
      request<{ id: string; name: string }[]>(`/accounts/${accountId}/albums`),
  },

  people: {
    all: () => request<Person[]>("/people"),
    byAccount: (accountId: string) => request<Person[]>(`/people/${accountId}`),
    thumbnailUrl: (accountId: string, personId: string) =>
      `/api/people/${accountId}/${personId}/thumbnail`,
    count: (accountId: string, personId: string) =>
      request<{ count: number }>(`/people/${accountId}/${personId}/count`),
  },

  matches: {
    list: () => request<Match[]>("/matches"),
    refresh: () => request<Match[]>("/matches/refresh", { method: "POST" }),
    dismiss: (matchId: string) =>
      request<void>(`/matches/${matchId}/dismiss`, { method: "POST" }),
  },

  sync: {
    names: (matchId: string, name: string) =>
      request<SyncLogEntry[]>("/sync/names", {
        method: "POST",
        body: JSON.stringify({ match_id: matchId, name }),
      }),
    namesMulti: (body: {
      persons: { account_id: string; person_id: string }[];
      canonical_name: string;
      album_name?: string;
      owner_account_id?: string;
    }) =>
      request<SyncLogEntry[]>("/sync/names-multi", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    album: (body: {
      match_id: string;
      owner_account_id: string;
      album_name?: string;
      existing_album_id?: string;
    }) =>
      request<SyncLogEntry[]>("/sync/album", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    refreshAlbum: (managedAlbumId: string) =>
      request<SyncLogEntry[]>(`/sync/album/${managedAlbumId}/refresh`, { method: "POST" }),
    albums: () => request<ManagedAlbum[]>("/sync/albums"),
    deleteAlbum: (managedAlbumId: string) =>
      request<void>(`/sync/albums/${managedAlbumId}`, { method: "DELETE" }),
    undo: (logEntryId: string) =>
      request<SyncLogEntry>("/sync/undo", {
        method: "POST",
        body: JSON.stringify({ log_entry_id: logEntryId }),
      }),
    extend: (body: {
      managed_album_id: string;
      account_id: string;
      person_id: string;
      person_name?: string;
      canonical_name?: string;
    }) =>
      request<SyncLogEntry[]>("/sync/extend", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    log: () => request<SyncLogEntry[]>("/sync/log"),
  },

  health: () => request<HealthStatus>("/health"),
};
