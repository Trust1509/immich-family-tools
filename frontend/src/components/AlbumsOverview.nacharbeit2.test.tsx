// Nacharbeit 2 zu #123 — letzte Runde. Blind- und Gegenpruefer haben f0f2890
// geprueft: kein BLOCKER, alle Behauptungen halten im Code; die Funde hier
// sind Testluecken, zwei kleine Verhaltensfehler und Doku (der Verhaltensteil
// steht in `AlbumsOverview.tsx`, dieser Datei geht es um die Testluecken).
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
      {
        account_id: "konto-zwei",
        person_id: "person-2",
        person_name: "Person Zwei",
        account_name: "Konto Zwei",
        account_color: "#222222",
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
  deleteMock.mockResolvedValue(undefined);
  renameMock.mockResolvedValue([
    { id: "l", timestamp: "", action: "rename_album", details: "", status: "success" },
  ]);
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
// Fund 1: 404 `err_managed_album_not_found` ist Erfolg, kein Fehlschlag
// (Gegenpruefer K1/K2, Blindpruefer K4).
// ---------------------------------------------------------------------------

describe("Fund 1: ein 404 err_managed_album_not_found zaehlt beim Entfernen als Erfolg", () => {
  function dreiAlben() {
    return [
      album({ id: "a", album_name: "Drei", owner_account_id: "konto-a" }),
      album({ id: "b", album_name: "Drei", owner_account_id: "konto-b" }),
      album({ id: "c", album_name: "Drei", owner_account_id: "konto-c" }),
    ];
  }

  it("Gruppe a(404 not_found)/b(204)/c(500): die Meldung nennt 1 von 3, nicht 2 von 3", async () => {
    albenMock.mockResolvedValue(dreiAlben());
    deleteMock.mockImplementation((id: string) => {
      if (id === "a") {
        return Promise.reject(
          new ApiError("Verwaltetes Album nicht gefunden", 404, "err_managed_album_not_found")
        );
      }
      if (id === "b") return Promise.resolve();
      return Promise.reject(new ApiError("Serverfehler", 500, "err_internal"));
    });
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );

    await rendern("Drei");
    fireEvent.click(screen.getByRole("button", { name: /Verknüpfung entfernen/i }));

    await waitFor(() => expect(deleteMock).toHaveBeenCalledTimes(3));
    expect(await screen.findByText("1 von 3 Einträgen konnte nicht entfernt werden.")).toBeTruthy();
  });

  it("Gruppe, in der NUR 404 not_found und Erfolge vorkommen: keine Fehlermeldung", async () => {
    albenMock.mockResolvedValue(dreiAlben());
    deleteMock.mockImplementation((id: string) =>
      id === "a"
        ? Promise.reject(
            new ApiError("Verwaltetes Album nicht gefunden", 404, "err_managed_album_not_found")
          )
        : Promise.resolve()
    );
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );

    await rendern("Drei");
    fireEvent.click(screen.getByRole("button", { name: /Verknüpfung entfernen/i }));

    await waitFor(() => expect(deleteMock).toHaveBeenCalledTimes(3));
    await waitFor(() =>
      expect(
        (
          screen.getByRole("button", {
            name: /Verknüpfung entfernen/i,
          }) as HTMLButtonElement
        ).disabled
      ).toBe(false)
    );
    expect(screen.queryByText(/konnte.*nicht entfernt werden/)).toBeNull();
  });

  it("Einzel-Entfernen mit 404 not_found: keine Meldung, kein 'konnte nicht entfernt werden'", async () => {
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
    deleteMock.mockRejectedValue(
      new ApiError("Verwaltetes Album nicht gefunden", 404, "err_managed_album_not_found")
    );
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );

    await rendern("Gemischt");
    fireEvent.click(screen.getByRole("button", { name: /Dieses verwaiste Album entfernen/i }));

    await waitFor(() => expect(deleteMock).toHaveBeenCalledWith("verwaist"));
    // Zeit fuer ein etwaiges (falsches) Setzen der Fehlermeldung geben.
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.queryByText(/konnte nicht entfernt werden/)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Fund 2: Testluecken (je Test, der unter f0f2890 mit der genannten Mutation
// ROT wird).
// ---------------------------------------------------------------------------

describe("Fund 2: Besitzerzeile gezielt pruefen (Blind W1)", () => {
  it("die Besitzer-ZEILE zeigt den lebenden Besitzer, nicht nur irgendwo auf der Karte", async () => {
    // Das verwaiste Album steht in der Liste VORN — nur so zeigt sich ein
    // Rueckbau auf `ownerRef`/`group[0]` oder `displayedOwnerMissing` von
    // `group[0]` ueberhaupt: Mit dem gesunden Album vorn waere `group[0]`
    // zufaellig schon das richtige.
    albenMock.mockResolvedValue([
      album({
        id: "verwaist",
        album_name: "Gemischt",
        owner_account_id: "konto-tot",
        owner_account_missing: true,
        person_refs: [],
      }),
      album({
        id: "gesund",
        album_name: "Gemischt",
        owner_account_id: "konto-lebt",
        owner_account_missing: false,
        person_refs: [
          {
            account_id: "konto-lebt",
            person_id: "person-x",
            person_name: "Person X",
            account_name: "Konto Lebt",
            account_color: "#333333",
          },
        ],
      }),
    ]);
    await rendern("Gemischt");

    // GEZIELT: die Besitzer-ZEILE traegt "Besitzer: Konto Lebt" als EIGENEN
    // Textinhalt (ein <p> ohne Kindelemente) — anders als
    // `getAllByText(/Konto/)`, das auch das Personen-Abzeichen darunter
    // traefe (dasselbe "Konto Lebt" steht dort erneut, unabhaengig davon, ob
    // die Besitzerzeile richtig oder falsch ist). Eine Mutation, die
    // `ownerRef`/den Anzeigenamen wieder auf `group[0]` zurueckfallen laesst,
    // wuerde hier "Besitzerkonto gelöscht" zeigen — `getAllByText(/Konto/)`
    // allein bliebe trotzdem gruen, weil das Abzeichen unveraendert bleibt.
    expect(screen.getByText("Besitzer: Konto Lebt")).toBeTruthy();
    expect(screen.queryByText(/^Besitzer:\s*Besitzerkonto gelöscht/)).toBeNull();
  });
});

describe("Fund 2: Einzel-Entfernen macht einen echten Fehlschlag sichtbar (Blind W2, Gegen W1)", () => {
  it("zeigt die Fehlermeldung, wenn das Loeschen eines verwaisten Albums an einem ANDEREN Fehler scheitert", async () => {
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
    deleteMock.mockRejectedValue(new Error("Immich antwortet nicht"));
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

describe("Fund 2: Neuladen auch nach einem Fehlschlag, beide Wege (Blind F17b/F17c)", () => {
  it("Einzel-Entfernen laedt die Liste AUCH bei einem Fehlschlag neu", async () => {
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
    deleteMock.mockRejectedValue(new Error("Immich antwortet nicht"));
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );

    await rendern("Gemischt");
    const ladeAufrufeVorher = albenMock.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: /Dieses verwaiste Album entfernen/i }));

    await waitFor(() => expect(albenMock.mock.calls.length).toBeGreaterThan(ladeAufrufeVorher));
  });

  it("Gruppen-Entfernen laedt die Liste AUCH bei einem Teilfehler neu", async () => {
    const gruppe = [
      album({ id: "a", album_name: "Drei", owner_account_id: "konto-a" }),
      album({ id: "b", album_name: "Drei", owner_account_id: "konto-b" }),
      album({ id: "c", album_name: "Drei", owner_account_id: "konto-c" }),
    ];
    albenMock.mockResolvedValue(gruppe);
    deleteMock.mockImplementation((id: string) =>
      id === "b" ? Promise.reject(new Error("kaputt")) : Promise.resolve()
    );
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );

    await rendern("Drei");
    const ladeAufrufeVorher = albenMock.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: /Verknüpfung entfernen/i }));

    await waitFor(() => expect(deleteMock).toHaveBeenCalledTimes(3));
    await waitFor(() => expect(albenMock.mock.calls.length).toBeGreaterThan(ladeAufrufeVorher));
  });
});

