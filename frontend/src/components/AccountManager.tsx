import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Trash2,
  CheckCircle,
  XCircle,
  Loader2,
  Eye,
  EyeOff,
  Wifi,
  Users,
  Pencil,
  X,
} from "lucide-react";
import { api, Account } from "../api/client";
import { useT } from "../i18n";

const PRESET_COLORS = [
  "#6366f1", // indigo
  "#10b981", // emerald
  "#f59e0b", // amber
  "#ef4444", // red
  "#8b5cf6", // violet
  "#06b6d4", // cyan
  "#ec4899", // pink
  "#f97316", // orange
  "#84cc16", // lime
  "#14b8a6", // teal
];

function ColorPicker({ value, onChange }: { value: string; onChange: (c: string) => void }) {
  const { t } = useT();
  return (
    <div className="flex items-center gap-2 flex-wrap">
      {PRESET_COLORS.map((c) => (
        <button
          key={c}
          type="button"
          onClick={() => onChange(c)}
          className={`w-6 h-6 rounded-full border-2 transition-all hover:scale-110 ${
            value.toLowerCase() === c.toLowerCase()
              ? "border-white scale-110 ring-2 ring-immich-primary"
              : "border-transparent"
          }`}
          style={{ backgroundColor: c }}
          title={c}
        />
      ))}
      <label
        className="w-6 h-6 rounded-full overflow-hidden cursor-pointer border-2 border-immich-border hover:border-gray-400 transition-colors relative"
        title={t("account_color_label")}
      >
        <input
          type="color"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        />
        <div className="w-full h-full" style={{ backgroundColor: value }} />
      </label>
    </div>
  );
}

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
    <span title={data.error}>
      <XCircle size={14} className="text-red-400" />
    </span>
  );
}

function EditAccountForm({ account, onClose }: { account: Account; onClose: () => void }) {
  const { t } = useT();
  const qc = useQueryClient();
  const [name, setName] = useState(account.name);
  const [url, setUrl] = useState(account.immich_url);
  const [key, setKey] = useState("");
  const [color, setColor] = useState(account.color);
  const [showKey, setShowKey] = useState(false);

  const mutation = useMutation({
    mutationFn: () =>
      api.accounts.update(account.id, {
        name: name !== account.name ? name : undefined,
        immich_url: url !== account.immich_url ? url : undefined,
        api_key: key.trim() ? key : undefined,
        color: color !== account.color ? color : undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["accounts"] });
      qc.invalidateQueries({ queryKey: ["account-status", account.id] });
      onClose();
    },
  });

  const hasChanges =
    name !== account.name || url !== account.immich_url || !!key.trim() || color !== account.color;

  return (
    <div className="card space-y-3 border-immich-primary">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-sm">{t("account_edit_title")}</h3>
        <button onClick={onClose} className="text-gray-500 hover:text-gray-300">
          <X size={14} />
        </button>
      </div>

      <div className="space-y-2">
        <input
          className="input"
          placeholder={t("account_name_ph")}
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
            placeholder={account.api_key_configured ? t("account_api_key_unchanged") : "API Key"}
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

        <div className="space-y-1.5">
          <label className="text-xs text-gray-500">{t("account_color_label")}</label>
          <ColorPicker value={color} onChange={setColor} />
        </div>
      </div>

      {mutation.error && (
        <p className="text-red-400 text-xs">{(mutation.error as Error).message}</p>
      )}

      <div className="flex gap-2">
        <button
          className="btn-primary flex items-center gap-2 text-sm"
          onClick={() => mutation.mutate()}
          disabled={!name || !url || !hasChanges || mutation.isPending}
        >
          {mutation.isPending ? <Loader2 size={14} className="animate-spin" /> : <Wifi size={14} />}
          {mutation.isPending ? t("account_saving") : t("account_save")}
        </button>
        <button className="btn-ghost text-sm" onClick={onClose}>
          {t("cancel")}
        </button>
      </div>
    </div>
  );
}

function AccountCard({ account, onDelete }: { account: Account; onDelete: () => void }) {
  const { t } = useT();
  const [editing, setEditing] = useState(false);

  const { data: status } = useQuery({
    queryKey: ["account-status", account.id],
    queryFn: () => api.accounts.status(account.id),
    staleTime: 60_000,
  });

  if (editing) {
    return <EditAccountForm account={account} onClose={() => setEditing(false)} />;
  }

  return (
    <div className="card flex items-center gap-4">
      {/* Color dot */}
      <div
        className="w-3 h-3 rounded-full shrink-0"
        style={{
          backgroundColor: account.color,
          boxShadow: `0 0 0 2px #1e2028, 0 0 0 4px ${account.color}`,
        }}
      />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium">{account.name}</span>
          {/* Account badge preview */}
          <span className="badge text-xs" style={{ backgroundColor: account.color }}>
            {account.name}
          </span>
          <StatusDot accountId={account.id} />
        </div>
        <p className="text-xs text-gray-500 truncate">{account.immich_url}</p>
        {status?.user_email && (
          <p className="text-xs text-gray-600 truncate">{status.user_email}</p>
        )}
        {status?.error && <p className="text-xs text-red-400 truncate">{status.error}</p>}
      </div>
      <div className="flex items-center gap-1 shrink-0">
        <button
          onClick={() => setEditing(true)}
          className="text-gray-600 hover:text-gray-300 transition-colors p-1.5 rounded"
          title={t("account_edit")}
        >
          <Pencil size={15} />
        </button>
        <button
          onClick={onDelete}
          className="text-gray-600 hover:text-red-400 transition-colors p-1.5 rounded"
          title={t("account_remove_tip")}
        >
          <Trash2 size={15} />
        </button>
      </div>
    </div>
  );
}

function AddAccountForm({ onClose }: { onClose: () => void }) {
  const { t } = useT();
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
      <h3 className="font-semibold text-sm">{t("account_add_title")}</h3>
      <div className="space-y-2">
        <input
          className="input"
          placeholder={t("account_name_ph")}
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
          {mutation.isPending ? t("account_test") : t("account_add_btn")}
        </button>
        <button className="btn-ghost text-sm" onClick={onClose}>
          {t("cancel")}
        </button>
      </div>
    </div>
  );
}

export default function AccountManager() {
  const { t } = useT();
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
          <h1 className="text-xl font-bold">{t("accounts_title")}</h1>
          <p className="text-sm text-gray-500 mt-0.5">{t("accounts_subtitle")}</p>
        </div>
        {!showForm && (
          <button
            className="btn-primary flex items-center gap-2 text-sm"
            onClick={() => setShowForm(true)}
          >
            <Plus size={16} />
            {t("account_add")}
          </button>
        )}
      </div>

      {showForm && (
        <div className="mb-4">
          <AddAccountForm onClose={() => setShowForm(false)} />
        </div>
      )}

      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 size={24} className="animate-spin text-gray-500" />
        </div>
      ) : accounts.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <Users size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">{t("account_empty")}</p>
          <p className="text-xs mt-1">{t("account_empty_hint")}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {accounts.map((acc) => (
            <AccountCard
              key={acc.id}
              account={acc}
              onDelete={() => {
                if (confirm(t("account_remove_confirm", acc.name))) deleteMutation.mutate(acc.id);
              }}
            />
          ))}
        </div>
      )}

      <div className="mt-8 card bg-immich-bg border-immich-border text-xs text-gray-500 space-y-1">
        <p className="font-medium text-gray-400">{t("account_api_hint")}</p>
        <p>{t("account_api_hint_body")}</p>
      </div>
    </div>
  );
}
