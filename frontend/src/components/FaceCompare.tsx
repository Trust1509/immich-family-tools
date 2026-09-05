import { useState } from "react";
import { User } from "lucide-react";
import { PersonRef } from "../api/client";
import { api } from "../api/client";
import { useT } from "../i18n";

interface Props {
  personA: PersonRef;
  personB: PersonRef;
  confidence: number;
  reasons: string[];
}

// `REASON_LABELS` used to be a plain string lookup at module scope, which
// can't call `t()` — there's no LanguageProvider up there. Resolving the
// backend reason code to a label now happens inside the component, where
// `t` is available. A `switch` (not an object lookup) keeps this typesafe:
// each case passes a literal key straight to `t()`, so a typo or a removed
// key is a compile error instead of a silent `undefined`.
function reasonLabel(t: ReturnType<typeof useT>["t"], reason: string): string {
  switch (reason) {
    case "name_similarity":
      return t("reason_name_similarity");
    case "embedding_similarity":
      return t("reason_embedding_similarity");
    case "manual":
      return t("reason_manual");
    default:
      return reason;
  }
}

function Thumb({ person }: { person: PersonRef }) {
  const { t } = useT();
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
        {person.person_name || <span className="text-gray-500 italic">{t("unknown")}</span>}
      </p>
      <span className="badge" style={{ backgroundColor: person.account_color }}>
        {person.account_name}
      </span>
    </div>
  );
}

export default function FaceCompare({ personA, personB, confidence, reasons }: Props) {
  const { t } = useT();
  const pct = Math.round(confidence * 100);
  const color = pct >= 85 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-500" : "bg-red-500";

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <Thumb person={personA} />
        <div className="flex flex-col items-center gap-1 shrink-0">
          <span
            className="text-2xl font-bold"
            style={{ color: pct >= 85 ? "#10b981" : pct >= 50 ? "#f59e0b" : "#ef4444" }}
          >
            {pct}%
          </span>
          <span className="text-xs text-gray-500">{t("match_label")}</span>
        </div>
        <Thumb person={personB} />
      </div>

      {/* Confidence bar */}
      <div className="space-y-1">
        <div className="h-1.5 bg-immich-border rounded-full overflow-hidden">
          <div
            className={`h-full ${color} rounded-full transition-all`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="flex flex-wrap gap-1">
          {reasons.map((r) => (
            <span
              key={r}
              className="text-xs bg-immich-border px-2 py-0.5 rounded-full text-gray-400"
            >
              {reasonLabel(t, r)}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
