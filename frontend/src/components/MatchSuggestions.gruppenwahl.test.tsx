// Die Gruppenwahl beim Anlegen (#81), geprueft am gerenderten Dialog.
//
// Warum am Bildschirm und nicht an der Funktion: Bei #78 hat genau diese
// Klasse zweimal ueberlebt — die Regel war geprueft, die VERDRAHTUNG nicht
// (`docs/agents/lehren.md` §28). Hier ist sie bereits beim Bauen aufgetreten:
// Der Mutations-Rueckruf nahm `force_new_group` nicht an, TypeScript erlaubte
// das trotzdem (ein Rueckruf darf weniger Felder annehmen als der Aufrufer
// schickt), und das Feld waere still verschwunden.
//
// Und der Zwischenzustand ist ein eigenes Verhalten (§29): Solange die
// Abfrage laeuft, darf nichts behauptet werden.
import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import MatchSuggestions from "./MatchSuggestions";
import { LanguageProvider } from "../i18n";
import { SPEICHER_SCHLUESSEL } from "../test-konstanten";

// Alle Daten erfunden; das Repo ist oeffentlich.
const MATCH = {
  id: "match-1",
  confidence: 0.9,
  reasons: ["name_similarity"],
  status: "pending",
  has_album: false,
  names_synced: false,
  person_a: {
    account_id: "konto-1",
    person_id: "p1",
    person_name: "Person A",
    account_name: "Konto Eins",
    account_color: "#111111",
  },
  person_b: {
    account_id: "konto-2",
    person_id: "p2",
    person_name: "Person A",
    account_name: "Konto Zwei",
    account_color: "#222222",
  },
};

const GRUPPE = {
  group_id: "gruppe-1",
  album_names: ["Testalbum"],
  person_refs: [
    {
      account_id: "konto-1",
      person_id: "p8",
      person_name: "Person X",
      account_name: "Konto Eins",
      account_color: "#111111",
    },
  ],
};

const { matchesMock, kontenMock, albenMock, albumMock, vorschauMock, thumbMock, kontoAlbenMock } =
  vi.hoisted(() => ({
    matchesMock: vi.fn(),
    kontenMock: vi.fn(),
    albenMock: vi.fn(),
    albumMock: vi.fn(),
    vorschauMock: vi.fn(),
    thumbMock: vi.fn(),
    kontoAlbenMock: vi.fn(),
  }));

vi.mock("../api/client", () => ({
  api: {
    matches: {
      list: matchesMock,
      refresh: matchesMock,
      dismiss: vi.fn().mockResolvedValue(undefined),
    },
    accounts: { list: kontenMock, albums: kontoAlbenMock },
    sync: {
      albums: albenMock,
      album: albumMock,
      albumGroupPreview: vorschauMock,
      names: vi.fn().mockResolvedValue([]),
      refreshAlbum: vi.fn().mockResolvedValue([]),
    },
    people: { thumbnailUrl: thumbMock },
  },
}));

function zeichne() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <LanguageProvider>
        <MatchSuggestions />
      </LanguageProvider>
    </QueryClientProvider>
  );
}

/** Oeffnet den Album-Dialog einer Vorschlagskarte. */
async function oeffneDialog() {
  zeichne();
  const knopf = await screen.findByText("Album verbinden");
  fireEvent.click(knopf);
  return await screen.findByPlaceholderText("Album-Name…");
}

beforeEach(() => {
  vi.clearAllMocks();
  try {
    localStorage.setItem(SPEICHER_SCHLUESSEL, "de");
  } catch {
    /* in dieser Umgebung nicht zwingend vorhanden */
  }
  matchesMock.mockResolvedValue([MATCH]);
  kontenMock.mockResolvedValue([
    { id: "konto-1", name: "Konto Eins", color: "#111111" },
    { id: "konto-2", name: "Konto Zwei", color: "#222222" },
  ]);
  albenMock.mockResolvedValue([]);
  albumMock.mockResolvedValue([]);
  thumbMock.mockReturnValue("");
  kontoAlbenMock.mockResolvedValue([]);
  vorschauMock.mockResolvedValue(GRUPPE);
});

