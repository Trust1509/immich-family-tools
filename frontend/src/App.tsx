import { useState } from "react";
import { Users, GitMerge, Grid, ScrollText, Activity, Disc } from "lucide-react";
import AccountManager from "./components/AccountManager";
import PeopleGrid from "./components/PeopleGrid";
import MatchSuggestions from "./components/MatchSuggestions";
import SyncPanel from "./components/SyncPanel";
import AlbumsOverview from "./components/AlbumsOverview";

type Page = "accounts" | "people" | "matches" | "albums" | "log";

const NAV: { id: Page; label: string; icon: React.ReactNode }[] = [
  { id: "accounts", label: "Accounts", icon: <Users size={18} /> },
  { id: "people", label: "Personen", icon: <Grid size={18} /> },
  { id: "matches", label: "Match-Vorschläge", icon: <GitMerge size={18} /> },
  { id: "albums", label: "Alben", icon: <Disc size={18} /> },
  { id: "log", label: "Sync Log", icon: <ScrollText size={18} /> },
];

export default function App() {
  const [page, setPage] = useState<Page>("accounts");

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 bg-immich-surface border-r border-immich-border flex flex-col">
        <div className="p-4 border-b border-immich-border">
          <div className="flex items-center gap-2">
            <Activity size={20} className="text-immich-primary" />
            <span className="font-semibold text-sm">Family Tools</span>
          </div>
          <p className="text-xs text-gray-500 mt-0.5">Immich Multi-Account</p>
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
        <div className="p-3 border-t border-immich-border">
          <p className="text-xs text-gray-600 text-center">v1.0.0</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        {page === "accounts" && <AccountManager />}
        {page === "people" && <PeopleGrid />}
        {page === "matches" && <MatchSuggestions />}
        {page === "albums" && <AlbumsOverview />}
        {page === "log" && <SyncPanel />}
      </main>
    </div>
  );
}
