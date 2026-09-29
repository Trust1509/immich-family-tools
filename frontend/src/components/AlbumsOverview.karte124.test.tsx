// Bau-Brief S1 (Welle 4): Albumkarte — Hinweise, Totalausfall,
// Umbenennen-Nullvorgang (#124 Teil A + B11/B12, #102, #103 Punkt 5, #121
// Frontend-Rest). Diese Datei buendelt die Proben, die keine natuerliche
// Heimat in einer bestehenden Testdatei haben:
//
// - #124 Fund A3: `renameError` wird jetzt auch beim START von Abgleichen
//   und Entfernen zurueckgesetzt (bis hierher nur `deleteError` und
//   `renameSkipped`); Enter ohne Aenderung (der Nullvorgang aus Fund B11)
//   raeumt einen stehenden Fehler-/Uebersprungen-Hinweis mit weg.
// - #102: Ein (teilweise) gescheiterter Abgleich — einzeln oder im
//   Sammellauf — bekommt eine EIGENE Zeile, getrennt vom Protokoll; ein
//   Sammellauf, der fuer eine Gruppe komplett scheitert, loescht deren
//   voriges Ergebnis nicht mehr kommentarlos.
// - #121 (Nachlese #101, „Klein"-Punkt): „Jetzt synchronisieren" bleibt
//   nicht mehr bedienbar, waehrend ein Entfernen fuer dieselbe Karte laeuft.
//
// Alle Daten erfunden; das Repo ist oeffentlich.
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
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

// ---------------------------------------------------------------------------
// #124 Fund A1 (WICHTIG): die Gesamtzahl im Uebersprungen-Hinweis gehoert dem
// DURCHLAUF, nicht der beim Rendern aktuell geladenen Liste.
// ---------------------------------------------------------------------------

