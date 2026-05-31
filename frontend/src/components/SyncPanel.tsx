import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, ScrollText, CheckCircle, XCircle, RotateCcw } from "lucide-react";
import { api, SyncLogEntry } from "../api/client";

function LogRow({ entry }: { entry: SyncLogEntry }) {
  const qc = useQueryClient();
  const undoMutation = useMutation({
    mutationFn: () => api.sync.undo(entry.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sync-log"] }),
  });

  const canUndo = entry.action === "sync_names" && entry.status === "success" && !!entry.undo_data;
  const ts = new Date(entry.timestamp).toLocaleString("de-AT");

  const ACTION_LABELS: Record<string, string> = {
    sync_names: "Namen sync",
    create_album: "Album erstellen",
    undo_sync_names: "Undo Namen",
  };

  return (
    <tr className="border-b border-immich-border hover:bg-immich-surface/50 transition-colors">
      <td className="py-3 px-4 text-xs text-gray-500 whitespace-nowrap">{ts}</td>
      <td className="py-3 px-4">
        <span className="text-xs bg-immich-border px-2 py-0.5 rounded-full text-gray-300">
          {ACTION_LABELS[entry.action] ?? entry.action}
        </span>
      </td>
      <td className="py-3 px-4 text-sm text-gray-300 max-w-xs truncate" title={entry.details}>
        {entry.details}
      </td>
      <td className="py-3 px-4">
        {entry.status === "success" ? (
          <CheckCircle size={14} className="text-emerald-400" />
        ) : (
          <span title={entry.error_message}><XCircle size={14} className="text-red-400" /></span>
        )}
      </td>
      <td className="py-3 px-4">
        {canUndo && (
          <button
            onClick={() => undoMutation.mutate()}
            disabled={undoMutation.isPending}
            className="text-xs text-gray-500 hover:text-gray-200 flex items-center gap-1 transition-colors"
            title="Rückgängig machen"
          >
            {undoMutation.isPending ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <RotateCcw size={12} />
            )}
            Undo
          </button>
        )}
      </td>
    </tr>
  );
}

export default function SyncPanel() {
  const { data: log = [], isLoading } = useQuery({
    queryKey: ["sync-log"],
    queryFn: api.sync.log,
    staleTime: 10_000,
    refetchInterval: 30_000,
  });

  const sorted = [...log].reverse(); // newest first

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-xl font-bold">Sync Log</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          {log.length} Einträge (neueste zuerst)
        </p>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 size={28} className="animate-spin text-gray-500" />
        </div>
      ) : sorted.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <ScrollText size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">Noch keine Sync-Aktionen durchgeführt.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-immich-border text-left text-xs text-gray-500">
                <th className="pb-2 px-4 font-medium">Zeitstempel</th>
                <th className="pb-2 px-4 font-medium">Aktion</th>
                <th className="pb-2 px-4 font-medium">Details</th>
                <th className="pb-2 px-4 font-medium">Status</th>
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
