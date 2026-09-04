import React, { createContext, useContext, useState } from "react";

export type Lang = "de" | "en" | "br";

// ── Translations ───────────────────────────────────────────────────────────

const translations = {
  // ── App / Navigation ──────────────────────────────────────────────────
  nav_accounts: { de: "Accounts", en: "Accounts", br: "Contas" },
  nav_people: { de: "Personen", en: "People", br: "Pessoa" },
  nav_matches: { de: "Match-Vorschläge", en: "Match Suggestions", br: "Sugestões de Correspondência" },
  nav_manual: { de: "Manuell matchen", en: "Manual Match", br: "Correspondência Manual" },
  nav_albums: { de: "Alben", en: "Albums", br: "Álbuns" },
  nav_log: { de: "Sync Log", en: "Sync Log", br: "Sync Log" },
  nav_extend: { de: "Match erweitern", en: "Extend Match", br: "Correspondência Exata" },
  app_subtitle: { de: "Immich Multi-Account", en: "Immich Multi-Account", br: "Immich Multi-Account" },
  support_project: { de: "Projekt unterstützen", en: "Support this project", br: "Apoie este projeto" },

  // ── Common ────────────────────────────────────────────────────────────
  cancel: { de: "Abbrechen", en: "Cancel", br: "Cancelar" },
  save: { de: "Speichern", en: "Save", br: "Salvar" },
  unknown: { de: "Unbekannt", en: "Unknown", br: "Desconhecido" },
  loading: { de: "Lade…", en: "Loading…", br: "Carregando…" },
  photos: { de: "Fotos", en: "photos", br: "Fotos" },
  owner: { de: "Besitzer", en: "Owner", br: "Proprietário" },
  name: { de: "Name", en: "Name", br: "Nome" },
  album: { de: "Album", en: "Album", br: "Álbum" },
  error_prefix: { de: "Fehler:", en: "Error:", br: "Erro:" },
  result: { de: "Ergebnis", en: "Result", br: "Resultado" },
  undo: { de: "Rückgängig", en: "Undo", br: "Desfazer" },
  status: { de: "Status", en: "Status", br: "Status" },
  details: { de: "Details", en: "Details", br: "Detalhes" },
  action: { de: "Aktion", en: "Action", br: "Ação" },
  timestamp: { de: "Zeitstempel", en: "Timestamp", br: "Timestamp" },
  search_name: { de: "Name suchen…", en: "Search name…", br: "Buscar nome…" },
  processing: { de: "Wird verarbeitet…", en: "Processing…", br: "Processando…" },
  syncing: { de: "Synchronisiert…", en: "Syncing…", br: "Sincronizando…" },
  running: { de: "Wird ausgeführt…", en: "Running…", br: "Executando…" },
  min: { de: "min.", en: "min.", br: "min." },

  // ── AccountManager ────────────────────────────────────────────────────
  accounts_title: { de: "Accounts", en: "Accounts", br: "Contas" },
  accounts_subtitle: { de: "Immich API Keys verwalten", en: "Manage Immich API Keys", br: "Gerenciar Chaves de API do Immich" },
  account_add: { de: "Account hinzufügen", en: "Add Account", br: "Contas" },
  account_add_title: { de: "Account hinzufügen", en: "Add Account", br: "Adicionar Conta" },
  account_remove_tip: { de: "Account entfernen", en: "Remove account", br: "Remover Conta" },
  account_remove_confirm: {
    de: (name: string) => `Account "${name}" wirklich entfernen?`,
    en: (name: string) => `Really remove account "${name}"?`,
    br: (name: string) => `Certeza que deseja remover a conta "${name}"?`,
  },
  account_empty: { de: "Noch keine Accounts konfiguriert.", en: "No accounts configured yet.", br: "Nenhuma conta configurada ainda." },
  account_empty_hint: {
    de: "Füge deinen ersten Immich-Account hinzu.",
    en: "Add your first Immich account.",
    br: "Adicione sua primeira conta do Immich.",
  },
  account_name_ph: { de: "Name (z.B. Manu)", en: "Name (e.g. Manu)", br: "Nome (ex. Manu)" },
  account_test: { de: "Teste Verbindung…", en: "Testing connection…", br: "Testando conexão…" },
  account_add_btn: { de: "Hinzufügen", en: "Add", br: "Adicionar" },
  account_edit: { de: "Bearbeiten", en: "Edit", br: "Editar" },
  account_edit_title: { de: "Account bearbeiten", en: "Edit Account", br: "Editar Conta" },
  account_save: { de: "Speichern", en: "Save", br: "Salvar" },
  account_saving: { de: "Wird gespeichert…", en: "Saving…", br: "Salvando…" },
  account_color_label: { de: "Farbe", en: "Color", br: "Cor" },
  account_api_hint: { de: "Wo finde ich meinen API Key?", en: "Where do I find my API Key?", br: "Onde encontro minha Chave de API?" },
  account_api_hint_body: {
    de: "Immich öffnen → Nutzermenü (oben rechts) → Account-Einstellungen → API Keys → Neuen Key erstellen",
    en: "Open Immich → User menu (top right) → Account Settings → API Keys → Create new key",
    br: "Abra o Immich → Menu Usuário (topo na direita) → Configurações da Conta → Chaves de API → Criar nova chave",
  },

  // ── PeopleGrid ────────────────────────────────────────────────────────
  people_title: { de: "Personen", en: "People", br: "Pessoa" },
  people_subtitle: {
    de: (total: number, named: number, unnamed: number) =>
      `${total} Personen aus allen Accounts · ${named} benannt · ${unnamed} unbekannt`,
    en: (total: number, named: number, unnamed: number) =>
      `${total} people from all accounts · ${named} named · ${unnamed} unknown`,
    br: (total: number, named: number, unnamed: number) =>
      `${total} pessoas de todas as contas · ${named} nomeadas · ${unnamed} sem nome`,
  },
  filter_all: { de: "Alle", en: "All", br: "Todos" },
  filter_named: { de: "Benannt", en: "Named", br: "Nomeado" },
  filter_unnamed: { de: "Unbekannt", en: "Unknown", br: "Sem nome" },
  people_empty: { de: "Keine Personen gefunden.", en: "No people found.", br: "Nenhuma pessoa encontrada" },

  // ── MatchSuggestions ─────────────────────────────────────────────────
  matches_title: { de: "Match-Vorschläge", en: "Match Suggestions", br: "Sugestões de Combinações" },
  matches_subtitle: {
    de: (open: number, dismissed: number, high: number) =>
      `${open} offen · ${dismissed} abgelehnt · ${high} hochkonfident (≥85%)`,
    en: (open: number, dismissed: number, high: number) =>
      `${open} open · ${dismissed} dismissed · ${high} high confidence (≥85%)`,
    br: (open: number, dismissed: number, high: number) =>
      `${open} abertos · ${dismissed} dispensados · ${high} alta confiança (≥85%)`,
  },
  bulk_sync: { de: (n: number) => `Bulk-Sync (${n})`, en: (n: number) => `Bulk Sync (${n})`, br: (n: number) => `Sincronizar em Lote (${n})` },
  bulk_sync_confirm: {
    de: (n: number) => `Alle ${n} hochkonfidenten Matches synchronisieren?`,
    en: (n: number) => `Sync all ${n} high-confidence matches?`,
    br: (n: number) => `Sincronizar todas as ${n} combinações com alta confiança?`,
  },
  recalculate: { de: "Neu berechnen", en: "Recalculate", br: "Recalcular" },
  album_new: { de: "Neues Album", en: "New Album", br: "Novo Álbum" },
  album_link_existing: { de: "Vorhandenes verknüpfen", en: "Link existing", br: "Vínculo existente" },
  album_select_ph: { de: "— Album wählen —", en: "— Select album —", br: "— Selecionar álbum —" },
  album_new_desc: {
    de: "Neues Album wird erstellt, mit den beteiligten Accounts geteilt und Fotos automatisch hinzugefügt.",
    en: "New album will be created, shared with participating accounts, and photos added automatically.",
    br: "Novo álbum será criado, compartilhado com as contas participantes, e fotos adicionadas automaticamente.",
  },
  album_existing_desc: {
    de: "Bestehendes Album wird mit den beteiligten Accounts geteilt und fehlende Fotos werden ergänzt.",
    en: "Existing album will be shared with participating accounts and missing photos will be added.",
    br: "Álbum existente será compartilhado com as contas participantes e fotos que faltam serão adicionadas.",
  },
  album_create_btn: { de: "Album erstellen", en: "Create album", br: "Criar álbum" },
  album_link_btn: { de: "Album verknüpfen", en: "Link album", br: "Vincular álbum" },
  album_name_ph: { de: "Album-Name…", en: "Album name…", br: "Nome do Álbum…" },
  dismissed_label: {
    de: "Abgelehnt — nicht dieselbe Person",
    en: "Dismissed — not the same person",
    br: "Descartado — não é a mesma pessoa",
  },
  restore: { de: "Wiederherstellen", en: "Restore", br: "Restaurar" },
  names_synced_ok: { de: "Namen synchronisiert!", en: "Names synced!", br: "Nomes sincronizados!" },
  names_synced_partial: { de: "Teilweise fehlgeschlagen.", en: "Partially failed.", br: "Falhou parcialmente." },
  album_linked_ok: { de: "Album verbunden!", en: "Album linked!", br: "Álbum vinculado!" },
  album_linked_err: { de: "Fehler beim Erstellen.", en: "Error creating album.", br: "Erro ao criar o álbum." },
  album_refreshed_ok: { de: "Album aktualisiert!", en: "Album updated!", br: "Álbum atualizado!" },
  badge_names_synced: { de: "Namen sync", en: "Names synced", br: "Nomes sincronizados" },
  badge_album_linked: { de: "Album verbunden", en: "Album linked", br: "Álbum vinculado" },
  canonical_name_ph: { de: "Gemeinsamer Name…", en: "Shared name…", br: "Nome Compartilhado…" },
  sync_names_btn: { de: "Namen synchronisieren", en: "Sync names", br: "Sincronizar nomes" },
  sync_names_again: { de: "Namen erneut synchronisieren", en: "Re-sync names", br: "Re-sincronizar nomes" },
  album_update_btn: { de: "Album aktualisieren", en: "Update album", br: "Atualizar álbum" },
  album_connect_btn: { de: "Album verbinden", en: "Link album", br: "Vincular álbum" },
  not_same_person: { de: "Nicht dieselbe Person", en: "Not the same person", br: "Não é a mesma pessoa" },
  filter_names_synced: { de: "Namen sync", en: "Names synced", br: "Nomes sincronizados" },
  filter_album_linked: { de: "Album verbunden", en: "Album linked", br: "Álbum vinculado" },
  filter_dismissed: { de: "Abgelehnte", en: "Dismissed", br: "Descartado" },
  visible_of: {
    de: (v: number, t: number) => `${v} von ${t} Vorschlägen sichtbar`,
    en: (v: number, t: number) => `${v} of ${t} suggestions visible`,
    br: (v: number, t: number) => `${v} de ${t} sugestões visíveis`,
  },
  match_multi_account_hint: {
    de: 'Dieser Match ist Teil eines Albums mit mehr als 2 Accounts. Bitte Änderungen über "Alben" oder "Match erweitern" vornehmen.',
    en: 'This match is part of an album with more than 2 accounts. Please make changes via "Albums" or "Extend Match".',
    br: 'Esta correspondência faz parte de um álbum com mais de duas contas. Por favor, faça alterações via "Álbums" ou "Estender Correspondência".',
  },
  no_open_matches: { de: "Keine offenen Vorschläge.", en: "No open suggestions.", br: "Sem sugestões abertas." },
  no_matches_filter: {
    de: "Kein Vorschlag passt zu den Filtern.",
    en: "No suggestion matches the filters.",
    br: "Sem sugestões correspondentes aos filtros.",
  },

  // ── AlbumsOverview ────────────────────────────────────────────────────
  albums_title: { de: "Verwaltete Alben", en: "Managed Albums", br: "Álbuns Gerenciados" },
  albums_subtitle: {
    de: (n: number) => `${n} ${n === 1 ? "Album" : "Alben"} mit automatischer Synchronisation`,
    en: (n: number) => `${n} album${n !== 1 ? "s" : ""} with automatic sync`,
    br: (n: number) => `${n} album${n !== 1 ? "s" : ""} com sincronismo automático`,
  },
  sync_all: { de: "Alle synchronisieren", en: "Sync all", br: "Sincronizar tudo" },
  linked_people: { de: "Verknüpfte Personen", en: "Linked people", br: "Pessoa vinculada" },
  last_sync: { de: (d: string) => `Letzter Sync: ${d}`, en: (d: string) => `Last sync: ${d}`, br: (d: string) => `Último Sincronismo: ${d}` },
  album_deleted_warn: {
    de: "Album wurde in Immich gelöscht. Eintrag hier entfernen?",
    en: "Album was deleted in Immich. Remove entry here?",
    br: "O álbum foi apagado no Immich. Remover registro aqui?",
  },
  sync_now: { de: "Jetzt synchronisieren", en: "Sync now", br: "Sincronizar agora" },
  remove_link: { de: "Verknüpfung entfernen", en: "Remove link", br: "Remover vínculo" },
  auto_sync_label: { de: "Auto-Sync", en: "Auto-Sync", br: "Auto-Sincronismo" },
  auto_sync_time: { de: "Uhrzeit (Serverzeit)", en: "Time (server time)", br: "Hora (do servidor)" },
  auto_sync_next: {
    de: (t: string, day: string) => `Nächster Sync: ${day} um ${t}`,
    en: (t: string, day: string) => `Next sync: ${day} at ${t}`,
    br: (t: string, day: string) => `Próximo sincronismo: ${day} às ${t}`,
  },
  auto_sync_today: { de: "heute", en: "today", br: "hoje" },
  auto_sync_tomorrow: { de: "morgen", en: "tomorrow", br: "amanhã" },
  albums_empty: { de: "Noch keine verwalteten Alben.", en: "No managed albums yet.", br: "Sem álbuns gerenciados ainda." },
  albums_empty_hint: {
    de: "Erstelle ein Album über einen Match-Vorschlag oder Manuelles Matching.",
    en: "Create an album via a match suggestion or manual matching.",
    br: "Crie um álbum por meio de uma sugestão de correspondência ou de uma correspondência manual.",
  },
  album_remove_confirm: {
    de: (name: string, n: number) =>
      n > 1
        ? `${n} Einträge für Album "${name}" entfernen?\n\nDas Album in Immich bleibt erhalten, wird aber nicht mehr synchronisiert.`
        : `Eintrag für Album "${name}" entfernen?\n\nDas Album in Immich bleibt erhalten, wird aber nicht mehr synchronisiert.`,
    en: (name: string, n: number) =>
      n > 1
        ? `Remove ${n} entries for album "${name}"?\n\nThe album in Immich will be kept but will no longer be synced.`
        : `Remove entry for album "${name}"?\n\nThe album in Immich will be kept but will no longer be synced.`,
    br: (name: string, n: number) =>
      n > 1
        ? `Remover ${n} registros do álbum "${name}"?\n\nO álbum no Immich será mantido, mas não haverá novos sincronismos.`
        : `Remover registros do álbum "${name}"?\n\nO álbum no Immich será mantido, mas não haverá novos sincronismos.`,
  },

  // ── SyncPanel ─────────────────────────────────────────────────────────
  log_subtitle: {
    de: (n: number) => `${n} Einträge (neueste zuerst)`,
    en: (n: number) => `${n} entries (newest first)`,
    br: (n: number) => `${n} registros (novos primeiro)`,
  },
  log_empty: { de: "Noch keine Sync-Aktionen durchgeführt.", en: "No sync actions performed yet.", br: "Sem ação de sincronismo executada ainda." },
  undo_tip: { de: "Rückgängig machen", en: "Undo action", br: "Desfazer ação" },
  action_sync_names: { de: "Namen sync", en: "Name sync", br: "Sincronização de nomes" },
  action_create_album: { de: "Album erstellen", en: "Create album", br: "Criar álbum" },
  action_undo_names: { de: "Undo Namen", en: "Undo names", br: "Desfazer nomes" },
  action_share_album: { de: "Album teilen", en: "Share album", br: "Compartilhar álbum" },
  action_add_assets: { de: "Assets hinzufügen", en: "Add assets", br: "Adicionar itens" },
  action_refresh: { de: "Album aktualisieren", en: "Refresh album", br: "Atualizar álbum" },
  action_link: { de: "Album verknüpfen", en: "Link album", br: "Vincular álbum" },

  // ── ExtendMatch ───────────────────────────────────────────────────────
  extend_title: { de: "Match erweitern", en: "Extend Match", br: "Extender Correspondência" },
  extend_subtitle: {
    de: "Füge einen Account und eine Person zu einem bestehenden gemeinsamen Album hinzu.",
    en: "Add an account and person to an existing shared album.",
    br: "Adicione uma conta e uma pessoa a um álbum compartilhado existente.",
  },
  extend_pick_album: { de: "Album wählen", en: "Select album", br: "Selecionar álbum" },
  extend_pick_album_hint: {
    de: "Klicke auf ein Album um es auszuwählen.",
    en: "Click an album to select it.",
    br: "Clique em um álbum para seleciona-lo.",
  },
  extend_new_account: { de: "Neuer Account", en: "New account", br: "Nova conta" },
  extend_new_person: { de: "Person auswählen", en: "Select person", br: "Selecionar pessoa" },
  extend_sync_name: { de: "Namen synchronisieren", en: "Sync name", br: "Sincronizar nome" },
  extend_sync_name_hint: {
    de: (name: string) => `Person auf „${name}" umbenennen`,
    en: (name: string) => `Rename person to "${name}"`,
    br: (name: string) => `Renomear pessoa para "${name}"`,
  },
  extend_submit: { de: "Zum Match hinzufügen", en: "Add to match", br: "Adicionar à correspondência" },
  extend_already_in: { de: "Bereits enthalten", en: "Already included", br: "Já inserido" },
  extend_no_albums: {
    de: "Noch keine verwalteten Alben vorhanden. Erstelle zuerst ein Match.",
    en: "No managed albums yet. Create a match first.",
    br: "Sem álbuns gerenciados ainda. Primeiro crie uma correspondência.",
  },
  extend_no_accounts: {
    de: "Alle konfigurierten Accounts sind bereits in diesem Match enthalten.",
    en: "All configured accounts are already in this match.",
    br: "Todas as contas configuradas já estão nesta correspondência.",
  },
  extend_search_person: { de: "Person suchen…", en: "Search person…", br: "Pesquisar pessoa…" },
  manual_album_owner: { de: "Album-Besitzer", en: "Album owner", br: "Proprietário do álbum" },
  manual_hint: {
    de: 'Nur für neue Matches über mehrere Accounts. Um eine Person zu einem bestehenden Match hinzuzufügen → "Match erweitern" verwenden.',
    en: 'For new matches across multiple accounts only. To add a person to an existing match → use "Extend Match".',
    br: 'Apenas para novas correspondências em múltiplas contas. Para adicionar uma pessoa a uma correspondência existente. → use "Extender Correspondência".',
  },

  // ── ManualMatch ───────────────────────────────────────────────────────
  manual_title: { de: "Manuelles Matching", en: "Manual Matching", br: "Correspondência Manual" },
  manual_subtitle: {
    de: "Wähle für jeden konfigurierten Account die passende Person, vergib einen gemeinsamen Namen und erstelle optional ein geteiltes Album.",
    en: "Select the matching person for each configured account, assign a shared name, and optionally create a shared album.",
    br: "Selecione a pessoa correspondente para cada conta configurada, atribua um nome compartilhado e, opcionalmente, crie um álbum compartilhado.",
  },
  manual_people: { de: "Personen", en: "People", br: "Pessoa" },
  account_select_ph: { de: "— Account wählen —", en: "— Select account —", br: "— Selecionar conta —" },
  person_select_ph: { de: "— Person wählen —", en: "— Select person —", br: "— Selecionar pessoa —" },
  person_unknown_ph: {
    de: (n: number) => `(unbekannt, ${n} Fotos)`,
    en: (n: number) => `(unknown, ${n} photos)`,
    br: (n: number) => `(desconhecido, ${n} fotos)`,
  },
  add_person: { de: "Person hinzufügen", en: "Add person", br: "Adicionar pessoa" },
  shared_name: { de: "Gemeinsamer Name", en: "Shared name", br: "Nome compartilhado" },
  shared_name_ph: { de: "z. B. Max Mustermann", en: "e.g. Max Doe", br: "ex. Neymar Jr" },
  create_shared_album: { de: "Geteiltes Album erstellen", en: "Create shared album", br: "Criar álbum compartilhado" },
  album_name_label: { de: "Album-Name", en: "Album name", br: "Nome do álbum" },
  run_btn: { de: "Namen sync + Album erstellen", en: "Sync names + create album", br: "Sincronizar nomes + criar álbum" },
} as const;