describe("#124 Fund A1: die Gesamtzahl im Hinweis bleibt die des DURCHLAUFS, auch wenn sich die Liste danach aendert", () => {
  it("nennt nach einem Neuladen weiterhin '1 von 3', nicht '1 von 2'", async () => {
    const drei = [
      album({ id: "a", album_name: "Drei", owner_account_id: "konto-a" }),
      album({ id: "b", album_name: "Drei", owner_account_id: "konto-b" }),
      album({ id: "c", album_name: "Drei", owner_account_id: "konto-c" }),
    ];
    albenMock.mockResolvedValueOnce(drei);
    // NACH dem Umbenennen (die Invalidierung im `finally` von `handleRename`
    // loest einen Refetch aus) liefert der Server b GAR NICHT mehr — der
    // Verwaltungseintrag wurde "in einem anderen Tab" waehrend des
    // Umbenennens entfernt. Sowohl `gesundeAlben.length` (faellt von 3 auf 2)
    // ALS AUCH `group.albums.length` (faellt ebenfalls von 3 auf 2, weil b
    // nicht nur verwaist, sondern ganz aus der Liste verschwunden ist)
    // wuerden dieselbe FALSCHE Zahl liefern — nur der eingefrorene Wert
    // bleibt bei 3.
    albenMock.mockResolvedValue([drei[0], drei[2]]);
    renameMock.mockImplementation(async (id: string) => {
      if (id === "b") {
        throw new ApiError("Owner-Account nicht gefunden", 404, "err_owner_account_not_found");
      }
      return [
        { id: `log-${id}`, timestamp: "", action: "rename_album", details: "", status: "success" },
      ];
    });

    await rendern("Drei");
    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/i }));
    const feld = await screen.findByDisplayValue("Drei");
    fireEvent.change(feld, { target: { value: "Neuer Name" } });
    fireEvent.keyDown(feld, { key: "Enter" });

    await waitFor(() => expect(renameMock).toHaveBeenCalledTimes(3));
    // Die Liste hat sich zwischenzeitlich geaendert — der Hinweis nennt
    // TROTZDEM weiter die Zahl DES DURCHLAUFS (1 von 3), nicht die aus der
    // neu geladenen Liste neu berechnete (1 von 2).
    await waitFor(() =>
      expect(
        screen.getByText(
          "Übersprungen, weil das Besitzerkonto inzwischen gelöscht ist: 1 von 3 Alben."
        )
      ).toBeTruthy()
    );
    expect(screen.queryByText(/1 von 2 Alben/)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// #124 Fund A2 (WICHTIG, Testluecke): Entfernen darf nur GENAU den Schluessel
// `err_managed_album_not_found` als Erfolg werten — nicht "irgendein 404".
// Die vorhandenen Proben zu Fund 1 (#123, Nacharbeit 2) decken nur den
// Schluesselvergleich gegen einen 500er ab; ein 404 OHNE Schluessel (Proxy,
// falsche Route) oder mit einem ANDEREN Schluessel war ungeprueft.
// ---------------------------------------------------------------------------

describe("#124 Fund A2: ein 404 zaehlt nur mit dem RICHTIGEN Schluessel als Erfolg", () => {
  it("Gruppen-Entfernen: ein 404 OHNE error_key zaehlt als Fehlschlag, nicht als Erfolg", async () => {
    const gruppe = [
      album({ id: "a", owner_account_id: "konto-a" }),
      album({ id: "b", owner_account_id: "konto-b" }),
    ];
    albenMock.mockResolvedValue(gruppe);
    deleteMock.mockImplementation((id: string) =>
      id === "a"
        ? Promise.resolve()
        : // 404 OHNE error_key — die Form, die `extractError` liefert, wenn
          // z. B. ein Proxy oder eine falsche Route dazwischenfunkt, ohne
          // dass unser eigener `errors.py` geantwortet hat.
          Promise.reject(new ApiError("Not Found", 404))
    );
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );

    await rendern("Gruppe");
    fireEvent.click(screen.getByRole("button", { name: /Verknüpfung entfernen/i }));

    await waitFor(() => expect(deleteMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("1 von 2 Einträgen konnte nicht entfernt werden.")).toBeTruthy();
  });

  it("Gruppen-Entfernen: ein 404 mit einem ANDEREN Schluessel zaehlt als Fehlschlag", async () => {
    const gruppe = [
      album({ id: "a", owner_account_id: "konto-a" }),
      album({ id: "b", owner_account_id: "konto-b" }),
    ];
    albenMock.mockResolvedValue(gruppe);
    deleteMock.mockImplementation((id: string) =>
      id === "a"
        ? Promise.resolve()
        : Promise.reject(new ApiError("Match nicht gefunden", 404, "err_match_not_found"))
    );
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );

    await rendern("Gruppe");
    fireEvent.click(screen.getByRole("button", { name: /Verknüpfung entfernen/i }));

    await waitFor(() => expect(deleteMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("1 von 2 Einträgen konnte nicht entfernt werden.")).toBeTruthy();
  });

  it("Einzel-Entfernen: ein 404 OHNE error_key zeigt die Fehlermeldung, statt stillschweigend als Erfolg zu gelten", async () => {
    const gruppe = [
      album({ id: "gesund", album_name: "Gemischt", owner_account_id: "konto-lebt" }),
      album({
        id: "verwaist",
        album_name: "Gemischt",
        owner_account_id: "konto-tot",
        owner_account_missing: true,
      }),
    ];
    albenMock.mockResolvedValue(gruppe);
    deleteMock.mockRejectedValue(new ApiError("Not Found", 404));
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );

    await rendern("Gemischt");
    fireEvent.click(screen.getByRole("button", { name: /Dieses verwaiste Album entfernen/i }));

    expect(
      await screen.findByText(
        'Eintrag für das verwaiste Album "Gemischt" konnte nicht entfernt werden.'
      )
    ).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// #124 Fund A3
// ---------------------------------------------------------------------------

describe("#124 Fund A3: renameError wird beim Start von Abgleichen/Entfernen zurueckgesetzt", () => {
  function zweiAlben() {
    return [
      album({ id: "a", owner_account_id: "konto-a" }),
      album({ id: "b", owner_account_id: "konto-b" }),
    ];
  }

  async function mitRenameError() {
    // Ein ANDERER Fehler als die beiden bekannten Ueberspringen-Gruende
    // bricht die Schleife ab und setzt `renameError` — das ist der stehende
    // Hinweis, den diese Proben pruefen.
    albenMock.mockResolvedValue(zweiAlben());
    renameMock.mockRejectedValue(new ApiError("Serverfehler", 500, "err_internal"));

    await rendern("Gruppe");
    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/i }));
    const feld = await screen.findByDisplayValue("Gruppe");
    fireEvent.change(feld, { target: { value: "Neuer Name" } });
    fireEvent.keyDown(feld, { key: "Enter" });

    expect(await screen.findByText("Serverfehler")).toBeTruthy();
  }

  it("Abgleichen (Jetzt synchronisieren) setzt einen stehenden renameError zurueck", async () => {
    await mitRenameError();
    refreshMock.mockResolvedValue([]);
    fireEvent.click(screen.getByRole("button", { name: /Jetzt synchronisieren/i }));

    await waitFor(() => expect(screen.queryByText("Serverfehler")).toBeNull());
  });

  it("Entfernen (Gruppe) setzt einen stehenden renameError zurueck", async () => {
    await mitRenameError();
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );
    deleteMock.mockResolvedValue(undefined);
    fireEvent.click(screen.getByRole("button", { name: /Verknüpfung entfernen/i }));

    await waitFor(() => expect(screen.queryByText("Serverfehler")).toBeNull());
  });
});

describe("#124 Fund A3: Enter ohne Aenderung (Nullvorgang, Fund B11) raeumt einen stehenden Uebersprungen-Hinweis weg", () => {
  // KLEIN (Welle 4, S1, Nacharbeit 2, LETZTE Runde): Der `it`-Titel nannte
  // bis hierher einen "fehlgeschlagenen Versuch", den dieser Test gar nicht
  // ausloest (kein Mock wirft hier) — er prueft den EINFACHEN no-op-Zweig
  // OHNE jeden vorherigen Versuch. Der Fall MIT vorherigem, uebersprungenem
  // Versuch steht im zweiten Test dieses `describe`-Blocks.
  it("Feld oeffnen und Enter OHNE jede Aenderung bleibt ein Nullvorgang (kein Server-Aufruf, Feld schliesst)", async () => {
    // Diese Probe zeigt den no-op-Zweig OHNE vorherigen Versuch: Feld
    // oeffnen, SOFORT (ohne zu tippen) Enter — das ist immer noch ein
    // echter Nullvorgang, unabhaengig vom weiteren Verlauf.
    const gruppe = [album({ id: "a", album_name: "Ausgangsname", owner_account_id: "konto-a" })];
    albenMock.mockResolvedValue(gruppe);

    await rendern("Ausgangsname");
    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/i }));
    const feld = await screen.findByDisplayValue("Ausgangsname");
    fireEvent.keyDown(feld, { key: "Enter" });

    await new Promise((r) => setTimeout(r, 10));
    expect(renameMock).not.toHaveBeenCalled();
    expect(screen.queryByDisplayValue("Ausgangsname")).toBeNull();
  });

  it("Nacharbeit 1 (#124, WICHTIG 3): NACH einem echten (ganz uebersprungenen) Versuch ist ein erneutes Enter mit demselben Text KEIN Nullvorgang mehr", async () => {
    // ZWEI Alben, BEIDE werden mit dem no-op-Namen (dem urspruenglich
    // geoeffneten Feldwert) uebersprungen — das Feld bleibt offen
    // (`logs.length` bleibt 0), der Hinweis steht. Das IST bereits ein
    // echter Versuch (es wurden zwei Netzwerkaufrufe gemacht), auch wenn
    // beide uebersprungen wurden.
    const gruppe = [
      album({ id: "a", album_name: "Ausgangsname", owner_account_id: "konto-a" }),
      album({ id: "b", album_name: "Ausgangsname", owner_account_id: "konto-b" }),
    ];
    albenMock.mockResolvedValue(gruppe);
    renameMock.mockRejectedValue(
      new ApiError("Owner-Account nicht gefunden", 404, "err_owner_account_not_found")
    );

    await rendern("Ausgangsname");
    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/i }));
    const feld = await screen.findByDisplayValue("Ausgangsname");
    fireEvent.change(feld, { target: { value: "Neuer Name" } });
    fireEvent.keyDown(feld, { key: "Enter" });

    await waitFor(() => expect(renameMock).toHaveBeenCalledTimes(2));
    expect(
      await screen.findByText(
        "Übersprungen, weil die zugehörigen Besitzerkonten inzwischen gelöscht sind: 2 von 2 Alben."
      )
    ).toBeTruthy();
    // Das Feld steht noch offen (kein Album wurde tatsaechlich umbenannt).
    const feldNochOffen = screen.getByDisplayValue("Neuer Name");

    // Nacharbeit 1 (#124, WICHTIG 3): Der Nutzer setzt den Feldwert zurueck
    // auf den Wert BEIM OEFFNEN und bestaetigt erneut. VOR dieser Nacharbeit
    // war das ein (stiller) Nullvorgang — genau die Luecke aus WICHTIG 3:
    // Nach einem bereits gelaufenen Versuch ist JEDES weitere Enter ein
    // ECHTER Versuch, unabhaengig vom Text. Diesmal gelingt er (der Server
    // nimmt "Ausgangsname" jetzt an), und das Feld schliesst ueber den
    // Erfolgspfad, nicht ueber einen stillen Nullvorgang.
    renameMock.mockClear();
    renameMock.mockResolvedValue([
      { id: "l", timestamp: "", action: "rename_album", details: "", status: "success" },
    ]);
    fireEvent.change(feldNochOffen, { target: { value: "Ausgangsname" } });
    fireEvent.keyDown(feldNochOffen, { key: "Enter" });

    await waitFor(() => expect(renameMock).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(
        screen.queryByText(
          "Übersprungen, weil die zugehörigen Besitzerkonten inzwischen gelöscht sind: 2 von 2 Alben."
        )
      ).toBeNull()
    );
    expect(screen.queryByDisplayValue("Neuer Name")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// #102: eigene Fehlerzeile fuer einen (teilweise) gescheiterten Abgleich
// ---------------------------------------------------------------------------

describe("#102: Einzelabgleich (Jetzt synchronisieren)", () => {
  it("Totalausfall (P2): zeigt eine eigene Fehlerzeile statt zu schweigen", async () => {
    albenMock.mockResolvedValue([album({ id: "a" })]);
    refreshMock.mockRejectedValue(new Error("Immich antwortet nicht"));

    await rendern("Gruppe");
    fireEvent.click(screen.getByRole("button", { name: /Jetzt synchronisieren/i }));

    // Wartet auf das ENDE des Vorgangs (Knopf wieder bedienbar), nicht nur
    // auf den Aufruf der Attrappe (`docs/agents/lehren.md` §44/§45).
    await waitFor(() =>
      expect(
        (screen.getByRole("button", { name: /Jetzt synchronisieren/i }) as HTMLButtonElement)
          .disabled
      ).toBe(false)
    );
    expect(await screen.findByText("1 von 1 Album konnte nicht abgeglichen werden.")).toBeTruthy();
  });

  it("Teilausfall: zeigt den gelungenen Eintrag UND die Fehlerzeile", async () => {
    albenMock.mockResolvedValue([
      album({ id: "a", owner_account_id: "konto-a" }),
      album({ id: "b", owner_account_id: "konto-b" }),
    ]);
    refreshMock.mockImplementation(async (albumId: string) => {
      if (albumId === "b") throw new Error("Immich antwortet nicht");
      return [
        {
          id: "log-a",
          timestamp: "2026-01-01T00:00:00+00:00",
          action: "refresh_album",
          details: "Eintrag a",
          status: "success",
        },
      ];
    });

    await rendern("Gruppe");
    fireEvent.click(screen.getByRole("button", { name: /Jetzt synchronisieren/i }));

    expect(await screen.findByText("Eintrag a")).toBeTruthy();
    expect(await screen.findByText("1 von 2 Alben konnte nicht abgeglichen werden.")).toBeTruthy();
  });
});

describe("#102: Sammelabgleich (Alle synchronisieren)", () => {
  it("P1 — zweiter Sammellauf mit Totalausfall loescht das erste Ergebnis NICHT kommentarlos und zeigt einen Hinweis", async () => {
    albenMock.mockResolvedValue([album({ id: "a" })]);
    refreshMock.mockResolvedValueOnce([
      {
        id: "log-1",
        timestamp: "2026-01-01T00:00:00+00:00",
        action: "refresh_album",
        details: "Erster Lauf",
        status: "success",
      },
    ]);

    await rendern("Gruppe");
    fireEvent.click(screen.getByRole("button", { name: /Alle synchronisieren/i }));
    expect(await screen.findByText("Erster Lauf")).toBeTruthy();

    // Zweiter Sammellauf: JEDER Aufruf wirft — vorher verschwand das Ergebnis
    // des ersten Laufs kommentarlos (Issue #102, P1).
    refreshMock.mockRejectedValue(new Error("Immich antwortet nicht"));
    fireEvent.click(screen.getByRole("button", { name: /Alle synchronisieren/i }));

    await waitFor(() =>
      expect(
        (screen.getByRole("button", { name: /Alle synchronisieren/i }) as HTMLButtonElement)
          .disabled
      ).toBe(false)
    );

    // Das VORIGE Ergebnis steht noch da...
    expect(screen.getByText("Erster Lauf")).toBeTruthy();
    // ...UND der Fehlschlag des zweiten Laufs ist sichtbar.
    expect(await screen.findByText("1 von 1 Album konnte nicht abgeglichen werden.")).toBeTruthy();
  });

  it("Teilausfall im Sammellauf: gelungene Eintraege UND Hinweis sind beide sichtbar", async () => {
    albenMock.mockResolvedValue([
      album({ id: "a", owner_account_id: "konto-a" }),
      album({ id: "b", owner_account_id: "konto-b" }),
    ]);
    refreshMock.mockImplementation(async (albumId: string) => {
      if (albumId === "b") throw new Error("Immich antwortet nicht");
      return [
        {
          id: "log-a",
          timestamp: "2026-01-01T00:00:00+00:00",
          action: "refresh_album",
          details: "Eintrag a (Sammellauf)",
          status: "success",
        },
      ];
    });

    await rendern("Gruppe");
    fireEvent.click(screen.getByRole("button", { name: /Alle synchronisieren/i }));

    expect(await screen.findByText("Eintrag a (Sammellauf)")).toBeTruthy();
    expect(await screen.findByText("1 von 2 Alben konnte nicht abgeglichen werden.")).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// #121 (Nachlese #101): „Jetzt synchronisieren" bleibt nicht bedienbar,
// solange ein Entfernen fuer dieselbe Karte laeuft.
// ---------------------------------------------------------------------------

describe("#121: Jetzt synchronisieren waehrend eines laufenden Entfernens", () => {
  it("ist gesperrt, solange das Entfernen dieser Gruppe haengt", async () => {
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
    fireEvent.click(screen.getByRole("button", { name: /Verknüpfung entfernen/i }));

    // Das Entfernen haengt (die Attrappe hat noch nicht aufgeloest) — der
    // Abgleichs-Knopf muss JETZT gesperrt sein.
    await waitFor(() =>
      expect(
        (screen.getByRole("button", { name: /Jetzt synchronisieren/i }) as HTMLButtonElement)
          .disabled
      ).toBe(true)
    );

    freigeben?.();
    await waitFor(() => expect(deleteMock).toHaveBeenCalled());
  });
});

// =============================================================================
// Welle 4, S1, Nacharbeit 2 (#124/#102, LETZTE Runde): Startnummer-Modell.
//
// Der Blindpruefer hatte 6fae875 widerlegt: Ein vollstaendig gescheiterter
// Sammellauf blieb ohne Fehlerzeile, wenn eine LOKALE Aktion VOR seinem Start
// begann und DANACH endete (`setLokalZuletzt(true)` erst am ENDE der lokalen
// Aktion). Die folgenden Tests sind die Ablaeufe der Sonden Q1-Q7
// (`…\blind\S1na1\sonde\…\AlbumsOverview.sonde.test.tsx`, die nur MASS, nicht
// BEHAUPTETE) mit echten Erwartungen, plus dedizierte Proben fuer die in
// Block 2 des Bau-Briefs genannten Testluecken (M02, M23, M24, M27*).
// =============================================================================

function eintrag124(details: string, id = details) {
  return {
    id,
    timestamp: "2026-01-01T00:00:00+00:00",
    action: "refresh_album",
    details,
    status: "success",
  };
}

const FEHL_1_1 = "1 von 1 Album konnte nicht abgeglichen werden.";
const FEHL_2_2 = "2 von 2 Alben konnten nicht abgeglichen werden.";
const FEHL_2_2_EN = "2 of 2 albums could not be synced.";

function knopf124(name: RegExp) {
  return screen.getByRole("button", { name }) as HTMLButtonElement;
}
const schlaf124 = (ms: number) => new Promise((r) => setTimeout(r, ms));
async function bisFrei124(name: RegExp) {
  await waitFor(() => expect(knopf124(name).disabled).toBe(false));
  await schlaf124(30);
}
function Umschalter124() {
  const { setLang } = useT();
  return (
    <button type="button" onClick={() => setLang("en")}>
      NACH-EN
    </button>
  );
}

describe("B1 Q1i: lokaler Abgleich haengt VOR dem Sammellauf-Start, endet NACH dessen Totalausfall", () => {
  it("die Sammel-Fehlerzeile bleibt stehen, auch wenn die AELTERE lokale Aktion zuletzt endet", async () => {
    albenMock.mockResolvedValue([album({ id: "a" })]);
    let lokalLos: (() => void) | undefined;
    refreshMock.mockImplementationOnce(
      () =>
        new Promise((r) => {
          lokalLos = () => r([eintrag124("Lokaler Lauf")]);
        })
    );
    await rendern("Gruppe");
    fireEvent.click(knopf124(/Jetzt synchronisieren/i));
    await waitFor(() => expect(lokalLos).toBeDefined());

    refreshMock.mockRejectedValue(new Error("weg"));
    fireEvent.click(knopf124(/Alle synchronisieren/i));
    await bisFrei124(/Alle synchronisieren/i);
    // Der Sammellauf (juenger, weil SPAETER GESTARTET) ist fertig und
    // gescheitert, WAEHREND der lokale Abgleich noch haengt.
    expect(screen.queryByText(FEHL_1_1)).toBeTruthy();

    lokalLos!();
    await screen.findByText("Lokaler Lauf");
    await schlaf124(30);
    // Der 6fae875-Bug: das Ende der AELTEREN lokalen Aktion ueberschrieb die
    // juengere Sammel-Fehlerzeile. Nach dem Fix bleibt sie stehen — die
    // STARTNUMMER entscheidet, nicht die Endzeit.
    expect(screen.queryByText(FEHL_1_1)).toBeTruthy();
  });
});

describe("B1 Q1ii: lokaler Abgleich endet ZUERST, Sammel-Totalausfall danach", () => {
  it("die Sammel-Fehlerzeile erscheint trotzdem, obwohl sie zeitlich NACH dem lokalen Ende eintrifft", async () => {
    albenMock.mockResolvedValue([album({ id: "a" })]);
    let lokalLos: (() => void) | undefined;
    let sammelWeg: (() => void) | undefined;
    refreshMock.mockImplementationOnce(
      () =>
        new Promise((r) => {
          lokalLos = () => r([eintrag124("Lokaler Lauf")]);
        })
    );
    refreshMock.mockImplementationOnce(
      () =>
        new Promise((_r, rej) => {
          sammelWeg = () => rej(new Error("weg"));
        })
    );
    await rendern("Gruppe");
    fireEvent.click(knopf124(/Jetzt synchronisieren/i));
    await waitFor(() => expect(lokalLos).toBeDefined());
    fireEvent.click(knopf124(/Alle synchronisieren/i));
    await waitFor(() => expect(sammelWeg).toBeDefined());

    // Der lokale Abgleich ist fertig, der Sammellauf haengt noch — solange
    // IRGENDEINE Aktion dieser Karte noch laeuft, zeigt `SyncLogDisplay`
    // weiter den Spinner statt eines Protokolls (unveraendertes `syncing`,
    // OR ueber lokal und extern); "Lokaler Lauf" ist deshalb hier noch NICHT
    // sichtbar — geprueft wird erst nach dem Ende beider Aktionen.
    lokalLos!();
    await schlaf124(30);
    expect(screen.queryByText(FEHL_1_1)).toBeNull();

    sammelWeg!();
    await bisFrei124(/Alle synchronisieren/i);
    expect(await screen.findByText(FEHL_1_1)).toBeTruthy();
    // Das juengste ERFOLGREICHE Protokoll bleibt der lokale Lauf — der
    // Sammellauf war ein Totalausfall, kein Erfolg.
    expect(screen.queryByText("Lokaler Lauf")).toBeTruthy();
  });
});

describe("B1 Q2: Sammellauf startet WAEHREND ein Umbenennen laeuft, faellt danach total aus", () => {
  it("die Sammel-Fehlerzeile erscheint, obwohl der Sammellauf NACH dem Umbenennen-Start begann", async () => {
    albenMock.mockResolvedValue([album({ id: "a" })]);
    let umLos: (() => void) | undefined;
    renameMock.mockImplementationOnce(
      () =>
        new Promise((r) => {
          umLos = () => r([{ ...eintrag124("Umbenannt"), action: "rename_album" }]);
        })
    );
    let sammelWeg: (() => void) | undefined;
    refreshMock.mockImplementationOnce(
      () =>
        new Promise((_r, rej) => {
          sammelWeg = () => rej(new Error("weg"));
        })
    );
    await rendern("Gruppe");
    fireEvent.click(knopf124(/Album umbenennen/i));
    const feld = await screen.findByDisplayValue("Gruppe");
    fireEvent.change(feld, { target: { value: "Neu" } });
    fireEvent.keyDown(feld, { key: "Enter" });
    await waitFor(() => expect(umLos).toBeDefined());

    fireEvent.click(knopf124(/Alle synchronisieren/i));
    await waitFor(() => expect(sammelWeg).toBeDefined());

    // Solange der Sammellauf noch haengt, zeigt die Karte den Spinner statt
    // eines Protokolls (`syncing` bleibt ueber lokal ODER extern wahr) — das
    // Umbenennen-Ergebnis wird deshalb erst NACH dem Sammellauf-Ende
    // geprueft, zusammen mit der Fehlerzeile.
    umLos!();
    await schlaf124(30);
    sammelWeg!();
    await bisFrei124(/Alle synchronisieren/i);

    expect(await screen.findByText(FEHL_1_1)).toBeTruthy();
    expect(screen.getByText("Umbenannt")).toBeTruthy();
  });
});

describe("W1 Q3: Sammel OK -> lokaler Abgleich OK -> Sammel-Totalausfall", () => {
  it("zeigt die Sammel-Fehlerzeile UND das juengste ERFOLGREICHE Protokoll (den lokalen, nicht den ersten Sammellauf)", async () => {
    // Begruendung (Bau-Brief Block 9, Frage 2): "juengstes ERFOLGREICHES
    // Protokoll" heisst nach STARTNUMMER, nicht nach Abschlusszeit — der
    // zweite Sammellauf startet zwar zuletzt, scheitert aber TOTAL (kein
    // Erfolg) und darf das juengere lokale Erfolgsprotokoll deshalb nicht
    // verdraengen. Waere "juengstes Protokoll" stattdessen als "das zuletzt
    // ABGESCHLOSSENE" definiert, wuerde ein Totalausfall (leeres Ergebnis)
    // das vorige Protokoll unbegruendet loeschen — das widerspraeche der
    // Projekt-Praemisse "nichts verschwindet still" (Bau-Brief Block 9,
    // Frage 11).
    albenMock.mockResolvedValue([album({ id: "a" })]);
    refreshMock.mockResolvedValueOnce([eintrag124("Erster Lauf")]);
    await rendern("Gruppe");
    fireEvent.click(knopf124(/Alle synchronisieren/i));
    await screen.findByText("Erster Lauf");
    await bisFrei124(/Alle synchronisieren/i);

    refreshMock.mockResolvedValueOnce([eintrag124("Lokaler Lauf")]);
    fireEvent.click(knopf124(/Jetzt synchronisieren/i));
    await screen.findByText("Lokaler Lauf");
    await bisFrei124(/Jetzt synchronisieren/i);

    refreshMock.mockRejectedValue(new Error("weg"));
    fireEvent.click(knopf124(/Alle synchronisieren/i));
    await bisFrei124(/Alle synchronisieren/i);

    expect(await screen.findByText(FEHL_1_1)).toBeTruthy();
    expect(screen.getByText("Lokaler Lauf")).toBeTruthy();
    expect(screen.queryByText("Erster Lauf")).toBeNull();
  });
});

describe("W1 Q3b: ein 0-Anfragen-Sammellauf verdraengt kein juengeres Protokoll", () => {
  it("Sammel OK -> Umbenennen macht die Gruppe ganz verwaist -> ein weiterer Sammellauf (0 Anfragen) laesst 'Umbenannt' stehen", async () => {
    albenMock.mockResolvedValue([album({ id: "a" })]);
    refreshMock.mockResolvedValueOnce([eintrag124("Erster Lauf")]);
    renameMock.mockResolvedValue([{ ...eintrag124("Umbenannt"), action: "rename_album" }]);
    await rendern("Gruppe");
    fireEvent.click(knopf124(/Alle synchronisieren/i));
    await screen.findByText("Erster Lauf");
    await bisFrei124(/Alle synchronisieren/i);

    albenMock.mockResolvedValue([
      album({ id: "a", album_name: "Neu", owner_account_missing: true }),
    ]);
    fireEvent.click(knopf124(/Album umbenennen/i));
    const feld = await screen.findByDisplayValue("Gruppe");
    fireEvent.change(feld, { target: { value: "Neu" } });
    fireEvent.keyDown(feld, { key: "Enter" });
    await screen.findByText("Umbenannt");
    await waitFor(() => expect(knopf124(/Jetzt synchronisieren/i).disabled).toBe(true));

    const aufrufeVorher = refreshMock.mock.calls.length;
    fireEvent.click(knopf124(/Alle synchronisieren/i));
    await bisFrei124(/Alle synchronisieren/i);

    // Der Sammellauf hat fuer diese (jetzt ganz verwaiste) Gruppe KEINE
    // Anfrage gestellt und zaehlt deshalb nicht fuer sie — er verdraengt
    // weder das Protokoll, noch erzeugt er eine Fehlerzeile.
    expect(refreshMock.mock.calls.length).toBe(aufrufeVorher);
    expect(screen.getByText("Umbenannt")).toBeTruthy();
    expect(screen.queryByText(FEHL_1_1)).toBeNull();
  });
});

// Nacharbeit-Fund (Mutationslauf dieser Runde): Der Test oben allein reicht
// nicht als Nachweis fuer "ein 0-Anfragen-Lauf zaehlt fuer die Karte NICHT" —
// er wird durch eine Mutation, die `betroffene`/die `continue`-Wache entfernt
// (der Sammellauf stempelt und beruehrt dann JEDE Gruppe, auch verwaiste),
// NICHT rot: Ein leeres Sammelergebnis aktualisiert `letztesProtokoll` schon
// wegen der eigenen "nicht-leer"-Bedingung nie, unabhaengig davon, ob es
// gezaehlt hat oder nicht — das Protokoll allein beweist die Nummer-Zaehlung
// nicht. Sichtbar wird der Unterschied erst an der FEHLERZEILE: zaehlt der
// 0-Anfragen-Lauf faelschlich, ueberholt seine Nummer eine STEHENDE lokale
// Fehlerzeile und blendet sie aus (`lokalGewinnt` kippt), obwohl er selbst
// nichts getan hat.
describe("W1 Q3b (Ergaenzung, Mutationslauf): ein 0-Anfragen-Sammellauf verdraengt auch keine lokale Fehlerzeile", () => {
  it("eine stehende lokale Abgleichs-Fehlerzeile bleibt sichtbar, wenn die Gruppe DANACH ganz verwaist und ein Sammellauf sie 0 Anfragen kostet", async () => {
    albenMock.mockResolvedValueOnce([
      album({ id: "a", owner_account_id: "konto-a" }),
      album({ id: "b", owner_account_id: "konto-b" }),
    ]);
    albenMock.mockResolvedValue([
      album({ id: "a", owner_account_id: "konto-a", owner_account_missing: true }),
      album({ id: "b", owner_account_id: "konto-b", owner_account_missing: true }),
    ]);
    refreshMock.mockImplementation(async (id: string) => {
      if (id === "b") throw new Error("weg");
      return [eintrag124("Eintrag a")];
    });
    await rendern("Gruppe");
    fireEvent.click(knopf124(/Jetzt synchronisieren/i));
    await screen.findByText("1 von 2 Alben konnte nicht abgeglichen werden.");
    // Der naechste Refetch (Invalidierung im `finally`) liefert die Gruppe
    // ganz verwaist zurueck.
    await waitFor(() => expect(knopf124(/Jetzt synchronisieren/i).disabled).toBe(true));

    const aufrufeVorher = refreshMock.mock.calls.length;
    fireEvent.click(knopf124(/Alle synchronisieren/i));
    await bisFrei124(/Alle synchronisieren/i);

    expect(refreshMock.mock.calls.length).toBe(aufrufeVorher);
    expect(screen.queryByText("1 von 2 Alben konnte nicht abgeglichen werden.")).toBeTruthy();
  });
});

describe("K2 Q4: lokaler Abgleich haengt NACH einem Sammel-Totalausfall", () => {
  it("die aeltere Sammel-Fehlerzeile ist waehrend des Haengens nicht mehr sichtbar", async () => {
    albenMock.mockResolvedValue([album({ id: "a" })]);
    refreshMock.mockRejectedValue(new Error("weg"));
    await rendern("Gruppe");
    fireEvent.click(knopf124(/Alle synchronisieren/i));
    await screen.findByText(FEHL_1_1);
    await bisFrei124(/Alle synchronisieren/i);

    let lokalLos: (() => void) | undefined;
    refreshMock.mockImplementationOnce(
      () =>
        new Promise((r) => {
          lokalLos = () => r([eintrag124("Lokal")]);
        })
    );
    fireEvent.click(knopf124(/Jetzt synchronisieren/i));
    await waitFor(() => expect(lokalLos).toBeDefined());
    await schlaf124(30);

    // Der lokale Abgleich ist jetzt die juengere (noch laufende) Aktion —
    // eine Fehlerzeile einer AELTEREN Aktion darf nicht mehr stehen
    // ("blendet aus", Bau-Brief §2 Richtung).
    expect(screen.queryByText(FEHL_1_1)).toBeNull();

    lokalLos!();
    await screen.findByText("Lokal");
  });
});

describe("W3/K3 Q6 (Mutation M28): Enter auf leerem Feld NACH einem gescheiterten Versuch", () => {
  it("schickt nichts an den Server und schliesst das Feld nicht still", async () => {
    albenMock.mockResolvedValue([album({ id: "a" })]);
    renameMock.mockRejectedValueOnce(new ApiError("Serverfehler", 500, "err_internal"));
    await rendern("Gruppe");
    fireEvent.click(knopf124(/Album umbenennen/i));
    const feld = await screen.findByDisplayValue("Gruppe");
    fireEvent.change(feld, { target: { value: "Neu" } });
    fireEvent.keyDown(feld, { key: "Enter" });
    await screen.findByText("Serverfehler");

    const aufrufeVorher = renameMock.mock.calls.length;
    const f2 = screen.getByDisplayValue("Neu");
    fireEvent.change(f2, { target: { value: "   " } });
    fireEvent.keyDown(f2, { key: "Enter" });

    expect(await screen.findByText("Bitte einen Namen eingeben.")).toBeTruthy();
    expect(renameMock.mock.calls.length).toBe(aufrufeVorher);
    // Das Feld bleibt offen — kein stiller Rueckfall auf den Anzeigetext.
    expect(screen.queryAllByRole("textbox").length).toBe(1);
  });
});

describe("Q5a: lokale Abgleich-Fehlerzeile wechselt die Sprache mit", () => {
  it("nach dem Umschalten auf EN zeigt die Zeile die englische Uebersetzung", async () => {
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
          <Umschalter124 />
          <AlbumsOverview />
        </LanguageProvider>
      </QueryClientProvider>
    );
    await waitFor(() => expect(screen.getAllByText("Gruppe").length).toBeGreaterThan(0));
    fireEvent.click(knopf124(/Jetzt synchronisieren/i));
    await screen.findByText(FEHL_2_2);

    fireEvent.click(screen.getByText("NACH-EN"));
    await waitFor(() => expect(screen.queryByText(FEHL_2_2)).toBeNull());
    expect(await screen.findByText(FEHL_2_2_EN)).toBeTruthy();
  });
});

describe("Q5b: Entfernen-Teilausfall-Zeile wechselt die Sprache mit", () => {
  it("nach dem Umschalten auf EN zeigt die Zeile die englische Uebersetzung", async () => {
    albenMock.mockResolvedValue([
      album({ id: "a", owner_account_id: "konto-a" }),
      album({ id: "b", owner_account_id: "konto-b" }),
    ]);
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );
    deleteMock.mockImplementation((id: string) =>
      id === "a" ? Promise.resolve() : Promise.reject(new ApiError("x", 500, "err_internal"))
    );
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <LanguageProvider>
          <Umschalter124 />
          <AlbumsOverview />
        </LanguageProvider>
      </QueryClientProvider>
    );
    await waitFor(() => expect(screen.getAllByText("Gruppe").length).toBeGreaterThan(0));
    fireEvent.click(knopf124(/Verknüpfung entfernen/i));
    await screen.findByText("1 von 2 Einträgen konnte nicht entfernt werden.");

    fireEvent.click(screen.getByText("NACH-EN"));
    await waitFor(() =>
      expect(screen.queryByText("1 von 2 Einträgen konnte nicht entfernt werden.")).toBeNull()
    );
    expect(await screen.findByText("1 of 2 entries could not be removed.")).toBeTruthy();
  });
});

describe("Q7: mehrere Karten — ein neuer Sammellauf raeumt Hinweise ALLER betroffenen Karten beim START", () => {
  it("Karte A haengt in der Sammelschleife, Karte B's Umbenennen-Fehler verschwindet trotzdem sofort beim Sammel-Start", async () => {
    albenMock.mockResolvedValue([
      album({ id: "a1", group_id: "g-a", album_name: "Karte A", owner_account_id: "k1" }),
      album({ id: "a2", group_id: "g-a", album_name: "Karte A", owner_account_id: "k2" }),
      album({ id: "b1", group_id: "g-b", album_name: "Karte B", owner_account_id: "k3" }),
    ]);
    await rendern("Karte A");
    renameMock.mockRejectedValue(new ApiError("Serverfehler B", 500, "err_internal"));
    const knoepfe = screen.getAllByRole("button", { name: /Album umbenennen/i });
    fireEvent.click(knoepfe[1]);
    const feld = await screen.findByDisplayValue("Karte B");
    fireEvent.change(feld, { target: { value: "B neu" } });
    fireEvent.keyDown(feld, { key: "Enter" });
    await screen.findByText("Serverfehler B");

    let aLos: (() => void) | undefined;
    refreshMock.mockImplementation((id: string) => {
      if (id === "a1")
        return new Promise((_r, rej) => {
          aLos = () => rej(new Error("weg"));
        });
      if (id === "a2") return Promise.reject(new Error("weg"));
      return Promise.resolve([eintrag124("B ok " + id)]);
    });
    fireEvent.click(knopf124(/Alle synchronisieren/i));
    await waitFor(() => expect(aLos).toBeDefined());
    await schlaf124(20);

    // Karte B ist in der sequenziellen Sammel-Schleife noch gar nicht an der
    // Reihe (sie haengt bei a1 fest) — ihr STEHENDER Umbenennen-Fehler ist
    // trotzdem schon weg: der Sammellauf stempelt ALLE betroffenen Karten
    // synchron beim eigenen START (Testluecken M02/M27* dieser Runde).
    expect(screen.queryByText("Serverfehler B")).toBeNull();

    aLos!();
    await bisFrei124(/Alle synchronisieren/i);

    expect(await screen.findByText("B ok b1")).toBeTruthy();
  });
});

describe("Testluecke M23/M24 (Nacharbeit 2): ein Nullvorgang vergibt KEINE neue Startnummer", () => {
  it("ein unveraendertes ODER ein leeres Enter VOR dem ersten Versuch verdraengt keine stehende Sammel-Fehlerzeile", async () => {
    albenMock.mockResolvedValue([album({ id: "a" })]);
    refreshMock.mockRejectedValue(new Error("weg"));
    await rendern("Gruppe");
    fireEvent.click(knopf124(/Alle synchronisieren/i));
    await screen.findByText(FEHL_1_1);
    await bisFrei124(/Alle synchronisieren/i);

    fireEvent.click(knopf124(/Album umbenennen/i));
    const feld = await screen.findByDisplayValue("Gruppe");
    fireEvent.keyDown(feld, { key: "Enter" });
    await schlaf124(20);
    expect(renameMock).not.toHaveBeenCalled();
    expect(screen.queryByText(FEHL_1_1)).toBeTruthy();

    fireEvent.click(knopf124(/Album umbenennen/i));
    const feld2 = await screen.findByDisplayValue("Gruppe");
    fireEvent.change(feld2, { target: { value: "   " } });
    fireEvent.keyDown(feld2, { key: "Enter" });
    await schlaf124(20);
    expect(renameMock).not.toHaveBeenCalled();
    expect(screen.queryByText(FEHL_1_1)).toBeTruthy();
  });
});

describe("Testluecke M27/M27b (Nacharbeit 2): ein neuer Sammellauf raeumt einen stehenden deleteError ab", () => {
  it("deleteError verschwindet, sobald ein neuer Sammellauf fuer dieselbe Karte startet", async () => {
    albenMock.mockResolvedValue([
      album({ id: "a", owner_account_id: "konto-a" }),
      album({ id: "b", owner_account_id: "konto-b" }),
    ]);
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );
    deleteMock.mockImplementation((id: string) =>
      id === "a" ? Promise.resolve() : Promise.reject(new ApiError("x", 500, "err_internal"))
    );
    await rendern("Gruppe");
    fireEvent.click(knopf124(/Verknüpfung entfernen/i));
    await screen.findByText("1 von 2 Einträgen konnte nicht entfernt werden.");

    refreshMock.mockResolvedValue([]);
    fireEvent.click(knopf124(/Alle synchronisieren/i));

    await waitFor(() =>
      expect(screen.queryByText("1 von 2 Einträgen konnte nicht entfernt werden.")).toBeNull()
    );
  });
});

// Nacharbeit-Fund (Mutationslauf dieser Runde): `renameErrorText`,
// `renameSkipped`/`renameSkippedRemoved` und `renameEmptyHint` haengen an
// FUENF UNABHAENGIGEN JSX-Bedingungen, nicht an einem gemeinsamen Codepfad —
// eine fruehere Fassung dieses Kommentars behauptete das Gegenteil (falsch,
// siehe Bau-Brief Block 9, Frage 6 "jede Behauptung belegt oder als Annahme
// markiert"). Der Mutationslauf entfernte `lokalGewinnt &&` einzeln aus jeder
// der fuenf Zeilen: `renameErrorText` und `deleteErrorText` wurden von
// bestehenden Tests aufgefangen (Q7 oben bzw. der Test direkt darueber),
// `renameSkipped`/`renameSkippedRemoved`/`renameEmptyHint` blieben GRUEN —
// die drei folgenden Tests schliessen genau diese Luecke.
describe("Testluecke (Nacharbeit 2, Mutationslauf): ein neuer Sammellauf raeumt renameSkipped/renameSkippedRemoved ab", () => {
  it("beide Umbenennen-Uebersprungen-Hinweise verschwinden, sobald ein neuer Sammellauf fuer dieselbe Karte startet", async () => {
    albenMock.mockResolvedValue([
      album({ id: "a", owner_account_id: "konto-a" }),
      album({ id: "b", owner_account_id: "konto-b" }),
    ]);
    renameMock.mockImplementation(async (id: string) => {
      if (id === "a") throw new ApiError("x", 404, "err_owner_account_not_found");
      throw new ApiError("x", 404, "err_managed_album_not_found");
    });
    await rendern("Gruppe");
    fireEvent.click(knopf124(/Album umbenennen/i));
    const feld = await screen.findByDisplayValue("Gruppe");
    fireEvent.change(feld, { target: { value: "Neu" } });
    fireEvent.keyDown(feld, { key: "Enter" });
    await screen.findByText(/Besitzerkonto inzwischen gel/);
    await screen.findByText(/inzwischen entfernt wurde/);

    refreshMock.mockResolvedValue([]);
    fireEvent.click(knopf124(/Alle synchronisieren/i));

    await waitFor(() => expect(screen.queryByText(/Besitzerkonto inzwischen gel/)).toBeNull());
    await waitFor(() => expect(screen.queryByText(/inzwischen entfernt wurde/)).toBeNull());
  });
});

describe("Testluecke (Nacharbeit 2, Mutationslauf): ein neuer Sammellauf raeumt einen stehenden renameEmptyHint ab", () => {
  it("der Hinweis 'Bitte einen Namen eingeben.' verschwindet, sobald ein neuer Sammellauf fuer dieselbe Karte startet", async () => {
    albenMock.mockResolvedValue([album({ id: "a" })]);
    renameMock.mockRejectedValueOnce(new ApiError("Serverfehler", 500, "err_internal"));
    await rendern("Gruppe");
    fireEvent.click(knopf124(/Album umbenennen/i));
    const feld = await screen.findByDisplayValue("Gruppe");
    fireEvent.change(feld, { target: { value: "Neu" } });
    fireEvent.keyDown(feld, { key: "Enter" });
    await screen.findByText("Serverfehler");

    const f2 = screen.getByDisplayValue("Neu");
    fireEvent.change(f2, { target: { value: "   " } });
    fireEvent.keyDown(f2, { key: "Enter" });
    await screen.findByText("Bitte einen Namen eingeben.");

    refreshMock.mockResolvedValue([]);
    fireEvent.click(knopf124(/Alle synchronisieren/i));

    await waitFor(() => expect(screen.queryByText("Bitte einen Namen eingeben.")).toBeNull());
  });
});

describe("Testluecke M17 (Mutationslauf): ein neues Oeffnen setzt 'schon ein Versuch gelaufen' zurueck", () => {
  it("nach Abbrechen und Neu-Oeffnen ist ein unveraendertes Enter wieder ein Nullvorgang (kein Server-Aufruf)", async () => {
    albenMock.mockResolvedValue([album({ id: "a" })]);
    renameMock.mockRejectedValueOnce(new ApiError("x", 404, "err_owner_account_not_found"));
    await rendern("Gruppe");
    fireEvent.click(knopf124(/Album umbenennen/i));
    const feld = await screen.findByDisplayValue("Gruppe");
    fireEvent.change(feld, { target: { value: "Neu" } });
    fireEvent.keyDown(feld, { key: "Enter" });
    await screen.findByText(/Besitzerkonto inzwischen gel/);

    // Abbrechen (X) und das Feld NEU oeffnen — eine frische Session, in der
    // "schon ein Versuch gelaufen" (`renameAttempted`) wieder `false` sein
    // muss, sonst waere ein unveraendertes Enter faelschlich KEIN
    // Nullvorgang mehr.
    fireEvent.click(screen.getByRole("button", { name: /Abbrechen/i }));
    fireEvent.click(knopf124(/Album umbenennen/i));
    const feld2 = await screen.findByDisplayValue("Gruppe");
    const aufrufeVorher = renameMock.mock.calls.length;
    fireEvent.keyDown(feld2, { key: "Enter" });
    await schlaf124(20);

    expect(renameMock.mock.calls.length).toBe(aufrufeVorher);
  });
});
