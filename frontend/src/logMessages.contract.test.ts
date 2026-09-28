import { describe, expect, it } from "vitest";
import vertrag from "./logMessages.contract.json";
import { LANG_LABELS, logMessages } from "./i18n";
import type { Lang, LogMessageParams } from "./i18n";

/**
 * Laufzeit-Vertragspruefung fuer die Protokollmeldungen (Nacharbeit 1 zu
 * #94, Frontend-Haelfte). Der Vorlaeufer dieses Tests las die Vorlagen als
 * TEXT (Regex auf `i18n.tsx`) und wurde vom Hauptagenten widerlegt: Eine
 * deutsche Vorlage von `log_album_created`, umgeschrieben zu
 * `(q) => ... ${q.acount} ...`, blieb bei allen damaligen Tests gruen
 * (268 gruen), das Protokoll zeigte zur Laufzeit "undefined" — andere
 * Parameternamen, Destrukturierung, `function`-Schreibweise und Kommentare
 * (ein auskommentierter Eintrag zaehlte als vorhanden) faellt bei einem
 * Textvergleich still aus dem Bild.
 *
 * Dieser Test ruft jede Vorlage TATSAECHLICH auf und zeichnet per `Proxy`
 * auf, welche Eigenschaften sie liest. Syntaxform ist damit per Konstruktion
 * irrelevant: Eine Vorlage mit Destrukturierung, einer `function`-Deklaration
 * oder einem falschen Parameternamen liest trotzdem genau die Eigenschaften,
 * die sie tatsaechlich liest — und ein auskommentierter Eintrag existiert
 * zur Laufzeit schlicht nicht (er fehlt aus `Object.keys(logMessages)`).
 *
 * Beide Seiten (Backend: `backend/tests/test_log_messages.py`, Frontend:
 * hier) pruefen gegen DIESELBE Datei `logMessages.contract.json` — es gibt
 * keine zweite, unabhaengige Erfassung mehr, die auseinanderlaufen kann.
 */

function gelesenePlatzhalter(fn: (p: LogMessageParams) => string): Set<string> {
  const gelesen = new Set<string>();
  const proxy = new Proxy({} as LogMessageParams, {
    get(_target, eigenschaft) {
      if (typeof eigenschaft === "string") {
        gelesen.add(eigenschaft);
      }
      // Ein harmloser Platzhalterwert, damit die Vorlage beim Aufruf nicht
      // mit einer Fehlermeldung abbricht (Template-Strings brauchen einen
      // Wert, keinen `undefined`-Ausdruck).
      return "x";
    },
  });
  fn(proxy);
  return gelesen;
}

type LogMessagesForm = Record<string, Partial<Record<Lang, (p: LogMessageParams) => string>>>;
type VertragForm = Record<string, string[]>;

/**
 * Die eigentliche Vertragspruefung — wird vom Produktivtest UND von jedem
 * Rot-Beweis unten aufgerufen, nicht eine fuer die Rot-Beweise nachgebaute
 * Kopie der Vergleichslogik.
 */
function pruefeVertrag(
  logMessagesObjekt: LogMessagesForm,
  vertragObjekt: VertragForm,
  sprachenListe: Lang[]
): void {
  const hinten = Object.keys(logMessagesObjekt).sort();
  const vorne = Object.keys(vertragObjekt).sort();
  expect(hinten, "Schluesselmenge von logMessages vs. Vertrag").toEqual(vorne);

  const sortierteSprachen = [...sprachenListe].sort();
  for (const schluessel of vorne) {
    const vorlagen = logMessagesObjekt[schluessel];
    if (!vorlagen) {
      throw new Error(`'${schluessel}' fehlt in logMessages`);
    }
    expect(Object.keys(vorlagen).sort(), `Sprachen von '${schluessel}'`).toEqual(sortierteSprachen);
    const erwartet = new Set(vertragObjekt[schluessel]);
    for (const sprache of sprachenListe) {
      const fn = vorlagen[sprache];
      if (!fn) {
        throw new Error(`'${schluessel}/${sprache}' fehlt in logMessages`);
      }
      const gelesen = gelesenePlatzhalter(fn);
      expect(gelesen, `${schluessel}/${sprache}`).toEqual(erwartet);
    }
  }
}

const sprachen = Object.keys(LANG_LABELS) as Lang[];

describe("logMessages folgt logMessages.contract.json", () => {
  it("die Vertragsdatei ist nicht leer", () => {
    // Siehe backend/tests/test_log_messages.py::test_vertragsdatei_ist_nicht_leer
    // fuer die Begruendung, warum das die fruehere Mindestzahl-Zusicherung
    // ersetzt statt sie zu wiederholen.
    expect(Object.keys(vertrag).length).toBeGreaterThan(0);
  });

  it("logMessages stimmt mit dem Vertrag ueberein (Schluessel, Sprachen, Platzhalter)", () => {
    pruefeVertrag(logMessages, vertrag, sprachen);
  });
});

describe("Rot-Beweise (Fixtures — ruehren die echte i18n.tsx nie an)", () => {
  it("eine Vorlage mit falschem Platzhalternamen (q.acount statt q.account) faellt auf", () => {
    const kaputt: LogMessagesForm = {
      ...logMessages,
      log_assets_added: {
        ...logMessages.log_assets_added,
        de: (q) => `${q.acount} Assets hinzugefuegt`,
      },
    };
    expect(() => pruefeVertrag(kaputt, vertrag, sprachen)).toThrow();
  });

  it("eine auskommentierte Vorlage (fehlender Schluessel zur Laufzeit) faellt auf", () => {
    const { log_share_failed: _entfernt, ...ohneEintrag } = logMessages;
    expect(() => pruefeVertrag(ohneEintrag, vertrag, sprachen)).toThrow();
  });

  it("ein Vertragseintrag ohne Sendestelle faellt auf", () => {
    const erweiterterVertrag: VertragForm = { ...vertrag, log_niemand_sendet_mich: [] };
    expect(() => pruefeVertrag(logMessages, erweiterterVertrag, sprachen)).toThrow();
  });
});
