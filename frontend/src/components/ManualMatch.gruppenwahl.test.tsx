// Der ZWEITE Anlege-Weg: die Gruppenwahl im manuellen Abgleich (#81).
//
// Warum eigens geprueft, obwohl die Komponente `GruppenWahl` bereits Tests
// hat: Bei #78 ist genau diese Klasse zweimal durchgerutscht — die Regel war
// geprueft, die VERDRAHTUNG nicht (`docs/agents/lehren.md` §28). Und der
// Mutationslauf zu diesem Slice hat gezeigt, dass es hier wieder so war: Die
// Zeile, die `force_new_group` mitschickt, liess sich entfernen, ohne dass
// ein Test rot wurde.
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ManualMatch from "./ManualMatch";
import { LanguageProvider } from "../i18n";
import { SPEICHER_SCHLUESSEL } from "../test-konstanten";

const STARTKNOPF = "Namen sync + Album erstellen";

// Alle Daten erfunden; das Repo ist oeffentlich.
const KONTEN = [
  { id: "konto-1", name: "Konto Eins", color: "#111111" },
  { id: "konto-2", name: "Konto Zwei", color: "#222222" },
];

const LEUTE: Record<
  string,
  { id: string; name: string; account_id: string; asset_count: number }[]
> = {
  "konto-1": [{ id: "p1", name: "Person A", account_id: "konto-1", asset_count: 3 }],
  "konto-2": [{ id: "p2", name: "Person A", account_id: "konto-2", asset_count: 4 }],
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

const { kontenMock, leuteMock, namesMultiMock, vorschauMock, kontoAlbenMock } = vi.hoisted(() => ({
  kontenMock: vi.fn(),
  leuteMock: vi.fn(),
  namesMultiMock: vi.fn(),
  vorschauMock: vi.fn(),
  kontoAlbenMock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  api: {
    accounts: { list: kontenMock, albums: kontoAlbenMock },
    people: { byAccount: leuteMock, thumbnailUrl: () => "" },
    sync: { namesMulti: namesMultiMock, albumGroupPreview: vorschauMock },
  },
}));

function zeichne() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <LanguageProvider>
        <ManualMatch />
      </LanguageProvider>
    </QueryClientProvider>
  );
}

/** Zwei Personen auswaehlen und einen Namen setzen, bis abgeschickt werden kann. */
async function fuelleFormular() {
  zeichne();
  await waitFor(() => expect(kontenMock).toHaveBeenCalled());

  const kontoFelder = await screen.findAllByRole("combobox");
  fireEvent.change(kontoFelder[0], { target: { value: "konto-1" } });
  fireEvent.change(kontoFelder[1], { target: { value: "konto-2" } });

  await waitFor(() => expect(leuteMock).toHaveBeenCalled());

  // Je Zeile eine Person waehlen — sonst bleibt der Absendeknopf gesperrt.
  for (const zeile of [0, 1]) {
    const felder = await waitFor(() => {
      const treffer = screen.getAllByPlaceholderText("Person suchen…");
      if (treffer.length < 2) throw new Error("Personenfelder noch nicht da");
      return treffer;
    });
    fireEvent.focus(felder[zeile]);
    const umgebung = within(felder[zeile].parentElement as HTMLElement);
    const eintrag = await umgebung.findByText("Person A");
    fireEvent.mouseDown(eintrag);
  }

  // Der gemeinsame Name traegt die Gruppenabfrage, wenn kein Albumname
  // gesetzt ist — genau die Verkettung, die hier gesichert werden soll.
  fireEvent.change(screen.getByPlaceholderText("z. B. Max Mustermann"), {
    target: { value: "Testalbum" },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  try {
    localStorage.setItem(SPEICHER_SCHLUESSEL, "de");
  } catch {
    /* in dieser Umgebung nicht zwingend vorhanden */
  }
  kontenMock.mockResolvedValue(KONTEN);
  leuteMock.mockImplementation(async (id: string) => LEUTE[id] ?? []);
  namesMultiMock.mockResolvedValue([]);
  vorschauMock.mockResolvedValue(GRUPPE);
  kontoAlbenMock.mockResolvedValue([{ id: "immich-1", name: "Testalbum" }]);
});

describe("ManualMatch: Gruppenwahl", () => {
  it("zeigt die getroffene Gruppe, sobald ein Name feststeht", async () => {
    await fuelleFormular();

    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());
    expect(screen.getByText("Person X")).toBeTruthy();
  });

  it("schickt 'eigene Gruppe' wirklich mit", async () => {
    await fuelleFormular();
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());

    fireEvent.click(screen.getByLabelText("Eigene Gruppe anlegen"));
    fireEvent.click(screen.getByText(STARTKNOPF));

    await waitFor(() => expect(namesMultiMock).toHaveBeenCalled());
    expect(namesMultiMock.mock.calls[0][0].force_new_group).toBe(true);
  });
});

