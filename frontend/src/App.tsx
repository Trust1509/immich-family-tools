import { useState } from "react";
import {
  Users,
  GitMerge,
  Grid,
  ScrollText,
  Activity,
  Disc,
  Shuffle,
  UserPlus,
  LogOut,
  Coffee,
} from "lucide-react";
import { api } from "./api/client";
import { APP_VERSION } from "./version";
import AccountManager from "./components/AccountManager";
import PeopleGrid from "./components/PeopleGrid";
import MatchSuggestions from "./components/MatchSuggestions";
import SyncPanel from "./components/SyncPanel";
import AlbumsOverview from "./components/AlbumsOverview";
import ManualMatch from "./components/ManualMatch";
import ExtendMatch from "./components/ExtendMatch";
import { useT, LANG_LABELS, type Lang } from "./i18n";

type Page = "accounts" | "people" | "matches" | "manual" | "extend" | "albums" | "log";

export default function App() {
  const [page, setPage] = useState<Page>("accounts");
  const { t, lang, setLang } = useT();

  const NAV: { id: Page; label: string; icon: React.ReactNode }[] = [
    { id: "accounts", label: t("nav_accounts"), icon: <Users size={18} /> },
    { id: "people", label: t("nav_people"), icon: <Grid size={18} /> },
    { id: "matches", label: t("nav_matches"), icon: <GitMerge size={18} /> },
    { id: "manual", label: t("nav_manual"), icon: <Shuffle size={18} /> },
    { id: "extend", label: t("nav_extend"), icon: <UserPlus size={18} /> },
    { id: "albums", label: t("nav_albums"), icon: <Disc size={18} /> },
    { id: "log", label: t("nav_log"), icon: <ScrollText size={18} /> },
  ];

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 bg-immich-surface border-r border-immich-border flex flex-col">
        <div className="p-4 border-b border-immich-border">
          <div className="flex items-center gap-2">
            <Activity size={20} className="text-immich-primary" />
            <span className="font-semibold text-sm">Family Tools</span>
          </div>
          <p className="text-xs text-gray-500 mt-0.5">{t("app_subtitle")}</p>
        </div>
        <nav className="flex-1 p-2 space-y-0.5">
          {NAV.map((item) => (
            <button
              key={item.id}
              onClick={() => setPage(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                page === item.id
                  ? "bg-immich-primary text-white"
                  : "text-gray-400 hover:text-gray-100 hover:bg-immich-border"
              }`}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </nav>
        <div className="p-3 border-t border-immich-border space-y-2">
          <button
            className="w-full text-xs text-gray-500 hover:text-gray-200 flex items-center justify-center gap-1"
            onClick={async () => {
              await api.auth.logout();
              window.location.reload();
            }}
          >
            <LogOut size={12} /> {t("lock_button")}
          </button>
          {/* Language toggle: two columns, not one row.
              Measured in the real sidebar (w-56 → 200px inner, gap-1), with
              the actual rendered label widths — "🇧🇷 PT-BR" is the longest at
              43.8px:

                languages     one row (flex-1)            grid-cols-2
                4             47px each                   98px each, 2 rows
                5             35 / 35 / 43.8px, unequal   98px each, 3 rows
                6             at content width            98px each, 3 rows
                8             OVERFLOWS by 48px           98px each, 4 rows

              The row does not clip before eight languages — `flex-1` carries
              `min-width: auto`, so a button never shrinks below its own text.
              It degrades differently: from five languages on, the buttons stop
              being equal and the padding around the shorter labels collapses
              to a few pixels, while PT-BR keeps its full width. It looks like
              a mistake before it becomes one.
              The grid keeps every button at 98px at any count and spends
              vertical space instead — 53px at four languages, 82px at six.
              That is the right trade here: contributors add languages faster
              than we plan for them (pt-BR and es-ES arrived within a week),
              and the sidebar has the height to spare. */}
          <div className="grid grid-cols-2 gap-1">
            {(Object.keys(LANG_LABELS) as Lang[]).map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                aria-current={lang === l ? "true" : undefined}
                className={`min-w-0 truncate py-1 rounded text-[11px] font-medium transition-colors ${
                  lang === l
                    ? "bg-immich-primary text-white"
                    : "text-gray-500 hover:text-gray-300 bg-immich-bg"
                }`}
              >
                {LANG_LABELS[l]}
              </button>
            ))}
          </div>
          <a
            href="https://buymeacoffee.com/trust1509"
            target="_blank"
            rel="noopener noreferrer"
            className="w-full text-xs text-gray-500 hover:text-amber-300 flex items-center justify-center gap-1 transition-colors"
          >
            <Coffee size={12} /> {t("support_project")}
          </a>
          <p className="text-xs text-gray-600 text-center">v{APP_VERSION}</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {page === "accounts" && <AccountManager />}
        {page === "people" && <PeopleGrid />}
        {page === "matches" && <MatchSuggestions />}
        {page === "manual" && <ManualMatch />}
        {page === "extend" && <ExtendMatch />}
        {page === "albums" && <AlbumsOverview />}
        {page === "log" && <SyncPanel />}
      </main>
    </div>
  );
}