describe("Fund 2: Zaehlung mit ZWEI Fehlschlaegen (Blind K5)", () => {
  it("nennt 2 von 4, nicht auf 1 gedeckelt", async () => {
    const gruppe = [
      album({ id: "a", album_name: "Vier", owner_account_id: "konto-a" }),
      album({ id: "b", album_name: "Vier", owner_account_id: "konto-b" }),
      album({ id: "c", album_name: "Vier", owner_account_id: "konto-c" }),
      album({ id: "d", album_name: "Vier", owner_account_id: "konto-d" }),
    ];
    albenMock.mockResolvedValue(gruppe);
    deleteMock.mockImplementation((id: string) =>
      id === "b" || id === "d" ? Promise.reject(new Error("kaputt")) : Promise.resolve()
    );
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );

    await rendern("Vier");
    fireEvent.click(screen.getByRole("button", { name: /Verknüpfung entfernen/i }));

    await waitFor(() => expect(deleteMock).toHaveBeenCalledTimes(4));
    expect(
      await screen.findByText("2 von 4 Einträgen konnten nicht entfernt werden.")
    ).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Fund 3: stehenbleibende Hinweise (Blind K3). Escape und X schliessen das
// Feld und setzen `renameSkipped`/`renameError` zurueck; `deleteError` und
// `renameSkipped` werden beim START jeder neuen Aktion (Abgleichen,
// Umbenennen, Entfernen) zurueckgesetzt.
// ---------------------------------------------------------------------------

describe("Fund 3: Escape und X setzen renameError und renameSkipped zurueck", () => {
  function dreiAlben() {
    return [
      album({ id: "a", album_name: "Drei", owner_account_id: "konto-a" }),
      album({ id: "b", album_name: "Drei", owner_account_id: "konto-b" }),
      album({ id: "c", album_name: "Drei", owner_account_id: "konto-c" }),
    ];
  }

  async function mitSkipUndError() {
    // b wird uebersprungen (renameSkipped), c wirft einen ANDEREN Fehler und
    // bricht die Schleife ab (renameError) — beide Zustaende gleichzeitig
    // gesetzt, wie es real vorkommen kann.
    albenMock.mockResolvedValue(dreiAlben());
    renameMock.mockImplementation(async (id: string) => {
      if (id === "b") {
        throw new ApiError("Owner-Account nicht gefunden", 404, "err_owner_account_not_found");
      }
      if (id === "c") {
        throw new ApiError("Serverfehler", 500, "err_internal");
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
    await waitFor(() =>
      expect(screen.getByText(/Übersprungen, weil das Besitzerkonto/)).toBeTruthy()
    );
    expect(screen.getByText(/Serverfehler/)).toBeTruthy();
    return feld;
  }

  it("Escape schliesst das Feld und raeumt beide Hinweise weg", async () => {
    const feld = await mitSkipUndError();
    fireEvent.keyDown(feld, { key: "Escape" });

    await waitFor(() =>
      expect(screen.queryByRole("textbox", { name: /Album umbenennen/i })).toBeNull()
    );
    expect(screen.queryByText(/Übersprungen, weil das Besitzerkonto/)).toBeNull();
    expect(screen.queryByText(/Serverfehler/)).toBeNull();
  });

  it("X (Abbrechen) schliesst das Feld und raeumt beide Hinweise weg", async () => {
    await mitSkipUndError();
    fireEvent.click(screen.getByRole("button", { name: /Abbrechen/i }));

    await waitFor(() =>
      expect(screen.queryByRole("textbox", { name: /Album umbenennen/i })).toBeNull()
    );
    expect(screen.queryByText(/Übersprungen, weil das Besitzerkonto/)).toBeNull();
    expect(screen.queryByText(/Serverfehler/)).toBeNull();
  });
});

describe("Fund 3: deleteError und renameSkipped werden bei jeder neuen Aktion zurueckgesetzt", () => {
  function dreiAlben() {
    return [
      album({ id: "a", album_name: "Drei", owner_account_id: "konto-a" }),
      album({ id: "b", album_name: "Drei", owner_account_id: "konto-b" }),
      album({ id: "c", album_name: "Drei", owner_account_id: "konto-c" }),
    ];
  }

  async function mitDeleteError() {
    albenMock.mockResolvedValue(dreiAlben());
    deleteMock.mockRejectedValue(new Error("kaputt"));
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );

    await rendern("Drei");
    fireEvent.click(screen.getByRole("button", { name: /Verknüpfung entfernen/i }));
    await waitFor(() => expect(deleteMock).toHaveBeenCalledTimes(3));
    expect(await screen.findByText(/nicht entfernt werden/)).toBeTruthy();

    // Fuer den naechsten Versuch soll das Entfernen wieder gelingen, damit
    // spaetere Tests in dieser Datei nicht an derselben Attrappe haengen.
    deleteMock.mockResolvedValue(undefined);
  }

  async function mitRenameSkipped() {
    renameMock.mockImplementation(async (id: string) => {
      if (id === "b") {
        throw new ApiError("Owner-Account nicht gefunden", 404, "err_owner_account_not_found");
      }
      return [
        { id: `log-${id}`, timestamp: "", action: "rename_album", details: "", status: "success" },
      ];
    });
    albenMock.mockResolvedValue(dreiAlben());

    await rendern("Drei");
    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/i }));
    const feld = await screen.findByDisplayValue("Drei");
    fireEvent.change(feld, { target: { value: "Neuer Name" } });
    fireEvent.keyDown(feld, { key: "Enter" });
    await waitFor(() => expect(renameMock).toHaveBeenCalledTimes(3));
    expect(await screen.findByText(/Übersprungen, weil das Besitzerkonto/)).toBeTruthy();
  }

  it("Abgleichen (Jetzt synchronisieren) setzt einen stehenden deleteError zurueck", async () => {
    await mitDeleteError();
    fireEvent.click(screen.getByRole("button", { name: /Jetzt synchronisieren/i }));

    await waitFor(() => expect(screen.queryByText(/nicht entfernt werden/)).toBeNull());
  });

  it("Umbenennen setzt einen stehenden deleteError zurueck, sobald es ausgeloest wird", async () => {
    await mitDeleteError();
    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/i }));
    const feld = await screen.findByDisplayValue("Drei");
    fireEvent.change(feld, { target: { value: "Neuer Name" } });
    fireEvent.keyDown(feld, { key: "Enter" });

    await waitFor(() => expect(screen.queryByText(/nicht entfernt werden/)).toBeNull());
  });

  it("Gruppen-Entfernen setzt einen stehenden renameSkipped-Hinweis zurueck", async () => {
    await mitRenameSkipped();
    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );
    deleteMock.mockResolvedValue(undefined);
    fireEvent.click(screen.getByRole("button", { name: /Verknüpfung entfernen/i }));

    await waitFor(() =>
      expect(screen.queryByText(/Übersprungen, weil das Besitzerkonto/)).toBeNull()
    );
  });

  it("Einzel-Entfernen setzt einen stehenden renameSkipped-Hinweis zurueck", async () => {
    // Eine gemischte Gruppe: "a" gesund und wird umbenannt, "b" gilt beim
    // Laden noch als gesund, der Server lehnt sie beim Umbenennen aber mit
    // `err_owner_account_not_found` ab (renameSkipped), "verwaist" ist von
    // Anfang an verwaist und traegt den Einzel-Entfernen-Knopf.
    const gruppe = [
      album({ id: "a", album_name: "Gemischt", owner_account_id: "konto-a" }),
      album({ id: "b", album_name: "Gemischt", owner_account_id: "konto-b" }),
      album({
        id: "verwaist",
        album_name: "Gemischt",
        owner_account_id: "konto-tot",
        owner_account_missing: true,
      }),
    ];
    albenMock.mockResolvedValue(gruppe);
    renameMock.mockImplementation(async (id: string) => {
      if (id === "b") {
        throw new ApiError("Owner-Account nicht gefunden", 404, "err_owner_account_not_found");
      }
      return [
        { id: `log-${id}`, timestamp: "", action: "rename_album", details: "", status: "success" },
      ];
    });

    await rendern("Gemischt");
    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/i }));
    const feld = await screen.findByDisplayValue("Gemischt");
    fireEvent.change(feld, { target: { value: "Neuer Name" } });
    fireEvent.keyDown(feld, { key: "Enter" });
    await waitFor(() => expect(renameMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/Übersprungen, weil das Besitzerkonto/)).toBeTruthy();

    vi.stubGlobal(
      "confirm",
      vi.fn(() => true)
    );
    deleteMock.mockResolvedValue(undefined);
    fireEvent.click(screen.getByRole("button", { name: /Dieses verwaiste Album entfernen/i }));

    await waitFor(() =>
      expect(screen.queryByText(/Übersprungen, weil das Besitzerkonto/)).toBeNull()
    );
  });
});

