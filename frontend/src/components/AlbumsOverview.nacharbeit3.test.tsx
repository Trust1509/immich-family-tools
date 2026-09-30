// Nacharbeit 1 (Welle 4, S1, Basis 02822f7) — Albumkarte (#124/#102).
//
// Blindpruefer (mit Sonden) und Fremdpruefer hatten 02822f7 geprueft: die
// Zusage (g) "jeder gescheiterte Abgleich zeigt eine Fehlerzeile" war
// gebrochen (BLOCKER), (c) und (f) galten nur teilweise, und mehrere Zusagen
// waren durch keinen Test bewacht (Mutationen blieben GRUEN). Diese Datei
// deckt beides ab:
//
// - Jeder Ablauf aus den Sonden P1, P1b, P2, P3, P3b, P4, P5, P6, P7, P8, P9
//   des Blindpruefers (`…/blind/S1/sonde/…/AlbumsOverview.sonde.test.tsx`)
//   wird hier ein Test mit einer echten Erwartung (die Sonde selbst hat nur
//   GEMESSEN, nicht behauptet).
// - Die in WICHTIG 4 genannten, gruen gebliebenen Mutationen (M02, M03,
//   M03b, M08, M09, M11, M13, M13b, M20, M22, M25, M27, M29, M34) bekommen
//   je einen Test, der mit der genannten Aenderung ueber die GANZE Suite rot
//   wird.
//
// Alle Daten erfunden; das Repo ist oeffentlich.
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import AlbumsOverview from "./AlbumsOverview";
import { LanguageProvider, useT } from "../i18n";
import { SPEICHER_SCHLUESSEL } from "../test-konstanten";
import { ApiError } from "../api/client";

function album(overrides: Record<string, unknown>) {
  return {
    id: "album",
    match_id: "m",
    album_id: "immich",
    album_name: "Gruppe",
    group_id: "gruppe-1",
    owner_account_id: "konto",
    person_refs: [
      {
        account_id: "konto",
        person_id: "person-1",
        person_name: "Person Eins",
        account_name: "Konto Eins",
        account_color: "#111111",
      },
    ],
    linked_match_ids: [],
    created_at: "2026-01-01T00:00:00+00:00",
    last_synced_at: "2026-01-01T00:00:00+00:00",
    total_assets: 1,
    owner_account_missing: false,
    too_few_people: false,
    ...overrides,
  };
}

const { albenMock, autoSyncGet, refreshMock, renameMock, deleteMock } = vi.hoisted(() => ({
  albenMock: vi.fn(),
  autoSyncGet: vi.fn(),
  refreshMock: vi.fn(),
  renameMock: vi.fn(),
  deleteMock: vi.fn(),
}));

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    api: {
      sync: {
        albums: albenMock,
        refreshAlbum: refreshMock,
        deleteAlbum: deleteMock,
        renameAlbum: renameMock,
      },
      autoSync: { get: autoSyncGet, set: vi.fn() },
    },
  };
});

