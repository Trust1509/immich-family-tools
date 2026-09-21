// Die Gruppenwahl-Komponente fuer sich (#81).
//
// Der Zwischenzustand ist ein eigenes Verhalten (`docs/agents/lehren.md` §29):
// Ein Hinweis, der zu einer VERALTETEN Eingabe gehoert, ist schlimmer als
// keiner — der Nutzer bestaetigt dann eine Gruppe, die zu dem Namen, den er
// gerade tippt, gar nicht passt.
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { GruppenWahl } from "./GruppenWahl";
import { LanguageProvider } from "../i18n";
import { SPEICHER_SCHLUESSEL } from "../test-konstanten";

// Alle Daten erfunden; das Repo ist oeffentlich.
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

const { vorschauMock } = vi.hoisted(() => ({ vorschauMock: vi.fn() }));

vi.mock("../api/client", () => ({
  api: { sync: { albumGroupPreview: vorschauMock } },
}));

function zeichne(albumName: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const baum = (name: string) => (
    <QueryClientProvider client={qc}>
      <LanguageProvider>
        <GruppenWahl
          albumName={name}
          eigeneGruppe={false}
          onEigeneGruppeChange={() => {}}
          onGruppeChange={() => {}}
        />
      </LanguageProvider>
    </QueryClientProvider>
  );
  const ergebnis = render(baum(albumName));
  return { ...ergebnis, neuZeichnen: (name: string) => ergebnis.rerender(baum(name)) };
}

beforeEach(() => {
  vi.clearAllMocks();
  try {
    localStorage.setItem(SPEICHER_SCHLUESSEL, "de");
  } catch {
    /* in dieser Umgebung nicht zwingend vorhanden */
  }
  vorschauMock.mockResolvedValue(GRUPPE);
});

describe("GruppenWahl", () => {
  it("zeigt gar nichts, solange kein Name eingegeben ist", () => {
    zeichne("   ");

    expect(screen.queryByText("Wird geprüft …")).toBeNull();
    expect(screen.queryByText("Tritt der bestehenden Gruppe bei")).toBeNull();
    expect(vorschauMock).not.toHaveBeenCalled();
  });

  it("nimmt die Antwort zurueck, sobald der Name nicht mehr dazu passt", async () => {
    // Genau der Fall, den ein Test mit einer haengenden Abfrage NICHT trifft:
    // Die Antwort ist da, sie gehoert nur zu einem aelteren Namen.
    const { neuZeichnen } = zeichne("Testalbum");
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());

    neuZeichnen("Ganz anderer Name");

    // SOFORT weg — nicht erst, wenn die neue Abfrage geantwortet hat.
    expect(screen.queryByText("Tritt der bestehenden Gruppe bei")).toBeNull();
    expect(screen.getByText("Wird geprüft …")).toBeTruthy();
  });

  it("nimmt die Antwort auch zurueck, wenn das Feld GELEERT wird", async () => {
    // Ein eigener Fall, kein Sonderfall des vorigen: Bei leerem Feld wird
    // NICHT gesucht, also greift der Pruefzustand nicht — die alte Antwort
    // haengt aber noch am vorigen Schluessel. Gemessen: Ohne die zweite
    // Schranke behauptete die App rund eine Drittelsekunde etwas ueber einen
    // Namen, den es nicht mehr gab.
    const { neuZeichnen } = zeichne("Testalbum");
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());

    neuZeichnen("");

    expect(screen.queryByText("Tritt der bestehenden Gruppe bei")).toBeNull();
    expect(screen.queryByText("Wird geprüft …")).toBeNull();
  });
});

/** Zeichnet die Komponente MIT Zustand — sonst laesst sich der Ruecksetzer
 *  nicht beobachten, und genau der war ungedeckt. */
function zeichneMitZustand(start: string) {
  const gemeldet: (string | null)[] = [];
  function Huelle({ name }: { name: string }) {
    const [eigen, setEigen] = React.useState(false);
    return (
      <>
        <span data-testid="wahl">{String(eigen)}</span>
        <GruppenWahl
          albumName={name}
          eigeneGruppe={eigen}
          onEigeneGruppeChange={setEigen}
          onGruppeChange={(g) => gemeldet.push(g)}
        />
      </>
    );
  }
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const baum = (name: string) => (
    <QueryClientProvider client={qc}>
      <LanguageProvider>
        <Huelle name={name} />
      </LanguageProvider>
    </QueryClientProvider>
  );
  const e = render(baum(start));
  return { gemeldet, neuZeichnen: (n: string) => e.rerender(baum(n)) };
}

describe("GruppenWahl: die Wahl und ihre Meldung", () => {
  it("setzt die Wahl zurueck, wenn die Gruppe wirklich verschwindet", async () => {
    // Die Zeile liess sich ersatzlos streichen, ohne dass ein Test rot wurde
    // (Blindpruefer 21.09.2026) — obwohl genau dieses Verhalten der Fund war.
    const { neuZeichnen } = zeichneMitZustand("Testalbum");
    await waitFor(() => expect(screen.getByText("Tritt der bestehenden Gruppe bei")).toBeTruthy());

    fireEvent.click(screen.getByLabelText("Eigene Gruppe anlegen"));
    expect(screen.getByTestId("wahl").textContent).toBe("true");

    vorschauMock.mockResolvedValue(null);
    neuZeichnen("Kennt keine Gruppe");

    await waitFor(() => expect(screen.getByTestId("wahl").textContent).toBe("false"));
  });

  it("meldet keine Gruppe, solange die Antwort nicht zur Eingabe passt", async () => {
    const { gemeldet, neuZeichnen } = zeichneMitZustand("Testalbum");
    await waitFor(() => expect(gemeldet).toContain("gruppe-1"));

    neuZeichnen("Anderer Name");

    // Die zuletzt gemeldete Kennung muss null sein — sonst schickt der
    // Aufrufer eine Gruppe mit, die zur Eingabe nicht mehr gehoert.
    await waitFor(() => expect(gemeldet[gemeldet.length - 1]).toBeNull());
  });
});
