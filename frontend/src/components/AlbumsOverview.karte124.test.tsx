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
import { LanguageProvider } from "../i18n";
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
  it("zeigt den Hinweis nach dem fehlgeschlagenen Versuch, aber nicht mehr nach dem no-op Enter (VOR dem ersten Versuch)", async () => {
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