describe("Gruppenwahl beim Anlegen", () => {
  it("zeigt, wem das neue Album beitreten wuerde", async () => {
    await oeffneDialog();

    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());
    // Wem — nicht nur dass. Ohne die Personen waere die Bestaetigung leer.
    expect(screen.getByText("Person X")).toBeTruthy();
  });

  it("behauptet nichts, solange die Abfrage laeuft", async () => {
    // §29: Der Zwischenzustand ist ein eigenes Verhalten und braucht eine
    // eigene Zusicherung. Die Abfrage wird hier ANGEHALTEN — sonst prueft der
    // Test nur die Entprellung und waere gruen, ohne je einen laufenden
    // Aufruf gesehen zu haben.
    vorschauMock.mockImplementation(() => new Promise(() => {}));

    await oeffneDialog();

    // Erst warten, bis die Abfrage wirklich LAEUFT.
    await waitFor(() => expect(vorschauMock).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText("Wird geprüft …")).toBeTruthy());

    expect(screen.queryByText("Tritt der bestehenden Gruppe bei")).toBeNull();
    expect(screen.queryByText("Eigene Gruppe anlegen")).toBeNull();
  });

  it("schickt ohne Wahl KEIN force_new_group — das bisherige Verhalten", async () => {
    await oeffneDialog();
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());

    fireEvent.click(screen.getByText("Album erstellen"));

    await waitFor(() => expect(albumMock).toHaveBeenCalled());
    expect(albumMock.mock.calls[0][0].force_new_group).toBeUndefined();
  });

  it("schickt die angezeigte Gruppe beim Beitritt mit", async () => {
    // Was ANGEZEIGT wird, wird auch GESCHICKT. Ohne diese Bindung liess die
    // App das Backend beim Bestaetigen erneut ueber den Namen raten — kommt
    // dazwischen ein zweites gleichnamiges Album, landet der Nutzer in einer
    // DRITTEN Gruppe, obwohl er einen Beitritt bestaetigt hat.
    await oeffneDialog();
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());

    fireEvent.click(screen.getByText("Album erstellen"));

    await waitFor(() => expect(albumMock).toHaveBeenCalled());
    expect(albumMock.mock.calls[0][0].group_id).toBe("gruppe-1");
  });

  it("behaelt die Wahl, wenn danach weitergetippt wird", async () => {
    // Gemessen vom Blindpruefer: Der Ruecksetzer feuerte bei JEDEM
    // Tastendruck, weil "wird gerade geprueft" mit "es gibt keine Gruppe" in
    // einer Bedingung lag. Der Haken verschwand still, und das Album landete
    // in genau der Gruppe, gegen die sich der Nutzer entschieden hatte.
    await oeffneDialog();
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());

    fireEvent.click(screen.getByLabelText("Eigene Gruppe anlegen"));
    fireEvent.change(screen.getByPlaceholderText("Album-Name…"), {
      target: { value: "Testalbum 2026" },
    });

    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());
    fireEvent.click(screen.getByText("Album erstellen"));

    await waitFor(() => expect(albumMock).toHaveBeenCalled());
    expect(albumMock.mock.calls[0][0].force_new_group).toBe(true);
  });

  it("schickt die Wahl 'eigene Gruppe' wirklich mit", async () => {
    // DIE tragende Zusicherung dieses Slices. Ohne sie waere die Oberflaeche
    // ein Schalter, der nichts tut — gemessen: der Mutations-Rueckruf nahm
    // das Feld anfangs nicht an, und `tsc` sagte nichts.
    await oeffneDialog();
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());

    fireEvent.click(screen.getByLabelText("Eigene Gruppe anlegen"));
    fireEvent.click(screen.getByText("Album erstellen"));

    await waitFor(() => expect(albumMock).toHaveBeenCalled());
    expect(albumMock.mock.calls[0][0].force_new_group).toBe(true);
  });
});

describe("Gruppenwahl beim VERKNUEPFEN eines bestehenden Albums", () => {
  it("schickt die Wahl auch im Verknuepfen-Zweig mit", async () => {
    // Gemessen vom Blindpruefer: Das Entfernen von `...gruppenwahl` in genau
    // diesem Zweig ueberlebte die volle Suite — der Pfad "Wahl + bestehendes
    // Album" war end-to-end ungedeckt.
    kontoAlbenMock.mockResolvedValue([{ id: "immich-1", name: "Testalbum" }]);
    await oeffneDialog();

    fireEvent.click(screen.getByText("Vorhandenes verknüpfen"));

    // Erst warten, bis die Albumliste wirklich da ist — sonst waehlt der
    // Test in ein leeres Feld und prueft nichts.
    await screen.findByText("Testalbum");
    const felder = screen.getAllByRole("combobox");
    fireEvent.change(felder[felder.length - 1], { target: { value: "immich-1" } });

    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());
    fireEvent.click(screen.getByLabelText("Eigene Gruppe anlegen"));
    fireEvent.click(screen.getByText("Album verknüpfen"));

    await waitFor(() => expect(albumMock).toHaveBeenCalled());
    expect(albumMock.mock.calls[0][0].force_new_group).toBe(true);
    expect(albumMock.mock.calls[0][0].existing_album_id).toBe("immich-1");
  });
});
