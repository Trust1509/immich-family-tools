import { useState } from "react";
import { User } from "lucide-react";
import { PersonRef } from "../api/client";
import { api } from "../api/client";

interface Props {
  personA: PersonRef;
  personB: PersonRef;
  confidence: number;
  reasons: string[];
}

const REASON_LABELS: Record<string, string> = {
  name_similarity: "Namensähnlichkeit",
  embedding_similarity: "Gesichtserkennung",
  manual: "Manuell",
};

function Thumb({ person }: { person: PersonRef }) {
  const [err, setErr] = useState(false);
  const url = api.people.thumbnailUrl(person.account_id, person.person_id);

  return (
    <div className="flex flex-col items-center gap-2 flex-1">
      <div className="w-24 h-24 rounded-full overflow-hidden bg-immich-border flex items-center justify-center">
        {!err ? (
          <img
            src={url}
            alt={person.person_name ?? "?"}
            className="w-full h-full object-cover"
            onError={() => setErr(true)}
          />
        ) : (
          <User size={36} className="text-gray-600" />
        )}
      </div>
      <p className="text-sm font-medium text-center">
        {person.person_name || <span className="text-gray-500 italic">Unbekannt</span>}
      </p>
      <span className="badge" style={{ backgroundColor: person.account_color }}>
        {person.account_name}
      </span>
    </div>
  );
}

export default function FaceCompare({ personA, personB, confidence, reasons }: Props) {
  const pct = Math.round(confidence * 100);
  const color =
    pct >= 85 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-500" : "bg-red-500";

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <Thumb person={personA} />
        <div className="flex flex-col items-center gap-1 shrink-0">
          <span className="text-2xl font-bold" style={{ color: pct >= 85 ? "#10b981" : pct >= 50 ? "#f59e0b" : "#ef4444" }}>
            {pct}%
          </span>
          <span className="text-xs text-gray-500">Match</span>
        </div>
        <Thumb person={personB} />
      </div>

      {/* Confidence bar */}
      <div className="space-y-1">
        <div className="h-1.5 bg-immich-border rounded-full overflow-hidden">
          <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
        </div>
        <div className="flex flex-wrap gap-1">
          {reasons.map((r) => (
            <span key={r} className="text-xs bg-immich-border px-2 py-0.5 rounded-full text-gray-400">
              {REASON_LABELS[r] ?? r}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
