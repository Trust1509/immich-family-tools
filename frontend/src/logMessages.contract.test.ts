import { describe, expect, it } from "vitest";
import vertrag from "./logMessages.contract.json";
import { LANG_LABELS, logMessages } from "./i18n";
import type { Lang, LogMessageParams } from "./i18n";

/**
 * Laufzeit-Vertragspruefung fuer die Protokollmeldungen (Nacharbeit 1+2 zu
 * #94, Frontend-Haelfte). Der Vorlaeufer dieses Tests las die Vorlagen als
 * TEXT (Regex auf `i18n.tsx`) und wurde vom Hauptagenten widerlegt: Eine
 * deutsche Vorlage von `log_album_created`, umgeschrieben zu
 * `(q) => ... ${q.acount} ...`, blieb bei allen damaligen Tests gruen, das
 * Protokoll zeigte zur Laufzeit "undefined" — andere Parameternamen,
 * Destrukturierung, `function`-Schreibweise und Kommentare (ein
 * auskommentierter Eintrag zaehlte als vorhanden) faellt bei einem
 * Textvergleich still aus dem Bild.
 *
 * Dieser Test ruft jede Vorlage TATSAECHLICH auf und zeichnet per `Proxy`
 * auf, welche Eigenschaften sie liest. Ein auskommentierter Eintrag
 * existiert zur Laufzeit schlicht nicht (er fehlt aus
 * `Object.keys(logMessages)`).
 *
 * NACHARBEIT 2 — WAS DIE ERSTE PROXY-FASSUNG NICHT SAH (vom Blindpruefer
 * gemessen, gruen geblieben): Ein einziger Aufruf mit einem einzigen
 * Platzhalterwert deckt nur EINEN Zweig einer bedingten Vorlage ab, z. B.
 *   `p.count === 1 ? `...${p.acount}...` : `...${p.account}...``
 * — mit nur einem Wert liest man entweder den einen oder den anderen Ast,
 * nie beide. Ebenso sah der reine `get`-Trap eine `in`-Abfrage
 * (`"acount" in p`) gar nicht, weil `in` den `has`-Trap ausloest, nicht
 * `get`. Die Antwort ist deshalb NICHT ein einziger Aufruf, sondern mehrere
 * mit unterschiedlichen Werten (0, 1, 2, "", "x" — deckt Vergleich auf eine
 * bestimmte Zahl, auf Null, auf einen leeren String und auf Wahrheitswert
 * ab) plus ein `has`-Trap, der VORHANDEN und ABWESEND je einmal durchspielt.
 * Die gelesenen Eigenschaften werden ueber alle Laeufe vereinigt.
 *
 * BEKANNTE GRENZE, DIE BLEIBT (kein Anspruch auf Vollstaendigkeit): Ein Lesen
 * ausserhalb des synchronen Aufrufs — etwa `setTimeout(() => use(p.x))` oder
 * eine `Promise`, die `p` erst spaeter ausliest — wird nicht erfasst, weil
 * dieser Test nach dem synchronen Rueckgabewert der Vorlagenfunktion nicht
 * weiterwartet. Keine heutige Vorlage tut das (alle sind reine, synchrone
 * Template-Strings); wird das je anders, deckt dieser Test es nicht ab.
 *
 * Beide Seiten (Backend: `backend/tests/test_log_messages.py`, Frontend:
 * hier) pruefen gegen DIESELBE Datei `logMessages.contract.json` — es gibt
 * keine zweite, unabhaengige Erfassung mehr, die auseinanderlaufen kann.
 */

// Deckt Vergleiche wie `p.x === 1`, `p.x === 0`, Wahrheitswert-Pruefungen
// (`p.x ? ... : ...`) und Leerstring-Pruefungen (`p.x === "" ? ... : ...`)
// ab, indem jede Vorlage einmal je Wert aufgerufen und die UNION der dabei
// gelesenen Eigenschaften gebildet wird.
const SONDEN_WERTE: Array<string | number> = [0, 1, 2, "", "x"];

