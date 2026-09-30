// Nacharbeit 1 zu #113/#119/#124 — Radiogruppen je Instanz (Gegen F1, Blind
// K-3) und Ruecksetzer fuer "Eigene Gruppe" bei jeder neuen Vorschau-Lage
// (Blind W-3). An die Sonden der Pruefstimmen angelehnt
// (`scratchpad/welle4/blind/S2/sonden/GruppenWahl.sonde.test.tsx`,
// `scratchpad/welle4/gegen/S2/proben/GegenS2.gruppenwahl.test.tsx`), hier als
// feste, assertierende Tests.
//
// Alle Daten erfunden; das Repo ist oeffentlich.
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { GruppenWahl, gruppenBereitschaft, type GruppenAntwort } from "./GruppenWahl";
import { LanguageProvider } from "../i18n";
import { SPEICHER_SCHLUESSEL } from "../test-konstanten";

const ref = (id: string, name: string) => ({
  account_id: "konto-1",
  person_id: id,
  person_name: name,
  account_name: "Konto Eins",
  account_color: "#111111",
});
const MANY = (a: string, b: string) => ({
  status: "many" as const,
  candidates: [
    { group_id: `g-${a}`, album_names: ["X"], person_refs: [ref(a, `Person ${a}`)] },
    { group_id: `g-${b}`, album_names: ["X"], person_refs: [ref(b, `Person ${b}`)] },
  ],
});

const { vorschauMock } = vi.hoisted(() => ({ vorschauMock: vi.fn() }));
vi.mock("../api/client", () => ({ api: { sync: { albumGroupPreview: vorschauMock } } }));

beforeEach(() => {
  vi.resetAllMocks();
  try {
    localStorage.setItem(SPEICHER_SCHLUESSEL, "de");
  } catch {
    /* egal */
  }
  vorschauMock.mockImplementation(async (name: string) => {
    if (name === "Doppelt A") return MANY("a1", "a2");
    if (name === "Doppelt B") return MANY("b1", "b2");
    return null;
  });
});

function Huelle({
  name,
  antworten,
  id,
}: {
  name: string;
  antworten: GruppenAntwort[];
  id: string;
}) {
  const [eigen, setEigen] = React.useState(false);
  return (
    <div data-testid={`karte-${id}`}>
      <span data-testid={`eigen-${id}`}>{String(eigen)}</span>
      <GruppenWahl
        albumName={name}
        eigeneGruppe={eigen}
        onEigeneGruppeChange={setEigen}
        onAntwort={(a) => antworten.push(a)}
      />
    </div>
  );
}

describe("Radiogruppen je Instanz (Gegen F1, Blind K-3)", () => {
  it("zwei gleichzeitig offene Dialoge mit demselben mehrdeutigen Namen tragen VERSCHIEDENE Radio-Namen", async () => {
    vorschauMock.mockResolvedValue(MANY("p1", "p2"));
    const antwortenA: GruppenAntwort[] = [];
    const antwortenB: GruppenAntwort[] = [];
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <LanguageProvider>
          <div data-testid="karte-a">
            <GruppenWahl
              albumName="Fest"
              eigeneGruppe={false}
              onEigeneGruppeChange={() => {}}
              onAntwort={(a) => antwortenA.push(a)}
            />
          </div>
          <div data-testid="karte-b">
            <GruppenWahl
              albumName="Fest"
              eigeneGruppe={false}
              onEigeneGruppeChange={() => {}}
              onAntwort={(a) => antwortenB.push(a)}
            />
          </div>
        </LanguageProvider>
      </QueryClientProvider>
    );
    await waitFor(() => expect(screen.getAllByText("Person p1")).toHaveLength(2));
    const radios = screen.getAllByRole("radio") as HTMLInputElement[];
    expect(radios).toHaveLength(6); // 3 je Instanz: A = 0..2, B = 3..5
    const namenA = new Set(radios.slice(0, 3).map((r) => r.name));
    const namenB = new Set(radios.slice(3, 6).map((r) => r.name));
    expect(namenA.size).toBe(1);
    expect(namenB.size).toBe(1);
    // Der eigentliche Fund: EIN fester Name fuer alle Instanzen macht aus
    // zwei Dialogen im Browser EINE Radiogruppe — jetzt tragen sie
    // VERSCHIEDENE Namen.
    expect([...namenA][0]).not.toBe([...namenB][0]);

    // Und die WIRKUNG bleibt getrennt: Eine Wahl in Karte B veraendert Karte
    // A nicht.
    const erstesP1 = screen
      .getAllByText("Person p1")[0]
      .closest("label")
      ?.querySelector('input[type="radio"]') as HTMLInputElement;
    fireEvent.click(erstesP1); // erste "Person p1" gehoert zu Karte A (DOM-Reihenfolge)
    await waitFor(() =>
      expect(gruppenBereitschaft(antwortenA[antwortenA.length - 1], "Fest").gruppeId).toBe("g-p1")
    );
    const zweitesP2 = screen
      .getAllByText("Person p2")[1]
      .closest("label")
      ?.querySelector('input[type="radio"]') as HTMLInputElement;
    fireEvent.click(zweitesP2); // "Person p2" in Karte B
    await waitFor(() =>
      expect(gruppenBereitschaft(antwortenB[antwortenB.length - 1], "Fest").gruppeId).toBe("g-p2")
    );
    const a = gruppenBereitschaft(antwortenA[antwortenA.length - 1], "Fest");
    expect(a.gruppeId).toBe("g-p1"); // Karte As Wahl steht noch, trotz Klick in B
  });
});

