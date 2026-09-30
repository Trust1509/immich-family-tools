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
 * NACHARBEIT 3 (#115) — ZWEI WEITERE RESTFORMEN, VOM BLINDPRUEFER DER
 * NACHLESE ZU #94 GEMESSEN (beide blieben mit den Sondenwerten aus
 * Nacharbeit 2 gruen):
 *   1. Eine Schwelle AUSSERHALB der Sondenwerte, z. B.
 *      `Number(p.count) > 5 ? `...${p.acount}...` : `...${p.account}...`` —
 *      keiner der Werte 0, 1, 2, "", "x" ist als Zahl > 5 (Number("") ist 0,
 *      Number("x") ist NaN), der wahre Zweig mit dem Tippfehler `acount`
 *      wurde nie gelesen. Behoben durch zwei grosse Zahlen in SONDEN_WERTE.
 *   2. `Object.hasOwn(p, "account")` loest NICHT den `has`-Trap aus, sondern
 *      `getOwnPropertyDescriptor` (`Object.hasOwn` ruft intern
 *      `[[GetOwnProperty]]`, nicht `[[HasProperty]]`) — ohne einen eigenen
 *      Trap dafuer faellt ein Proxy auf das TARGET zurueck (ein leeres
 *      Objekt), `Object.hasOwn` liefert dann IMMER `false`, unabhaengig vom
 *      Sondenwert, und der wahre Zweig wird nie gelesen. Behoben durch einen
 *      eigenen `getOwnPropertyDescriptor`-Trap, der wie `has` protokolliert
 *      und dem `vorhandenLautHas`-Flag folgt. Der Rot-Beweis unten nutzt
 *      `Object.prototype.hasOwnProperty.call(p, ...)` statt `Object.hasOwn`
 *      selbst — `tsconfig.json` steht auf ES2020-Lib, `Object.hasOwn` braucht
 *      ES2022; beide loesen denselben `[[GetOwnProperty]]`-Mechanismus und
 *      damit denselben Trap aus.
 *
 * BEKANNTE GRENZE, DIE BLEIBT (kein Anspruch auf Vollstaendigkeit): Ein Lesen
 * ausserhalb des synchronen Aufrufs — etwa `setTimeout(() => use(p.x))` oder
 * eine `Promise`, die `p` erst spaeter ausliest — wird nicht erfasst, weil
 * dieser Test nach dem synchronen Rueckgabewert der Vorlagenfunktion nicht
 * weiterwartet. Keine heutige Vorlage tut das (alle sind reine, synchrone
 * Template-Strings); wird das je anders, deckt dieser Test es nicht ab. Eine
 * Schwelle GROESSER als die groessten Sondenwerte hier (heute 100) wuerde
 * ebenso durchrutschen wie vor Nacharbeit 3 eine Schwelle > 5 — das ist
 * dieselbe Klasse von Luecke, nur verschoben, nicht behoben.
 *
 * NACHARBEIT 1 (#115) — WEITERE RESTFORMEN (Panel-Nachlese zu Nacharbeit 3):
 *   1. Alle Sondenwerte waren bis hierher GLEICH fuer JEDEN Parameter einer
 *      Vorlage — ein Vergleich ZWISCHEN zwei verschiedenen Parametern
 *      (`p.count !== p.account`) blieb deshalb immer falsch (bzw. immer
 *      wahr), egal welcher der Werte oben verwendet wurde, weil beide Seiten
 *      denselben Wert lasen. Ein zusaetzlicher Durchlauf mit
 *      NAMENSABHAENGIGEN Werten (die Laenge des Eigenschaftsnamens als Zahl)
 *      macht unterschiedlich benannte Parameter mit hoher Wahrscheinlichkeit
 *      auch unterschiedlich wertig.
 *   2. `typeof p.x === "boolean"` wurde nie wahr, weil kein Sondenwert ein
 *      Boolean war — der wahre Zweig blieb ungelesen. `true`/`false` ergaenzt.
 *   3. Ein negativer Vergleich (`p.count < 0`) und eine Zahl mit exaktem
 *      Vergleich (`p.count === 3`) waren nicht abgedeckt — `-1` und `3`
 *      ergaenzt.
 *   4. `String(p.album).length > 20` und `String(p.names).includes(",")`
 *      brauchen einen laengeren, kommahaltigen String — `"eins, zwei, drei"`
 *      ergaenzt (17 Zeichen reicht fuer `includes(",")`, nicht fuer
 *      `length > 20`; ein zweiter, laengerer Wert deckt beides).
 *   5. `Object.keys(p)`/Objekt-Rest-Destrukturierung (`const {a, ...rest} =
 *      p`) loesen den `ownKeys`-Trap aus, nicht `get`/`has` — ohne eigenen
 *      Trap faellt ein Proxy auf das leere Target zurueck, `Object.keys(p)`
 *      liefert IMMER `[]`. Ein eigener `ownKeys`-Trap liefert die bereits ueber
 *      `get`/`has`/`getOwnPropertyDescriptor` in FRUEHEREN Durchlaeufen
 *      gefundenen Eigenschaften zurueck (mit passenden Deskriptoren) — eine
 *      Vorlage, die AUSSCHLIESSLICH ueber Enumeration liest, bleibt bewusst
 *      als Luecke (leeres Ergebnis, siehe Docstring unten), weil dieser Test
 *      sonst wissen muesste, welche Namen es zu enumerieren gibt, bevor er
 *      sie gefunden hat.
 *
 * BEKANNTE GRENZE (Nacharbeit 1): Eine Vorlage, die NUR per `Object.keys(p)`/
 * Rest-Destrukturierung liest und NIE eine einzelne Eigenschaft direkt
 * anspricht, bleibt unentdeckt (der `ownKeys`-Trap kennt nur, was fruehere
 * Durchlaeufe bereits gefunden haben) — dieselbe Klasse Luecke wie die
 * Schwellen-Grenze oben, nur an einer anderen Stelle. Heute keine Vorlage in
 * dieser Form.
 *
 * Beide Seiten (Backend: `backend/tests/test_log_messages.py`, Frontend:
 * hier) pruefen gegen DIESELBE Datei `logMessages.contract.json` — es gibt
 * keine zweite, unabhaengige Erfassung mehr, die auseinanderlaufen kann.
 */

// Deckt Vergleiche wie `p.x === 1`, `p.x === 0`, Wahrheitswert-Pruefungen
// (`p.x ? ... : ...`) und Leerstring-Pruefungen (`p.x === "" ? ... : ...`)
// ab, indem jede Vorlage einmal je Wert aufgerufen und die UNION der dabei
// gelesenen Eigenschaften gebildet wird. 6 und 100 (Nacharbeit 3, #115)
// decken Schwellen ab, die ueber den kleinen Werten liegen (z. B.
// `Number(p.count) > 5 ? ... : ...`) — eine bekannte Restgrenze bleibt eine
// Schwelle > 100, siehe Moduldocstring. -1 (negativer Vergleich), 3 (exakter
// Vergleich ausserhalb 0/1/2), true (Wahrheitswert-TYP, nicht nur truthy
// Zahl/String — `typeof p.x === "boolean"` braucht einen ECHTEN Boolean) und
// ein laengerer, kommahaltiger String (`String(p.x).length > 20` UND
// `.includes(",")`) kamen in Nacharbeit 1 (#115) dazu. `null` (Nacharbeit 2,
// #115, Gegenpruefer NA1 T3/T11) deckt `p.x == null ? ... : ...`-Verzweigungen
// ab, die bei keinem Wert oben wahr werden -- kein heutiges Template in
// `i18n.tsx` benutzt dieses Muster (gemessen per Durchsicht), der Frontend-Typ
// `LogMessageParams` kennt `null` selbst nicht, die Sonde ist trotzdem ohne
// Fehlalarm moeglich, weil `aufrufen` jeden Fehler einer Vorlage schluckt
// (siehe `catch` unten) und `null` in einem Template-String klaglos zu
// "null" wird.
const SONDEN_WERTE: Array<string | number | boolean | null> = [
  0,
  1,
  2,
  "",
  "x",
  6,
  100,
  -1,
  3,
  true,
  "eins, zwei, drei, vier",
  null,
];

function gelesenePlatzhalter(fn: (p: LogMessageParams) => string): Set<string> {
  const gelesen = new Set<string>();

  const aufrufen = (
    wertFuer: (eigenschaft: string) => string | number | boolean | null,
    vorhandenLautHas: boolean
  ): void => {
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
        return typeof eigenschaft === "string" ? wertFuer(eigenschaft) : undefined;
      },
      has(_target, eigenschaft) {
        if (typeof eigenschaft === "string") gelesen.add(eigenschaft);
        return vorhandenLautHas;
      },
      // `Object.hasOwn(p, "x")` loest DIESEN Trap aus, nicht `has` (siehe
      // Moduldocstring, Nacharbeit 3 / #115) — ohne ihn faellt der Proxy auf
      // das leere Target zurueck und `Object.hasOwn` liefert immer `false`.
      getOwnPropertyDescriptor(_target, eigenschaft) {
        if (typeof eigenschaft === "string") gelesen.add(eigenschaft);
        if (!vorhandenLautHas || typeof eigenschaft !== "string") return undefined;
        return { configurable: true, enumerable: true, value: wertFuer(eigenschaft) };
      },
      // `Object.keys(p)`/Objekt-Rest-Destrukturierung (`const {a, ...rest} =
      // p`) loesen DIESEN Trap aus, nicht `get`/`has` (Nacharbeit 1, #115) —
      // ohne ihn faellt der Proxy auf das leere Target zurueck,
      // `Object.keys(p)` liefert IMMER `[]`. Liefert die in FRUEHEREN
      // Durchlaeufen bereits gefundenen Eigenschaften zurueck (bekannte
      // Grenze: eine Vorlage, die AUSSCHLIESSLICH per Enumeration liest und
      // nie eine einzelne Eigenschaft direkt anspricht, bleibt unentdeckt —
      // siehe Moduldocstring).
      ownKeys() {
        return [...gelesen];
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
    aufrufen(() => wert, true);
  }
  // Eigener Lauf fuer den ABWESEND-Zweig einer `"name" in p`-Abfrage — mit
  // den Laeufen oben (immer `vorhandenLautHas: true`) allein wuerde eine
  // Vorlage, die zwischen "Eigenschaft da" und "Eigenschaft fehlt"
  // verzweigt, nur den ersten Zweig zeigen.
  aufrufen(() => "x", false);
  // Eigener Lauf mit NAMENSABHAENGIGEN Werten (Nacharbeit 1, #115): alle
  // Laeufe oben liefern JEDEM Parameter denselben Wert — ein Vergleich
  // ZWISCHEN zwei verschiedenen Parametern (`p.count !== p.account`) bleibt
  // damit immer falsch (bzw. immer wahr), unabhaengig vom Sondenwert.
  //
  // NACHARBEIT 2 (#115, Gegenpruefer NA1 T1/T2): Der erste Versuch benutzte
  // die LAENGE des Eigenschaftsnamens als Wert — zwei gleich lange Namen
  // (z. B. "album" und "count", beide 5 Zeichen) bekamen dadurch DENSELBEN
  // Wert, ein Vergleich zwischen ihnen blieb also weiterhin nie
  // unterscheidbar. Selbst gemessen: 6 von 31 echten Vertragsschluesseln
  // haben mindestens ein Parameterpaar mit gleicher Namenslaenge
  // (log_album_created, log_album_name_adopted, log_album_renamed,
  // log_album_shared, log_assets_added_to_album, log_assets_linked). Der
  // Wert ist jetzt die POSITION des ERSTMALS gesehenen Namens (0, 1, 2, …) —
  // per Definition verschieden fuer zwei verschiedene Namen, unabhaengig
  // von deren Laenge.
  {
    const positionen = new Map<string, number>();
    aufrufen((eigenschaft) => {
      if (!positionen.has(eigenschaft)) positionen.set(eigenschaft, positionen.size);
      return positionen.get(eigenschaft)!;
    }, true);
  }
  // Ein letzter Durchlauf NACH allen anderen: der `ownKeys`-Trap oben
  // liefert erst hier etwas Sinnvolles zurueck, weil `gelesen` bis dahin
  // schon die Summe aller vorherigen Durchlaeufe enthaelt.
  aufrufen(() => 1, true);

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
    expect(() => pruefeVertrag(kaputt, vertrag, sprachen)).toThrow(/log_assets_added\/de/);
  });

  it("eine `in`-Abfrage auf einen falschen Namen faellt auf", () => {
    const kaputt: LogMessagesForm = {
      ...logMessages,
      log_assets_added: {
        ...logMessages.log_assets_added,
        de: (p) => ("acount" in p ? `${p.account}` : "?"),
      },
    };
    expect(() => pruefeVertrag(kaputt, vertrag, sprachen)).toThrow(/log_assets_added\/de/);
  });

  it("eine auskommentierte Vorlage (fehlender Schluessel zur Laufzeit) faellt auf", () => {
    const { log_share_failed: _entfernt, ...ohneEintrag } = logMessages;
    // Vitest kuerzt lange Array-Diffs ("…(29)") -- der Schluesselname selbst
    // steht deshalb nicht zuverlaessig in der Meldung, wohl aber, WELCHE
    // Zusicherung ausgeloest hat (Schluesselmengen-Vergleich, nicht z. B.
    // Sprachen oder Platzhalter).
    expect(() => pruefeVertrag(ohneEintrag, vertrag, sprachen)).toThrow(
      /Schluesselmenge von logMessages vs\. Vertrag/
    );
  });

  it("ein Vertragseintrag ohne Vorlage faellt auf", () => {
    const erweiterterVertrag: VertragForm = { ...vertrag, log_niemand_sendet_mich: [] };
    expect(() => pruefeVertrag(logMessages, erweiterterVertrag, sprachen)).toThrow(
      /Schluesselmenge von logMessages vs\. Vertrag/
    );
  });

  // Nacharbeit 3 (#115): die zwei Restformen aus dem Moduldocstring.

  it("eine Schwelle ausserhalb der kleinen Sondenwerte faellt auf", () => {
    // Ohne 6/100 in SONDEN_WERTE waere `Number(p.count) > 5` nie wahr
    // gewesen und der Tippfehler `acount` nie gelesen worden.
    const kaputt: LogMessagesForm = {
      ...logMessages,
      log_assets_added: {
        ...logMessages.log_assets_added,
        de: (p) =>
          Number(p.count) > 5
            ? `${p.count} Assets von '${p.acount}' hinzugefuegt`
            : `${p.count} Assets von '${p.account}' hinzugefuegt`,
      },
    };
    expect(() => pruefeVertrag(kaputt, vertrag, sprachen)).toThrow();
  });

  it("eine `hasOwnProperty`-Abfrage mit Tippfehler im wahren Zweig faellt auf", () => {
    // `Object.hasOwn(p, "account")` (so im Befund #115 benannt) braucht das
    // ES2022-Lib-Target — `tsconfig.json` steht auf ES2020 und diese Datei
    // haelt sich daran, statt den Compiler-Target projektweit anzuheben
    // (ausserhalb des Umfangs dieses Slices). `Object.prototype.
    // hasOwnProperty.call(p, "account")` loest denselben internen
    // `[[GetOwnProperty]]`-Mechanismus aus wie `Object.hasOwn` — und damit
    // denselben `getOwnPropertyDescriptor`-Trap, nicht `has`.
    //
    // `count` wird IMMER gelesen (haelt beide Faelle sonst ununterscheidbar).
    // Ohne den `getOwnPropertyDescriptor`-Trap faellt die Abfrage auf das
    // leere Target zurueck und liefert IMMER `false` — der Zweig mit dem
    // Tippfehler `acount` wuerde nie gelesen, `gelesen` waere
    // {"account","count"} und traefe zufaellig genau den Vertrag
    // (Nacharbeit-2-Lehre: "Testdaten muessen den Unterschied erzwingen").
    // Erst der Trap macht die Abfrage (bei den WAHR-Laeufen) wahr, liest
    // dadurch `acount` UND haelt die Divergenz zum Vertrag sichtbar.
    const kaputt: LogMessagesForm = {
      ...logMessages,
      log_assets_added: {
        ...logMessages.log_assets_added,
        de: (p) =>
          `${p.count}: ` +
          (Object.prototype.hasOwnProperty.call(p, "account") ? `${p.acount}` : `${p.account}`),
      },
    };
    expect(() => pruefeVertrag(kaputt, vertrag, sprachen)).toThrow(/log_assets_added\/de/);
  });

  // Nacharbeit 1 (#115): weitere Vorlagen-Formen — "alle Parameter bekommen
  // heute denselben Sondenwert" behoben (namensabhaengiger Durchlauf) plus
  // Schwellen/Typen, die die Sondenwerte vor Nacharbeit 1 nicht abdeckten.

  it("ein Vergleich auf einen konkreten Zahlenwert (3) mit Tippfehler faellt auf", () => {
    const kaputt: LogMessagesForm = {
      ...logMessages,
      log_assets_added: {
        ...logMessages.log_assets_added,
        de: (p) =>
          p.count === 3
            ? `genau drei von '${p.acount}' hinzugefuegt`
            : `${p.count} Assets von '${p.account}' hinzugefuegt`,
      },
    };
    expect(() => pruefeVertrag(kaputt, vertrag, sprachen)).toThrow(/log_assets_added\/de/);
  });

  it("ein negativer Vergleich mit Tippfehler faellt auf", () => {
    const kaputt: LogMessagesForm = {
      ...logMessages,
      log_assets_added: {
        ...logMessages.log_assets_added,
        de: (p) =>
          Number(p.count) < 0
            ? `ungueltige Anzahl von '${p.acount}'`
            : `${p.count} Assets von '${p.account}' hinzugefuegt`,
      },
    };
    expect(() => pruefeVertrag(kaputt, vertrag, sprachen)).toThrow(/log_assets_added\/de/);
  });

  it("eine typeof-boolean-Pruefung mit Tippfehler im wahren Zweig faellt auf", () => {
    // Ohne einen echten Boolean unter den Sondenwerten waere dieser Zweig
    // nie wahr gewesen (siehe Moduldocstring, Nacharbeit 1) — `true` deckt
    // das jetzt ab.
    const kaputt: LogMessagesForm = {
      ...logMessages,
      log_assets_added: {
        ...logMessages.log_assets_added,
        de: (p) =>
          typeof p.count === "boolean"
            ? `Flag von '${p.acount}'`
            : `${p.count} Assets von '${p.account}' hinzugefuegt`,
      },
    };
    expect(() => pruefeVertrag(kaputt, vertrag, sprachen)).toThrow(/log_assets_added\/de/);
  });

  it("eine Laengenpruefung auf einem String-Parameter mit Tippfehler faellt auf", () => {
    const kaputt: LogMessagesForm = {
      ...logMessages,
      log_album_shared: {
        ...logMessages.log_album_shared,
        de: (p) =>
          String(p.album).length > 20
            ? `langer Albumname: '${p.albu}'`
            : `Album '${p.album}' mit ${p.names} geteilt`,
      },
    };
    expect(() => pruefeVertrag(kaputt, vertrag, sprachen)).toThrow(/log_album_shared\/de/);
  });

  it("eine includes(',')-Pruefung auf einem String-Parameter mit Tippfehler faellt auf", () => {
    const kaputt: LogMessagesForm = {
      ...logMessages,
      log_album_shared: {
        ...logMessages.log_album_shared,
        de: (p) =>
          String(p.names).includes(",")
            ? `mehrere Namen: '${p.name}'`
            : `Album '${p.album}' mit ${p.names} geteilt`,
      },
    };
    expect(() => pruefeVertrag(kaputt, vertrag, sprachen)).toThrow(/log_album_shared\/de/);
  });

  it("ein Vergleich ZWISCHEN zwei verschiedenen Parametern mit Tippfehler faellt auf", () => {
    // Nacharbeit 1 (#115): ohne den namensabhaengigen Durchlauf in
    // `gelesenePlatzhalter` waeren p.count und p.account bei JEDEM
    // Sondenwert gleich (derselbe Wert fuer alle Eigenschaften einer
    // Sonde) — `p.count !== p.account` also nie wahr, der Zweig mit dem
    // Tippfehler nie gelesen.
    const kaputt: LogMessagesForm = {
      ...logMessages,
      log_assets_added: {
        ...logMessages.log_assets_added,
        de: (p) =>
          p.count !== p.account
            ? `${p.acount} Assets fuer '${p.account}'`
            : `${p.count} Assets von '${p.account}' hinzugefuegt`,
      },
    };
    expect(() => pruefeVertrag(kaputt, vertrag, sprachen)).toThrow(/log_assets_added\/de/);
  });

  it("eine Schwelle, die NUR der Sondenwert 6 (nicht 100) faengt, faellt auf", () => {
    // Beweist, dass 6 selbststaendig etwas faengt, nicht nur 100 (siehe
    // Moduldocstring, "Sondenwerte 6 und 100 je einzeln festhalten").
    const kaputt: LogMessagesForm = {
      ...logMessages,
      log_assets_added: {
        ...logMessages.log_assets_added,
        de: (p) =>
          Number(p.count) > 5 && Number(p.count) < 50
            ? `${p.count} Assets von '${p.acount}' hinzugefuegt`
            : `${p.count} Assets von '${p.account}' hinzugefuegt`,
      },
    };
    expect(() => pruefeVertrag(kaputt, vertrag, sprachen)).toThrow(/log_assets_added\/de/);
  });

  it("eine Schwelle, die NUR der Sondenwert 100 (nicht 6) faengt, faellt auf", () => {
    // Beweist die Kehrseite: 100 faengt selbststaendig etwas, das 6 nicht
    // faengt -- keiner der beiden Werte ist redundant.
    const kaputt: LogMessagesForm = {
      ...logMessages,
      log_assets_added: {
        ...logMessages.log_assets_added,
        de: (p) =>
          Number(p.count) > 50
            ? `${p.count} Assets von '${p.acount}' hinzugefuegt`
            : `${p.count} Assets von '${p.account}' hinzugefuegt`,
      },
    };
    expect(() => pruefeVertrag(kaputt, vertrag, sprachen)).toThrow(/log_assets_added\/de/);
  });

  // Nacharbeit 2 (#115): T1/T2, ownKeys-Rot-Beweis, GLEICHHEIT statt
  // Teilmenge, ALLE vier Sprachen, `null`-Sonde (T3/T11).

  it("zwei gleich lange Parameternamen mit vertauschtem Vergleich fallen auf", () => {
    // T1/T2 (Gegenpruefer NA1): Vor dieser Runde bekam der namensabhaengige
    // Durchlauf jeder Eigenschaft die LAENGE ihres Namens als Wert -- "album"
    // und "names" sind beide 5 Zeichen lang und damit ununterscheidbar. Der
    // Wert ist jetzt die POSITION des erstmals gesehenen Namens.
    const kaputt: LogMessagesForm = {
      ...logMessages,
      log_album_shared: {
        ...logMessages.log_album_shared,
        de: (p) =>
          p.album !== p.names
            ? `Tippfehlerzweig: '${p.albu}'`
            : `Album '${p.album}' mit ${p.names} geteilt`,
      },
    };
    expect(() => pruefeVertrag(kaputt, vertrag, sprachen)).toThrow(/log_album_shared\/de/);
  });

  it("eine Vorlage, die eine NICHT im Vertrag stehende Eigenschaft zusaetzlich liest, faellt auf", () => {
    // FM4 (Gegenpruefer NA1): `pruefeVertrag` vergleicht `gelesen` und
    // `erwartet` per `toEqual` (GLEICHHEIT) -- eine Mutation, die das auf
    // eine reine TEILMENGEN-Pruefung "jede erwartete Eigenschaft wurde
    // gelesen" (`erwartet ⊆ gelesen`) verkuerzt, blieb bislang GRUEN, weil
    // JEDER bisherige Rot-Beweis einen TYPO in einem Zweig einbaut -- das
    // erzeugt eine EXTRA gelesene Eigenschaft (z. B. "acount" NEBEN dem
    // weiterhin im anderen Zweig gelesenen "account"), keine FEHLENDE. Diese
    // Vorlage liest ZUSAETZLICH eine komplett erfundene Eigenschaft, ohne
    // dabei eine der echten zu verlieren -- eine reine "wurde alles Erwartete
    // gelesen"-Pruefung saehe das nicht, nur echte Gleichheit der Mengen tut
    // das.
    const kaputt: LogMessagesForm = {
      ...logMessages,
      log_album_shared: {
        ...logMessages.log_album_shared,
        de: (p) =>
          `Album '${p.album}' mit ${p.names} geteilt (${(p as Record<string, unknown>).ungueltig})`,
      },
    };
    expect(() => pruefeVertrag(kaputt, vertrag, sprachen)).toThrow(/log_album_shared\/de/);
  });

  it.each(["en", "pt-BR", "es-ES"] as const)(
    "ein Tippfehler in der Sprache '%s' (nicht nur 'de') faellt auf",
    (sprache) => {
      // FM5 (Gegenpruefer NA1): ALLE bisherigen Rot-Beweise aendern
      // ausschliesslich `de` -- eine Mutation, die die Sprachschleife in
      // `pruefeVertrag` auf eine feste Sprache verengt, waere bislang nie
      // aufgefallen. Je eine Sonde fuer die drei anderen Sprachen.
      const kaputt: LogMessagesForm = {
        ...logMessages,
        log_assets_added: {
          ...logMessages.log_assets_added,
          [sprache]: (p: LogMessageParams) =>
            p.count === 1 ? `Tippfehlerzweig: '${p.acount}'` : `${p.count}/${p.account}`,
        },
      };
      expect(() => pruefeVertrag(kaputt, vertrag, sprachen)).toThrow(
        new RegExp(`log_assets_added/${sprache}`)
      );
    }
  );

  it("eine Vorlage, die ueber Object.keys(p) verzweigt, faellt auf (ownKeys-Trap)", () => {
    // Rot-Beweis fuer den `ownKeys`-Trap selbst (vorher unbewiesen -- siehe
    // Moduldocstring): `Object.keys(p)` loest ausschliesslich den `ownKeys`-
    // Trap aus, nicht `get`/`has`. Diese Vorlage verzweigt im ERSTEN Aufruf
    // (der `ownKeys`-Trap kennt noch NICHTS, `gelesen` ist zu diesem
    // Zeitpunkt leer) in den TIPPFEHLER-Zweig (`p.acount`), weil
    // `Object.keys(p).includes("count")` dann `false` ist; erst NACHDEM
    // `count` per direktem Zugriff im else-Zweig bekannt wurde, macht der
    // `ownKeys`-Trap den Vergleich ab dem naechsten Aufruf wahr und der
    // korrekte Zweig greift. Ohne den `ownKeys`-Trap bliebe
    // `Object.keys(p)` immer `[]` (der Proxy faellt auf das leere Target
    // zurueck) -- `includes("count")` waere NIE wahr, der Tippfehler-Zweig
    // wuerde NIE gelesen, und diese Sonde bliebe faelschlich gruen.
    const kaputt: LogMessagesForm = {
      ...logMessages,
      log_assets_added: {
        ...logMessages.log_assets_added,
        de: (p) =>
          Object.keys(p).includes("count")
            ? `Tippfehlerzweig: '${p.acount}'`
            : `${p.count} Assets von '${p.account}' hinzugefuegt`,
      },
    };
    expect(() => pruefeVertrag(kaputt, vertrag, sprachen)).toThrow(/log_assets_added\/de/);
  });

  it("ein `== null`-Vergleich mit Tippfehler im wahren Zweig faellt auf", () => {
    // T3/T11 (Gegenpruefer NA1): `p.x == null ? … : …` wird bei keinem der
    // bisherigen Sondenwerte wahr -- `null` selbst ergaenzt das.
    const kaputt: LogMessagesForm = {
      ...logMessages,
      log_assets_added: {
        ...logMessages.log_assets_added,
        de: (p) =>
          p.count == null // eslint-disable-line eqeqeq -- die Vorlage selbst prueft bewusst == null
            ? `unbekannte Anzahl von '${p.acount}'`
            : `${p.count} Assets von '${p.account}' hinzugefuegt`,
      },
    };
    expect(() => pruefeVertrag(kaputt, vertrag, sprachen)).toThrow(/log_assets_added\/de/);
  });
});