function gelesenePlatzhalter(fn: (p: LogMessageParams) => string): Set<string> {
  const gelesen = new Set<string>();

  const aufrufen = (wert: string | number, vorhandenLautHas: boolean): void => {
    const proxy = new Proxy({} as LogMessageParams, {
      get(_target, eigenschaft) {
        if (typeof eigenschaft === "string") gelesen.add(eigenschaft);
        // Kein Template-String bricht an einem `undefined`-Wert ab (der
        // wuerde einfach als "undefined" eingesetzt) — der Grund fuer einen
        // echten Wert ist ein anderer: Manche Vorlage koennte eine
        // TYP-SPEZIFISCHE METHODE auf dem Wert aufrufen (z. B. `.toFixed()`
        // auf einer erwarteten Zahl), und ein `undefined` liesse GENAU DAS
        // mit einem eigenen Fehler abbrechen, bevor ueberhaupt alle
        // Eigenschaften gelesen wurden. Ein echter Wert haelt den Aufruf am
        // Laufen, ohne die gelesene Eigenschaftsmenge zu verfaelschen.
        return wert;
      },
      has(_target, eigenschaft) {
        if (typeof eigenschaft === "string") gelesen.add(eigenschaft);
        return vorhandenLautHas;
      },
    });
    try {
      fn(proxy);
    } catch {
      // Ein Wert war fuer diese Vorlage ungeeignet (z. B. eine
      // typ-spezifische Methode auf dem falschen Typ). Was bis zum Fehler
      // gelesen wurde, steht trotzdem schon in `gelesen` — der naechste
      // Sondenwert probiert es weiter.
    }
  };

  for (const wert of SONDEN_WERTE) {
    aufrufen(wert, true);
  }
  // Eigener Lauf fuer den ABWESEND-Zweig einer `"name" in p`-Abfrage — mit
  // den Laeufen oben (immer `vorhandenLautHas: true`) allein wuerde eine
  // Vorlage, die zwischen "Eigenschaft da" und "Eigenschaft fehlt"
  // verzweigt, nur den ersten Zweig zeigen.
  aufrufen("x", false);

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

  it("jede Parameterliste im Vertrag ist alphabetisch sortiert", () => {
    // Bislang nur behauptet (Docstring der Vorrunde), nicht geprueft — hier
    // nachgeholt: reine Lesbarkeits-/Diff-Eigenschaft der Datei selbst, hat
    // keinen Einfluss auf die Mengengleichheit oben.
    for (const [schluessel, parameter] of Object.entries(vertrag)) {
      expect(parameter, `Parameterliste von '${schluessel}'`).toEqual([...parameter].sort());
    }
  });

  it("logMessages stimmt mit dem Vertrag ueberein (Schluessel, Sprachen, Platzhalter)", () => {
    pruefeVertrag(logMessages, vertrag, sprachen);
  });
});

describe("Rot-Beweise (Fixtures — ruehren die echte i18n.tsx nie an)", () => {
  it("eine Vorlage mit falschem Platzhalternamen in NUR EINEM Zweig faellt auf", () => {
    // Reproduziert die vom Blindpruefer gemessene Luecke der Vorrunde: der
    // Tippfehler sitzt NUR im count===1-Zweig, der andere Zweig bleibt
    // korrekt. Ein Aufruf mit einem einzigen Wert haette (je nach Wert)
    // nur einen der beiden Zweige gesehen und die Vorlage waere zufaellig
    // gruen geblieben.
    const kaputt: LogMessagesForm = {
      ...logMessages,
      log_assets_added: {
        ...logMessages.log_assets_added,
        de: (p) =>
          p.count === 1
            ? `1 Asset von '${p.acount}' hinzugefuegt`
            : `${p.count} Assets von '${p.account}' hinzugefuegt`,
      },
    };
    expect(() => pruefeVertrag(kaputt, vertrag, sprachen)).toThrow();
  });

  it("eine `in`-Abfrage auf einen falschen Namen faellt auf", () => {
    const kaputt: LogMessagesForm = {
      ...logMessages,
      log_assets_added: {
        ...logMessages.log_assets_added,
        de: (p) => ("acount" in p ? `${p.account}` : "?"),
      },
    };
    expect(() => pruefeVertrag(kaputt, vertrag, sprachen)).toThrow();
  });

  it("eine auskommentierte Vorlage (fehlender Schluessel zur Laufzeit) faellt auf", () => {
    const { log_share_failed: _entfernt, ...ohneEintrag } = logMessages;
    expect(() => pruefeVertrag(ohneEintrag, vertrag, sprachen)).toThrow();
  });

  it("ein Vertragseintrag ohne Vorlage faellt auf", () => {
    const erweiterterVertrag: VertragForm = { ...vertrag, log_niemand_sendet_mich: [] };
    expect(() => pruefeVertrag(logMessages, erweiterterVertrag, sprachen)).toThrow();
  });
});
