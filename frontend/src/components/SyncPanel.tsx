import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, ScrollText, CheckCircle, XCircle, RotateCcw, Trash2 } from "lucide-react";
import { api, SyncLogEntry } from "../api/client";
import { formatDate, LANG_LOCALES, useT } from "../i18n";

function LogRow({ entry }: { entry: SyncLogEntry }) {
  const { t, lang, logMessage } = useT();
  const qc = useQueryClient();
  const undoMutation = useMutation({
    mutationFn: () => api.sync.undo(entry.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sync-log"] }),
  });

  const canUndo =
    entry.action === "sync_names" &&
    entry.status === "success" &&
    !!entry.undo_data &&
    !entry.undone_at;
  const ts = formatDate(entry.timestamp, LANG_LOCALES[lang]);

  const actionLabel: Record<string, string> = {
    sync_names: t("action_sync_names"),
    create_album: t("action_create_album"),
    undo_sync_names: t("action_undo_names"),
    share_album: t("action_share_album"),
    album_add_assets: t("action_add_assets"),
    refresh_album: t("action_refresh"),
    link_album: t("action_link"),
  };

  return (
    <tr className="border-b border-immich-border hover:bg-immich-surface/50 transition-colors">
      <td className="py-3 px-4 text-xs text-gray-500 whitespace-nowrap">{ts}</td>
      <td className="py-3 px-4">
        <span className="text-xs bg-immich-border px-2 py-0.5 rounded-full text-gray-300">
          {actionLabel[entry.action] ?? entry.action}
        </span>
      </td>
      <td className="py-3 px-4 text-sm text-gray-300 max-w-xs truncate" title={logMessage(entry)}>
        {logMessage(entry)}
      </td>
      <td className="py-3 px-4">
        {entry.status === "success" ? (
          <CheckCircle size={14} className="text-emerald-400" />
        ) : (
          <span title={entry.error_message}>
            <XCircle size={14} className="text-red-400" />
          </span>
        )}
      </td>
      <td className="py-3 px-4">
        {canUndo && (
          <button
            onClick={() => undoMutation.mutate()}
            disabled={undoMutation.isPending}
            className="text-xs text-gray-500 hover:text-gray-200 flex items-center gap-1 transition-colors"
            title={t("undo_tip")}
          >
            {undoMutation.isPending ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <RotateCcw size={12} />
            )}
            {t("undo")}
          </button>
        )}
      </td>
    </tr>
  );
}

export default function SyncPanel() {
  const { t } = useT();
  const { data: log = [], isLoading } = useQuery({
    queryKey: ["sync-log"],
    queryFn: api.sync.log,
    staleTime: 10_000,
    refetchInterval: 30_000,
  });

  const sorted = [...log].reverse();
  const qc = useQueryClient();
  const clearMutation = useMutation({
    mutationFn: api.sync.clearLog,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sync-log"] }),
  });

  return (
    <div className="p-6">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold">{t("nav_log")}</h1>
          <p className="text-sm text-gray-500 mt-0.5">{t("log_subtitle", log.length)}</p>
        </div>
        {log.length > 0 && (
          <button
            className="btn-ghost text-xs text-red-400 flex items-center gap-1"
            onClick={() => confirm(t("log_clear_confirm")) && clearMutation.mutate()}
          >
            <Trash2 size={13} /> {t("log_clear")}
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 size={28} className="animate-spin text-gray-500" />
        </div>
      ) : sorted.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <ScrollText size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">{t("log_empty")}</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-immich-border text-left text-xs text-gray-500">
                <th className="pb-2 px-4 font-medium">{t("timestamp")}</th>
                <th className="pb-2 px-4 font-medium">{t("action")}</th>
                <th className="pb-2 px-4 font-medium">{t("details")}</th>
                <th className="pb-2 px-4 font-medium">{t("status")}</th>
                <th className="pb-2 px-4 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((entry) => (
                <LogRow key={entry.id} entry={entry} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