describe("Vorauswahl 'Eigene Gruppe' wird bei neuer Mehrdeutigkeit zurueckgesetzt (Blind W-3)", () => {
  it("mehrdeutig A -> 'Eigene Gruppe' -> mehrdeutig B: der Haken faellt weg", async () => {
    const antworten: GruppenAntwort[] = [];
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const baum = (name: string) => (
      <QueryClientProvider client={qc}>
        <LanguageProvider>
          <Huelle name={name} antworten={antworten} id="1" />
        </LanguageProvider>
      </QueryClientProvider>
    );
    const e = render(baum("Doppelt A"));
    await waitFor(() => expect(screen.getByText("Person a1")).toBeTruthy());
    fireEvent.click(screen.getByLabelText("Eigene Gruppe anlegen"));
    await waitFor(() => expect(screen.getByTestId("eigen-1").textContent).toBe("true"));
    await waitFor(() =>
      expect(gruppenBereitschaft(antworten[antworten.length - 1], "Doppelt A").bereit).toBe(true)
    );

    e.rerender(baum("Doppelt B"));
    await waitFor(() => expect(screen.getByText("Person b1")).toBeTruthy());

    // Der Fund: Ohne den Ruecksetzer blieb "Eigene Gruppe" fuer den NEUEN,
    // mehrdeutigen Namen vorgewaehlt und `bereit: true`, obwohl der Nutzer
    // zu "Doppelt B" noch gar nichts entschieden hat.
    await waitFor(() => expect(screen.getByTestId("eigen-1").textContent).toBe("false"));
    const radios = screen.getAllByRole("radio") as HTMLInputElement[];
    expect(radios.some((r) => r.checked)).toBe(false);
    const stand = gruppenBereitschaft(antworten[antworten.length - 1], "Doppelt B");
    expect(stand.bereit).toBe(false);
  });
});

describe("Ruecksetzer der Kandidatenwahl (Blind F3/F4, Gegen FM1/FM2) — Testluecke Nacharbeit 1", () => {
  it("FM1: gewaehlter Kandidat faellt weg, wenn der Name wechselt", async () => {
    const antworten: GruppenAntwort[] = [];
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const baum = (name: string) => (
      <QueryClientProvider client={qc}>
        <LanguageProvider>
          <Huelle name={name} antworten={antworten} id="1" />
        </LanguageProvider>
      </QueryClientProvider>
    );
    const e = render(baum("Doppelt A"));
    await waitFor(() => expect(screen.getByText("Person a1")).toBeTruthy());
    const radioA1 = screen
      .getByText("Person a1")
      .closest("label")
      ?.querySelector('input[type="radio"]') as HTMLInputElement;
    fireEvent.click(radioA1);
    await waitFor(() =>
      expect(gruppenBereitschaft(antworten[antworten.length - 1], "Doppelt A").gruppeId).toBe(
        "g-a1"
      )
    );

    e.rerender(baum("Doppelt B"));
    await waitFor(() => expect(screen.getByText("Person b1")).toBeTruthy());

    // In `waitFor` gewickelt, nicht als einmalige Prüfung direkt nach dem
    // Text: Der Rücksetzer selbst ist ein EIGENER Effekt (eigener Render),
    // der nach dem Erscheinen von "Person b1" noch laufen kann — dieselbe
    // Klasse Zwischenzustand wie an anderer Stelle in dieser Datei.
    await waitFor(() => {
      const radios = screen.getAllByRole("radio") as HTMLInputElement[];
      expect(radios.some((r) => r.checked)).toBe(false);
    });
    await waitFor(() => {
      const stand = gruppenBereitschaft(antworten[antworten.length - 1], "Doppelt B");
      expect(stand.bereit).toBe(false);
    });
  });

  it("FM2: gewaehlter Kandidat faellt weg, wenn er aus einer aufgefrischten Antwort verschwindet (Name bleibt gleich)", async () => {
    let daten: ReturnType<typeof MANY> = MANY("a1", "a2");
    vorschauMock.mockImplementation(async () => daten);
    const antworten: GruppenAntwort[] = [];
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <LanguageProvider>
          <Huelle name="Doppelt A" antworten={antworten} id="1" />
        </LanguageProvider>
      </QueryClientProvider>
    );
    await waitFor(() => expect(screen.getByText("Person a1")).toBeTruthy());
    const radioA1 = screen
      .getByText("Person a1")
      .closest("label")
      ?.querySelector('input[type="radio"]') as HTMLInputElement;
    fireEvent.click(radioA1);
    await waitFor(() =>
      expect(gruppenBereitschaft(antworten[antworten.length - 1], "Doppelt A").gruppeId).toBe(
        "g-a1"
      )
    );

    // Dieselbe Eingabe, aber eine aufgefrischte Antwort ohne die gewaehlte
    // Gruppe (z.B. eine gleichzeitige Aktion hat sie entfernt) — kein
    // Namenswechsel, nur eine neue Lage zum SELBEN Namen.
    daten = MANY("a3", "a2");
    await act(async () => {
      await qc.invalidateQueries();
    });
    await waitFor(() => expect(screen.getByText("Person a3")).toBeTruthy());

    // In `waitFor` gewickelt, nicht als einmalige Pruefung direkt nach dem
    // Text: Der Ruecksetzer (`gewaehlterKandidat` verschwindet aus den
    // frischen Kandidaten) ist ein EIGENER Effekt, der nach dem Erscheinen
    // von "Person a3" noch laufen kann.
    await waitFor(() => {
      const radios = screen.getAllByRole("radio") as HTMLInputElement[];
      expect(radios.some((r) => r.checked)).toBe(false);
    });
    await waitFor(() => {
      const stand = gruppenBereitschaft(antworten[antworten.length - 1], "Doppelt A");
      expect(stand.bereit).toBe(false);
    });
  });
});