describe("ManualMatch: Gruppenwahl beim VERKNUEPFEN", () => {
  it("zeigt die Gruppe auch im Modus 'Vorhandenes verknuepfen'", async () => {
    // Die erste Fassung schaltete die Anzeige dort ab (`wirksamerName` war
    // fest ""), waehrend das Backend weiter ueber den Namen verschmolz — ein
    // stiller Beitritt ohne jeden Hinweis. MatchSuggestions bot die Wahl in
    // genau diesem Modus an; die Asymmetrie war nirgends begruendet
    // (Blindpruefer und Zweitstimme 21.09.2026, unabhaengig).
    await fuelleFormular();

    fireEvent.click(screen.getByText("Vorhandenes verknüpfen"));
    await screen.findByText("Testalbum");
    const felder = screen.getAllByRole("combobox");
    fireEvent.change(felder[felder.length - 1], { target: { value: "immich-1" } });

    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());
    expect(screen.getByText("Person X")).toBeTruthy();
  });
});

describe("ManualMatch: die angezeigte Gruppe wird auch geschickt", () => {
  it("schickt group_id beim Beitritt mit", async () => {
    // Gemessen vom Gegenpruefer: Das Entfernen des `group_id`-Zweigs hier
    // ueberlebte die volle Suite — geprueft war nur force_new_group.
    await fuelleFormular();
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());

    fireEvent.click(screen.getByText(STARTKNOPF));

    await waitFor(() => expect(namesMultiMock).toHaveBeenCalled());
    expect(namesMultiMock.mock.calls[0][0].group_id).toBe("gruppe-1");
  });

  it("schickt beim Verknuepfen keinen stehengebliebenen Albumnamen", async () => {
    // Das Namensfeld gehoert dem Anlege-Modus und wird beim Umschalten nur
    // AUSGEBLENDET. Mitgeschickt entschied sein Wert ueber die Gruppe,
    // waehrend die Vorschau nach dem Namen des Immich-Albums gefragt hatte —
    // ein stiller Beitritt zu einer fremden Gruppe (beide Stimmen, gemessen).
    await fuelleFormular();
    fireEvent.change(screen.getByPlaceholderText("Album-Name"), {
      target: { value: "Stehengeblieben" },
    });

    fireEvent.click(screen.getByText("Vorhandenes verknüpfen"));
    await screen.findByText("Testalbum");
    const felder = screen.getAllByRole("combobox");
    fireEvent.change(felder[felder.length - 1], { target: { value: "immich-1" } });

    fireEvent.click(screen.getByText(STARTKNOPF));

    await waitFor(() => expect(namesMultiMock).toHaveBeenCalled());
    expect(namesMultiMock.mock.calls[0][0].album_name).toBeUndefined();
    expect(namesMultiMock.mock.calls[0][0].existing_album_id).toBe("immich-1");
  });
});
