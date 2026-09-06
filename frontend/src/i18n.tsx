import React, { createContext, useContext, useState } from "react";

export type Lang = "de" | "en" | "es-ES" | "pt-BR";

/** Single source of truth for known languages: which ones exist, their
 *  toggle labels, and (via `Object.keys`) the storage-validation whitelist.
 *  Add a new language here and both the switcher (App.tsx) and the
 *  localStorage guard below pick it up automatically. */
export const LANG_LABELS: Record<Lang, string> = {
  de: "🇩🇪 DE",
  en: "🇬🇧 EN",
  "es-ES": "🇪🇸 ES",
  "pt-BR": "🇧🇷 PT-BR",
};

/** Second mapping tied to the same key set as `LANG_LABELS` — the BCP-47
 *  locale each language formats dates/numbers with. `Record<Lang, string>`
 *  keeps the two in lockstep: adding a language to `LANG_LABELS` without
 *  adding it here is a compile error, not a silent gap.
 *  `en: "en-GB"` is a deliberate choice, not a default — it keeps the
 *  day-before-month date order the German locale already uses, rather than
 *  switching an English-reading user to `en-US`'s month-before-day. */
export const LANG_LOCALES: Record<Lang, string> = {
  de: "de-AT",
  en: "en-GB",
  "es-ES": "es-ES",
  "pt-BR": "pt-BR",
};

/** Shared `Intl`-backed date/time formatter for "last synced" timestamps.
 *  Lives here, next to `LANG_LOCALES`, because every caller needs exactly
 *  that mapping to pick a locale — `AlbumsOverview.tsx` and `ExtendMatch.tsx`
 *  used to each define an identical copy of this function, doubling the
 *  surface a future format change would need to touch.
 *
 *  A missing value isn't the only way in here: the timestamps ultimately
 *  come from `accounts.json` on disk (see `docs/agents/lehren.md`'s
 *  hand-recovered-storage case, a real instance of exactly this), so an
 *  unreadable-but-present string is a real possibility, not a theoretical
 *  one. `new Date("not-a-date")` doesn't throw — it silently produces an
 *  Invalid Date whose `toLocaleString()` renders as the untranslated
 *  English string `"Invalid Date"`, which is just as much a language leak
 *  as the missing-value case the `!iso` guard already covers (Fund 1c).
 *  `Number.isFinite(date.getTime())` is the standard way to detect that:
 *  an Invalid Date's `getTime()` is `NaN`, which fails `Number.isFinite`
 *  while every valid date's timestamp passes it. */
