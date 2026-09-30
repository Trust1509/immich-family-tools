// Die Gruppenauswahl, geprueft am gerenderten Bildschirm statt an der Regel.
//
// Warum (#78): Der Slice stellt die Gruppen-BILDUNG auf `group_id` um. Die
// Gruppen-IDENTITAET lag danach in dieser Datei weiter auf `album_name` —
// `groups.find((g) => g.album_name === selectedGroupName)`. Solange der Name
// der Schluessel WAR, konnten zwei Gruppen nie gleich heissen; genau diese
// Voraussetzung hebt der Slice auf.
//
// Gemessen vom Panel an der ersten Fassung: Klick auf die zweite Karte,
// abgeschickt wurde die erste. Das fuegt eine Person in ein FREMDES
// Immich-Album ein und teilt dieses Album mit einem weiteren Konto — kein
// Anzeigefehler, ein Schreibzugriff am falschen Ort.
//
// Die drei Konsumenten hatten bis hierher keinen einzigen Test; die
// Auslagerung nach lib/albumGroups hat die Regel prueffaehig gemacht und die
// Verdrahtung in ungepruefften Code verschoben.
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ExtendMatch from "./ExtendMatch";
import { LanguageProvider } from "../i18n";
import { SPEICHER_SCHLUESSEL } from "../test-konstanten";

// Zwei Gruppen mit DEMSELBEN Anzeigenamen und verschiedenen Kennungen —
// seit #78 ein gueltiger Zustand, den das Backend ausdruecklich traegt.
// Alle Daten erfunden; das Repo ist oeffentlich.
const ALBEN = [
  {
    id: "album-eins",
    match_id: "m-1",
    album_id: "immich-eins",
    album_name: "Testalbum",
    group_id: "gruppe-1",
    owner_account_id: "konto-1",
    person_refs: [
      {
        account_id: "konto-1",
        person_id: "person-a",
        person_name: "Person A",
        account_name: "Konto Eins",
        account_color: "#111111",
      },
    ],
    linked_match_ids: [],
    created_at: "2026-01-01T00:00:00+00:00",
    last_synced_at: "2026-01-01T00:00:00+00:00",
    total_assets: 1,
  },
  {
    id: "album-zwei",
    match_id: "m-2",
    album_id: "immich-zwei",
    album_name: "Testalbum",
    group_id: "gruppe-2",
    owner_account_id: "konto-2",
    person_refs: [
      {
        account_id: "konto-2",
        person_id: "person-b",
        person_name: "Person B",
        account_name: "Konto Zwei",
        account_color: "#222222",
      },
    ],
    linked_match_ids: [],
    created_at: "2026-01-02T00:00:00+00:00",
    last_synced_at: "2026-01-02T00:00:00+00:00",
    total_assets: 1,
  },
];

const { albenMock, kontenMock, extendMock, personenMock, byAccountMock } = vi.hoisted(() => ({
  albenMock: vi.fn(),
  kontenMock: vi.fn(),
  extendMock: vi.fn(),
  personenMock: vi.fn(),
  byAccountMock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  api: {
    sync: { albums: albenMock, extend: extendMock },
    accounts: { list: kontenMock },
    people: { list: personenMock, byAccount: byAccountMock, thumbnailUrl: () => "" },
  },
}));

function zeichne() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <LanguageProvider>
        <ExtendMatch />
      </LanguageProvider>
    </QueryClientProvider>
  );
}

/** Die Karte, die zu dieser Person gehoert — Personen sind hier das einzige
 *  Merkmal, das die beiden gleichnamigen Gruppen unterscheidet. */
function karteMit(personName: string): HTMLElement {
  const treffer = screen.getByText(personName);
  const karte = treffer.closest("button");
  if (!karte) throw new Error(`keine Karte zu ${personName}`);
  return karte;
}

beforeEach(() => {
  vi.clearAllMocks();
  // Sprache ausdruecklich setzen: ohne gespeicherten Wert faellt die App auf
  // die Browsersprache zurueck, und die ist hier en-US.
  try {
    localStorage.setItem(SPEICHER_SCHLUESSEL, "de");
  } catch {
    /* in dieser Umgebung nicht zwingend vorhanden */
  }
  albenMock.mockResolvedValue(ALBEN);
  kontenMock.mockResolvedValue([
    { id: "konto-1", name: "Konto Eins", color: "#111111" },
    { id: "konto-2", name: "Konto Zwei", color: "#222222" },
  ]);
  personenMock.mockResolvedValue([]);
  byAccountMock.mockResolvedValue([]);
  extendMock.mockResolvedValue([]);
});

