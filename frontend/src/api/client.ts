const BASE = "/api";

/** Thrown by `request()` for any non-OK response. Carries the HTTP status
 *  code alongside the message — plain `Error` didn't, so a caller (e.g.
 *  `AuthGate`) could only ever display the raw `detail` text and had no way
 *  to branch on "this was a 401" vs. "this was a 429" to show a translated,
 *  language-aware message instead of whatever English string the backend
 *  happened to send. */
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Extracts a human-readable message from a failed response's body, without
 *  ever assuming the body is the object shape it usually is. The prior
 *  version read `err.detail` straight off whatever `res.json()` resolved
 *  to — but a JSON body of `null` (the backend legitimately sends this for
 *  some error responses) makes that a `TypeError` on property access,
 *  thrown *before* `ApiError` is ever constructed, so the caller's status
 *  code branch (`AuthGate`'s 401/429 mapping) never runs. And `{}`, an
 *  empty `detail`, or a non-string `detail` (e.g. a validation error's
 *  `42`) all produced a falsy-but-not-nullish message that `?? res.statusText`
 *  doesn't catch either — which `AuthGate` then renders as nothing at all
 *  (Fund 1b). This treats the body as `unknown`, only trusts a non-empty
 *  string `detail`, and falls through to `statusText` and finally the
 *  status code itself so the result is never empty. */
async function extractErrorMessage(res: Response): Promise<string> {
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    body = undefined;
  }
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.length > 0) return detail;
  }
  if (res.statusText) return res.statusText;
  return `HTTP ${res.status}`;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
  });
  if (!res.ok) {
    throw new ApiError(await extractErrorMessage(res), res.status);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Types ──────────────────────────────────────────────────────────────────

export interface Account {
  id: string;
  name: string;
  immich_url: string;
  api_key_configured: boolean;
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
  person_refs: {
    account_id: string;
    person_id: string;
    person_name: string;
    account_name: string;
    account_color: string;
  }[];
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
  undone_at?: string;
  message_key?: string;
  message_params?: Record<string, string | number>;
}

export interface HealthStatus {
  status: string;
  accounts: number;
  thumbnail_cache_entries: number;
  thumbnail_cache_bytes: number;
}

// ── API ────────────────────────────────────────────────────────────────────

export const api = {
  auth: {
    status: () => request<{ authenticated: boolean }>("/auth/status"),
    login: (token: string) =>
      request<{ authenticated: boolean }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ token }),
      }),
    logout: () => request<void>("/auth/logout", { method: "POST" }),
  },
  accounts: {
    list: () => request<Account[]>("/accounts"),
    add: (data: { name: string; immich_url: string; api_key: string }) =>
      request<Account>("/accounts", { method: "POST", body: JSON.stringify(data) }),
    update: (
      id: string,
      data: { name?: string; immich_url?: string; api_key?: string; color?: string }
    ) => request<Account>(`/accounts/${id}`, { method: "PUT", body: JSON.stringify(data) }),
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
    dismiss: (matchId: string) => request<void>(`/matches/${matchId}/dismiss`, { method: "POST" }),
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
      existing_album_id?: string;
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
    clearLog: () => request<void>("/sync/log", { method: "DELETE" }),
  },

  autoSync: {
    get: () => request<{ enabled: boolean; time: string }>("/sync/autosync-config"),
    set: (enabled: boolean, time: string) =>
      request<{ enabled: boolean; time: string }>("/sync/autosync-config", {
        method: "PUT",
        body: JSON.stringify({ enabled, time }),
      }),
  },

  health: () => request<HealthStatus>("/health"),
};