export function formatDate(iso: string | undefined, locale: string): string {
  if (!iso) return "–";
  const date = new Date(iso);
  if (!Number.isFinite(date.getTime())) return "–";
  return date.toLocaleString(locale, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const KNOWN_LANGS = Object.keys(LANG_LABELS) as Lang[];

/** Validates a raw (e.g. `localStorage`) value against the known languages,
 *  falling back to `"de"` for anything else — including a stale `"br"` from
 *  before the pt-BR rename. Exported so it can be unit-tested without a
 *  DOM/localStorage stub. */
export function resolveLang(stored: string | null): Lang {
  return KNOWN_LANGS.includes(stored as Lang) ? (stored as Lang) : "de";
}

/** Best-effort match of a raw `navigator.language` value (e.g. `"pt-BR"`,
 *  `"pt"`, `"de-DE"`, `"en-US"`) against the known languages: exact match
 *  first, then by BCP-47 primary subtag (the part before the first `-`), so
 *  a browser reporting a regional variant we don't ship (`"en-US"`,
 *  `"de-DE"`) still lands on the language it's closest to instead of `"de"`.
 *  Falls back to `"de"` when nothing matches, or when no language is given
 *  at all. Exported so it can be unit-tested without a `navigator` stub,
 *  mirroring `resolveLang` above. */
export function detectBrowserLang(raw: string | null | undefined): Lang {
  if (!raw) return "de";
  if (KNOWN_LANGS.includes(raw as Lang)) return raw as Lang;
  const prefix = raw.split("-")[0].toLowerCase();
  return KNOWN_LANGS.find((l) => l.split("-")[0].toLowerCase() === prefix) ?? "de";
}

/** Reads the persisted language and validates it in one step — this is the
 *  exact call the Provider makes, so a test exercising `readStoredLang()`
 *  proves what the Provider actually does, not just what `resolveLang()` can
 *  do in isolation. A locked-down `localStorage` (private browsing, blocked
 *  site data, a sandboxed iframe) throws on the property access itself, not
 *  just on `.getItem()` — caught here so a blocked store falls back to
 *  `"de"` instead of leaving the whole app on a blank screen.
 *
 *  When nothing is stored yet (first visit), the browser's own language
 *  (`navigator.language`) decides the starting language instead of always
 *  defaulting to German — but only then: an existing, even invalid, stored
 *  value still goes through `resolveLang` as before and never falls through
 *  to the browser language. */
export function readStoredLang(): Lang {
  try {
    const stored = localStorage.getItem("ift_lang");
    if (stored !== null) return resolveLang(stored);
    return detectBrowserLang(typeof navigator === "undefined" ? undefined : navigator.language);
  } catch {
    return "de";
  }
}

// ── Translations ───────────────────────────────────────────────────────────

const translations = {
  // ── App / Navigation ──────────────────────────────────────────────────
  nav_accounts: { de: "Accounts", en: "Accounts", "pt-BR": "Contas", "es-ES": "Cuentas" },
  nav_people: { de: "Personen", en: "People", "pt-BR": "Pessoas", "es-ES": "Personas" },
  nav_matches: {
    de: "Match-Vorschläge",
    en: "Match Suggestions",
    "pt-BR": "Sugestões de Correspondência",
    "es-ES": "Sugerencias de coincidencias",
  },
  nav_manual: {
    de: "Manuell matchen",
    en: "Manual Match",
    "pt-BR": "Correspondência Manual",
    "es-ES": "Coincidencia manual",
  },
  nav_albums: { de: "Alben", en: "Albums", "pt-BR": "Álbuns", "es-ES": "Álbumes" },
  nav_log: {
    de: "Sync Log",
    en: "Sync Log",
    "pt-BR": "Sync Log",
    "es-ES": "Registro de sincronización",
  },
  nav_extend: {
    de: "Match erweitern",
    en: "Extend Match",
    "pt-BR": "Estender Correspondência",
    "es-ES": "Ampliar coincidencia",
  },
  app_subtitle: {
    de: "Immich Multi-Account",
    en: "Immich Multi-Account",
    "pt-BR": "Immich Multi-Account",
    "es-ES": "Immich Multi-Account",
  },
  support_project: {
    de: "Projekt unterstützen",
    en: "Support this project",
    "pt-BR": "Apoie este projeto",
    "es-ES": "Apoya este proyecto",
  },
  lock_button: { de: "Sperren", en: "Lock", "pt-BR": "Bloquear", "es-ES": "Bloquear" },

  // ── AuthGate ──────────────────────────────────────────────────────────
  auth_title: {
    de: "Family Tools entsperren",
    en: "Unlock Family Tools",
    "pt-BR": "Desbloquear o Family Tools",
    "es-ES": "Desbloquear Family Tools",
  },
  auth_subtitle: {
    de: "Gemeinsames Zugriffstoken eingeben",
    en: "Enter the shared access token",
    "pt-BR": "Insira o token de acesso compartilhado",
    "es-ES": "Introduce el token de acceso compartido",
  },
  auth_token_ph: {
    de: "Zugriffstoken",
    en: "Access token",
    "pt-BR": "Token de acesso",
    "es-ES": "Token de acceso",
  },
  auth_checking: {
    de: "Prüfe…",
    en: "Checking…",
    "pt-BR": "Verificando…",
    "es-ES": "Comprobando…",
  },
  auth_unlock: { de: "Entsperren", en: "Unlock", "pt-BR": "Desbloquear", "es-ES": "Desbloquear" },
  auth_error_invalid: {
    de: "Ungültiges Zugriffstoken",
    en: "Invalid access token",
    "pt-BR": "Token de acesso inválido",
    "es-ES": "Token de acceso no válido",
  },
  auth_error_rate_limited: {
    de: "Zu viele Anmeldeversuche. Bitte in einer Minute erneut versuchen.",
    en: "Too many login attempts. Try again in one minute.",
    "pt-BR": "Muitas tentativas de login. Tente novamente em um minuto.",
    "es-ES": "Demasiados intentos de inicio de sesión. Inténtalo de nuevo en un minuto.",
  },
  auth_error_generic: {
    de: "Anmeldung fehlgeschlagen. Bitte später erneut versuchen.",
    en: "Login failed. Please try again later.",
    "pt-BR": "Falha no login. Tente novamente mais tarde.",
    "es-ES": "No se ha podido iniciar sesión. Inténtalo de nuevo más tarde.",
  },

  // ── Common ────────────────────────────────────────────────────────────
  cancel: { de: "Abbrechen", en: "Cancel", "pt-BR": "Cancelar", "es-ES": "Cancelar" },
  save: { de: "Speichern", en: "Save", "pt-BR": "Salvar", "es-ES": "Guardar" },
  unknown: { de: "Unbekannt", en: "Unknown", "pt-BR": "Desconhecido", "es-ES": "Desconocido" },
  loading: { de: "Lade…", en: "Loading…", "pt-BR": "Carregando…", "es-ES": "Cargando…" },
  photos: { de: "Fotos", en: "photos", "pt-BR": "Fotos", "es-ES": "fotos" },
  owner: { de: "Besitzer", en: "Owner", "pt-BR": "Proprietário", "es-ES": "Propietario" },
  name: { de: "Name", en: "Name", "pt-BR": "Nome", "es-ES": "Nombre" },
  album: { de: "Album", en: "Album", "pt-BR": "Álbum", "es-ES": "Álbum" },
  error_prefix: { de: "Fehler:", en: "Error:", "pt-BR": "Erro:", "es-ES": "Error:" },
  result: { de: "Ergebnis", en: "Result", "pt-BR": "Resultado", "es-ES": "Resultado" },
  undo: { de: "Rückgängig", en: "Undo", "pt-BR": "Desfazer", "es-ES": "Deshacer" },
  status: { de: "Status", en: "Status", "pt-BR": "Status", "es-ES": "Estado" },
  details: { de: "Details", en: "Details", "pt-BR": "Detalhes", "es-ES": "Detalles" },
  action: { de: "Aktion", en: "Action", "pt-BR": "Ação", "es-ES": "Acción" },
  timestamp: { de: "Zeitstempel", en: "Timestamp", "pt-BR": "Timestamp", "es-ES": "Fecha y hora" },
  search_name: {
    de: "Name suchen…",
    en: "Search name…",
    "pt-BR": "Buscar nome…",
    "es-ES": "Buscar por nombre…",
  },
  processing: {
    de: "Wird verarbeitet…",
    en: "Processing…",
    "pt-BR": "Processando…",
    "es-ES": "Procesando…",
  },
  syncing: {
    de: "Synchronisiert…",
    en: "Syncing…",
    "pt-BR": "Sincronizando…",
    "es-ES": "Sincronizando…",
  },
  running: {
    de: "Wird ausgeführt…",
    en: "Running…",
    "pt-BR": "Executando…",
    "es-ES": "Ejecutando…",
  },
  min: { de: "min.", en: "min.", "pt-BR": "min.", "es-ES": "min." },

  // ── AccountManager ────────────────────────────────────────────────────
  accounts_title: { de: "Accounts", en: "Accounts", "pt-BR": "Contas", "es-ES": "Cuentas" },
  accounts_subtitle: {
    de: "Immich API Keys verwalten",
    en: "Manage Immich API Keys",
    "pt-BR": "Gerenciar Chaves de API do Immich",
    "es-ES": "Gestiona las claves de API de Immich",
  },
  account_add: {
    de: "Account hinzufügen",
    en: "Add Account",
    "pt-BR": "Adicionar Conta",
    "es-ES": "Añadir cuenta",
  },
  account_add_title: {
    de: "Account hinzufügen",
    en: "Add Account",
    "pt-BR": "Adicionar Conta",
    "es-ES": "Añadir cuenta",
  },
  account_remove_tip: {
    de: "Account entfernen",
    en: "Remove account",
    "pt-BR": "Remover Conta",
    "es-ES": "Eliminar cuenta",
  },
  account_remove_confirm: {
    de: (name: string) => `Account "${name}" wirklich entfernen?`,
    en: (name: string) => `Really remove account "${name}"?`,
    "pt-BR": (name: string) => `Certeza que deseja remover a conta "${name}"?`,
    "es-ES": (name: string) => `¿Seguro que quieres eliminar la cuenta "${name}"?`,
  },
  account_empty: {
    de: "Noch keine Accounts konfiguriert.",
    en: "No accounts configured yet.",
    "pt-BR": "Nenhuma conta configurada ainda.",
    "es-ES": "Todavía no hay ninguna cuenta configurada.",
  },
  account_empty_hint: {
    de: "Füge deinen ersten Immich-Account hinzu.",
    en: "Add your first Immich account.",
    "pt-BR": "Adicione sua primeira conta do Immich.",
    "es-ES": "Añade tu primera cuenta de Immich.",
  },
  account_name_ph: {
    de: "Name (z.B. Manu)",
    en: "Name (e.g. Manu)",
    "pt-BR": "Nome (ex. Manu)",
    "es-ES": "Nombre (p. ej., Manu)",
  },
  account_test: {
    de: "Teste Verbindung…",
    en: "Testing connection…",
    "pt-BR": "Testando conexão…",
    "es-ES": "Probando la conexión…",
  },
  account_add_btn: { de: "Hinzufügen", en: "Add", "pt-BR": "Adicionar", "es-ES": "Añadir" },
  account_edit: { de: "Bearbeiten", en: "Edit", "pt-BR": "Editar", "es-ES": "Editar" },
  account_edit_title: {
    de: "Account bearbeiten",
    en: "Edit Account",
    "pt-BR": "Editar Conta",
    "es-ES": "Editar cuenta",
  },
  account_save: { de: "Speichern", en: "Save", "pt-BR": "Salvar", "es-ES": "Guardar" },
  account_saving: {
    de: "Wird gespeichert…",
    en: "Saving…",
    "pt-BR": "Salvando…",
    "es-ES": "Guardando…",
  },
  account_color_label: { de: "Farbe", en: "Color", "pt-BR": "Cor", "es-ES": "Color" },
  account_api_key_unchanged: {
    de: "API-Key unverändert",
    en: "API key unchanged",
    "pt-BR": "Chave de API inalterada",
    "es-ES": "Clave de API sin cambios",
  },
  account_api_hint: {
    de: "Wo finde ich meinen API Key?",
    en: "Where do I find my API Key?",
    "pt-BR": "Onde encontro minha Chave de API?",
    "es-ES": "¿Dónde puedo encontrar mi clave de API?",
  },
  account_api_hint_body: {
    de: "Immich öffnen → Nutzermenü (oben rechts) → Account-Einstellungen → API Keys → Neuen Key erstellen",
    en: "Open Immich → User menu (top right) → Account Settings → API Keys → Create new key",
    "pt-BR":
      "Abra o Immich → Menu Usuário (topo na direita) → Configurações da Conta → Chaves de API → Criar nova chave",
    "es-ES":
      "Abre Immich → Menú de usuario (arriba a la derecha) → Configuración de la cuenta → Claves de API → Crear una clave nueva",
  },

  // ── PeopleGrid ────────────────────────────────────────────────────────
  people_title: { de: "Personen", en: "People", "pt-BR": "Pessoas", "es-ES": "Personas" },
  people_subtitle: {
    de: (total: number, named: number, unnamed: number) =>
      `${total} Personen aus allen Accounts · ${named} benannt · ${unnamed} unbekannt`,
    en: (total: number, named: number, unnamed: number) =>
      `${total} people from all accounts · ${named} named · ${unnamed} unknown`,
    "pt-BR": (total: number, named: number, unnamed: number) =>
      `${total} pessoas de todas as contas · ${named} nomeadas · ${unnamed} sem nome`,
    "es-ES": (total: number, named: number, unnamed: number) =>
      `${total} personas de todas las cuentas · ${named} con nombre · ${unnamed} desconocidas`,
  },
  filter_all: { de: "Alle", en: "All", "pt-BR": "Todos", "es-ES": "Todas" },
  filter_named: { de: "Benannt", en: "Named", "pt-BR": "Nomeado", "es-ES": "Con nombre" },
  filter_unnamed: { de: "Unbekannt", en: "Unknown", "pt-BR": "Sem nome", "es-ES": "Desconocidas" },
  people_empty: {
    de: "Keine Personen gefunden.",
    en: "No people found.",
    "pt-BR": "Nenhuma pessoa encontrada.",
    "es-ES": "No se ha encontrado ninguna persona.",
  },

  // ── MatchSuggestions ─────────────────────────────────────────────────
  matches_title: {
    de: "Match-Vorschläge",
    en: "Match Suggestions",
    "pt-BR": "Sugestões de Correspondência",
    "es-ES": "Sugerencias de coincidencias",
  },
  matches_subtitle: {
    de: (open: number, dismissed: number, high: number) =>
      `${open} offen · ${dismissed} abgelehnt · ${high} hochkonfident (≥85%)`,
    en: (open: number, dismissed: number, high: number) =>
      `${open} open · ${dismissed} dismissed · ${high} high confidence (≥85%)`,
    "pt-BR": (open: number, dismissed: number, high: number) =>
      `${open} abertos · ${dismissed} dispensados · ${high} alta confiança (≥85%)`,
    "es-ES": (open: number, dismissed: number, high: number) =>
      `${open} abiertas · ${dismissed} descartadas · ${high} de alta confianza (≥85 %)`,
  },
  bulk_sync: {
    de: (n: number) => `Bulk-Sync (${n})`,
    en: (n: number) => `Bulk Sync (${n})`,
    "pt-BR": (n: number) => `Sincronizar em Lote (${n})`,
    "es-ES": (n: number) => `Sincronización en lote (${n})`,
  },
  bulk_sync_confirm: {
    de: (n: number) => `Alle ${n} hochkonfidenten Matches synchronisieren?`,
    en: (n: number) => `Sync all ${n} high-confidence matches?`,
    "pt-BR": (n: number) => `Sincronizar todas as ${n} correspondências com alta confiança?`,
    "es-ES": (n: number) => `¿Sincronizar las ${n} coincidencias de alta confianza?`,
  },
  recalculate: {
    de: "Neu berechnen",
    en: "Recalculate",
    "pt-BR": "Recalcular",
    "es-ES": "Recalcular",
  },
  album_new: { de: "Neues Album", en: "New Album", "pt-BR": "Novo Álbum", "es-ES": "Álbum nuevo" },
  album_link_existing: {
    de: "Vorhandenes verknüpfen",
    en: "Link existing",
    "pt-BR": "Vínculo existente",
    "es-ES": "Vincular uno existente",
  },
  album_select_ph: {
    de: "— Album wählen —",
    en: "— Select album —",
    "pt-BR": "— Selecionar álbum —",
    "es-ES": "— Selecciona un álbum —",
  },
  album_new_desc: {
    de: "Neues Album wird erstellt, mit den beteiligten Accounts geteilt und Fotos automatisch hinzugefügt.",
    en: "New album will be created, shared with participating accounts, and photos added automatically.",
    "pt-BR":
      "Novo álbum será criado, compartilhado com as contas participantes, e fotos adicionadas automaticamente.",
    "es-ES":
      "Se creará un álbum nuevo, se compartirá con las cuentas participantes y se añadirán las fotos automáticamente.",
  },
  album_existing_desc: {
    de: "Bestehendes Album wird mit den beteiligten Accounts geteilt und fehlende Fotos werden ergänzt.",
    en: "Existing album will be shared with participating accounts and missing photos will be added.",
    "pt-BR":
      "Álbum existente será compartilhado com as contas participantes e fotos que faltam serão adicionadas.",
    "es-ES":
      "El álbum existente se compartirá con las cuentas participantes y se añadirán las fotos que falten.",
  },
  album_create_btn: {
    de: "Album erstellen",
    en: "Create album",
    "pt-BR": "Criar álbum",
    "es-ES": "Crear álbum",
  },
  album_link_btn: {
    de: "Album verknüpfen",
    en: "Link album",
    "pt-BR": "Vincular álbum",
    "es-ES": "Vincular álbum",
  },
  album_name_ph: {
    de: "Album-Name…",
    en: "Album name…",
    "pt-BR": "Nome do Álbum…",
    "es-ES": "Nombre del álbum…",
  },
  dismissed_label: {
    de: "Abgelehnt — nicht dieselbe Person",
    en: "Dismissed — not the same person",
    "pt-BR": "Descartado — não é a mesma pessoa",
    "es-ES": "Descartada — no es la misma persona",
  },
  restore: { de: "Wiederherstellen", en: "Restore", "pt-BR": "Restaurar", "es-ES": "Restaurar" },
  names_synced_ok: {
    de: "Namen synchronisiert!",
    en: "Names synced!",
    "pt-BR": "Nomes sincronizados!",
    "es-ES": "¡Nombres sincronizados!",
  },
  names_synced_partial: {
    de: "Teilweise fehlgeschlagen.",
    en: "Partially failed.",
    "pt-BR": "Falhou parcialmente.",
    "es-ES": "Se ha producido un error parcial.",
  },
  album_linked_ok: {
    de: "Album verbunden!",
    en: "Album linked!",
    "pt-BR": "Álbum vinculado!",
    "es-ES": "¡Álbum vinculado!",
  },
  album_linked_err: {
    de: "Fehler beim Erstellen.",
    en: "Error creating album.",
    "pt-BR": "Erro ao criar o álbum.",
    "es-ES": "Error al crear el álbum.",
  },
  album_refreshed_ok: {
    de: "Album aktualisiert!",
    en: "Album updated!",
    "pt-BR": "Álbum atualizado!",
    "es-ES": "¡Álbum actualizado!",
  },
  badge_names_synced: {
    de: "Namen sync",
    en: "Names synced",
    "pt-BR": "Nomes sincronizados",
    "es-ES": "Nombres sincronizados",
  },
  badge_album_linked: {
    de: "Album verbunden",
    en: "Album linked",
    "pt-BR": "Álbum vinculado",
    "es-ES": "Álbum vinculado",
  },
  canonical_name_ph: {
    de: "Gemeinsamer Name…",
    en: "Shared name…",
    "pt-BR": "Nome Compartilhado…",
    "es-ES": "Nombre compartido…",
  },
  sync_names_btn: {
    de: "Namen synchronisieren",
    en: "Sync names",
    "pt-BR": "Sincronizar nomes",
    "es-ES": "Sincronizar nombres",
  },
  sync_names_again: {
    de: "Namen erneut synchronisieren",
    en: "Re-sync names",
    "pt-BR": "Re-sincronizar nomes",
    "es-ES": "Volver a sincronizar los nombres",
  },
  album_update_btn: {
    de: "Album aktualisieren",
    en: "Update album",
    "pt-BR": "Atualizar álbum",
    "es-ES": "Actualizar álbum",
  },
  album_connect_btn: {
    de: "Album verbinden",
    en: "Link album",
    "pt-BR": "Vincular álbum",
    "es-ES": "Vincular álbum",
  },
  not_same_person: {
    de: "Nicht dieselbe Person",
    en: "Not the same person",
    "pt-BR": "Não é a mesma pessoa",
    "es-ES": "No es la misma persona",
  },
  filter_names_synced: {
    de: "Namen sync",
    en: "Names synced",
    "pt-BR": "Nomes sincronizados",
    "es-ES": "Nombres sincronizados",
  },
  filter_album_linked: {
    de: "Album verbunden",
    en: "Album linked",
    "pt-BR": "Álbum vinculado",
    "es-ES": "Álbum vinculado",
  },
  filter_dismissed: {
    de: "Abgelehnte",
    en: "Dismissed",
    "pt-BR": "Descartado",
    "es-ES": "Descartadas",
  },
  visible_of: {
    de: (v: number, t: number) => `${v} von ${t} Vorschlägen sichtbar`,
    en: (v: number, t: number) => `${v} of ${t} suggestions visible`,
    "pt-BR": (v: number, t: number) => `${v} de ${t} sugestões visíveis`,
    "es-ES": (visible: number, total: number) => `${visible} de ${total} sugerencias visibles`,
  },
  match_multi_account_hint: {
    de: 'Dieser Match ist Teil eines Albums mit mehr als 2 Accounts. Bitte Änderungen über "Alben" oder "Match erweitern" vornehmen.',
    en: 'This match is part of an album with more than 2 accounts. Please make changes via "Albums" or "Extend Match".',
    "pt-BR":
      'Esta correspondência faz parte de um álbum com mais de duas contas. Por favor, faça alterações via "Álbuns" ou "Estender Correspondência".',
    "es-ES":
      'Esta coincidencia forma parte de un álbum con más de 2 cuentas. Haz los cambios desde "Álbumes" o "Ampliar coincidencia".',
  },
  no_open_matches: {
    de: "Keine offenen Vorschläge.",
    en: "No open suggestions.",
    "pt-BR": "Sem sugestões abertas.",
    "es-ES": "No hay sugerencias abiertas.",
  },
  no_matches_filter: {
    de: "Kein Vorschlag passt zu den Filtern.",
    en: "No suggestion matches the filters.",
    "pt-BR": "Sem sugestões correspondentes aos filtros.",
    "es-ES": "Ninguna sugerencia coincide con los filtros.",
  },

  // ── AlbumsOverview ────────────────────────────────────────────────────
  albums_title: {
    de: "Verwaltete Alben",
    en: "Managed Albums",
    "pt-BR": "Álbuns Gerenciados",
    "es-ES": "Álbumes gestionados",
  },
  albums_subtitle: {
    de: (n: number) => `${n} ${n === 1 ? "Album" : "Alben"} mit automatischer Synchronisation`,
    en: (n: number) => `${n} album${n !== 1 ? "s" : ""} with automatic sync`,
    "pt-BR": (n: number) => `${n} ${n === 1 ? "álbum" : "álbuns"} com sincronismo automático`,
    "es-ES": (n: number) => `${n} ${n === 1 ? "álbum" : "álbumes"} con sincronización automática`,
  },
  sync_all: {
    de: "Alle synchronisieren",
    en: "Sync all",
    "es-ES": "Sincronizar todo",
    "pt-BR": "Sincronizar tudo",
  },
  linked_people: {
    de: "Verknüpfte Personen",
    en: "Linked people",
    "es-ES": "Personas vinculadas",
    "pt-BR": "Pessoas vinculadas",
  },
  last_sync: {
    de: (d: string) => `Letzter Sync: ${d}`,
    en: (d: string) => `Last sync: ${d}`,
    "pt-BR": (d: string) => `Último Sincronismo: ${d}`,
    "es-ES": (date: string) => `Última sincronización: ${date}`,
  },
  album_deleted_warn: {
    de: "Album wurde in Immich gelöscht. Eintrag hier entfernen?",
    en: "Album was deleted in Immich. Remove entry here?",
    "pt-BR": "O álbum foi apagado no Immich. Remover registro aqui?",
    "es-ES": "El álbum se ha eliminado de Immich. ¿Quieres eliminar esta entrada?",
  },
  sync_now: {
    de: "Jetzt synchronisieren",
    en: "Sync now",
    "pt-BR": "Sincronizar agora",
    "es-ES": "Sincronizar ahora",
  },
  remove_link: {
    de: "Verknüpfung entfernen",
    en: "Remove link",
    "pt-BR": "Remover vínculo",
    "es-ES": "Eliminar vínculo",
  },
  auto_sync_label: {
    de: "Auto-Sync",
    en: "Auto-Sync",
    "pt-BR": "Auto-Sincronismo",
    "es-ES": "Sincronización automática",
  },
  auto_sync_time: {
    de: "Uhrzeit (Serverzeit)",
    en: "Time (server time)",
    "pt-BR": "Hora (do servidor)",
    "es-ES": "Hora (hora del servidor)",
  },
  auto_sync_next: {
    de: (t: string, day: string) => `Nächster Sync: ${day} um ${t}`,
    en: (t: string, day: string) => `Next sync: ${day} at ${t}`,
    "pt-BR": (t: string, day: string) => `Próximo sincronismo: ${day} às ${t}`,
    "es-ES": (time: string, day: string) => `Próxima sincronización: ${day} a las ${time}`,
  },
  auto_sync_today: { de: "heute", en: "today", "pt-BR": "hoje", "es-ES": "hoy" },
  auto_sync_tomorrow: { de: "morgen", en: "tomorrow", "pt-BR": "amanhã", "es-ES": "mañana" },
  albums_empty: {
    de: "Noch keine verwalteten Alben.",
    en: "No managed albums yet.",
    "pt-BR": "Sem álbuns gerenciados ainda.",
    "es-ES": "Todavía no hay álbumes gestionados.",
  },
  albums_empty_hint: {
    de: "Erstelle ein Album über einen Match-Vorschlag oder Manuelles Matching.",
    en: "Create an album via a match suggestion or manual matching.",
    "pt-BR":
      "Crie um álbum por meio de uma sugestão de correspondência ou de uma correspondência manual.",
    "es-ES":
      "Crea un álbum desde una sugerencia de coincidencia o mediante una coincidencia manual.",
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
    "pt-BR": (name: string, n: number) =>
      n > 1
        ? `Remover ${n} registros do álbum "${name}"?\n\nO álbum no Immich será mantido, mas não haverá novos sincronismos.`
        : `Remover registros do álbum "${name}"?\n\nO álbum no Immich será mantido, mas não haverá novos sincronismos.`,
    "es-ES": (name: string, n: number) =>
      n > 1
        ? `¿Eliminar ${n} entradas del álbum "${name}"?\n\nEl álbum se conservará en Immich, pero dejará de sincronizarse.`
        : `¿Eliminar la entrada del álbum "${name}"?\n\nEl álbum se conservará en Immich, pero dejará de sincronizarse.`,
  },

  // ── SyncPanel ─────────────────────────────────────────────────────────
  log_subtitle: {
    de: (n: number) => `${n} Einträge (neueste zuerst)`,
    en: (n: number) => `${n} entries (newest first)`,
    "pt-BR": (n: number) => `${n} registros (novos primeiro)`,
    "es-ES": (n: number) => `${n} entradas (las más recientes primero)`,
  },
  log_empty: {
    de: "Noch keine Sync-Aktionen durchgeführt.",
    en: "No sync actions performed yet.",
    "pt-BR": "Sem ação de sincronismo executada ainda.",
    "es-ES": "Todavía no se ha realizado ninguna acción de sincronización.",
  },
  undo_tip: {
    de: "Rückgängig machen",
    en: "Undo action",
    "pt-BR": "Desfazer ação",
    "es-ES": "Deshacer acción",
  },
  log_clear: {
    de: "Log löschen",
    en: "Delete log",
    "pt-BR": "Excluir Log",
    "es-ES": "Eliminar registro",
  },
  log_clear_confirm: {
    de: "Sync-Log wirklich löschen?",
    en: "Really delete the sync log?",
    "pt-BR": "Excluir mesmo o Sync Log?",
    "es-ES": "¿Seguro que quieres eliminar el registro de sincronización?",
  },
  action_sync_names: {
    de: "Namen sync",
    en: "Name sync",
    "pt-BR": "Sincronização de nomes",
    "es-ES": "Sincronizar nombres",
  },
  action_create_album: {
    de: "Album erstellen",
    en: "Create album",
    "pt-BR": "Criar álbum",
    "es-ES": "Crear álbum",
  },
  action_undo_names: {
    de: "Undo Namen",
    en: "Undo names",
    "pt-BR": "Desfazer nomes",
    "es-ES": "Deshacer nombres",
  },
  action_share_album: {
    de: "Album teilen",
    en: "Share album",
    "pt-BR": "Compartilhar álbum",
    "es-ES": "Compartir álbum",
  },
  action_add_assets: {
    de: "Assets hinzufügen",
    en: "Add assets",
    "pt-BR": "Adicionar itens",
    "es-ES": "Añadir elementos",
  },
  action_refresh: {
    de: "Album aktualisieren",
    en: "Refresh album",
    "pt-BR": "Atualizar álbum",
    "es-ES": "Actualizar álbum",
  },
  action_link: {
    de: "Album verknüpfen",
    en: "Link album",
    "pt-BR": "Vincular álbum",
    "es-ES": "Vincular álbum",
  },

  // ── ExtendMatch ───────────────────────────────────────────────────────
  extend_title: {
    de: "Match erweitern",
    en: "Extend Match",
    "pt-BR": "Estender Correspondência",
    "es-ES": "Ampliar coincidencia",
  },
  extend_subtitle: {
    de: "Füge einen Account und eine Person zu einem bestehenden gemeinsamen Album hinzu.",
    en: "Add an account and person to an existing shared album.",
    "pt-BR": "Adicione uma conta e uma pessoa a um álbum compartilhado existente.",
    "es-ES": "Añade una cuenta y una persona a un álbum compartido existente.",
  },
  extend_pick_album: {
    de: "Album wählen",
    en: "Select album",
    "pt-BR": "Selecionar álbum",
    "es-ES": "Seleccionar álbum",
  },
  extend_pick_album_hint: {
    de: "Klicke auf ein Album um es auszuwählen.",
    en: "Click an album to select it.",
    "pt-BR": "Clique em um álbum para selecioná-lo.",
    "es-ES": "Haz clic en un álbum para seleccionarlo.",
  },
  extend_new_account: {
    de: "Neuer Account",
    en: "New account",
    "pt-BR": "Nova conta",
    "es-ES": "Cuenta nueva",
  },
  extend_new_person: {
    de: "Person auswählen",
    en: "Select person",
    "pt-BR": "Selecionar pessoa",
    "es-ES": "Seleccionar persona",
  },
  extend_sync_name: {
    de: "Namen synchronisieren",
    en: "Sync name",
    "pt-BR": "Sincronizar nome",
    "es-ES": "Sincronizar nombre",
  },
  extend_sync_name_hint: {
    de: (name: string) => `Person auf „${name}" umbenennen`,
    en: (name: string) => `Rename person to "${name}"`,
    "pt-BR": (name: string) => `Renomear pessoa para "${name}"`,
    "es-ES": (name: string) => `Cambiar el nombre de la persona a "${name}"`,
  },
  extend_submit: {
    de: "Zum Match hinzufügen",
    en: "Add to match",
    "pt-BR": "Adicionar à correspondência",
    "es-ES": "Añadir a la coincidencia",
  },
  extend_already_in: {
    de: "Bereits enthalten",
    en: "Already included",
    "pt-BR": "Já inserido",
    "es-ES": "Ya incluida",
  },
  extend_no_albums: {
    de: "Noch keine verwalteten Alben vorhanden. Erstelle zuerst ein Match.",
    en: "No managed albums yet. Create a match first.",
    "pt-BR": "Sem álbuns gerenciados ainda. Primeiro crie uma correspondência.",
    "es-ES": "Todavía no hay álbumes gestionados. Crea primero una coincidencia.",
  },
  extend_no_accounts: {
    de: "Alle konfigurierten Accounts sind bereits in diesem Match enthalten.",
    en: "All configured accounts are already in this match.",
    "pt-BR": "Todas as contas configuradas já estão nesta correspondência.",
    "es-ES": "Todas las cuentas configuradas ya están incluidas en esta coincidencia.",
  },
  extend_search_person: {
    de: "Person suchen…",
    en: "Search person…",
    "pt-BR": "Pesquisar pessoa…",
    "es-ES": "Buscar persona…",
  },
  manual_album_owner: {
    de: "Album-Besitzer",
    en: "Album owner",
    "pt-BR": "Proprietário do álbum",
    "es-ES": "Propietario del álbum",
  },
  manual_hint: {
    de: 'Nur für neue Matches über mehrere Accounts. Um eine Person zu einem bestehenden Match hinzuzufügen → "Match erweitern" verwenden.',
    en: 'For new matches across multiple accounts only. To add a person to an existing match → use "Extend Match".',
    "pt-BR":
      'Apenas para novas correspondências em múltiplas contas. Para adicionar uma pessoa a uma correspondência existente. → use "Estender Correspondência".',
    "es-ES":
      'Solo para coincidencias nuevas entre varias cuentas. Para añadir una persona a una coincidencia existente, usa "Ampliar coincidencia".',
  },

  // ── ManualMatch ───────────────────────────────────────────────────────
  manual_title: {
    de: "Manuelles Matching",
    en: "Manual Matching",
    "pt-BR": "Correspondência Manual",
    "es-ES": "Coincidencia manual",
  },
  manual_subtitle: {
    de: "Wähle für jeden konfigurierten Account die passende Person, vergib einen gemeinsamen Namen und erstelle optional ein geteiltes Album.",
    en: "Select the matching person for each configured account, assign a shared name, and optionally create a shared album.",
    "pt-BR":
      "Selecione a pessoa correspondente para cada conta configurada, atribua um nome compartilhado e, opcionalmente, crie um álbum compartilhado.",
    "es-ES":
      "Selecciona la persona correspondiente en cada cuenta configurada, asígnale un nombre compartido y, si quieres, crea un álbum compartido.",
  },
  manual_people: { de: "Personen", en: "People", "pt-BR": "Pessoas", "es-ES": "Personas" },
  account_select_ph: {
    de: "— Account wählen —",
    en: "— Select account —",
    "pt-BR": "— Selecionar conta —",
    "es-ES": "— Selecciona una cuenta —",
  },
  person_select_ph: {
    de: "— Person wählen —",
    en: "— Select person —",
    "pt-BR": "— Selecionar pessoa —",
    "es-ES": "— Selecciona una persona —",
  },
  person_unknown_ph: {
    de: (n: number) => `(unbekannt, ${n} Fotos)`,
    en: (n: number) => `(unknown, ${n} photos)`,
    "pt-BR": (n: number) => `(desconhecido, ${n} fotos)`,
    "es-ES": (n: number) => `(desconocida, ${n} fotos)`,
  },
  add_person: {
    de: "Person hinzufügen",
    en: "Add person",
    "pt-BR": "Adicionar pessoa",
    "es-ES": "Añadir persona",
  },
  shared_name: {
    de: "Gemeinsamer Name",
    en: "Shared name",
    "pt-BR": "Nome compartilhado",
    "es-ES": "Nombre compartido",
  },
  shared_name_ph: {
    de: "z. B. Max Mustermann",
    en: "e.g. Max Doe",
    "pt-BR": "ex. Neymar Jr",
    "es-ES": "p. ej., Ana García",
  },
  create_shared_album: {
    de: "Geteiltes Album erstellen",
    en: "Create shared album",
    "pt-BR": "Criar álbum compartilhado",
    "es-ES": "Crear álbum compartido",
  },
  album_name_label: {
    de: "Album-Name",
    en: "Album name",
    "pt-BR": "Nome do álbum",
    "es-ES": "Nombre del álbum",
  },
  run_btn: {
    de: "Namen sync + Album erstellen",
    en: "Sync names + create album",
    "pt-BR": "Sincronizar nomes + criar álbum",
    "es-ES": "Sincronizar nombres y crear álbum",
  },

  // ── FaceCompare ───────────────────────────────────────────────────────
  match_label: { de: "Match", en: "Match", "pt-BR": "Correspondência", "es-ES": "Coincidencia" },
  reason_name_similarity: {
    de: "Namensähnlichkeit",
    en: "Name similarity",
    "pt-BR": "Similaridade de nome",
    "es-ES": "Similitud del nombre",
  },
  reason_embedding_similarity: {
    de: "Gesichtserkennung",
    en: "Face recognition",
    "pt-BR": "Reconhecimento facial",
    "es-ES": "Reconocimiento facial",
  },
  reason_manual: { de: "Manuell", en: "Manual", "pt-BR": "Manual", "es-ES": "Manual" },
} as const satisfies Record<string, Record<Lang, unknown>>;

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

const logMessages: Record<string, Record<Lang, LogMessageFn>> = {
  log_album_members_fetch_failed: {
    de: () => "Album-Mitglieder konnten nicht abgerufen werden",
    en: () => "Could not fetch album members",
    "pt-BR": () => "Não foi possível recuperar os membros do álbum",
    "es-ES": () => "No se han podido obtener los miembros del álbum",
  },
  log_album_shared: {
    de: (p) => `Album '${p.album}' geteilt mit: ${p.names}`,
    en: (p) => `Album '${p.album}' shared with: ${p.names}`,
    "pt-BR": (p) => `Álbum '${p.album}' compartilhado com: ${p.names}`,
    "es-ES": (p) => `Álbum '${p.album}' compartido con: ${p.names}`,
  },
  log_share_failed: {
    de: (p) => `Sharing mit ${p.names} fehlgeschlagen`,
    en: (p) => `Sharing with ${p.names} failed`,
    "pt-BR": (p) => `Compartilhamento com ${p.names} falhou`,
    "es-ES": (p) => `No se ha podido compartir con ${p.names}`,
  },
  log_name_synced: {
    de: (p) => `Account '${p.account}' – person ${p.person} → '${p.name}'`,
    en: (p) => `Account '${p.account}' – person ${p.person} renamed to '${p.name}'`,
    "pt-BR": (p) => `Conta de '${p.account}' – pessoa ${p.person} renomeada para '${p.name}'`,
    "es-ES": (p) => `Cuenta '${p.account}' – persona ${p.person} renombrada como '${p.name}'`,
  },
  log_name_sync_failed: {
    de: (p) => `Account '${p.account}' – person ${p.person}`,
    en: (p) => `Account '${p.account}' – person ${p.person}`,
    "pt-BR": (p) => `Conta de '${p.account}' – pessoa ${p.person}`,
    "es-ES": (p) => `Cuenta '${p.account}' – persona ${p.person}`,
  },
  log_assets_added: {
    de: (p) => `${p.count} Assets von '${p.account}' hinzugefügt`,
    en: (p) => `${p.count} assets added from '${p.account}'`,
    "pt-BR": (p) => `${p.count} itens adicionados de '${p.account}'`,
    "es-ES": (p) => `${p.count} elementos añadidos desde '${p.account}'`,
  },
  log_assets_add_failed: {
    de: (p) => `Assets von '${p.account}' konnten nicht hinzugefügt werden`,
    en: (p) => `Could not add assets from '${p.account}'`,
    "pt-BR": (p) => `Não pode adicionar itens de '${p.account}'`,
    "es-ES": (p) => `No se han podido añadir los elementos de '${p.account}'`,
  },
  log_assets_partial_failure: {
    de: (p) =>
      `${p.count} Assets von '${p.account}' konnten nicht hinzugefügt werden (z. B. fehlende Berechtigung)`,
    en: (p) => `${p.count} assets from '${p.account}' could not be added (e.g. missing permission)`,
    "pt-BR": (p) =>
      `${p.count} itens de '${p.account}' não puderam ser adicionados (ex. falta de permissão)`,
    "es-ES": (p) =>
      `No se han podido añadir ${p.count} elementos de '${p.account}' (p. ej., por falta de permisos)`,
  },
  log_assets_linked: {
    de: (p) => `${p.count} Assets von '${p.account}' zu '${p.album}' hinzugefügt`,
    en: (p) => `${p.count} assets from '${p.account}' added to '${p.album}'`,
    "pt-BR": (p) => `${p.count} itens de '${p.account}' adicionados em '${p.album}'`,
    "es-ES": (p) => `${p.count} elementos de '${p.account}' añadidos a '${p.album}'`,
  },
  log_assets_link_failed: {
    de: (p) => `Assets von '${p.account}' fehlgeschlagen`,
    en: (p) => `Assets from '${p.account}' failed`,
    "pt-BR": (p) => `Itens de '${p.account}' falharam`,
    "es-ES": (p) => `Han fallado los elementos de '${p.account}'`,
  },
  log_assets_added_to_album: {
    de: (p) => `${p.count} neue Assets von '${p.account}' zum Album '${p.album}' hinzugefügt`,
    en: (p) => `${p.count} new assets from '${p.account}' added to album '${p.album}'`,
    "pt-BR": (p) => `${p.count} novos itens de '${p.account}' adicionados ao álbum '${p.album}'`,
    "es-ES": (p) => `${p.count} elementos nuevos de '${p.account}' añadidos al álbum '${p.album}'`,
  },
  log_album_not_found: {
    de: (p) => `Album '${p.album}' existiert nicht in Immich.`,
    en: (p) => `Album '${p.album}' does not exist in Immich.`,
    "pt-BR": (p) => `Álbum '${p.album}' não existe no Immich.`,
    "es-ES": (p) => `El álbum '${p.album}' no existe en Immich.`,
  },
  log_album_deleted: {
    de: (p) =>
      `Album '${p.album}' wurde in Immich gelöscht. Eintrag kann über die Alben-Übersicht entfernt werden.`,
    en: (p) =>
      `Album '${p.album}' was deleted in Immich. The entry can be removed via the Albums overview.`,
    "pt-BR": (p) =>
      `Álbum '${p.album}' foi apagado no Immich. O item pode ser removido através da visão geral dos álbuns.`,
    "es-ES": (p) =>
      `El álbum '${p.album}' se ha eliminado de Immich. La entrada puede eliminarse desde la vista de álbumes.`,
  },
  log_album_unreachable: {
    de: () => "Album nicht abrufbar",
    en: () => "Album could not be reached",
    "pt-BR": () => "Não foi possível acessar o álbum",
    "es-ES": () => "No se ha podido acceder al álbum",
  },
  log_owner_account_missing: {
    de: () => "Owner-Account nicht mehr vorhanden",
    en: () => "Owner account no longer exists",
    "pt-BR": () => "Conta do proprietário já não existe mais",
    "es-ES": () => "La cuenta propietaria ya no existe",
  },
  log_person_already_in_album: {
    de: (p) => `Person ${p.person} aus '${p.account}' ist bereits in Album '${p.album}' enthalten.`,
    en: (p) => `Person ${p.person} from '${p.account}' is already included in album '${p.album}'.`,
    "pt-BR": (p) =>
      `Pessoa ${p.person} da conta de '${p.account}' já está inserida no álbum '${p.album}'.`,
    "es-ES": (p) =>
      `La persona ${p.person} de '${p.account}' ya está incluida en el álbum '${p.album}'.`,
  },
  log_person_validation_failed: {
    de: (p) => `Person in '${p.account}' konnte nicht validiert werden`,
    en: (p) => `Person in '${p.account}' could not be validated`,
    "pt-BR": (p) => `Pessoa da conta de '${p.account}' não pode ser validada`,
    "es-ES": (p) => `No se ha podido validar la persona de '${p.account}'`,
  },
  log_album_assets_fetch_failed: {
    de: () => "Album-Assets konnten nicht abgerufen werden",
    en: () => "Could not fetch album assets",
    "pt-BR": () => "Não foi possível recuperar os itens do álbum",
    "es-ES": () => "No se han podido obtener los elementos del álbum",
  },
  log_no_new_assets_from_account: {
    de: (p) => `Keine neuen Assets von '${p.account}' (alle bereits im Album)`,
    en: (p) => `No new assets from '${p.account}' (all already in the album)`,
    "pt-BR": (p) => `Sem novos itens de '${p.account}' (todos já estão no álbum)`,
    "es-ES": (p) => `No hay elementos nuevos de '${p.account}' (todos están ya en el álbum)`,
  },
  log_rename_failed: {
    de: (p) => `Umbenennung in '${p.account}' fehlgeschlagen`,
    en: (p) => `Renaming in '${p.account}' failed`,
    "pt-BR": (p) => `Renomear na conta de '${p.account}' falhou`,
    "es-ES": (p) => `No se ha podido cambiar el nombre en '${p.account}'`,
  },
  log_album_created: {
    de: (p) => `Album '${p.album}' in '${p.account}' mit ${p.count} Assets erstellt`,
    en: (p) => `Album '${p.album}' created in '${p.account}' with ${p.count} assets`,
    "pt-BR": (p) => `Álbum '${p.album}' criado na conta de '${p.account}' com ${p.count} itens`,
    "es-ES": (p) => `Álbum '${p.album}' creado en '${p.account}' con ${p.count} elementos`,
  },
  log_album_create_failed: {
    de: (p) => `Album '${p.album}' konnte nicht erstellt werden`,
    en: (p) => `Album '${p.album}' could not be created`,
    "pt-BR": (p) => `Álbum '${p.album}' não pode ser criado`,
    "es-ES": (p) => `No se ha podido crear el álbum '${p.album}'`,
  },
  log_sync_failed: {
    de: (p) => `Sync von '${p.account}' fehlgeschlagen`,
    en: (p) => `Sync from '${p.account}' failed`,
    "pt-BR": (p) => `Sincronismo de '${p.account}' falhou`,
    "es-ES": (p) => `Ha fallado la sincronización desde '${p.account}'`,
  },
  log_no_new_assets: {
    de: (p) => `Album '${p.album}': Keine neuen Assets gefunden`,
    en: (p) => `Album '${p.album}': no new assets found`,
    "pt-BR": (p) => `álbum '${p.album}': nenhum novo item encontrado`,
    "es-ES": (p) => `Álbum '${p.album}': no se han encontrado elementos nuevos`,
  },
  log_undo_name_reverted: {
    de: (p) => `Name von Person ${p.person} in '${p.account}' auf '${p.name}' zurückgesetzt`,
    en: (p) => `Reverted person ${p.person} in '${p.account}' to '${p.name}'`,
    "pt-BR": (p) => `Revertido nome da pessoa ${p.person} de '${p.account}' para '${p.name}'`,
    "es-ES": (p) =>
      `El nombre de la persona ${p.person} de '${p.account}' se ha restablecido a '${p.name}'`,
  },
  log_undo_failed: {
    de: (p) => `Rückgängig machen für Person ${p.person} fehlgeschlagen`,
    en: (p) => `Undo failed for person ${p.person}`,
    "pt-BR": (p) => `Falha ao desfazer para pessoa ${p.person}`,
    "es-ES": (p) => `No se ha podido deshacer para la persona ${p.person}`,
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

/** Writes `lang` to `<html lang>`. Pulled out of the effect below into its
 *  own exported function so it can be unit-tested directly against a stub
 *  `document` (this repo has no jsdom) instead of only through a React
 *  effect that `renderToString` never runs. A no-op outside a browser (SSR,
 *  the test file's `renderToString` calls) rather than a DOM dependency. */
export function applyDocumentLang(lang: Lang): void {
  if (typeof document !== "undefined") {
    document.documentElement.lang = lang;
  }
}

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  // Lazy initializer: only the first render needs the stored value, not
  // every re-render. The matching `<html lang>` write for this initial value
  // happens synchronously in main.tsx, *before* this component ever mounts
  // (`applyDocumentLang(readStoredLang())` right before `createRoot(...)
  // .render(...)`) — so the very first frame already carries the right
  // attribute instead of correcting it after the fact.
  const [lang, setLangState] = useState<Lang>(() => readStoredLang());

  // `setLang` is the only place `lang` ever changes after mount, so it's
  // also the only place that needs to keep `<html lang>` in sync — a
  // `useEffect` that ran `applyDocumentLang(lang)` on every change used to
  // sit here instead, but nothing proved it was ever wired in: deleting the
  // effect outright left every test green (Fund 3/6). Calling
  // `applyDocumentLang` directly, in the same function that already writes
  // to storage, means there's exactly one synchronous write path — state,
  // storage, and the document attribute — instead of a passive effect that
  // runs after the first paint and that a test can silently lose.
  const setLang = (l: Lang) => {
    try {
      localStorage.setItem("ift_lang", l);
    } catch {
      // Storage blocked (private browsing, sandboxed iframe, ...): the
      // choice still applies for the running session, it just isn't
      // persisted across reloads.
    }
    applyDocumentLang(l);
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