describe("ExtendMatch: Gruppen gleichen Namens", () => {
  it("zeigt zwei Karten, wenn zwei Gruppen gleich heissen", async () => {
    zeichne();

    await waitFor(() => expect(screen.getAllByText("Testalbum")).toHaveLength(2));
  });

  it("vergibt eindeutige Schluessel, auch bei gleichem Namen", async () => {
    // Ein doppelter React-Schluessel rendert TROTZDEM zwei Karten — deshalb
    // faengt ihn kein Test, der nur zaehlt (gemessen: die Mutation
    // `key={g.album_name}` ueberlebte die volle Suite). React meldet ihn nur
    // als Warnung; hier wird genau diese Warnung zum Pruefgegenstand.
    //
    // Folge eines doppelten Schluessels: React haelt zwei Karten fuer
    // dieselbe und kann ihren Zustand vertauschen, wenn sich die Liste
    // aendert — bei einer Auswahl, die ein Album in Immich veraendert, ist
    // das kein Schoenheitsfehler.
    const warnungen: string[] = [];
    const echt = console.error;
    console.error = (...args: unknown[]) => {
      warnungen.push(args.map(String).join(" "));
    };
    try {
      zeichne();
      await waitFor(() => expect(screen.getAllByText("Testalbum")).toHaveLength(2));
    } finally {
      console.error = echt;
    }

    const passendeWarnung = (w: string) => /same key|unique "key"|duplicate key/i.test(w);
    expect(warnungen.filter(passendeWarnung)).toEqual([]);

    // SELBSTPROBE: Ein Negativ-Waechter muss zeigen, dass sein Kanal lebt.
    // Sonst wird er lautlos gruen, wenn React die Formulierung aendert, der
    // Lauf unter einem Produktionsbau stattfindet oder die Konsole anderswo
    // stummgeschaltet wird (Blindpruefer 21.09.2026).
    const probe: string[] = [];
    console.error = (...args: unknown[]) => {
      probe.push(args.map(String).join(" "));
    };
    try {
      render(
        <ul>
          {["x", "x"].map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      );
    } finally {
      console.error = echt;
    }
    expect(probe.filter(passendeWarnung).length).toBeGreaterThan(0);
  });

  it("waehlt nur die angeklickte Gruppe aus", async () => {
    zeichne();
    await waitFor(() => expect(screen.getAllByText("Testalbum")).toHaveLength(2));

    fireEvent.click(karteMit("Person B"));

    // Die Auswahl faerbt genau eine Karte ein. Lag die Identitaet am Namen,
    // waren es beide.
    await waitFor(() => {
      const gewaehlt = screen
        .getAllByRole("button")
        .filter((b) => b.className.includes("border-immich-primary"));
      expect(gewaehlt).toHaveLength(1);
    });
    expect(karteMit("Person B").className).toContain("border-immich-primary");
    expect(karteMit("Person A").className).not.toContain("border-immich-primary");
  });

  it("arbeitet mit der angeklickten Gruppe, nicht nur mit ihrer Einfaerbung", async () => {
    // Der eigentliche Fund des Panels: geklickt die zweite, benutzt die
    // erste. Die Einfaerbung allein zeigt das NICHT — sie haengt an einer
    // anderen Zeile. Gemessen: Ein Test, der nur die Einfaerbung prueft,
    // ueberlebt den Rueckbau von `selectedGroup`.
    //
    // `availableAccounts` haengt unmittelbar an `selectedGroup`: Es sind die
    // Konten, die in der GEWAEHLTEN Gruppe noch fehlen. Gruppe 2 enthaelt
    // Konto Zwei, also muss genau Konto Eins angeboten werden.
    zeichne();
    await waitFor(() => expect(screen.getAllByText("Testalbum")).toHaveLength(2));

    fireEvent.click(karteMit("Person B"));

    const auswahl = await screen.findByRole("combobox");
    const angeboten = Array.from(auswahl.querySelectorAll("option"))
      .map((o) => o.textContent)
      .filter((t): t is string => !!t && t.startsWith("Konto"));
    expect(angeboten).toEqual(["Konto Eins"]);
  });
});

describe("ExtendMatch: bedingte Alben", () => {
  it("bietet nur normale Alben zum Erweitern an, auch bei gleicher Gruppenkennung", async () => {
    albenMock.mockResolvedValue([
      ALBEN[0],
      {
        ...ALBEN[0],
        id: "album-mindestzahl",
        group_id: "gruppe-1",
        person_refs: [
          { ...ALBEN[0].person_refs[0], person_id: "person-c", person_name: "Person C" },
        ],
        minimum_person_count: 2,
        condition_person_count: 2,
      },
      {
        ...ALBEN[0],
        id: "album-verknuepft",
        group_id: "gruppe-1",
        person_refs: [
          { ...ALBEN[0].person_refs[0], person_id: "person-d", person_name: "Person D" },
        ],
        minimum_person_count: 1,
        linked_person_ids: ["identitaet-1"],
      },
    ]);

    zeichne();

    await screen.findByText("Person A");
    expect(screen.getAllByText("Testalbum")).toHaveLength(1);
    expect(screen.queryByText("Person C")).toBeNull();
    expect(screen.queryByText("Person D")).toBeNull();
    fireEvent.click(karteMit("Person A"));
    expect(await screen.findByRole("combobox")).toBeTruthy();
  });

  it("bietet kein bedingtes Album allein zum Erweitern an", async () => {
    albenMock.mockResolvedValue([
      { ...ALBEN[0], minimum_person_count: 1, linked_person_ids: ["identitaet-1"] },
    ]);

    zeichne();

    await waitFor(() => expect(albenMock).toHaveBeenCalled());
    await screen.findByText(/Noch keine verwalteten Alben/);
    expect(screen.queryByText("Testalbum")).toBeNull();
  });
});

describe("ExtendMatch: Gruppen-Cache nach dem Erweitern (#110, Nacharbeit 2, Fund 3)", () => {
  it("invalidiert die Gruppenvorschau, sobald das Erweitern erfolgreich war", async () => {
    // Blindpruefer, Nacharbeit 2: die Invalidierung in ExtendMatch.tsx war
    // ungetestet — direkter Nachweis wie bei den anderen vier Aufrufstellen.
    byAccountMock.mockResolvedValue([
      { id: "person-neu", name: "Person Neu", account_id: "konto-2", asset_count: 1 },
    ]);
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const spion = vi.spyOn(qc, "invalidateQueries");
    render(
      <QueryClientProvider client={qc}>
        <LanguageProvider>
          <ExtendMatch />
        </LanguageProvider>
      </QueryClientProvider>
    );
    await waitFor(() => expect(screen.getAllByText("Testalbum")).toHaveLength(2));

    fireEvent.click(karteMit("Person A"));
    const kontoAuswahl = await screen.findByRole("combobox");
    fireEvent.change(kontoAuswahl, { target: { value: "konto-2" } });

    const personenfeld = await screen.findByPlaceholderText("Person suchen…");
    fireEvent.focus(personenfeld);
    fireEvent.mouseDown(await screen.findByText("Person Neu"));

    fireEvent.click(screen.getByText("Zum Match hinzufügen"));

    await waitFor(() => expect(extendMock).toHaveBeenCalled());
    await waitFor(() =>
      expect(
        spion.mock.calls.some(
          (call) =>
            call[0] &&
            typeof call[0] === "object" &&
            "queryKey" in call[0] &&
            (call[0] as { queryKey?: unknown[] }).queryKey?.[0] === "album-group"
        )
      ).toBe(true)
    );
  });

  it("invalidiert die Gruppenvorschau AUCH, wenn das Erweitern fehlschlaegt (#119, Punkt 3, onSettled)", async () => {
    // `onSettled` statt nur `onSuccess` — ExtendMatch aendert die Gruppe
    // (neue Person/neues Konto). `ExtendMatch.tsx` selbst zeigt zwar keine
    // GruppenWahl-Vorschau, aber ANDERE offene Dialoge (MatchSuggestions,
    // ManualMatch) fuer denselben Namen sollen danach keine veraltete
    // Antwort mehr sehen — bisher ungetestet fuer den FEHLERPFAD.
    extendMock.mockRejectedValueOnce(new Error("netzwerk kaputt"));
    byAccountMock.mockResolvedValue([
      { id: "person-neu", name: "Person Neu", account_id: "konto-2", asset_count: 1 },
    ]);
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const spion = vi.spyOn(qc, "invalidateQueries");
    render(
      <QueryClientProvider client={qc}>
        <LanguageProvider>
          <ExtendMatch />
        </LanguageProvider>
      </QueryClientProvider>
    );
    await waitFor(() => expect(screen.getAllByText("Testalbum")).toHaveLength(2));

    fireEvent.click(karteMit("Person A"));
    const kontoAuswahl = await screen.findByRole("combobox");
    fireEvent.change(kontoAuswahl, { target: { value: "konto-2" } });
    const personenfeld = await screen.findByPlaceholderText("Person suchen…");
    fireEvent.focus(personenfeld);
    fireEvent.mouseDown(await screen.findByText("Person Neu"));

    fireEvent.click(screen.getByText("Zum Match hinzufügen"));

    await waitFor(() => expect(extendMock).toHaveBeenCalled());
    await waitFor(() =>
      expect(
        spion.mock.calls.some(
          (call) =>
            call[0] &&
            typeof call[0] === "object" &&
            "queryKey" in call[0] &&
            (call[0] as { queryKey?: unknown[] }).queryKey?.[0] === "album-group"
        )
      ).toBe(true)
    );
  });
});
