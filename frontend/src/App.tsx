import { useState } from "react";
import { Users, GitMerge, Grid, ScrollText, Activity, Disc, Shuffle, UserPlus, LogOut } from "lucide-react";
import { api } from "./api/client";
import { APP_VERSION } from "./version";
import AccountManager from "./components/AccountManager";
import PeopleGrid from "./components/PeopleGrid";
import MatchSuggestions from "./components/MatchSuggestions";
import SyncPanel from "./components/SyncPanel";
import AlbumsOverview from "./components/AlbumsOverview";
import ManualMatch from "./components/ManualMatch";
import ExtendMatch from "./components/ExtendMatch";
import { useT } from "./i18n";

type Page = "accounts" | "people" | "matches" | "manual" | "extend" | "albums" | "log";

export default function App() {
  const [page, setPage] = useState<Page>("accounts");
  const { t, lang, setLang } = useT();

  const NAV: { id: Page; label: string; icon: React.ReactNode }[] = [
    { id: "accounts", label: t("nav_accounts"), icon: <Users size={18} /> },
    { id: "people",   label: t("nav_people"),   icon: <Grid size={18} /> },
    { id: "matches",  label: t("nav_matches"),  icon: <GitMerge size={18} /> },
    { id: "manual",   label: t("nav_manual"),   icon: <Shuffle size={18} /> },
    { id: "extend",   label: t("nav_extend"),   icon: <UserPlus size={18} /> },
    { id: "albums",   label: t("nav_albums"),   icon: <Disc size={18} /> },
    { id: "log",      label: t("nav_log"),      icon: <ScrollText size={18} /> },
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
            onClick={async () => { await api.auth.logout(); window.location.reload(); }}
          >
            <LogOut size={12} /> Sperren
          </button>
          {/* Language toggle */}
          <div className="flex gap-1">
            {(["de", "en"] as const).map((l) => (
              <button
                key={l}
                onClick={() => setLang(l)}
                className={`flex-1 py-1 rounded text-xs font-medium transition-colors ${
                  lang === l
                    ? "bg-immich-primary text-white"
                    : "text-gray-500 hover:text-gray-300 bg-immich-bg"
                }`}
              >
                {l === "de" ? "🇩🇪 DE" : "🇬🇧 EN"}
              </button>
            ))}
          </div>
          <p className="text-xs text-gray-600 text-center">v{APP_VERSION}</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {page === "accounts" && <AccountManager />}
        {page === "people"   && <PeopleGrid />}
        {page === "matches"  && <MatchSuggestions />}
        {page === "manual"   && <ManualMatch />}
        {page === "extend"   && <ExtendMatch />}
        {page === "albums"   && <AlbumsOverview />}
        {page === "log"      && <SyncPanel />}
      </main>
    </div>
  );
}