// Type helpers
type TranslationKey = keyof typeof translations;
type TranslationValue<K extends TranslationKey> = (typeof translations)[K];

// ── Sync-Log-Meldungen ────────────────────────────────────────────────────
// Structured translations for SyncLogEntry.message_key. Each entry takes a
// single params object (rather than positional args like `translations`
// above) because the key/params pair arrives at runtime from the backend
// and isn't known statically. Rendered via `logMessage()` from useT(),
// which falls back to `entry.details` (German) for unknown/missing keys —
// e.g. log entries persisted before message_key existed.
type LogMessageParams = Record<string, string | number>;
type LogMessageFn = (p: LogMessageParams) => string;

const logMessages: Record<string, { de: LogMessageFn; en: LogMessageFn }> = {
  log_album_members_fetch_failed: {
    de: () => "Album-Mitglieder konnten nicht abgerufen werden",
    en: () => "Could not fetch album members",
    br: () => "Não foi possível recuperar os membros do álbum",
  },
  log_album_shared: {
    de: (p) => `Album '${p.album}' geteilt mit: ${p.names}`,
    en: (p) => `Album '${p.album}' shared with: ${p.names}`,
    br: (p) => `Álbum '${p.album}' compartilhado com: ${p.names}`,
  },
  log_share_failed: {
    de: (p) => `Sharing mit ${p.names} fehlgeschlagen`,
    en: (p) => `Sharing with ${p.names} failed`,
    br: (p) => `Compartilhamento com ${p.names} falhou`,
  },
  log_name_synced: {
    de: (p) => `Account '${p.account}' – person ${p.person} → '${p.name}'`,
    en: (p) => `Account '${p.account}' – person ${p.person} renamed to '${p.name}'`,
    br: (p) => `Conta de '${p.account}' – pessoa ${p.person} renomeada para '${p.name}'`,
  },
  log_name_sync_failed: {
    de: (p) => `Account '${p.account}' – person ${p.person}`,
    en: (p) => `Account '${p.account}' – person ${p.person}`,
    br: (p) => `Conta de '${p.account}' – pessoa ${p.person}`,
  },
  log_assets_added: {
    de: (p) => `${p.count} Assets von '${p.account}' hinzugefügt`,
    en: (p) => `${p.count} assets added from '${p.account}'`,
    br: (p) => `${p.count} itens adicionados de '${p.account}'`,
  },
  log_assets_add_failed: {
    de: (p) => `Assets von '${p.account}' konnten nicht hinzugefügt werden`,
    en: (p) => `Could not add assets from '${p.account}'`,
    br: (p) => `Não pode adicionar itens de '${p.account}'`,
  },
  log_assets_partial_failure: {
    de: (p) =>
      `${p.count} Assets von '${p.account}' konnten nicht hinzugefügt werden (z. B. fehlende Berechtigung)`,
    en: (p) => `${p.count} assets from '${p.account}' could not be added (e.g. missing permission)`,
    br: (p) => `${p.count} itens de '${p.account}' não puderam ser adicionados (ex. falta de permissão)`,
  },
  log_assets_linked: {
    de: (p) => `${p.count} Assets von '${p.account}' zu '${p.album}' hinzugefügt`,
    en: (p) => `${p.count} assets from '${p.account}' added to '${p.album}'`,
    br: (p) => `${p.count} itens de '${p.account}' adicionados em '${p.album}'`,
  },
  log_assets_link_failed: {
    de: (p) => `Assets von '${p.account}' fehlgeschlagen`,
    en: (p) => `Assets from '${p.account}' failed`,
    br: (p) => `Itens de '${p.account}' falharam`,
  },
  log_assets_added_to_album: {
    de: (p) => `${p.count} neue Assets von '${p.account}' zum Album '${p.album}' hinzugefügt`,
    en: (p) => `${p.count} new assets from '${p.account}' added to album '${p.album}'`,
    br: (p) => `${p.count} novos itens de '${p.account}' adicionados ao álbum '${p.album}'`,
  },
  log_album_not_found: {
    de: (p) => `Album '${p.album}' existiert nicht in Immich.`,
    en: (p) => `Album '${p.album}' does not exist in Immich.`,
    br: (p) => `Álbum '${p.album}' não existe no Immich.`,
  },
  log_album_deleted: {
    de: (p) =>
      `Album '${p.album}' wurde in Immich gelöscht. Eintrag kann über die Alben-Übersicht entfernt werden.`,
    en: (p) =>
      `Album '${p.album}' was deleted in Immich. The entry can be removed via the Albums overview.`,
    br: (p) =>
      `Álbum '${p.album}' foi apagado no Immich. O item pode ser removido através da visão geral dos álbuns.`,
  },
  log_album_unreachable: {
    de: () => "Album nicht abrufbar",
    en: () => "Album could not be reached",
    br: () => "Não foi possível acessar o álbum",
  },
  log_owner_account_missing: {
    de: () => "Owner-Account nicht mehr vorhanden",
    en: () => "Owner account no longer exists",
    br: () => "Conta do proprietário já não existe mais",
  },
  log_person_already_in_album: {
    de: (p) => `Person ${p.person} aus '${p.account}' ist bereits in Album '${p.album}' enthalten.`,
    en: (p) => `Person ${p.person} from '${p.account}' is already included in album '${p.album}'.`,
    br: (p) => `Pessoa ${p.person} da conta de '${p.account}' já está inserida no álbum '${p.album}'.`,
  },
  log_person_validation_failed: {
    de: (p) => `Person in '${p.account}' konnte nicht validiert werden`,
    en: (p) => `Person in '${p.account}' could not be validated`,
    br: (p) => `Pessoa da conta de '${p.account}' não pode ser validada`,
  },
  log_album_assets_fetch_failed: {
    de: () => "Album-Assets konnten nicht abgerufen werden",
    en: () => "Could not fetch album assets",
    br: () => "Não foi possível recuperar os itens do álbum",
  },
  log_no_new_assets_from_account: {
    de: (p) => `Keine neuen Assets von '${p.account}' (alle bereits im Album)`,
    en: (p) => `No new assets from '${p.account}' (all already in the album)`,
    br: (p) => `Sem novos itens de '${p.account}' (todos já estão no álbum)`,
  },
  log_rename_failed: {
    de: (p) => `Umbenennung in '${p.account}' fehlgeschlagen`,
    en: (p) => `Renaming in '${p.account}' failed`,
    br: (p) => `Renomear na conta de '${p.account}' falhou`,
  },
  log_album_created: {
    de: (p) => `Album '${p.album}' in '${p.account}' mit ${p.count} Assets erstellt`,
    en: (p) => `Album '${p.album}' created in '${p.account}' with ${p.count} assets`,
    br: (p) => `Álbum '${p.album}' criado na conta de '${p.account}' com ${p.count} itens`,
  },
  log_album_create_failed: {
    de: (p) => `Album '${p.album}' konnte nicht erstellt werden`,
    en: (p) => `Album '${p.album}' could not be created`,
    br: (p) => `Álbum '${p.album}' não pode ser criado`,
  },
  log_sync_failed: {
    de: (p) => `Sync von '${p.account}' fehlgeschlagen`,
    en: (p) => `Sync from '${p.account}' failed`,
    br: (p) => `Sincronismo de '${p.account}' falhou`,
  },
  log_no_new_assets: {
    de: (p) => `Album '${p.album}': Keine neuen Assets gefunden`,
    en: (p) => `Album '${p.album}': no new assets found`,
    br: (p) => `álbum '${p.album}': nenhum novo item encontrado`,
  },
  log_undo_name_reverted: {
    de: (p) => `Name von Person ${p.person} in '${p.account}' auf '${p.name}' zurückgesetzt`,
    en: (p) => `Reverted person ${p.person} in '${p.account}' to '${p.name}'`,
    br: (p) => `Revertido nome da pessoa ${p.person} de '${p.account}' para '${p.name}'`,
  },
  log_undo_failed: {
    de: (p) => `Rückgängig machen für Person ${p.person} fehlgeschlagen`,
    en: (p) => `Undo failed for person ${p.person}`,
    br: (p) => `Falha ao desfazer para pessoa ${p.person}`,
  },
};