beforeEach(() => {
  vi.clearAllMocks();
  try {
    localStorage.setItem(SPEICHER_SCHLUESSEL, "de");
  } catch {
    /* in dieser Umgebung nicht zwingend vorhanden */
  }
  autoSyncGet.mockResolvedValue({ enabled: false, time: "01:00" });
  refreshMock.mockResolvedValue([]);
  renameMock.mockResolvedValue([
    { id: "l", timestamp: "", action: "rename_album", details: "", status: "success" },
  ]);
  deleteMock.mockResolvedValue(undefined);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function rendern(text: string) {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <LanguageProvider>
        <AlbumsOverview />
      </LanguageProvider>
    </QueryClientProvider>
  );
  await waitFor(() => expect(screen.getAllByText(text).length).toBeGreaterThan(0));
}

function knopf(name: RegExp) {
  return screen.getByRole("button", { name }) as HTMLButtonElement;
}
const schlaf = (ms: number) => new Promise((r) => setTimeout(r, ms));
async function bisFrei(name: RegExp) {
  await waitFor(() => expect(knopf(name).disabled).toBe(false));
  await schlaf(30);
}
function eintrag(details: string, id = details) {
  return {
    id,
    timestamp: "2026-01-01T00:00:00+00:00",
    action: "refresh_album",
    details,
    status: "success",
  };
}

const FEHL_1_1 = "1 von 1 Album konnte nicht abgeglichen werden.";
const FEHL_1_2 = "1 von 2 Alben konnte nicht abgeglichen werden.";
const FEHL_2_2 = "2 von 2 Alben konnten nicht abgeglichen werden.";
const FEHL_2_2_EN = "2 of 2 albums could not be synced.";

// ---------------------------------------------------------------------------
// BLOCKER (g): ein danach vollstaendig gescheiterter "Alle synchronisieren"
// bleibt ohne Fehlerzeile, wenn zuvor eine LOKALE Aktion lief. Sonden P1/P1b.
// ---------------------------------------------------------------------------

describe("BLOCKER (g, Sonde P1): Sammel-OK -> lokaler Abgleich -> Sammel-Totalausfall zeigt eine Fehlerzeile", () => {
  it("die dritte Aktion (Sammel-Totalausfall) zeigt '1 von 1 Album konnte nicht abgeglichen werden.'", async () => {
    albenMock.mockResolvedValue([album({ id: "a" })]);
    refreshMock.mockResolvedValueOnce([eintrag("Erster Lauf")]);
    await rendern("Gruppe");
    fireEvent.click(knopf(/Alle synchronisieren/i));
    await screen.findByText("Erster Lauf");
    await bisFrei(/Alle synchronisieren/i);

    refreshMock.mockResolvedValueOnce([eintrag("Lokaler Lauf")]);
    fireEvent.click(knopf(/Jetzt synchronisieren/i));
    await screen.findByText("Lokaler Lauf");
    await bisFrei(/Jetzt synchronisieren/i);

    refreshMock.mockRejectedValue(new Error("weg"));
    fireEvent.click(knopf(/Alle synchronisieren/i));
    await bisFrei(/Alle synchronisieren/i);

    expect(await screen.findByText(FEHL_1_1)).toBeTruthy();
  });
});

describe("BLOCKER (g, Sonde P1b): Umbenennen (lokal) -> Sammel-Totalausfall OHNE frueheren Sammellauf zeigt eine Fehlerzeile", () => {
  it("zeigt die Fehlerzeile, obwohl es nie einen vorigen guten Sammellauf gab (undefined -> undefined-Falle)", async () => {
    albenMock.mockResolvedValue([album({ id: "a" })]);
    renameMock.mockResolvedValue([{ ...eintrag("Umbenannt"), action: "rename_album" }]);
    await rendern("Gruppe");
    fireEvent.click(knopf(/Album umbenennen/i));
    const feld = await screen.findByDisplayValue("Gruppe");
    fireEvent.change(feld, { target: { value: "Neu" } });
    fireEvent.keyDown(feld, { key: "Enter" });
    await screen.findByText("Umbenannt");

    refreshMock.mockRejectedValue(new Error("weg"));
    fireEvent.click(knopf(/Alle synchronisieren/i));
    await bisFrei(/Alle synchronisieren/i);

    expect(await screen.findByText(FEHL_1_1)).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// WICHTIG 1 (g, Sonde P2): Gruppe wird zwischen zwei Sammellaeufen GANZ
// verwaist — der zweite Lauf (0 Anfragen) darf das voranstehende gute
// Ergebnis nicht kommentarlos loeschen, UND darf keine falsche Fehlerzeile
// erzeugen (bewusst dokumentiertes, unveraendertes Verhalten).
// ---------------------------------------------------------------------------

describe("WICHTIG 1 (g, Sonde P2): Gruppe inzwischen ganz verwaist -> zweiter Sammellauf", () => {
  it("laesst das vorige Ergebnis stehen und erzeugt keine Fehlerzeile fuer den 0-Anfragen-Lauf", async () => {
    albenMock.mockResolvedValueOnce([album({ id: "a" })]);
    albenMock.mockResolvedValue([album({ id: "a", owner_account_missing: true })]);
    refreshMock.mockResolvedValueOnce([eintrag("Erster Lauf")]);
    await rendern("Gruppe");
    fireEvent.click(knopf(/Alle synchronisieren/i));
    await screen.findByText("Erster Lauf");
    await bisFrei(/Alle synchronisieren/i);

    await waitFor(() => expect(knopf(/Jetzt synchronisieren/i).disabled).toBe(true));
    const aufrufeVorher = refreshMock.mock.calls.length;
    fireEvent.click(knopf(/Alle synchronisieren/i));
    await bisFrei(/Alle synchronisieren/i);

    expect(refreshMock.mock.calls.length).toBe(aufrufeVorher);
    expect(screen.getByText("Erster Lauf")).toBeTruthy();
    expect(screen.queryByText(FEHL_1_1)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// WICHTIG 2 (c, Sonde P3): eine Sammel-Fehlerzeile uebersteht neue Aktionen
// (Umbenennen, Entfernen) nicht mehr.
// ---------------------------------------------------------------------------

describe("WICHTIG 2 (c, Sonde P3): Sammel-Fehlerzeile wird von neuen Aktionen abgeloest", () => {
  it("Umbenennen-Fehlschlag und danach Entfernen-Teilausfall raeumen die Sammel-Fehlerzeile ab", async () => {
    albenMock.mockResolvedValue([
      album({ id: "a", owner_account_id: "konto-a" }),
      album({ id: "b", owner_account_id: "konto-b" }),
    ]);
    refreshMock.mockImplementation(async (id: string) => {
      if (id === "b") throw new Error("weg");
      return [eintrag("Eintrag a")];
    });
    await rendern("Gruppe");
    fireEvent.click(knopf(/Alle synchronisieren/i));
    await screen.findByText(FEHL_1_2);
    await bisFrei(/Alle synchronisieren/i);

    renameMock.mockRejectedValue(new ApiError("Serverfehler", 500, "err_internal"));
    fireEvent.click(knopf(/Album umbenennen/i));
    const feld = await screen.findByDisplayValue("Gruppe");
    fireEvent.change(feld, { target: { value: "Neu" } });
    fireEvent.keyDown(feld, { key: "Enter" });
    await screen.findByText("Serverfehler");

    // Der Umbenennen-Versuch ist die juengere Aktion — die stehende
    // Sammel-Fehlerzeile ist jetzt weg, auch wenn der Versuch selbst
    // scheitert.
    expect(screen.queryByText(FEHL_1_2)).toBeNull();

    fireEvent.click(knopf(/Abbrechen/i));
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );
    deleteMock.mockImplementation((id: string) =>
      id === "a" ? Promise.resolve() : Promise.reject(new ApiError("x", 500, "err_internal"))
    );
    fireEvent.click(knopf(/Verknüpfung entfernen/i));
    await screen.findByText("1 von 2 Einträgen konnte nicht entfernt werden.");

    expect(screen.queryByText(FEHL_1_2)).toBeNull();
  });
});

describe("WICHTIG 2 (c, Sonde P3b): ein neuer, haengender Sammellauf raeumt die ALTE Fehlerzeile beim START ab", () => {
  it("die Fehlerzeile des ersten Laufs ist waehrend des haengenden zweiten Laufs nicht mehr sichtbar", async () => {
    albenMock.mockResolvedValue([
      album({ id: "a", owner_account_id: "konto-a" }),
      album({ id: "b", owner_account_id: "konto-b" }),
    ]);
    refreshMock.mockImplementation(async (id: string) => {
      if (id === "b") throw new Error("weg");
      return [eintrag("Eintrag a")];
    });
    await rendern("Gruppe");
    fireEvent.click(knopf(/Alle synchronisieren/i));
    await screen.findByText(FEHL_1_2);
    await bisFrei(/Alle synchronisieren/i);

    let los: (() => void) | undefined;
    refreshMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          los = () => resolve([eintrag("Zweiter Lauf")]);
        })
    );
    fireEvent.click(knopf(/Alle synchronisieren/i));
    await waitFor(() => expect(los).toBeDefined());
    await schlaf(50);

    expect(screen.queryByText(FEHL_1_2)).toBeNull();

    // Aufraeumen: den haengenden Lauf ausloesen, damit der Test sauber endet.
    los?.();
    await schlaf(20);
    los?.();
    await bisFrei(/Alle synchronisieren/i);
  });
});

// ---------------------------------------------------------------------------
// WICHTIG 3 (f, Sonde P4): Nach einem echten Versuch ist jedes weitere Enter
// ein echter Versuch, auch wenn der Text wieder dem Oeffnungswert entspricht.
// ---------------------------------------------------------------------------

describe("WICHTIG 3 (f, Sonde P4): Nullvorgang gilt nur, solange noch kein Versuch lief", () => {
  it("Zuruecktippen auf den Oeffnungswert NACH einem gescheiterten Versuch ist ein echter Versuch, keine stille Nullaktion", async () => {
    albenMock.mockResolvedValueOnce([
      album({ id: "a", album_name: "A", owner_account_id: "konto-a" }),
      album({ id: "b", album_name: "A", owner_account_id: "konto-b" }),
    ]);
    albenMock.mockResolvedValue([
      album({ id: "a", album_name: "B", owner_account_id: "konto-a" }),
      album({ id: "b", album_name: "A", owner_account_id: "konto-b" }),
    ]);
    renameMock.mockImplementation(async (id: string) => {
      if (id === "b") throw new ApiError("Serverfehler", 500, "err_internal");
      return [{ ...eintrag("umbenannt a"), action: "rename_album" }];
    });
    await rendern("A");
    fireEvent.click(knopf(/Album umbenennen/i));
    const feld = await screen.findByDisplayValue("A");
    fireEvent.change(feld, { target: { value: "B" } });
    fireEvent.keyDown(feld, { key: "Enter" });
    await screen.findByText("Serverfehler");
    await waitFor(() => expect(albenMock.mock.calls.length).toBeGreaterThan(1));
    await schlaf(30);

    const feldOffen = screen.getByDisplayValue("B");
    renameMock.mockClear();
    renameMock.mockResolvedValue([
      { id: "l", timestamp: "", action: "rename_album", details: "", status: "success" },
    ]);
    fireEvent.change(feldOffen, { target: { value: "A" } });
    fireEvent.keyDown(feldOffen, { key: "Enter" });

    // VOR dieser Nacharbeit war das ein stiller Nullvorgang (kein Aufruf).
    // Jetzt ist es ein echter (zweiter) Versuch.
    await waitFor(() => expect(renameMock).toHaveBeenCalled());
    await waitFor(() => expect(screen.queryByText("Serverfehler")).toBeNull());
  });
});

// ---------------------------------------------------------------------------
// KLEIN (Sonde P5): Rand-Leerzeichen im Namen darf einen Nullvorgang nicht in
// einen echten Umbenennen-Versuch verwandeln.
// ---------------------------------------------------------------------------

describe("KLEIN (Sonde P5): Rand-Leerzeichen im Albumnamen", () => {
  it("'Urlaub ' + Enter ohne Aenderung bleibt ein Nullvorgang", async () => {
    albenMock.mockResolvedValue([album({ id: "a", album_name: "Urlaub " })]);
    await rendern("Urlaub");
    fireEvent.click(knopf(/Album umbenennen/i));
    const feld = (await screen.findAllByRole("textbox"))[0] as HTMLInputElement;
    expect(feld.value).toBe("Urlaub ");
    fireEvent.keyDown(feld, { key: "Enter" });
    await schlaf(30);

    expect(renameMock).not.toHaveBeenCalled();
    expect(screen.queryAllByRole("textbox").length).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// KLEIN (Sonde P6): Ein Nullvorgang loescht keine noch gueltige
// Abgleich-Fehlerzeile.
// ---------------------------------------------------------------------------

describe("KLEIN (Sonde P6): Nullvorgang laesst eine gueltige Abgleich-Fehlerzeile stehen", () => {
  it("Oeffnen und ein Enter ohne Aenderung raeumen die Fehlerzeile eines vorigen Abgleichs nicht ab", async () => {
    albenMock.mockResolvedValue([album({ id: "a" })]);
    refreshMock.mockRejectedValue(new Error("weg"));
    await rendern("Gruppe");
    fireEvent.click(knopf(/Jetzt synchronisieren/i));
    await screen.findByText(FEHL_1_1);

    fireEvent.click(knopf(/Album umbenennen/i));
    expect(screen.getByText(FEHL_1_1)).toBeTruthy();
    const feld = await screen.findByDisplayValue("Gruppe");
    fireEvent.keyDown(feld, { key: "Enter" });
    await schlaf(30);

    expect(renameMock).not.toHaveBeenCalled();
    expect(screen.getByText(FEHL_1_1)).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// KLEIN Punkt "h" (Sonde P7): waehrend ein Entfernen fuer diese Karte laeuft,
// darf ein offen gebliebenes Umbenennen-Feld nicht mehr per Enter feuern.
// ---------------------------------------------------------------------------

describe('KLEIN Punkt "h" (Sonde P7): Umbenennen ist waehrend eines haengenden Entfernens gesperrt', () => {
  it("Enter im offenen Feld loest waehrend eines haengenden Entfernens KEINEN Umbenennen-Aufruf aus", async () => {
    albenMock.mockResolvedValue([album({ id: "a" })]);
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );
    let freigeben: (() => void) | undefined;
    deleteMock.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          freigeben = () => resolve();
        })
    );
    await rendern("Gruppe");
    fireEvent.click(knopf(/Album umbenennen/i));
    const feld = (await screen.findByDisplayValue("Gruppe")) as HTMLInputElement;
    fireEvent.click(knopf(/Verknüpfung entfernen/i));
    await waitFor(() => expect(knopf(/Jetzt synchronisieren/i).disabled).toBe(true));

    fireEvent.change(feld, { target: { value: "Neu" } });
    fireEvent.keyDown(feld, { key: "Enter" });
    await schlaf(30);

    expect(renameMock).not.toHaveBeenCalled();
    expect(feld.disabled).toBe(true);

    freigeben?.();
    await waitFor(() => expect(deleteMock).toHaveBeenCalled());
  });
});

// ---------------------------------------------------------------------------
// Sonde P8: beide Ueberspringgruende gleichzeitig, korrekte (eingefrorene)
// Gesamtzahl aus GESUNDEN Alben — deckt zugleich M02 und M03b (Einfrieren mit
// `group.albums.length` statt `gesundeAlben.length`).
// ---------------------------------------------------------------------------

describe("Sonde P8 (+ WICHTIG 4: M02/M03b): beide Ueberspringgruende, Gesamtzahl aus GESUNDEN Alben", () => {
  it("nennt in BEIDEN Hinweisen 3 (gesundeAlben), nicht 4 (group.albums, inkl. des von ANFANG AN verwaisten Albums)", async () => {
    albenMock.mockResolvedValue([
      album({ id: "a", owner_account_id: "konto-a" }),
      album({ id: "b", owner_account_id: "konto-b" }),
      album({ id: "c", owner_account_id: "konto-c" }),
      album({ id: "v", owner_account_id: "konto-v", owner_account_missing: true }),
    ]);
    renameMock.mockImplementation(async (id: string) => {
      if (id === "b") throw new ApiError("x", 404, "err_owner_account_not_found");
      if (id === "c") throw new ApiError("x", 404, "err_managed_album_not_found");
      return [{ ...eintrag("ok a"), action: "rename_album" }];
    });
    await rendern("Gruppe");
    fireEvent.click(knopf(/Album umbenennen/i));
    const feld = await screen.findByDisplayValue("Gruppe");
    fireEvent.change(feld, { target: { value: "Neu" } });
    fireEvent.keyDown(feld, { key: "Enter" });
    await screen.findByText("ok a");

    expect(
      await screen.findByText(
        "Übersprungen, weil das Besitzerkonto inzwischen gelöscht ist: 1 von 3 Alben."
      )
    ).toBeTruthy();
    expect(
      await screen.findByText("Übersprungen, weil es inzwischen entfernt wurde: 1 von 3 Alben.")
    ).toBeTruthy();
    expect(screen.queryByText(/1 von 4/)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// WICHTIG 4: M03 — die "entfernt"-Gesamtzahl bleibt die des DURCHLAUFS, auch
// wenn die Liste danach neu laedt (Gegenprobe zu Fund A1, aber fuer die
// ANDERE der beiden Uebersprungen-Zahlen).
// ---------------------------------------------------------------------------

describe("WICHTIG 4: M03 — Gesamtzahl des Entfernt-Hinweises bleibt die des Durchlaufs", () => {
  it("nennt nach einem Neuladen weiterhin '1 von 3', nicht '1 von 2'", async () => {
    const drei = [
      album({ id: "a", album_name: "Drei", owner_account_id: "konto-a" }),
      album({ id: "b", album_name: "Drei", owner_account_id: "konto-b" }),
      album({ id: "c", album_name: "Drei", owner_account_id: "konto-c" }),
    ];
    albenMock.mockResolvedValueOnce(drei);
    // Nach dem Umbenennen liefert der Server b GAR NICHT mehr (ein anderer
    // Tab hat den Verwaltungseintrag waehrenddessen entfernt) — sowohl die
    // LIVE `gesundeAlben.length` (faellt auf 2) als auch `group.albums.length`
    // (faellt ebenfalls auf 2) waeren dieselbe FALSCHE Zahl; nur der
    // eingefrorene Wert bleibt bei 3.
    albenMock.mockResolvedValue([drei[0], drei[2]]);
    renameMock.mockImplementation(async (id: string) => {
      if (id === "b") {
        throw new ApiError("Verwaltetes Album nicht gefunden", 404, "err_managed_album_not_found");
      }
      return [
        { id: `log-${id}`, timestamp: "", action: "rename_album", details: "", status: "success" },
      ];
    });

    await rendern("Drei");
    fireEvent.click(knopf(/Album umbenennen/i));
    const feld = await screen.findByDisplayValue("Drei");
    fireEvent.change(feld, { target: { value: "Neuer Name" } });
    fireEvent.keyDown(feld, { key: "Enter" });

    await waitFor(() => expect(renameMock).toHaveBeenCalledTimes(3));
    await waitFor(() =>
      expect(
        screen.getByText("Übersprungen, weil es inzwischen entfernt wurde: 1 von 3 Alben.")
      ).toBeTruthy()
    );
    expect(screen.queryByText(/1 von 2 Alben/)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// WICHTIG 4: M08/M09 — `resetFremdeHinweise` raeumt WIRKLICH ALLE fuenf
// fremden Hinweise ab, auch die beiden, die bis hierher ungeprueft waren.
// ---------------------------------------------------------------------------

describe("WICHTIG 4: M08 — resetFremdeHinweise raeumt einen stehenden 'entfernt'-Hinweis ab", () => {
  it("ein Abgleich (Jetzt synchronisieren) nach einem teilweise 'entfernt'-uebersprungenen Umbenennen raeumt dessen Hinweis ab", async () => {
    albenMock.mockResolvedValue([
      album({ id: "a", owner_account_id: "konto-a" }),
      album({ id: "c", owner_account_id: "konto-c" }),
    ]);
    renameMock.mockImplementation(async (id: string) => {
      if (id === "c") throw new ApiError("x", 404, "err_managed_album_not_found");
      return [{ ...eintrag("ok a"), action: "rename_album" }];
    });
    await rendern("Gruppe");
    fireEvent.click(knopf(/Album umbenennen/i));
    const feld = await screen.findByDisplayValue("Gruppe");
    fireEvent.change(feld, { target: { value: "Neu" } });
    fireEvent.keyDown(feld, { key: "Enter" });
    await screen.findByText("Übersprungen, weil es inzwischen entfernt wurde: 1 von 2 Alben.");

    refreshMock.mockResolvedValue([]);
    fireEvent.click(knopf(/Jetzt synchronisieren/i));

    await waitFor(() =>
      expect(
        screen.queryByText("Übersprungen, weil es inzwischen entfernt wurde: 1 von 2 Alben.")
      ).toBeNull()
    );
  });
});

describe("WICHTIG 4: M09 — resetFremdeHinweise raeumt eine stehende Abgleich-Fehlerzeile ab", () => {
  it("ein Entfernen nach einem gescheiterten Einzelabgleich raeumt dessen Fehlerzeile ab", async () => {
    albenMock.mockResolvedValue([album({ id: "a" })]);
    refreshMock.mockRejectedValue(new Error("weg"));
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );
    await rendern("Gruppe");
    fireEvent.click(knopf(/Jetzt synchronisieren/i));
    await screen.findByText(FEHL_1_1);

    deleteMock.mockResolvedValue(undefined);
    fireEvent.click(knopf(/Verknüpfung entfernen/i));

    await waitFor(() => expect(screen.queryByText(FEHL_1_1)).toBeNull());
  });
});

// ---------------------------------------------------------------------------
// WICHTIG 4: M11 — ein ECHTER Umbenennen-Versuch raeumt eine stehende
// Abgleich-Fehlerzeile ab (anders als der Nullvorgang, siehe Sonde P6 oben).
// ---------------------------------------------------------------------------

describe("WICHTIG 4: M11 — ein echter Umbenennen-Versuch raeumt eine stehende Abgleich-Fehlerzeile ab", () => {
  it("Umbenennen MIT Aenderung raeumt die Fehlerzeile eines vorigen Abgleichs ab", async () => {
    albenMock.mockResolvedValue([album({ id: "a" })]);
    refreshMock.mockRejectedValue(new Error("weg"));
    await rendern("Gruppe");
    fireEvent.click(knopf(/Jetzt synchronisieren/i));
    await screen.findByText(FEHL_1_1);

    renameMock.mockResolvedValue([
      { id: "l", timestamp: "", action: "rename_album", details: "", status: "success" },
    ]);
    fireEvent.click(knopf(/Album umbenennen/i));
    const feld = await screen.findByDisplayValue("Gruppe");
    fireEvent.change(feld, { target: { value: "Neu" } });
    fireEvent.keyDown(feld, { key: "Enter" });

    await waitFor(() => expect(screen.queryByText(FEHL_1_1)).toBeNull());
  });
});

// ---------------------------------------------------------------------------
// WICHTIG 4: M13/M13b — ein ZWEITER echter Versuch (im selben, nie
// geschlossenen Feld) raeumt ALLE DREI fremden Umbenennen-Hinweise des
// ERSTEN Versuchs ab (renameError, renameSkipped, renameSkippedRemoved).
// ---------------------------------------------------------------------------

describe("WICHTIG 4: M13/M13b — ein zweiter echter Versuch raeumt renameError/renameSkipped/renameSkippedRemoved ab", () => {
  it("nach einem Versuch mit allen drei Ausfallarten raeumt ein erfolgreicher zweiter Versuch alle drei Hinweise ab", async () => {
    albenMock.mockResolvedValue([
      album({ id: "b", owner_account_id: "konto-b" }),
      album({ id: "d", owner_account_id: "konto-d" }),
      album({ id: "c", owner_account_id: "konto-c" }),
    ]);
    // Reihenfolge wichtig: b (uebersprungen, Konto weg) und d (uebersprungen,
    // entfernt) werden ERREICHT, BEVOR c hart wirft und die Schleife abbricht
    // — alle drei Hinweise stehen danach gleichzeitig.
    renameMock.mockImplementation(async (id: string) => {
      if (id === "b") throw new ApiError("x", 404, "err_owner_account_not_found");
      if (id === "d") throw new ApiError("x", 404, "err_managed_album_not_found");
      if (id === "c") throw new ApiError("Serverfehler", 500, "err_internal");
      throw new Error("unerwartet");
    });
    await rendern("Gruppe");
    fireEvent.click(knopf(/Album umbenennen/i));
    const feld = await screen.findByDisplayValue("Gruppe");
    fireEvent.change(feld, { target: { value: "Neu" } });
    fireEvent.keyDown(feld, { key: "Enter" });

    await screen.findByText("Serverfehler");
    expect(
      screen.getByText(
        "Übersprungen, weil das Besitzerkonto inzwischen gelöscht ist: 1 von 3 Alben."
      )
    ).toBeTruthy();
    expect(
      screen.getByText("Übersprungen, weil es inzwischen entfernt wurde: 1 von 3 Alben.")
    ).toBeTruthy();

    // Zweiter, erfolgreicher Versuch im SELBEN (nie geschlossenen) Feld.
    renameMock.mockReset();
    renameMock.mockResolvedValue([
      { id: "l", timestamp: "", action: "rename_album", details: "", status: "success" },
    ]);
    const feldNochOffen = screen.getByDisplayValue("Neu");
    fireEvent.keyDown(feldNochOffen, { key: "Enter" });

    await waitFor(() => expect(renameMock).toHaveBeenCalledTimes(3));
    await waitFor(() => expect(screen.queryByText("Serverfehler")).toBeNull());
    expect(
      screen.queryByText(
        "Übersprungen, weil das Besitzerkonto inzwischen gelöscht ist: 1 von 3 Alben."
      )
    ).toBeNull();
    expect(
      screen.queryByText("Übersprungen, weil es inzwischen entfernt wurde: 1 von 3 Alben.")
    ).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// WICHTIG 4: M20/M22 — der Vergleichswert des Nullvorgangs ist der beim
// OEFFNEN eingefrorene Wert, weder der (moeglicherweise inzwischen anders
// lautende) aktuelle Gruppenname noch ein beim MOUNT veralteter Wert.
// ---------------------------------------------------------------------------

describe("WICHTIG 4: M22 — der Oeffnen-Knopf friert den Vergleichswert bei JEDEM Oeffnen neu ein", () => {
  it("aendert sich der Gruppenname VOR dem Oeffnen, ist ein Enter ohne Aenderung trotzdem ein Nullvorgang", async () => {
    albenMock.mockResolvedValueOnce([album({ id: "a", album_name: "Alt" })]);
    albenMock.mockResolvedValue([album({ id: "a", album_name: "Neu" })]);
    refreshMock.mockResolvedValue([]);
    await rendern("Alt");

    // Ein erfolgreicher Abgleich loest eine Invalidierung/Refetch aus — der
    // Gruppenname aendert sich, BEVOR das Umbenennen-Feld je geoeffnet
    // wurde. Der `useState`-Anfangswert von `renameOpenedValue` (beim MOUNT
    // berechnet, also "Alt") darf NICHT mehr gelten.
    fireEvent.click(knopf(/Jetzt synchronisieren/i));
    await screen.findByText("Neu");

    fireEvent.click(knopf(/Album umbenennen/i));
    const feld = await screen.findByDisplayValue("Neu");
    fireEvent.keyDown(feld, { key: "Enter" });
    await schlaf(30);

    expect(renameMock).not.toHaveBeenCalled();
    expect(screen.queryByDisplayValue("Neu")).toBeNull();
  });
});

describe("WICHTIG 4: M20 — der Vergleichswert ist der Oeffnungswert, nicht der jeweils AKTUELLE Gruppenname", () => {
  it("aendert sich der Gruppenname WAEHREND das Feld offen ist, bleibt ein unveraendertes Enter trotzdem ein Nullvorgang", async () => {
    albenMock.mockResolvedValueOnce([
      album({ id: "a1", group_id: "gruppe-1", album_name: "Alt", owner_account_id: "konto-a1" }),
      album({ id: "a2", group_id: "gruppe-2", album_name: "G2", owner_account_id: "konto-a2" }),
    ]);
    albenMock.mockResolvedValue([
      album({ id: "a1", group_id: "gruppe-1", album_name: "Neu", owner_account_id: "konto-a1" }),
      album({ id: "a2", group_id: "gruppe-2", album_name: "G2", owner_account_id: "konto-a2" }),
    ]);
    refreshMock.mockResolvedValue([]);
    await rendern("Alt");
    await screen.findByText("G2");

    const karte1 = screen.getByText("Alt").closest(".card") as HTMLElement;
    const karte2 = screen.getByText("G2").closest(".card") as HTMLElement;

    // Feld auf Karte 1 oeffnen — `renameOpenedValue` friert JETZT "Alt" ein.
    fireEvent.click(within(karte1).getByRole("button", { name: /Album umbenennen/i }));
    const feld = await screen.findByDisplayValue("Alt");

    // Karte 2 loest einen Abgleich aus — der GETEILTE Cache
    // (`["managed-albums"]`) wird invalidiert und neu geladen: Karte 1 laedt
    // dabei "Neu" als AKTUELLEN Gruppennamen nach, auch wenn das nicht
    // sichtbar wird, solange das Umbenennen-Feld (mit seinem eigenen, davon
    // unabhaengigen lokalen Feldwert "Alt") offen ist.
    const aufrufeVorher = albenMock.mock.calls.length;
    const syncKnopf2 = within(karte2).getByRole("button", {
      name: /Jetzt synchronisieren/i,
    }) as HTMLButtonElement;
    fireEvent.click(syncKnopf2);
    await waitFor(() => expect(syncKnopf2.disabled).toBe(false));
    await waitFor(() => expect(albenMock.mock.calls.length).toBeGreaterThan(aufrufeVorher));
    await schlaf(30);
    expect((feld as HTMLInputElement).value).toBe("Alt");

    fireEvent.keyDown(feld, { key: "Enter" });
    await schlaf(30);

    expect(renameMock).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// WICHTIG 4: M25/M34 — die Gesamtzahl im Abgleichs-Fehlschlag ist die der
// GESUNDEN Alben, nicht aller Alben der Gruppe (inkl. eines Verwaisten).
// ---------------------------------------------------------------------------

describe("WICHTIG 4: M25 — Einzelabgleich nennt die Gesamtzahl der GESUNDEN Alben", () => {
  it("eine Gruppe mit einem gesunden und einem verwaisten Album zeigt '1 von 1 Album', nicht '1 von 2'", async () => {
    albenMock.mockResolvedValue([
      album({ id: "a", owner_account_id: "konto-a" }),
      album({ id: "v", owner_account_id: "konto-v", owner_account_missing: true }),
    ]);
    refreshMock.mockRejectedValue(new Error("weg"));
    await rendern("Gruppe");
    fireEvent.click(knopf(/Jetzt synchronisieren/i));

    expect(await screen.findByText(FEHL_1_1)).toBeTruthy();
    expect(screen.queryByText(/1 von 2 Alben/)).toBeNull();
  });
});

describe("WICHTIG 4: M34 — Sammelabgleich nennt die Gesamtzahl der GESUNDEN Alben", () => {
  it("eine Gruppe mit einem gesunden und einem verwaisten Album zeigt '1 von 1 Album', nicht '1 von 2'", async () => {
    albenMock.mockResolvedValue([
      album({ id: "a", owner_account_id: "konto-a" }),
      album({ id: "v", owner_account_id: "konto-v", owner_account_missing: true }),
    ]);
    refreshMock.mockRejectedValue(new Error("weg"));
    await rendern("Gruppe");
    fireEvent.click(knopf(/Alle synchronisieren/i));

    expect(await screen.findByText(FEHL_1_1)).toBeTruthy();
    expect(screen.queryByText(/1 von 2 Alben/)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// WICHTIG 4: M27 — eine LOKALE Fehlerzeile hat Vorrang vor einer stehenden
// SAMMEL-Fehlerzeile, auch wenn beide (zufaellig) denselben Wortlaut haetten.
// ---------------------------------------------------------------------------

describe("WICHTIG 4: M27 — eine lokale Fehlerzeile hat Vorrang vor der stehenden Sammel-Fehlerzeile", () => {
  it("nach Sammel-Totalausfall UND anschliessendem lokalen Teilausfall wird die LOKALE Zahl angezeigt", async () => {
    albenMock.mockResolvedValue([
      album({ id: "a", owner_account_id: "konto-a" }),
      album({ id: "b", owner_account_id: "konto-b" }),
    ]);
    refreshMock.mockRejectedValue(new Error("weg"));
    await rendern("Gruppe");
    fireEvent.click(knopf(/Alle synchronisieren/i));
    await screen.findByText(FEHL_2_2);
    await bisFrei(/Alle synchronisieren/i);

    refreshMock.mockImplementation(async (id: string) => {
      if (id === "b") throw new Error("weg");
      return [eintrag("Eintrag a (lokal)")];
    });
    fireEvent.click(knopf(/Jetzt synchronisieren/i));

    expect(await screen.findByText(FEHL_1_2)).toBeTruthy();
    expect(screen.queryByText(FEHL_2_2)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// WICHTIG 4 (urspruenglich M29): eine erfolgreiche Sammel-Wiederholung
// raeumt die Sammel-Fehlerzeile IHRER GRUPPE ab. Die urspruengliche Mutation
// (das `else { next.delete(...) }` je Gruppe in der Schleife) ist seit dem
// `setBulkSyncErrors(new Map())` am START jedes Laufs (WICHTIG 2, siehe
// `handleRefreshAll`) toter Code geworden — dieser Test bleibt trotzdem
// bestehen, weil er die SICHTBARE Zusage direkt prueft, unabhaengig vom
// Mechanismus dahinter.
// ---------------------------------------------------------------------------

describe("WICHTIG 4: ein erfolgreicher zweiter Sammellauf raeumt die Sammel-Fehlerzeile ab", () => {
  it("Totalausfall, dann Volltreffer: die Fehlerzeile ist danach weg", async () => {
    albenMock.mockResolvedValue([album({ id: "a" })]);
    refreshMock.mockRejectedValue(new Error("weg"));
    await rendern("Gruppe");
    fireEvent.click(knopf(/Alle synchronisieren/i));
    await screen.findByText(FEHL_1_1);
    await bisFrei(/Alle synchronisieren/i);

    refreshMock.mockResolvedValue([eintrag("Zweiter Lauf, ok")]);
    fireEvent.click(knopf(/Alle synchronisieren/i));
    await bisFrei(/Alle synchronisieren/i);

    expect(screen.queryByText(FEHL_1_1)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// KLEIN (Sprache, Sonde P9): die Sammel-Fehlerzeile ist Schluessel + Zahlen,
// nicht ein fertig gerenderter String — ein Sprachwechsel wirkt sofort.
// ---------------------------------------------------------------------------

function Umschalter() {
  const { setLang } = useT();
  return (
    <button type="button" onClick={() => setLang("en")}>
      NACH-EN
    </button>
  );
}

describe("KLEIN (Sonde P9): die Sammel-Fehlerzeile wechselt die Sprache mit", () => {
  it("nach dem Umschalten auf EN zeigt die Zeile die englische Uebersetzung, nicht mehr die deutsche", async () => {
    albenMock.mockResolvedValue([
      album({ id: "a", owner_account_id: "konto-a" }),
      album({ id: "b", owner_account_id: "konto-b" }),
    ]);
    refreshMock.mockRejectedValue(new Error("weg"));

    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <LanguageProvider>
          <Umschalter />
          <AlbumsOverview />
        </LanguageProvider>
      </QueryClientProvider>
    );
    await waitFor(() => expect(screen.getAllByText("Gruppe").length).toBeGreaterThan(0));
    fireEvent.click(knopf(/Alle synchronisieren/i));
    await screen.findByText(FEHL_2_2);
    await bisFrei(/Alle synchronisieren/i);

    fireEvent.click(screen.getByText("NACH-EN"));

    await waitFor(() => expect(screen.queryByText(FEHL_2_2)).toBeNull());
    expect(await screen.findByText(FEHL_2_2_EN)).toBeTruthy();
  });
});
