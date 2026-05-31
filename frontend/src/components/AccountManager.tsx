import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, CheckCircle, XCircle, Loader2, Eye, EyeOff, Wifi, Users } from "lucide-react";
import { api, Account } from "../api/client";

function StatusDot({ accountId }: { accountId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["account-status", accountId],
    queryFn: () => api.accounts.status(accountId),
    staleTime: 60_000,
  });

  if (isLoading) return <Loader2 size={14} className="animate-spin text-gray-500" />;
  if (!data) return null;
  return data.reachable ? (
    <CheckCircle size={14} className="text-emerald-400" />
  ) : (
    <span title={data.error}><XCircle size={14} className="text-red-400" /></span>
  );
}

function AccountCard({ account, onDelete }: { account: Account; onDelete: () => void }) {
  const { data: status } = useQuery({
    queryKey: ["account-status", account.id],
    queryFn: () => api.accounts.status(account.id),
    staleTime: 60_000,
  });

  return (
    <div className="card flex items-center gap-4">
      <div
        className="w-3 h-3 rounded-full shrink-0"
        style={{ backgroundColor: account.color }}
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium">{account.name}</span>
          <StatusDot accountId={account.id} />
        </div>
        <p className="text-xs text-gray-500 truncate">{account.immich_url}</p>
        {status?.user_email && (
          <p className="text-xs text-gray-600 truncate">{status.user_email}</p>
        )}
        {status?.error && (
          <p className="text-xs text-red-400 truncate">{status.error}</p>
        )}
      </div>
      <button
        onClick={onDelete}
        className="text-gray-600 hover:text-red-400 transition-colors p-1 rounded"
        title="Account entfernen"
      >
        <Trash2 size={16} />
      </button>
    </div>
  );
}

function AddAccountForm({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("http://192.168.2.3:30041");
  const [key, setKey] = useState("");
  const [showKey, setShowKey] = useState(false);

  const qc = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => api.accounts.add({ name, immich_url: url, api_key: key }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["accounts"] });
      onClose();
    },
  });

  return (
    <div className="card space-y-3">
      <h3 className="font-semibold text-sm">Account hinzufügen</h3>
      <div className="space-y-2">
        <input
          className="input"
          placeholder="Name (z.B. Manu)"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className="input"
          placeholder="Immich URL"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <div className="relative">
          <input
            className="input pr-10"
            type={showKey ? "text" : "password"}
            placeholder="API Key"
            value={key}
            onChange={(e) => setKey(e.target.value)}
          />
          <button
            type="button"
            onClick={() => setShowKey((v) => !v)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
          >
            {showKey ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>
      </div>
      {mutation.error && (
        <p className="text-red-400 text-xs">{(mutation.error as Error).message}</p>
      )}
      <div className="flex gap-2">
        <button
          className="btn-primary flex items-center gap-2 text-sm"
          onClick={() => mutation.mutate()}
          disabled={!name || !url || !key || mutation.isPending}
        >
          {mutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Wifi size={14} />}
          {mutation.isPending ? "Teste Verbindung…" : "Hinzufügen"}
        </button>
        <button className="btn-ghost text-sm" onClick={onClose}>
          Abbrechen
        </button>
      </div>
    </div>
  );
}

export default function AccountManager() {
  const [showForm, setShowForm] = useState(false);
  const qc = useQueryClient();

  const { data: accounts = [], isLoading } = useQuery({
    queryKey: ["accounts"],
    queryFn: api.accounts.list,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.accounts.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });

  return (
    <div className="p-6 max-w-2xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold">Accounts</h1>
          <p className="text-sm text-gray-500 mt-0.5">Immich API Keys verwalten</p>
        </div>
        {!showForm && (
          <button className="btn-primary flex items-center gap-2 text-sm" onClick={() => setShowForm(true)}>
            <Plus size={16} />
            Account hinzufügen
          </button>
        )}
      </div>

      {showForm && <div className="mb-4"><AddAccountForm onClose={() => setShowForm(false)} /></div>}

      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 size={24} className="animate-spin text-gray-500" />
        </div>
      ) : accounts.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <Users size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">Noch keine Accounts konfiguriert.</p>
          <p className="text-xs mt-1">Füge deinen ersten Immich-Account hinzu.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {accounts.map((acc) => (
            <AccountCard
              key={acc.id}
              account={acc}
              onDelete={() => {
                if (confirm(`Account "${acc.name}" wirklich entfernen?`))
                  deleteMutation.mutate(acc.id);
              }}
            />
          ))}
        </div>
      )}

      <div className="mt-8 card bg-immich-bg border-immich-border text-xs text-gray-500 space-y-1">
        <p className="font-medium text-gray-400">Wo finde ich meinen API Key?</p>
        <p>Immich öffnen → Nutzermenü (oben rechts) → Account-Einstellungen → API Keys → Neuen Key erstellen</p>
      </div>
    </div>
  );
}
