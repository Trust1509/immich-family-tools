import { FormEvent, useEffect, useState } from "react";
import { LockKeyhole, Loader2 } from "lucide-react";
import { api } from "../api/client";
import { useT } from "../i18n";

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const { t } = useT();
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [token, setToken] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.auth
      .status()
      .then(() => setAuthenticated(true))
      .catch(() => setAuthenticated(false))
      .finally(() => setLoading(false));
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.auth.login(token);
      setToken("");
      setAuthenticated(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  if (loading && !authenticated) {
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
        <button className="btn-primary w-full" disabled={!token || loading}>
          {loading ? t("auth_checking") : t("auth_unlock")}
        </button>
      </form>
    </div>
  );
}
