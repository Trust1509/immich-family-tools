import { FormEvent, useEffect, useState } from "react";
import { LockKeyhole, Loader2 } from "lucide-react";
import { ApiError, api } from "../api/client";
import { useT } from "../i18n";

/** Maps a failed login attempt to a translated, language-aware message.
 *  Exported (and pure — takes `t` as a parameter instead of calling
 *  `useT()` itself) so a test can assert the mapping without rendering the
 *  component: the backend's `detail` text is always English
 *  ("Invalid token", "Too many login attempts…"), so showing it verbatim
 *  left the one error state of an otherwise trilingual screen permanently
 *  English (Fund 1). Statuses the backend doesn't specifically call out
 *  fall back to the raw `detail`/message text — better an English string
 *  than no information at all. */
export function authErrorMessage(err: unknown, t: ReturnType<typeof useT>["t"]): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return t("auth_error_invalid");
    if (err.status === 429) return t("auth_error_rate_limited");
  }
  return err instanceof Error ? err.message : String(err);
}

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const { t } = useT();
  // Two separate flags, not one: `checkingAuth` covers the one-time status
  // probe on mount, `submitting` covers the login form's own request. A
  // single shared `loading` used to gate the whole form behind a full-page
  // spinner ("loading && !authenticated") — which also fired while
  // submitting the form, since `authenticated` is still false at that
  // point. That made the button's own "auth_checking" text unreachable
  // (Fund 7): the full-page spinner branch always won first.
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [token, setToken] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.auth
      .status()
      .then(() => setAuthenticated(true))
      .catch(() => setAuthenticated(false))
      .finally(() => setCheckingAuth(false));
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await api.auth.login(token);
      setToken("");
      setAuthenticated(true);
    } catch (err) {
      setError(authErrorMessage(err, t));
    } finally {
      setSubmitting(false);
    }
  };

  if (checkingAuth) {
    return (
      <div className="h-screen grid place-items-center">
        <Loader2 className="animate-spin" />
      </div>
    );
  }
  if (authenticated) return <>{children}</>;

  return (
    <div className="h-screen grid place-items-center p-6">
      <form onSubmit={submit} className="card w-full max-w-sm space-y-4">
        <div className="flex items-center gap-3">
          <LockKeyhole className="text-immich-primary" />
          <div>
            <h1 className="font-semibold">{t("auth_title")}</h1>
            <p className="text-xs text-gray-500">{t("auth_subtitle")}</p>
          </div>
        </div>
        <input
          className="input"
          type="password"
          autoFocus
          autoComplete="current-password"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          placeholder={t("auth_token_ph")}
        />
        {error && <p className="text-xs text-red-400">{error}</p>}
        <button className="btn-primary w-full" disabled={!token || submitting}>
          {submitting ? t("auth_checking") : t("auth_unlock")}
        </button>
      </form>
    </div>
  );
}