// ---------------------------------------------------------------------------
// Fund 4: Sind ALLE Alben uebersprungen, bleibt das Eingabefeld offen (Blind
// K2) — `logs.length &&` in `handleRename` darf nicht entfernt werden.
// ---------------------------------------------------------------------------

describe("Fund 4: Umbenennen bleibt sichtbar unerledigt, wenn ALLE Alben uebersprungen wurden", () => {
  it("das Eingabefeld bleibt offen, wenn jedes gesunde Album mit err_owner_account_not_found abgelehnt wird", async () => {
    const gruppe = [
      album({ id: "a", album_name: "Zwei", owner_account_id: "konto-a" }),
      album({ id: "b", album_name: "Zwei", owner_account_id: "konto-b" }),
    ];
    albenMock.mockResolvedValue(gruppe);
    renameMock.mockRejectedValue(
      new ApiError("Owner-Account nicht gefunden", 404, "err_owner_account_not_found")
    );

    await rendern("Zwei");
    fireEvent.click(screen.getByRole("button", { name: /Album umbenennen/i }));
    const feld = await screen.findByDisplayValue("Zwei");
    fireEvent.change(feld, { target: { value: "Neuer Name" } });
    fireEvent.keyDown(feld, { key: "Enter" });

    await waitFor(() => expect(renameMock).toHaveBeenCalledTimes(2));
    // KEIN Log-Eintrag entstand (jedes Album wurde uebersprungen, keins
    // umbenannt) — das Feld darf deshalb nicht verschwinden.
    expect(screen.getByDisplayValue("Neuer Name")).toBeTruthy();
    expect(
      await screen.findByText(
        "Übersprungen, weil das Besitzerkonto inzwischen gelöscht ist: 2 von 2 Alben."
      )
    ).toBeTruthy();
  });
});
