import React, { createContext, useContext, useState } from "react";

export type Lang = "de" | "en";

// ── Translations ───────────────────────────────────────────────────────────

const translations = {
  // ── App / Navigation ──────────────────────────────────────────────────
  nav_accounts:       { de: "Accounts",          en: "Accounts" },
  nav_people:         { de: "Personen",           en: "People" },
  nav_matches:        { de: "Match-Vorschläge",   en: "Match Suggestions" },
  nav_manual:         { de: "Manuell matchen",    en: "Manual Match" },
  nav_albums:         { de: "Alben",              en: "Albums" },
  nav_log:            { de: "Sync Log",           en: "Sync Log" },
  nav_extend:         { de: "Match erweitern",    en: "Extend Match" },
  app_subtitle:       { de: "Immich Multi-Account", en: "Immich Multi-Account" },

  // ── Common ────────────────────────────────────────────────────────────
  cancel:             { de: "Abbrechen",          en: "Cancel" },
  save:               { de: "Speichern",          en: "Save" },
  unknown:            { de: "Unbekannt",          en: "Unknown" },
  loading:            { de: "Lade…",              en: "Loading…" },
  photos:             { de: "Fotos",              en: "photos" },
  owner:              { de: "Besitzer",           en: "Owner" },
  name:               { de: "Name",               en: "Name" },
  album:              { de: "Album",              en: "Album" },
  error_prefix:       { de: "Fehler:",            en: "Error:" },
  result:             { de: "Ergebnis",           en: "Result" },
  undo:               { de: "Rückgängig",         en: "Undo" },
  status:             { de: "Status",             en: "Status" },
  details:            { de: "Details",            en: "Details" },
  action:             { de: "Aktion",             en: "Action" },
  timestamp:          { de: "Zeitstempel",        en: "Timestamp" },
  search_name:        { de: "Name suchen…",       en: "Search name…" },
  processing:         { de: "Wird verarbeitet…",  en: "Processing…" },
  syncing:            { de: "Synchronisiert…",    en: "Syncing…" },
  running:            { de: "Wird ausgeführt…",   en: "Running…" },
  min:                { de: "min.",               en: "min." },

  // ── AccountManager ────────────────────────────────────────────────────
  accounts_title:       { de: "Accounts",                       en: "Accounts" },
  accounts_subtitle:    { de: "Immich API Keys verwalten",      en: "Manage Immich API Keys" },
  account_add:          { de: "Account hinzufügen",             en: "Add Account" },
  account_add_title:    { de: "Account hinzufügen",             en: "Add Account" },
  account_remove_tip:   { de: "Account entfernen",              en: "Remove account" },
  account_remove_confirm: { de: (name: string) => `Account "${name}" wirklich entfernen?`, en: (name: string) => `Really remove account "${name}"?` },
  account_empty:        { de: "Noch keine Accounts konfiguriert.", en: "No accounts configured yet." },
  account_empty_hint:   { de: "Füge deinen ersten Immich-Account hinzu.", en: "Add your first Immich account." },
  account_name_ph:      { de: "Name (z.B. Manu)",              en: "Name (e.g. Manu)" },
  account_test:         { de: "Teste Verbindung…",             en: "Testing connection…" },
  account_add_btn:      { de: "Hinzufügen",                    en: "Add" },
  account_edit:         { de: "Bearbeiten",                    en: "Edit" },
  account_edit_title:   { de: "Account bearbeiten",           en: "Edit Account" },
  account_save:         { de: "Speichern",                    en: "Save" },
  account_saving:       { de: "Wird gespeichert…",            en: "Saving…" },
  account_color_label:  { de: "Farbe",                        en: "Color" },
  account_api_hint:     { de: "Wo finde ich meinen API Key?",  en: "Where do I find my API Key?" },
  account_api_hint_body:{ de: "Immich öffnen → Nutzermenü (oben rechts) → Account-Einstellungen → API Keys → Neuen Key erstellen",
                          en: "Open Immich → User menu (top right) → Account Settings → API Keys → Create new key" },

  // ── PeopleGrid ────────────────────────────────────────────────────────
  people_title:         { de: "Personen",                       en: "People" },
  people_subtitle:      { de: (total: number, named: number, unnamed: number) =>
                            `${total} Personen aus allen Accounts · ${named} benannt · ${unnamed} unbekannt`,
                          en: (total: number, named: number, unnamed: number) =>
                            `${total} people from all accounts · ${named} named · ${unnamed} unknown` },
  filter_all:           { de: "Alle",                           en: "All" },
  filter_named:         { de: "Benannt",                        en: "Named" },
  filter_unnamed:       { de: "Unbekannt",                      en: "Unknown" },
  people_empty:         { de: "Keine Personen gefunden.",       en: "No people found." },

  // ── MatchSuggestions ─────────────────────────────────────────────────
  matches_title:        { de: "Match-Vorschläge",               en: "Match Suggestions" },
  matches_subtitle:     { de: (open: number, dismissed: number, high: number) =>
                            `${open} offen · ${dismissed} abgelehnt · ${high} hochkonfident (≥85%)`,
                          en: (open: number, dismissed: number, high: number) =>
                            `${open} open · ${dismissed} dismissed · ${high} high confidence (≥85%)` },
  bulk_sync:            { de: (n: number) => `Bulk-Sync (${n})`,  en: (n: number) => `Bulk Sync (${n})` },
  bulk_sync_confirm:    { de: (n: number) => `Alle ${n} hochkonfidenten Matches synchronisieren?`,
                          en: (n: number) => `Sync all ${n} high-confidence matches?` },
  recalculate:          { de: "Neu berechnen",                  en: "Recalculate" },
  album_new:            { de: "Neues Album",                    en: "New Album" },
  album_link_existing:  { de: "Vorhandenes verknüpfen",         en: "Link existing" },
  album_select_ph:      { de: "— Album wählen —",              en: "— Select album —" },
  album_new_desc:       { de: "Neues Album wird erstellt, mit allen Accounts geteilt und Fotos automatisch hinzugefügt.",
                          en: "New album will be created, shared with all accounts, and photos added automatically." },
  album_existing_desc:  { de: "Bestehendes Album wird mit allen Accounts geteilt und fehlende Fotos werden ergänzt.",
                          en: "Existing album will be shared with all accounts and missing photos will be added." },
  album_create_btn:     { de: "Album erstellen",                en: "Create album" },
  album_link_btn:       { de: "Album verknüpfen",               en: "Link album" },
  album_name_ph:        { de: "Album-Name…",                   en: "Album name…" },
  dismissed_label:      { de: "Abgelehnt — nicht dieselbe Person", en: "Dismissed — not the same person" },
  restore:              { de: "Wiederherstellen",               en: "Restore" },
  names_synced_ok:      { de: "Namen synchronisiert!",         en: "Names synced!" },
  names_synced_partial: { de: "Teilweise fehlgeschlagen.",     en: "Partially failed." },
  album_linked_ok:      { de: "Album verbunden!",              en: "Album linked!" },
  album_linked_err:     { de: "Fehler beim Erstellen.",        en: "Error creating album." },
  album_refreshed_ok:   { de: "Album aktualisiert!",           en: "Album updated!" },
  badge_names_synced:   { de: "Namen sync",                    en: "Names synced" },
  badge_album_linked:   { de: "Album verbunden",               en: "Album linked" },
  canonical_name_ph:    { de: "Gemeinsamer Name…",             en: "Shared name…" },
  sync_names_btn:       { de: "Namen synchronisieren",         en: "Sync names" },
  sync_names_again:     { de: "Namen erneut synchronisieren",  en: "Re-sync names" },
  album_update_btn:     { de: "Album aktualisieren",           en: "Update album" },
  album_connect_btn:    { de: "Album verbinden",               en: "Link album" },
  not_same_person:      { de: "Nicht dieselbe Person",         en: "Not the same person" },
  filter_names_synced:  { de: "Namen sync",                    en: "Names synced" },
  filter_album_linked:  { de: "Album verbunden",               en: "Album linked" },
  filter_dismissed:     { de: "Abgelehnte",                    en: "Dismissed" },
  visible_of:           { de: (v: number, t: number) => `${v} von ${t} Vorschlägen sichtbar`,
                          en: (v: number, t: number) => `${v} of ${t} suggestions visible` },
  match_multi_account_hint: { de: "Dieser Match ist Teil eines Albums mit mehr als 2 Accounts. Bitte Änderungen über \"Alben\" oder \"Match erweitern\" vornehmen.",
                              en: "This match is part of an album with more than 2 accounts. Please make changes via \"Albums\" or \"Extend Match\"." },
  no_open_matches:      { de: "Keine offenen Vorschläge.",     en: "No open suggestions." },
  no_matches_filter:    { de: "Kein Vorschlag passt zu den Filtern.", en: "No suggestion matches the filters." },

  // ── AlbumsOverview ────────────────────────────────────────────────────
  albums_title:         { de: "Verwaltete Alben",              en: "Managed Albums" },
  albums_subtitle:      { de: (n: number) => `${n} ${n === 1 ? "Album" : "Alben"} mit automatischer Synchronisation`,
                          en: (n: number) => `${n} album${n !== 1 ? "s" : ""} with automatic sync` },
  sync_all:             { de: "Alle synchronisieren",          en: "Sync all" },
  linked_people:        { de: "Verknüpfte Personen",           en: "Linked people" },
  last_sync:            { de: (d: string) => `Letzter Sync: ${d}`, en: (d: string) => `Last sync: ${d}` },
  album_deleted_warn:   { de: "Album wurde in Immich gelöscht. Eintrag hier entfernen?",
                          en: "Album was deleted in Immich. Remove entry here?" },
  sync_now:             { de: "Jetzt synchronisieren",         en: "Sync now" },
  remove_link:          { de: "Verknüpfung entfernen",         en: "Remove link" },
  auto_sync_label:      { de: "Auto-Sync",                    en: "Auto-Sync" },
  auto_sync_time:       { de: "Uhrzeit (Serverzeit)",         en: "Time (server time)" },
  auto_sync_next:       { de: (t: string, day: string) => `Nächster Sync: ${day} um ${t}`,
                          en: (t: string, day: string) => `Next sync: ${day} at ${t}` },
  auto_sync_today:      { de: "heute",                        en: "today" },
  auto_sync_tomorrow:   { de: "morgen",                       en: "tomorrow" },
  albums_empty:         { de: "Noch keine verwalteten Alben.", en: "No managed albums yet." },
  albums_empty_hint:    { de: "Erstelle ein Album über einen Match-Vorschlag oder Manuelles Matching.",
                          en: "Create an album via a match suggestion or manual matching." },
  album_remove_confirm: { de: (name: string, n: number) =>
                            n > 1
                              ? `${n} Einträge für Album "${name}" entfernen?\n\nDas Album in Immich bleibt erhalten, wird aber nicht mehr synchronisiert.`
                              : `Eintrag für Album "${name}" entfernen?\n\nDas Album in Immich bleibt erhalten, wird aber nicht mehr synchronisiert.`,
                          en: (name: string, n: number) =>
                            n > 1
                              ? `Remove ${n} entries for album "${name}"?\n\nThe album in Immich will be kept but will no longer be synced.`
                              : `Remove entry for album "${name}"?\n\nThe album in Immich will be kept but will no longer be synced.` },

  // ── SyncPanel ─────────────────────────────────────────────────────────
  log_subtitle:         { de: (n: number) => `${n} Einträge (neueste zuerst)`,
                          en: (n: number) => `${n} entries (newest first)` },
  log_empty:            { de: "Noch keine Sync-Aktionen durchgeführt.", en: "No sync actions performed yet." },
  undo_tip:             { de: "Rückgängig machen",             en: "Undo action" },
  action_sync_names:    { de: "Namen sync",                    en: "Name sync" },
  action_create_album:  { de: "Album erstellen",               en: "Create album" },
  action_undo_names:    { de: "Undo Namen",                    en: "Undo names" },
  action_share_album:   { de: "Album teilen",                  en: "Share album" },
  action_add_assets:    { de: "Assets hinzufügen",             en: "Add assets" },
  action_refresh:       { de: "Album aktualisieren",           en: "Refresh album" },
  action_link:          { de: "Album verknüpfen",              en: "Link album" },

  // ── ExtendMatch ───────────────────────────────────────────────────────
  extend_title:         { de: "Match erweitern",           en: "Extend Match" },
  extend_subtitle:      { de: "Füge einen Account und eine Person zu einem bestehenden gemeinsamen Album hinzu.",
                          en: "Add an account and person to an existing shared album." },
  extend_pick_album:    { de: "Album wählen",              en: "Select album" },
  extend_pick_album_hint:{ de: "Klicke auf ein Album um es auszuwählen.", en: "Click an album to select it." },
  extend_new_account:   { de: "Neuer Account",             en: "New account" },
  extend_new_person:    { de: "Person auswählen",          en: "Select person" },
  extend_sync_name:     { de: "Namen synchronisieren",     en: "Sync name" },
  extend_sync_name_hint:{ de: (name: string) => `Person auf „${name}" umbenennen`,
                          en: (name: string) => `Rename person to "${name}"` },
  extend_submit:        { de: "Zum Match hinzufügen",      en: "Add to match" },
  extend_already_in:    { de: "Bereits enthalten",         en: "Already included" },
  extend_no_albums:     { de: "Noch keine verwalteten Alben vorhanden. Erstelle zuerst ein Match.",
                          en: "No managed albums yet. Create a match first." },
  extend_no_accounts:   { de: "Alle konfigurierten Accounts sind bereits in diesem Match enthalten.",
                          en: "All configured accounts are already in this match." },
  extend_search_person: { de: "Person suchen…",            en: "Search person…" },
  manual_album_owner:   { de: "Album-Besitzer",              en: "Album owner" },
  manual_hint:          { de: "Nur für neue Matches über mehrere Accounts. Um eine Person zu einem bestehenden Match hinzuzufügen → \"Match erweitern\" verwenden.",
                          en: "For new matches across multiple accounts only. To add a person to an existing match → use \"Extend Match\"." },

  // ── ManualMatch ───────────────────────────────────────────────────────
  manual_title:         { de: "Manuelles Matching",            en: "Manual Matching" },
  manual_subtitle:      { de: "Wähle für jeden konfigurierten Account die passende Person, vergib einen gemeinsamen Namen und erstelle optional ein geteiltes Album.",
                          en: "Select the matching person for each configured account, assign a shared name, and optionally create a shared album." },
  manual_people:        { de: "Personen",                      en: "People" },
  account_select_ph:    { de: "— Account wählen —",           en: "— Select account —" },
  person_select_ph:     { de: "— Person wählen —",            en: "— Select person —" },
  person_unknown_ph:    { de: (n: number) => `(unbekannt, ${n} Fotos)`, en: (n: number) => `(unknown, ${n} photos)` },
  add_person:           { de: "Person hinzufügen",             en: "Add person" },
  shared_name:          { de: "Gemeinsamer Name",              en: "Shared name" },
  shared_name_ph:       { de: "z. B. Max Mustermann",         en: "e.g. Max Doe" },
  create_shared_album:  { de: "Geteiltes Album erstellen",     en: "Create shared album" },
  album_name_label:     { de: "Album-Name",                   en: "Album name" },
  run_btn:              { de: "Namen sync + Album erstellen",  en: "Sync names + create album" },
} as const;

// Type helpers
type TranslationKey = keyof typeof translations;
type TranslationValue<K extends TranslationKey> = typeof translations[K];

// ── Context ────────────────────────────────────────────────────────────────

interface LangContextValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: <K extends TranslationKey>(
    key: K,
    ...args: TranslationValue<K>[Lang] extends (...a: infer A) => string ? A : []
  ) => string;
}

const LangContext = createContext<LangContextValue>({
  lang: "de",
  setLang: () => {},
  t: ((_key: TranslationKey, ..._args: any[]) => _key as string) as LangContextValue["t"],
});

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const stored = (localStorage.getItem("ift_lang") ?? "de") as Lang;
  const [lang, setLangState] = useState<Lang>(stored);

  const setLang = (l: Lang) => {
    localStorage.setItem("ift_lang", l);
    setLangState(l);
  };

  const t = <K extends TranslationKey>(key: K, ...args: any[]): string => {
    const entry = translations[key][lang] as any;
    if (typeof entry === "function") return entry(...args);
    return entry as string;
  };

  return <LangContext.Provider value={{ lang, setLang, t }}>{children}</LangContext.Provider>;
}

export function useT() {
  return useContext(LangContext);
}