// ── Context ────────────────────────────────────────────────────────────────

interface LogLikeEntry {
  message_key?: string;
  message_params?: LogMessageParams;
  details: string;
}

interface LangContextValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: <K extends TranslationKey>(
    key: K,
    ...args: TranslationValue<K>[Lang] extends (...a: infer A) => string ? A : []
  ) => string;
  /** Renders a SyncLogEntry via its message_key/message_params when known,
   *  falling back to the persisted (German) `details` string otherwise. */
  logMessage: (entry: LogLikeEntry) => string;
}

function renderLogMessage(lang: Lang, entry: LogLikeEntry): string {
  const key = entry.message_key;
  if (key && Object.prototype.hasOwnProperty.call(logMessages, key)) {
    return logMessages[key][lang](entry.message_params ?? {});
  }
  return entry.details;
}

const LangContext = createContext<LangContextValue>({
  lang: "de",
  setLang: () => {},
  t: ((_key: TranslationKey, ..._args: any[]) => _key as string) as LangContextValue["t"],
  logMessage: (entry) => renderLogMessage("de", entry),
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

  const logMessage = (entry: LogLikeEntry): string => renderLogMessage(lang, entry);

  return (
    <LangContext.Provider value={{ lang, setLang, t, logMessage }}>{children}</LangContext.Provider>
  );
}

export function useT() {
  return useContext(LangContext);
}
