"""Waechter: Bis zur ersten Ablehnung wird NICHTS geschrieben.

WARUM ES DIESE DATEI GIBT
-------------------------
Die Regel "alles, was ablehnen kann, gehoert vor den ersten Schreibvorgang"
wurde in `routers/albums.py` DREIMAL verletzt — ueber drei aufeinander
folgende Slices, jedes Mal vom selben Bauer, jedes Mal nachdem er sie im
Slice davor behoben hatte. Beim dritten Mal stand der Kommentar, der genau
davor warnt, vier Zeilen ueber der Aenderung.

Die Regel wurde bis hierher von Kommentaren und Aufmerksamkeit getragen. Nach
dem Massstab dieses Repos (`docs/agents/lehren.md`) ist das Disziplin, kein
Waechter. Hier ist der Waechter.

Die Folge einer Verletzung ist nicht kosmetisch: Der Aufrufer bekommt einen
Fehler, NACHDEM Personen in Immich umbenannt, Protokollzeilen geschrieben
oder Paare als abgeglichen markiert wurden. Eine Teilausfuehrung, die sich
als Eingabefehler ausgibt — und die der Nutzer nicht zurueckdrehen kann.

ZWEI TEILE, UND WARUM ES ZWEI BRAUCHT
-------------------------------------
TEIL A (statisch) nimmt die Endpunkte, die die Anwendung WIRKLICH montiert
hat, liest ihren Quelltext als Baum und verzweigt wie das Programm.

Hier stand einmal "prueft JEDEN Ausfuehrungspfad". Das war zu weit, und der
Blindpruefer hat es widerlegt: Der Schleifenkoerper lief nur EINMAL, also
blieb "je Feld pruefen, dann schreiben" unsichtbar — ab der zweiten Runde
liegt die Ablehnung dort hinter einem Schreibvorgang. Behoben (#89), samt
`for ... else` und einem Fehlfund bei `try`/`finally` mit `return`.

Der Satz kommt trotzdem nicht zurueck. Was Teil A NICHT sieht, steht
vollstaendig am Ende dieser Datei unter BENANNTE GRENZEN, jeder Punkt mit
Issue. Eine zu weite Zusage ausgerechnet in der Datei, die Disziplin durch
einen Waechter ersetzen soll, ist der Fehler, der spaeter jemanden trifft.

TEIL B (zur Laufzeit) faehrt je Endpunkt EINEN Ablehnungsfall durch die echte
Tuer und prueft, dass genau die erwartete Ablehnung ankommt UND nichts
geschrieben wurde. Teil A kennt nur Namen, Teil B kennt Zustaende.

DASS BEIDE NOETIG SIND, IST GEMESSEN (21.09.2026): Teil B wurde zuerst
gebaut — allein. Danach wurde der dritte Vorfall absichtlich wieder
eingebaut, und Teil B blieb GRUEN. Der Grund ist strukturell: Teil B kann je
Endpunkt nur den Ablehnungsweg fahren, den er von aussen ERREICHT, und das
ist fast immer der FRUEHESTE. Der Defekt lebt am SPAETESTEN.

Umgekehrt haelt Teil A einen AUFRUF fuer eine WIRKUNG:
`store.delete_account("gibt-es-nicht")` kehrt zurueck, ohne etwas zu aendern.
Solche Faelle stehen in ERLAUBT — mit einer ANZAHL je Fundtext, sodass
jeder zusaetzliche Fund in derselben Funktion rot ist, auch einer mit
demselben Text.

Die Anzahl ist teuer bezahlt: Vorher stand dort eine Menge von Texten, und
ein zweiter, ECHTER Fund mit demselben Text wurde mitgedeckt — bei
`account_not_found`, dem haeufigsten in `accounts.py`. Gemessen vom
Blindpruefer, der genau das gebaut hat (#91).

WAS DIE ERSTE FASSUNG FALSCH HATTE
----------------------------------
Zwei Pruefstimmen haben unabhaengig gemessen, dass der Waechter sich an
mehreren Stellen selbst ausgehebelt hat. Alle sind unten im Code an ihrer
Stelle benannt; hier die Liste, damit keine davon leise zurueckkommt:

  1. Der Vollstaendigkeitstest las `main.app.routes` und bekam die LEERE
     MENGE (dort liegen `_IncludedRouter`-Huellen ohne `path`). Er konnte
     nie rot werden.
  2. Zwei Tabellenzeilen zeigten auf `/api/faces/...`, waehrend der Router
     `/api/matches` heisst. Eine wurde nie gefahren, die andere war gruen an
     einem generischen 404.
  3. Teil B prueft nur "irgendein 4xx". Damit war er auch dann vollstaendig
     gruen, wenn ALLE Router abgehaengt waren oder die Anmeldung jede
     Anfrage mit 401 abwies.
  4. Teil A las `routers/*.py` per Dateimuster. Ein Umzug der Router in ein
     anderes Verzeichnis liess ihn mit NULL analysierten Endpunkten gruen.
  5. Die Schreibvorgaenge hatten keinen Fixpunkt: `mark_all_pairs_synced`
     schreibt ueber `mark_names_synced` und war unsichtbar — ausgerechnet
     in `sync_names_multi`, dem Endpunkt aller drei Vorfaelle.
  6. ERLAUBT befreite die ganze Funktion. Ein echter neuer Fehler in einer
     befreiten Funktion kam durch.
  7. `match`/`case` wurde flachgewalzt (Fehlfunde), Schreibvorgaenge aus
     `except`-Handlern wurden nicht weitergetragen (Luecke), und ein
     Schreibvorgang in einem Zweig, der mit `return` endet, wurde faelschlich
     weitergetragen (Fehlfund).

Alle Daten erfunden; das Repo ist oeffentlich.
"""

import ast
import inspect
import io
import json
import pathlib
import textwrap

import pytest
from fastapi.testclient import TestClient

import main

WURZEL = pathlib.Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# TEIL A — statisch: kein Ablehnungsweg hinter einem Schreibvorgang
# ---------------------------------------------------------------------------
#
# Die Listen, mit denen dieser Teil arbeitet, stammen AUS DEM BAUM, nicht aus
# dem Gedaechtnis des Bauers. Das ist Absicht: Eine erinnerte Liste hat in
# diesem Projekt schon mehrfach eine Zusage getragen, die nicht stimmte
# (`docs/agents/lehren.md`).


def _baum(rel: str) -> ast.Module:
    return ast.parse(io.open(WURZEL / rel, encoding="utf-8").read())


def _funktionen(baum: ast.AST) -> dict:
    return {n.name: n for n in ast.walk(baum)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _gerufene_namen(knoten: ast.AST) -> set:
    """Jeder Name, der in dieser Funktion aufgerufen wird."""
    aus = set()
    for c in ast.walk(knoten):
        if isinstance(c, ast.Call):
            f = c.func
            if isinstance(f, ast.Attribute):
                aus.add(f.attr)
            elif isinstance(f, ast.Name):
                aus.add(f.id)
    return aus


def _erreichbar(fns: dict, direkt: set) -> set:
    """Fixpunkt: wer `direkt` erreicht — unmittelbar ODER ueber Aufrufe.

    BEIDE Eigenschaften dieses Waechters brauchen denselben Fixpunkt, und
    beide Male ist das gemessen, nicht vermutet:

    * Bei den ABLEHNUNGEN haengt Vorfall 1 daran — dort stand kein `raise`
      hinter dem Schreibvorgang, sondern ein AUFRUF von
      `_name_des_bestehenden_albums`, der seinerseits ablehnt.
    * Bei den SCHREIBVORGAENGEN fehlte er in der ersten Fassung. Folge:
      `ConfigStore.mark_all_pairs_synced` schreibt ueber `mark_names_synced`
      und war damit unsichtbar — ausgerechnet in `sync_names_multi`, dem
      Endpunkt aller drei Vorfaelle.
    """
    kann = set(direkt)
    while True:
        neu = set(kann)
        for name, knoten in fns.items():
            if name not in kann and _gerufene_namen(knoten) & kann:
                neu.add(name)
        if neu == kann:
            return kann
        kann = neu


# Womit eine Ablehnung geworfen wird. `errors.*` ist die Hausform; die beiden
# anderen stehen hier, weil ein anderer Test sie zwar verbietet (keine nackte
# HTTPException), ein Waechter sich aber nicht auf einen anderen Waechter
# verlassen soll.
ABLEHNUNGS_TYPEN = {"HTTPException", "AppError"}


def _fehlernamen(baum: ast.AST) -> set:
    """Namen, die diese Datei direkt aus `errors` importiert hat.

    `from errors import match_not_found` ist dieselbe Ablehnung wie
    `errors.match_not_found()`, nur anders geschrieben — und die vorige
    Fassung sah sie nicht (Zweitstimme, gemessen: Verstoss im Baum, Suite
    gruen).
    """
    aus = set()
    for n in ast.walk(baum):
        if isinstance(n, ast.ImportFrom) and n.module:
            if n.module.split(".")[-1] == "errors":
                aus |= {a.asname or a.name for a in n.names}
    return aus


def _ist_ablehnung(raise_knoten, fehlernamen=frozenset()) -> str | None:
    if not isinstance(raise_knoten.exc, ast.Call):
        return None
    f = raise_knoten.exc.func
    if (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
            and f.value.id == "errors"):
        return f"raise errors.{f.attr}()"
    if isinstance(f, ast.Name) and (f.id in ABLEHNUNGS_TYPEN or f.id in fehlernamen):
        return f"raise {f.id}()"
    if isinstance(f, ast.Attribute) and f.attr in ABLEHNUNGS_TYPEN:
        return f"raise {f.attr}()"
    return None


def _lehnt_direkt_ab(knoten: ast.AST, fehlernamen=frozenset()) -> bool:
    return any(_ist_ablehnung(k, fehlernamen) for k in ast.walk(knoten)
               if isinstance(k, ast.Raise))


def _ablehnende_huelle(fns: dict, fehlernamen=frozenset()) -> set:
    return _erreichbar(fns, {n for n, k in fns.items()
                             if _lehnt_direkt_ab(k, fehlernamen)})


def _schreibende_huelle(fns: dict, schreibt: set) -> set:
    """Funktionen DIESER Datei, die einen Schreibvorgang erreichen.

    Fuer Ablehnungen gab es diese Huelle von Anfang an, fuer Schreibvorgaenge
    nicht. Gemessen von der Zweitstimme: Schon das harmlose Auslagern von
    `store.clear_log()` in eine gewoehnliche Modul-Hilfsfunktion liess Teil A
    den Schreibvorgang verlieren — eine Ablehnung danach war kein Fund mehr,
    und die ganze Suite blieb gruen.
    """
    direkt = {n for n, k in fns.items()
              if _gerufene_namen(k) & schreibt}
    return _erreichbar(fns, direkt)


def _schreibende_store_methoden() -> set:
    """Jede ConfigStore-Methode, die `self._save()` erreicht — auch ueber Umwege."""
    fns = _funktionen(_baum("services/config_store.py"))
    direkt = {name for name, k in fns.items() if "_save" in _gerufene_namen(k)}
    return _erreichbar(fns, direkt) - {"_save"}


# ---------------------------------------------------------------------------
# Der Aufrufgraph ueber MODULGRENZEN (#90)
# ---------------------------------------------------------------------------
#
# Die Huellen liefen frueher je Endpunkt-DATEI. Damit endete die Analyse an
# der Dateigrenze, und ein voellig gewoehnlicher Umbau hat den Waechter
# blind gemacht — die Zweitstimme hat es gemessen und als Blocker eingestuft:
#
#     # routers/accounts.py
#     from services.konten import aktualisiere_konto
#     ...
#     return aktualisiere_konto(request, account_id, updates)
#
#     # services/konten.py
#     def aktualisiere_konto(request, account_id, updates):
#         request.app.state.store.clear_log()
#         raise errors.account_not_found()
#
# Schreiben, dann ablehnen — und 20 Tests gruen. `_check_immich_version`
# liegt heute nur ZUFAELLIG in `accounts.py`; nach `services/` gezogen waere
# sie genauso verschwunden.
#
# Jetzt wird der Graph ueber alle Projektmodule gebildet und ueber die
# IMPORTE aufgeloest, nicht ueber blosse Namensgleichheit: `from services.x
# import y` und `import services.x as z` fuehren beide auf dieselbe Datei.
# Namensgleiche Funktionen in verschiedenen Modulen bleiben dadurch
# verschieden.


def _projekt_dateien() -> list:
    """Alle Projektmodule unter WURZEL — ohne Tests und ohne Fremdcode."""
    aus = []
    for pfad in sorted(WURZEL.rglob("*.py")):
        teile = set(pfad.relative_to(WURZEL).parts)
        if teile & {"tests", "__pycache__", ".venv", "venv", "site-packages"}:
            continue
        aus.append(pfad)
    return aus


def _modul_datei(modulname: str):
    """`services.sync_service` -> WURZEL/services/sync_service.py, falls es sie gibt."""
    if not modulname:
        return None
    kandidat = WURZEL.joinpath(*modulname.split("."))
    for p in (kandidat.with_suffix(".py"), kandidat / "__init__.py"):
        if p.exists():
            return p
    return None


def _importe(baum: ast.AST) -> tuple:
    """(Namen-Importe, Modul-Aliase) dieser Datei.

    Namen-Importe: `from services.x import y as z` -> {z: (datei_von_x, "y")}
    Modul-Aliase:  `from services import x` / `import services.x as z`
                   -> {x bzw. z: datei_von_x}
    """
    namen, aliase = {}, {}
    for n in ast.walk(baum):
        if isinstance(n, ast.ImportFrom) and n.module:
            eigen = _modul_datei(n.module)
            for a in n.names:
                lokal = a.asname or a.name
                unter = _modul_datei(f"{n.module}.{a.name}")
                if unter is not None:
                    aliase[lokal] = unter       # `from services import x`
                elif eigen is not None:
                    namen[lokal] = (eigen, a.name)
        elif isinstance(n, ast.Import):
            for a in n.names:
                datei = _modul_datei(a.name)
                if datei is not None:
                    aliase[a.asname or a.name.split(".")[0]] = datei
    return namen, aliase


_stand_puffer: dict = {}


def _projekt_stand() -> dict:
    """Einmal je Lauf: Baeume, Funktionen, Importe und die beiden Huellen.

    Die Huellen sind Mengen von (Datei, Funktionsname) — also modulweit
    eindeutig, nicht nach blossem Namen.
    """
    if _stand_puffer:
        return _stand_puffer

    schreibt_store = _schreibende_store_methoden()
    schreibt_immich = _immich_schreibsenken()

    dateien = {}
    for pfad in _projekt_dateien():
        baum = ast.parse(io.open(pfad, encoding="utf-8").read())
        namen, aliase = _importe(baum)
        dateien[pfad] = {
            "fns": _funktionen(baum),
            "fehlernamen": _fehlernamen(baum),
            "namen": namen,
            "aliase": aliase,
        }

    def ziele(pfad, knoten):
        """Die (Datei, Name), die diese Funktion nachweislich aufruft."""
        d = dateien[pfad]
        aus = set()
        for c in ast.walk(knoten):
            if not isinstance(c, ast.Call):
                continue
            f = c.func
            if isinstance(f, ast.Name):
                if f.id in d["fns"]:
                    aus.add((pfad, f.id))
                elif f.id in d["namen"]:
                    aus.add(d["namen"][f.id])
            elif isinstance(f, ast.Attribute):
                basis = f.value.id if isinstance(f.value, ast.Name) else None
                if basis in d["aliase"]:
                    aus.add((d["aliase"][basis], f.attr))
        return aus

    kanten = {}
    saat_lehnt, saat_schreibt = set(), set()
    for pfad, d in dateien.items():
        for name, knoten in d["fns"].items():
            kanten[(pfad, name)] = ziele(pfad, knoten)
            if _lehnt_direkt_ab(knoten, d["fehlernamen"]):
                saat_lehnt.add((pfad, name))
            # Ein Schreibvorgang ist: eine schreibende ConfigStore-Methode
            # ODER eine veraendernde ImmichClient-Methode. Die zweite Haelfte
            # ist noetig, damit `sync_service.sync_names_multi` weiter als
            # Schreibvorgang gilt — es ruft `client.update_person`.
            if _gerufene_namen(knoten) & (schreibt_store | schreibt_immich):
                saat_schreibt.add((pfad, name))

    def huelle(saat):
        kann = set(saat)
        while True:
            neu = set(kann)
            for knoten, z in kanten.items():
                if knoten not in kann and z & kann:
                    neu.add(knoten)
            if neu == kann:
                return kann
            kann = neu

    _stand_puffer.update({
        "dateien": dateien,
        "kanten": kanten,
        "schreibt_store": schreibt_store,
        "schreibt_immich": schreibt_immich,
        "lehnt": huelle(saat_lehnt),
        "schreibt": huelle(saat_schreibt),
    })
    return _stand_puffer


TRY_TYPEN = (ast.Try,) + ((ast.TryStar,) if hasattr(ast, "TryStar") else ())
ENDE_TYPEN = (ast.Return, ast.Raise, ast.Break, ast.Continue)


def _eigene_knoten(stmt: ast.stmt):
    """Die Ausdruecke DIESES Statements — ohne die eingebetteten Bloecke.

    Ohne diese Trennung meldet der Waechter Zweige gegeneinander: ein
    Schreibvorgang im `if`-Zweig und eine Ablehnung im `else`-Zweig liegen
    auf verschiedenen Pfaden und sind kein Fund. Genau das hat die erste
    Fassung zweimal gemeldet (`create_album`), gemessen am sauberen Baum —
    und bei `match`/`case` ein drittes Mal, weil es keinen eigenen Zweig
    hatte und in den Sammelfall fiel.
    """
    if isinstance(stmt, (ast.If, ast.While)):
        quellen = [stmt.test]
    elif isinstance(stmt, (ast.For, ast.AsyncFor)):
        quellen = [stmt.iter]
    elif isinstance(stmt, (ast.With, ast.AsyncWith)):
        quellen = [i.context_expr for i in stmt.items]
    elif isinstance(stmt, ast.Match):
        quellen = [stmt.subject]
    elif isinstance(stmt, TRY_TYPEN):
        quellen = []
    else:
        quellen = [stmt]
    for q in quellen:
        yield from ast.walk(q)


def _ereignisse(stmt, schreibt_store, lehnt_store, lehnt_helfer,
                schreibt_helfer, fehlernamen=frozenset(),
                modul_lehnt=frozenset(), modul_schreibt=frozenset()):
    """(Zeile, 'schreibt'|'lehnt_ab', Text) fuer dieses eine Statement."""
    aus = []
    for k in _eigene_knoten(stmt):
        if isinstance(k, ast.Raise):
            text = _ist_ablehnung(k, fehlernamen)
            if text:
                aus.append(((k.lineno, k.col_offset), "lehnt_ab", text))
        elif isinstance(k, ast.Call):
            f = k.func
            if isinstance(f, ast.Attribute):
                basis = f.value.id if isinstance(f.value, ast.Name) else None
                if basis == "errors":
                    continue
                # Eine Funktion kann BEIDES: erst ablehnen, dann schreiben.
                # Dann zaehlt sie als beides — sonst verschwindet eine
                # Ablehnung, sobald jemand ihrer Funktion ein `_save()` gibt.
                if f.attr in lehnt_store:
                    aus.append((( k.lineno, k.col_offset), "lehnt_ab", f"{f.attr}() lehnt ab"))
                if (basis, f.attr) in modul_lehnt:
                    aus.append(((k.lineno, k.col_offset), "lehnt_ab",
                                f"{basis}.{f.attr}() lehnt ab"))
                if f.attr in schreibt_store:
                    aus.append(((k.lineno, k.col_offset), "schreibt", f"store.{f.attr}()"))
                elif (basis, f.attr) in modul_schreibt:
                    aus.append(((k.lineno, k.col_offset), "schreibt",
                                f"{basis}.{f.attr}()"))
            elif isinstance(f, ast.Name):
                # Ein Helfer kann ebenfalls BEIDES. Reihenfolge wie oben:
                # erst ablehnen, dann schreiben.
                if f.id in lehnt_helfer:
                    aus.append(((k.lineno, k.col_offset), "lehnt_ab", f"{f.id}() lehnt ab"))
                if f.id in schreibt_helfer:
                    aus.append(((k.lineno, k.col_offset), "schreibt", f"{f.id}() schreibt"))
    # Bei gleicher Zeile zuerst die Ablehnung: Ein Aufruf, der beides kann,
    # lehnt ab, BEVOR er schreibt — sonst deckt er sich selbst zu.
    aus.sort(key=lambda e: (e[0], 0 if e[1] == "lehnt_ab" else 1))
    return aus


def _pfad_pruefen(stmts, geschrieben, funde, listen):
    """Laeuft die Statements der Reihe nach und verzweigt wie das Programm.

    `geschrieben` ist (Zeile, Text) des ersten Schreibvorgangs auf DIESEM
    Pfad — oder None.

    Rueckgabe: `(geschrieben, endet, aus_break, aus_continue)`.

    * `endet` — der Block wird IMMER verlassen (`return`, `raise`, `break`,
      `continue`). Ohne die Angabe wurde ein Schreibvorgang aus einem Zweig,
      der mit `return` endet, hinter das `if` getragen; eine Ablehnung danach
      war ein FEHLFUND. Und ein Schreibvorgang aus einem `except`-Handler
      wurde gar nicht weitergetragen; eine Ablehnung danach war eine LUECKE.

    * `aus_break` / `aus_continue` — der Schreibstand an einem `break` bzw.
      `continue`. DIE brauchte es, weil `endet` allein vier verschiedene
      Dinge in einen Topf wirft: `return` und `raise` verlassen die FUNKTION,
      `break` und `continue` nur den BLOCK. Ein Schreibvorgang vor einem
      `continue` lebt weiter — er erreicht den Schleifenkopf und steht damit
      in Runde 2 vor der Ablehnung.

      Gemessen vom Blindpruefer an der haeufigsten Form ueberhaupt:

          for eintrag in eintraege:
              if eintrag.id in bekannt:
                  store.aktualisieren(eintrag)
                  continue
              raise errors.unbekannt()

      Die kam durch, obwohl der Slice davor genau diese Klasse zu schliessen
      behauptete. Eine Schleife VERBRAUCHT die beiden Werte; nach aussen
      gibt sie sie nicht weiter, denn ein `break` gehoert der innersten
      Schleife.
    """
    endet = False
    aus_break = aus_continue = None
    for stmt in stmts:
        # Eine verschachtelte Funktion wird HIER nicht ausgefuehrt. Ihre
        # Zeilen gehoeren nicht in diesen Pfad; ist sie selbst ein Endpunkt,
        # wird sie eigens analysiert.
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

        for stelle, art, text in _ereignisse(stmt, *listen):
            if art == "lehnt_ab" and geschrieben:
                funde.append((stelle, text, geschrieben))
            elif art == "schreibt" and not geschrieben:
                geschrieben = (stelle, text)

        if isinstance(stmt, ast.If):
            a, ea, ba, ca = _pfad_pruefen(stmt.body, geschrieben, funde, listen)
            b, eb, bb, cb = _pfad_pruefen(stmt.orelse, geschrieben, funde, listen)
            aus_break = aus_break or ba or bb
            aus_continue = aus_continue or ca or cb
            geschrieben = geschrieben or _erster(((a, ea), (b, eb)))
            if ea and eb and stmt.orelse:
                endet = True
        elif isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
            # ZWEI RUNDEN, und das ist der Punkt (#89): Der Koerper laeuft in
            # der Wirklichkeit mehrfach. Was Runde 1 geschrieben hat, steht
            # fuer Runde 2 VOR dem Schleifenkopf — eine Ablehnung oben im
            # Koerper liegt dann hinter einem Schreibvorgang:
            #
            #     for feld, wert in updates.items():
            #         if feld not in ERLAUBTE_FELDER:
            #             raise errors.account_not_found()
            #         store.update_account(kennung, {feld: wert})
            #
            # Feld 3 ungueltig ⇒ Felder 1-2 sind geschrieben, der Aufrufer
            # bekommt 404. Genau die bewachte Klasse.
            a, ea, ba, ca = _pfad_pruefen(stmt.body, geschrieben, funde, listen)

            # Drei verschiedene Wege aus dem Koerper, und sie fuehren an
            # verschiedene Orte:
            durchgelaufen = None if ea else a      # faellt unten heraus
            zum_kopf = durchgelaufen or ca         # erreicht den Kopf wieder
            hinter_die_schleife = zum_kopf or ba   # steht danach

            # Runde 2 sieht nur, was den Kopf WIRKLICH wieder erreicht.
            # Endet jeder Koerperpfad mit `break`, laeuft die Schleife
            # hoechstens einmal — dann gibt es keine zweite Runde und damit
            # auch keinen Fehlfund (auch das gemessen).
            if zum_kopf is not None and zum_kopf is not geschrieben:
                # Bei `while` gehoert der KOPF zu jeder Runde: Seine
                # Bedingung wird vor der zweiten Iteration erneut
                # ausgewertet, und wenn sie ablehnen kann, steht die
                # Ablehnung dann hinter dem Schreibvorgang der ersten
                # (Zweitstimme, gemessen). Bei `for` nicht: Das Iterable
                # wird genau einmal ausgewertet.
                if isinstance(stmt, ast.While):
                    for _stelle, _art, _text in _ereignisse(stmt, *listen):
                        if _art == "lehnt_ab":
                            funde.append((_stelle, _text, zum_kopf))
                _pfad_pruefen(stmt.body, zum_kopf, funde, listen)

            # Das `else` laeuft, wenn die Schleife OHNE `break` endet — es
            # sieht den Koerper, aber nicht den `break`-Zweig.
            b, _eb, _bb, _cb = _pfad_pruefen(
                stmt.orelse, zum_kopf or geschrieben, funde, listen)
            geschrieben = geschrieben or hinter_die_schleife or b
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            a, ea, ba, ca = _pfad_pruefen(stmt.body, geschrieben, funde, listen)
            aus_break = aus_break or ba
            aus_continue = aus_continue or ca
            geschrieben = geschrieben or a
            endet = endet or ea
        elif isinstance(stmt, ast.Match):
            # Jeder Fall laeuft gegen den Stand VOR dem `match` — sonst sieht
            # `case _` den Schreibvorgang aus `case 1`, und die Zweigtrennung
            # ist wieder aufgehoben.
            #
            # Ob die Faelle erschoepfend sind, sagt der Baum nicht; deshalb
            # nie "endet", aber jeder Fall traegt seinen Schreibvorgang weiter.
            vorher = geschrieben
            zweige = [_pfad_pruefen(fall.body, vorher, funde, listen)
                      for fall in stmt.cases]
            for _w, _e, bz, cz in zweige:
                aus_break = aus_break or bz
                aus_continue = aus_continue or cz
            geschrieben = vorher or _erster([(w, e) for w, e, _b, _c in zweige])
        elif isinstance(stmt, TRY_TYPEN):
            im_try, e_try, b_try, c_try = _pfad_pruefen(
                stmt.body, geschrieben, funde, listen)
            # Ein `except` laeuft NACH dem, was im `try` schon passiert ist.
            handler = []
            for h in stmt.handlers:
                handler.append(_pfad_pruefen(
                    h.body, im_try or geschrieben, funde, listen))
            nach, e_else, b_else, c_else = _pfad_pruefen(
                stmt.orelse, im_try or geschrieben, funde, listen)
            weiter = ([(im_try, e_try), (nach, e_else)]
                      + [(w, e) for w, e, _b, _c in handler])
            basis = geschrieben or _erster(weiter)
            fin, e_fin, b_fin, c_fin = _pfad_pruefen(
                stmt.finalbody, basis, funde, listen)
            geschrieben = basis or fin
            for bz, cz in ([(b_try, c_try), (b_else, c_else), (b_fin, c_fin)]
                           + [(b, c) for _w, _e, b, c in handler]):
                aus_break = aus_break or bz
                aus_continue = aus_continue or cz
            # Ein `try` wird verlassen, wenn das `finally` es verlaesst ODER
            # wenn jeder Weg hindurch es tut: der Rumpf (bzw. sein `else`) und
            # JEDER Handler. Die erste Fassung sah nur das `finally` — und
            # meldete deshalb eine unerreichbare Ablehnung nach
            # `try: ... return / finally: pass` als FEHLFUND (#89).
            # `e_try OR e_else`, nicht nur `e_else`: Terminiert der Rumpf
            # immer, ist das `else` unerreichbar — die erste Fassung hielt
            # den Weg dann faelschlich fuer offen und meldete eine
            # unerreichbare Ablehnung danach (Zweitstimme, gemessen).
            durch_den_rumpf = (e_try or e_else) if stmt.orelse else e_try
            alle_wege = durch_den_rumpf and all(e for _w, e, _b, _c in handler)
            endet = endet or e_fin or alle_wege
        elif isinstance(stmt, ast.Break):
            aus_break = aus_break or geschrieben
            endet = True
        elif isinstance(stmt, ast.Continue):
            aus_continue = aus_continue or geschrieben
            endet = True
        elif isinstance(stmt, (ast.Return, ast.Raise)):
            endet = True

        if endet:
            break
    return geschrieben, endet, aus_break, aus_continue


def _ohne_dubletten(funde):
    """Derselbe Fund zaehlt einmal, auch wenn zwei Pfade ihn erreichen.

    Noetig, seit der Schleifenkoerper ZWEIMAL gelaufen wird (#89): Ein Fund
    aus Runde 1 taucht in Runde 2 wieder auf.

    Geschluesselt wird auf die AST-STELLE (Zeile UND Spalte) plus den Text.
    Hier stand einmal nur die Zeile, mit der Begruendung, zwei verschiedene
    Ablehnungen in derselben Zeile gebe es nicht. Das ist falsch:
    `ablehner(a); ablehner(b)` sind zwei erreichbare Stellen mit demselben
    Text in derselben Zeile — der erste Aufruf kann zurueckkehren und der
    zweite ablehnen. Die Zeilen-Entdopplung hat den zweiten verschluckt
    (Zweitstimme, gemessen). Mit der Spalte bleiben beide stehen.
    """
    gesehen, aus = set(), []
    for stelle, text, quelle in funde:
        if (stelle, text) in gesehen:
            continue
        gesehen.add((stelle, text))
        aus.append((stelle, text, quelle))
    return aus


def _erster(paare):
    """Der erste Schreibvorgang aus Zweigen, die WEITERLAUFEN."""
    for wert, endet in paare:
        if wert and not endet:
            return wert
    return None


def _ist_endpunkt(knoten) -> bool:
    return any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
               and d.func.attr in {"get", "post", "put", "patch", "delete"}
               for d in knoten.decorator_list)


# Stellen, an denen Teil A einen AUFRUF fuer eine WIRKUNG haelt — mit Grund.
#
# Der Wert ist die Menge der hier ERWARTETEN Fundtexte. Ein ZUSAETZLICHER
# Fund in derselben Funktion bleibt damit rot: Die erste Fassung befreite die
# ganze Funktion, und ein echter neuer Reihenfolgefehler darin kam durch
# (beide Pruefstimmen, unabhaengig gemessen).
#
# Ein Eintrag, zu dem es keinen Fund mehr gibt, macht die Suite ebenfalls rot:
# eine Ausnahme, die niemand mehr braucht, verschwindet, statt stumm etwas
# Neues zu decken.
ERLAUBT = {
    ("accounts.py", "delete_account"): (
        {("raise errors.account_not_found()", "store.delete_account()"): 1},
        "`store.delete_account` liefert bei unbekannter Kennung False, OHNE zu "
        "schreiben; die Ablehnung danach IST diese Antwort. Dass dabei wirklich "
        "nichts geschrieben wird, prueft Teil B "
        "(DELETE /api/accounts/gibt-es-nicht).",
    ),
    ("albums.py", "delete_managed_album"): (
        {("raise errors.managed_album_not_found()", "store.delete_managed_album()"): 1},
        "Wie oben, mit `store.delete_managed_album`; geprueft von Teil B "
        "(DELETE /api/sync/albums/gibt-es-nicht).",
    ),
}


def _montierte_endpunkte():
    """(Pfad, Methoden, Funktion) fuer alles, was die App WIRKLICH montiert hat.

    NICHT ueber ein Dateimuster wie `routers/*.py`: Ein Umzug der Router in
    ein anderes Verzeichnis liess die erste Fassung mit NULL analysierten
    Endpunkten gruen (Zweitstimme, gemessen — sie hat die Router nach
    `backend/api/` verschoben und die Suite blieb gruen).

    Und nicht ueber `route.path` allein: In `app.routes` liegen
    `_IncludedRouter`-Huellen, deren `path` `None` ist. Hier wird deshalb
    rekursiv in `original_router.routes` abgestiegen.
    """
    aus = []

    def lauf(routen):
        for r in routen:
            unter = getattr(r, "original_router", None)
            if unter is not None and hasattr(unter, "routes"):
                lauf(unter.routes)
                continue
            fn = getattr(r, "endpoint", None)
            pfad = getattr(r, "path", None) or ""
            if fn is None or not pfad.startswith("/api/"):
                continue
            # Nur PROJEKTCODE. FastAPI haengt eigene Endpunkte ein (Swagger,
            # OpenAPI, ReDoc); fuer die wurde `fastapi/applications.py` als
            # Huelle geparst, und sie polsterten die Mindestzahl um drei auf
            # (Blindpruefer). Sie gehoeren uns nicht und koennen unsere Regel
            # nicht verletzen.
            quelle = inspect.getsourcefile(fn)
            if quelle is None or not pathlib.Path(quelle).is_relative_to(WURZEL):
                continue
            aus.append((pfad, sorted(getattr(r, "methods", None) or []), fn))

    lauf(main.app.routes)
    return aus


def _quelle_einer_funktion(fn):
    """Baum der Funktion, mit den ZEILENNUMMERN der echten Datei."""
    zeilen, start = inspect.getsourcelines(fn)
    baum = ast.parse(textwrap.dedent("".join(zeilen)))
    ast.increment_lineno(baum, start - 1)
    return baum


def _endpunkt_funde(quelltext: str, listen) -> dict:
    """{Endpunkt: [(Zeile, Text, erster Schreibvorgang)]} fuer eine Quelle.

    Laeuft ueber `ast.walk`, nicht ueber `baum.body`: Ein Endpunkt, der in
    einem `if`-Block steht, war der ersten Fassung unsichtbar — und `main.py`
    macht mit `if STATIC_DIR.exists():` genau das.
    """
    aus = {}
    for knoten in ast.walk(ast.parse(quelltext)):
        if not isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not _ist_endpunkt(knoten):
            continue
        funde = []
        _pfad_pruefen(knoten.body, None, funde, listen)
        if funde:
            aus[knoten.name] = _ohne_dubletten(funde)
    return aus


# Eine Quelle, die es nur fuer diesen Test gibt: Endpunkte mit bekanntem
# Ergebnis — wie viele, zaehlt der Test selbst.
#
# Hier stand eine Zahl, und sie war nach zwei Slices falsch (elf statt
# zweiundzwanzig). In dieser Datei zaehlt so eine Zahl; also steht jetzt
# keine mehr da, die niemand nachrechnet. Sie prueft die Mechanik von Teil A gegen eine Vorlage, die sich
# NICHT mitbewegt, wenn jemand die Router umbaut.
#
# Ohne sie waere die Mechanik nur so lange bewiesen, wie zufaellig ein echter
# Fund im Baum steht (`docs/agents/lehren.md` §18).
MECHANIK_QUELLE = '''
from errors import nein_direkt

@router.post("/x")
def ablehnung_ueber_direkten_import(store):
    store.schreib()
    raise nein_direkt()

def schreibender_helfer(store):
    store.schreib()

@router.post("/x")
def schreibt_ueber_einen_helfer(store):
    schreibender_helfer(store)
    raise errors.nein()

@router.post("/x")
def nach_dem_schreiben(store):
    store.schreib()
    raise errors.nein()

@router.post("/x")
def vor_dem_schreiben(store):
    raise errors.nein()
    store.schreib()

@router.post("/x")
def in_getrennten_zweigen(store, a):
    if a:
        store.schreib()
    else:
        raise errors.nein()

@router.post("/x")
def in_getrennten_faellen(store, a):
    match a:
        case 1:
            store.schreib()
        case _:
            raise errors.nein()

@router.post("/x")
def zweig_endet_mit_return(store, a):
    if a:
        store.schreib()
        return 1
    raise errors.nein()

@router.post("/x")
def im_handler(store):
    try:
        store.schreib()
    except Exception:
        raise errors.nein()

@router.post("/x")
def handler_schreibt_dann_ablehnung(store, risky):
    try:
        risky()
    except Exception:
        store.schreib()
    raise errors.nein()

@router.post("/x")
def ueber_zwei_aufrufe(store):
    store.schreib()
    helfer()

def helfer():
    noch_tiefer()

def noch_tiefer():
    raise errors.nein()

@router.post("/x")
def ablehnung_oben_schreiben_unten(store, xs):
    for x in xs:
        if not x:
            raise errors.nein()
        store.schreib()

@router.post("/x")
def continue_traegt_den_schreibvorgang(store, eintraege, bekannt):
    for e in eintraege:
        if e in bekannt:
            store.schreib()
            continue
        raise errors.nein()

@router.post("/x")
def break_traegt_nach_aussen(store, xs):
    for x in xs:
        if x:
            store.schreib()
            break
    raise errors.nein()

@router.post("/x")
def continue_in_der_inneren_schleife(store, xs):
    for x in xs:
        for y in x:
            if y:
                store.schreib()
                continue
            raise errors.nein()

def ablehner(x):
    raise errors.nein()

@router.post("/x")
def while_kopf_lehnt_ab(store, x):
    while ablehner(x):
        store.schreib()

@router.post("/x")
def for_kopf_lehnt_ab(store, x):
    for y in ablehner(x):
        store.schreib()

@router.post("/x")
def try_else_nach_return(store):
    try:
        store.schreib()
        return 1
    except Exception:
        return 2
    else:
        pass
    raise errors.nein()

@router.post("/x")
def zwei_ablehnungen_in_einer_zeile(store, a, b):
    store.schreib()
    ablehner(a); ablehner(b)

@router.post("/x")
def koerper_endet_immer_mit_break(store, xs):
    for x in xs:
        if not x:
            raise errors.nein()
        store.schreib()
        break

@router.post("/x")
def suchschleife_mit_else(store, xs):
    for x in xs:
        if x:
            store.schreib()
            break
    else:
        raise errors.nein()

@router.post("/x")
def schreiben_und_ablehnung_im_koerper(store, xs):
    for x in xs:
        store.schreib()
        raise errors.nein()

@router.post("/x")
def schleife_mit_else(store, xs):
    for x in xs:
        store.schreib()
    else:
        raise errors.nein()

@router.post("/x")
def try_mit_return_dann_ablehnung(store):
    try:
        store.schreib()
        return 1
    finally:
        pass
    raise errors.nein()

@router.post("/x")
def nach_einer_schleife(store, xs):
    for x in xs:
        store.schreib()
    raise errors.nein()

@router.post("/x")
def nur_in_einer_inneren_funktion(store):
    def wird_nie_gerufen():
        store.schreib()
        raise errors.nein()
    return wird_nie_gerufen

def bedingt_eingehaengt():
    @router.post("/y")
    def in_einer_funktion(store):
        store.schreib()
        raise errors.nein()
'''

MECHANIK_FUNDE = {
    "ablehnung_ueber_direkten_import",  # `from errors import ...`
    "schreibt_ueber_einen_helfer",      # Schreibvorgang in einen Helfer ausgelagert
    "nach_dem_schreiben",               # der einfache Fall
    "im_handler",                       # `except` laeuft NACH dem try-Block
    "handler_schreibt_dann_ablehnung",  # der Handler schreibt, danach Ablehnung
    "ueber_zwei_aufrufe",               # Ablehnung ueber eine Aufrufkette
    "nach_einer_schleife",              # Schreibvorgang im Schleifenkoerper
    "ablehnung_oben_schreiben_unten",   # ab Runde 2 liegt die Ablehnung dahinter
    "schleife_mit_else",                # das `else` laeuft NACH dem Koerper
    "schreiben_und_ablehnung_im_koerper",  # beides im Koerper: nur EIN Fund
    "continue_traegt_den_schreibvorgang",  # `continue` erreicht den Kopf wieder
    "break_traegt_nach_aussen",            # `break` traegt ihn hinter die Schleife
    "continue_in_der_inneren_schleife",    # und das auch verschachtelt
    "while_kopf_lehnt_ab",                 # der `while`-Kopf laeuft vor JEDER Runde
    "zwei_ablehnungen_in_einer_zeile",     # zwei Stellen, nicht eine
    "in_einer_funktion",                # Endpunkt, der nicht auf Modulebene steht
}
# Wo die Anzahl der Funde der Sache nach feststeht, steht sie hier.
MECHANIK_ANZAHL = {
    "zwei_ablehnungen_in_einer_zeile": 2,
}

MECHANIK_NICHT_FUNDE = {
    "vor_dem_schreiben": "richtige Reihenfolge",
    "in_getrennten_zweigen": "if/else sind nie derselbe Pfad",
    "in_getrennten_faellen": "match/case ebenso",
    "zweig_endet_mit_return": "der schreibende Zweig verlaesst die Funktion",
    "nur_in_einer_inneren_funktion": "die innere Funktion wird hier nicht gerufen",
    "try_mit_return_dann_ablehnung": "der Rumpf verlaesst die Funktion, die "
                                     "Ablehnung danach ist unerreichbar",
    "koerper_endet_immer_mit_break": "jeder Koerperpfad endet mit `break`, die "
                                     "Schleife laeuft hoechstens EINMAL",
    "suchschleife_mit_else": "das `else` laeuft nur OHNE `break` — es sieht den "
                             "Schreibvorgang des break-Zweigs nie",
    "for_kopf_lehnt_ab": "das Iterable eines `for` wird GENAU EINMAL ausgewertet, "
                         "anders als eine `while`-Bedingung",
    "try_else_nach_return": "der Rumpf verlaesst die Funktion immer, also ist das "
                            "`else` und alles danach unerreichbar",
}


def test_mechanik_trennt_pfade_und_folgt_aufrufen():
    """Teil A gegen eine erfundene Quelle mit bekanntem Ergebnis."""
    fns = _funktionen(ast.parse(MECHANIK_QUELLE))
    namen = _fehlernamen(ast.parse(MECHANIK_QUELLE))
    listen = ({"schreib"}, set(), _ablehnende_huelle(fns, namen),
              _schreibende_huelle(fns, {"schreib"}), namen)
    alle = _endpunkt_funde(MECHANIK_QUELLE, listen)
    gefunden = set(alle)

    # Derselbe Fund darf nur EINMAL dastehen. Seit der Schleifenkoerper
    # zweimal gelaufen wird (#89), erreicht Runde 2 die Funde aus Runde 1
    # erneut — `ablehnung_oben_schreiben_unten` ist genau dieser Fall. Ohne
    # Entdopplung meldet die Ausgabe doppelt, und die ANZAHLEN in ERLAUBT
    # waeren von der Rundenzahl abhaengig statt von der Sache.
    for name, funde in alle.items():
        stellen = [(st, t) for st, t, _q in funde]
        assert len(stellen) == len(set(stellen)), (
            f"{name} meldet denselben Fund mehrfach: {stellen}")

    # Und wo die ANZAHL der Sache nach feststeht, wird sie gezaehlt. Ohne das
    # merkte niemand, dass die Entdopplung eine von zwei Stellen verschluckt:
    # Der Endpunkt stand weiter in der Fundmenge, nur mit einem Fund statt
    # zwei (gemessen an der Mutation, die auf die Zeile statt auf die
    # AST-Stelle entdoppelt).
    for name, erwartet in MECHANIK_ANZAHL.items():
        assert len(alle.get(name, [])) == erwartet, (
            f"{name}: {len(alle.get(name, []))} Funde statt {erwartet} — "
            "zwei Aufrufe in einer Zeile sind ZWEI erreichbare Stellen.")

    assert gefunden == MECHANIK_FUNDE, (
        "Die Mechanik von Teil A hat sich geaendert.\n"
        "Kein Fund sein MUESSEN ausserdem: "
        + ", ".join(f"{n} ({g})" for n, g in MECHANIK_NICHT_FUNDE.items())
    )


def test_erreichbarkeit_folgt_aufrufketten():
    """Der Fixpunkt traegt fuer BEIDE Eigenschaften, nicht nur fuer Ablehnungen."""
    quelle = '''
def schreibt_direkt(self):
    self._save()

def schreibt_ueber_eine_stufe(self):
    self.schreibt_direkt()

def schreibt_ueber_zwei_stufen(self):
    self.schreibt_ueber_eine_stufe()

def schreibt_gar_nicht(self):
    return 1
'''
    fns = _funktionen(ast.parse(quelle))
    direkt = {n for n, k in fns.items() if "_save" in _gerufene_namen(k)}
    assert direkt == {"schreibt_direkt"}
    assert _erreichbar(fns, direkt) == {
        "schreibt_direkt", "schreibt_ueber_eine_stufe", "schreibt_ueber_zwei_stufen",
    }, "Ohne Fixpunkt bleibt ein Schreibvorgang ueber zwei Stufen unsichtbar."


def _uebrige(funde, erlaubt):
    """Die Funde, die eine Ausnahme NICHT deckt.

    Geschluesselt auf (Ablehnung, SCHREIBVORGANG) und auf eine ANZAHL — beides
    ist gemessen noetig:

    * Nur der Ablehnungstext: Ein zweiter, ECHTER Fund mit demselben Text in
      derselben Funktion wurde mitgedeckt.
    * Ohne den Schreibvorgang: Ein ANDERER, echter Schreibvorgang vor
      derselben Ablehnung wurde mitgedeckt — gemessen an `delete_account`
      mit einem eingebauten `dismiss_match`, 18 Tests gruen. Die Begruendung
      der Ausnahme nennt den Schreibvorgang ohnehin im Klartext; jetzt tut es
      der Schluessel auch.
    """
    rest = dict(erlaubt)
    aus = []
    for stelle, text, quelle in funde:
        schluessel = (text, quelle[1])
        if rest.get(schluessel, 0) > 0:
            rest[schluessel] -= 1
        else:
            aus.append((stelle, text, quelle))
    return aus


def _ueberschuss(funde, erlaubt):
    """Was eine Ausnahme deckt, ohne dass es dafuer noch Funde gibt."""
    wirklich: dict = {}
    for _stelle, text, quelle in funde:
        schluessel = (text, quelle[1])
        wirklich[schluessel] = wirklich.get(schluessel, 0) + 1
    return {s: n - wirklich.get(s, 0) for s, n in erlaubt.items()
            if n > wirklich.get(s, 0)}


def test_ausnahmen_decken_genau_ihren_anlass():
    """Selbstprobe fuer die Ausnahmelogik — gegen eine feste Vorlage.

    Fuer die Mechanik von Teil A gab es diese Vorlage von Anfang an, fuer die
    Ausnahmelogik nicht: Sie stand inline im Testrumpf und war deshalb nicht
    pruefbar. Der Blindpruefer hat gemessen, dass man die Anzahl-Verrechnung
    ersatzlos entfernen kann, ohne dass ein Test rot wird — also war die
    Kernneuerung des Slices, der sie eingefuehrt hat, unbewiesen.
    """
    schreib = (7, "store.schreib()")
    fremd = (9, "store.etwas_anderes()")
    erlaubt = {("raise errors.x()", "store.schreib()"): 1}
    gedeckt = [(8, "raise errors.x()", schreib)]

    assert _uebrige(gedeckt, erlaubt) == []
    assert _ueberschuss(gedeckt, erlaubt) == {}

    zweimal = gedeckt + [(12, "raise errors.x()", schreib)]
    assert len(_uebrige(zweimal, erlaubt)) == 1, (
        "Ein ZWEITER Fund mit demselben Text muss uebrig bleiben.")

    anderer_schreibvorgang = [(8, "raise errors.x()", fremd)]
    assert _uebrige(anderer_schreibvorgang, erlaubt) == anderer_schreibvorgang, (
        "Dieselbe Ablehnung nach einem ANDEREN Schreibvorgang ist ein eigener "
        "Fund und darf nicht mitgedeckt werden.")

    assert _ueberschuss([], erlaubt) == {("raise errors.x()", "store.schreib()"): 1}


def test_jede_ausnahme_deckt_mindestens_einen_fall():
    """Eine Anzahl von 0 oder weniger deckt nichts und meldet auch nichts.

    Ein stiller Blindeintrag also — und der faellt niemandem auf, weil beide
    Gegenpruefungen ihn ueberspringen (Blindpruefer, HINWEIS).
    """
    for schluessel, (erlaubt, _grund) in ERLAUBT.items():
        for anlass, anzahl in erlaubt.items():
            assert anzahl >= 1, f"{schluessel}: {anlass} deckt {anzahl} Faelle"


def _erreichbare_projektfunktionen(endpunkte) -> set:
    """(Datei, Name) jeder Projektfunktion, die ein Endpunkt erreicht.

    Endpunkte selbst sind nicht dabei — die werden ueber ihr Funktionsobjekt
    analysiert, mit den Zeilennummern der echten Datei.
    """
    stand = _projekt_stand()
    kanten = stand["kanten"]
    rand = set()
    eigene = set()
    for fn in endpunkte:
        datei = pathlib.Path(inspect.getsourcefile(fn))
        eigene.add((datei, fn.__name__))
        rand |= kanten.get((datei, fn.__name__), set())
    erreicht = set()
    while rand:
        knoten = rand.pop()
        if knoten in erreicht or knoten not in kanten:
            continue
        erreicht.add(knoten)
        rand |= kanten[knoten] - erreicht
    return erreicht - eigene


def test_keine_ablehnung_hinter_einem_schreibvorgang():
    """Teil A: auf KEINEM Pfad steht eine Ablehnung hinter einem Schreibvorgang."""
    funktionen = {fn for _pfad, _methoden, fn in _montierte_endpunkte()}
    # EINE Zusicherung, nicht zwei: "nicht leer" kann nichts allein rot
    # machen, was diese Zahl nicht auch faengt — und eine Zusicherung, die
    # sich nicht einzeln rot beweisen laesst, ist nach dem Massstab dieses
    # Repos Beruhigung, kein Waechter. Die Zahl dagegen faellt allein, wenn
    # der Weg zu den montierten Endpunkten verengt wird.
    assert len(funktionen) >= 10, (
        f"Nur {len(funktionen)} montierte Endpunkt-Funktionen gefunden. Damit "
        "prueft dieser Test fast nichts mehr — genau der Zustand, in dem die "
        "erste Fassung gruen war. Sieh nach, wie die App ihre Router einhaengt "
        "und ob `_montierte_endpunkte` ihnen noch folgt."
    )

    gemeldet: dict = {}
    for fn in funktionen:
        datei = pathlib.Path(inspect.getsourcefile(fn))
        listen = _listen_fuer_datei(datei)
        funde: list = []
        _pfad_pruefen(_quelle_einer_funktion(fn).body[0].body, None, funde, listen)
        if funde:
            gemeldet[(datei.name, fn.__name__)] = _ohne_dubletten(funde)

    # UND jede Projektfunktion, die ein Endpunkt erreicht.
    #
    # Ohne das bleibt die Luecke aus #90 offen, auch mit Aufrufgraph: Liegt
    # der Verstoss IM Helfer (erst schreiben, dann ablehnen), sieht die
    # Aufrufstelle nur "schreibt und lehnt ab" — welche Reihenfolge darin
    # gilt, steht dort nicht. Gemessen: Der Umbau der Zweitstimme blieb auch
    # mit Graph gruen, bis die Analyse in die Funktion selbst hineinging.
    for datei, name in sorted(_erreichbare_projektfunktionen(funktionen)):
        knoten = _projekt_stand()["dateien"][datei]["fns"][name]
        funde = []
        _pfad_pruefen(knoten.body, None, funde, _listen_fuer_datei(datei))
        if funde:
            gemeldet[(datei.name, name)] = _ohne_dubletten(funde)

    unerwartet = {}
    for schluessel, funde in gemeldet.items():
        uebrig = _uebrige(funde, ERLAUBT.get(schluessel, ({}, ""))[0])
        if uebrig:
            unerwartet[schluessel] = uebrig

    zeilen = [""]
    for (datei, fn), funde in unerwartet.items():
        erste = funde[0][2]
        zeilen.append(f"{datei}:{fn} — erster Schreibvorgang Zeile "
                      f"{erste[0][0]} ({erste[1]}), danach:")
        zeilen += [f"    Zeile {st[0]}: {t}" for st, t, _ in funde]
    zeilen += [
        "",
        "Alles, was ablehnen kann, gehoert VOR den ersten Schreibvorgang —",
        "sonst bekommt der Aufrufer einen Fehler, nachdem schon geschrieben wurde.",
        "Schreibt der Aufruf gar nicht, gehoert er mit Begruendung nach ERLAUBT.",
    ]
    assert not unerwartet, "\n".join(zeilen)

    veraltet = sorted(set(ERLAUBT) - set(gemeldet))
    assert not veraltet, (
        "Diese ERLAUBT-Eintraege haben keinen Fund mehr und gehoeren entfernt, "
        f"sonst deckt die Ausnahme irgendwann etwas Neues: {veraltet}"
    )
    # Und die Anzahlen: Eine Ausnahme, die MEHR deckt, als es Funde gibt,
    # wartet nur darauf, den naechsten echten Fund zu verschlucken.
    zu_weit = {k: _ueberschuss(gemeldet.get(k, []), erwartet)
               for k, (erwartet, _grund) in ERLAUBT.items()}
    zu_weit = {k: v for k, v in zu_weit.items() if v}
    assert not zu_weit, (
        "Diese ERLAUBT-Eintraege decken mehr, als es Funde gibt — die Ausnahme "
        f"ist groesser als ihr Anlass: {zu_weit}"
    )


# ---------------------------------------------------------------------------
# TEIL B — zur Laufzeit: die Ablehnung kommt an, und nichts wurde geschrieben
# ---------------------------------------------------------------------------

# ERFUNDEN und als solches erkennbar.
TESTMARKE = "nur-fuer-den-test-kein-geheimnis"
KOPF = {"Authorization": f"Bearer {TESTMARKE}"}

KONTEN = {
    "konto-1": {"id": "konto-1", "name": "Konto Eins",
                "immich_url": "http://beispiel.invalid", "api_key": "platzhalter-1",
                "color": "#111111", "user_id": "u1"},
    "konto-2": {"id": "konto-2", "name": "Konto Zwei",
                "immich_url": "http://beispiel.invalid", "api_key": "platzhalter-2",
                "color": "#222222", "user_id": "u2"},
}

ALBUM = {
    "id": "a1", "match_id": "m-1", "album_id": "ia-1", "album_name": "Testalbum",
    "group_id": "gruppe-1", "owner_account_id": "konto-1",
    "person_refs": [{"account_id": "konto-1", "person_id": "p1", "person_name": "p1",
                     "account_name": "Konto Eins", "account_color": "#111111"}],
    "created_at": "2026-01-01T00:00:00+00:00", "last_synced_at": None,
    "total_assets": 0, "status": "active",
}

# WO Teil B den Schreibvorgang abgreift — und warum genau dort.
#
# Erste Fassung: Zustandsvergleich (Datei + `store._data`) plus die
# oeffentlichen Funktionen von `sync_service`. Die Zweitstimme hat beides
# gebrochen, jeweils mit vollstaendig gruener Suite:
#
#  * Ein Schreibvorgang, der denselben Inhalt zurueckschreibt, ist im
#    Zustandsvergleich UNSICHTBAR — gemessen an `DELETE /api/sync/log` bei
#    leerem Protokoll: `bytes_equal=True`, waehrend Inode und
#    `.bak`-Sicherung sich sehr wohl geaendert hatten.
#  * Die Dienst-Attrappen haengen am MODUL `sync_service`. Ein Router, der
#    `from services.sync_service import sync_names_multi` schreibt, haelt die
#    alte Referenz und laeuft daran vorbei — gemessen, Marker gesetzt, 17
#    Tests gruen.
#
# Beides ist behoben, indem nicht mehr die AUFRUFER instrumentiert werden,
# sondern die tiefsten echten SCHREIBSENKEN, und zwar auf der KLASSE:
#
#  * `ConfigStore._save` — jeder Schreibvorgang auf die Datei geht dort
#    durch, auch der, der nichts aendert.
#  * die schreibenden `ImmichClient`-Methoden — abgeleitet daraus, welche
#    davon `put`/`post`/`patch`/`delete` benutzen, nicht aus einer Liste.
#
# An der Klasse zu patchen macht die Importform der Aufrufer gleichgueltig.
# Der Zustandsvergleich bleibt zusaetzlich bestehen, als zweite Sicht.

# POST heisst bei Immich nicht immer "schreiben": Die Suche nimmt ihre
# Filter im Koerper entgegen. Benannt statt stillschweigend uebergangen —
# und wenn die Methode verschwindet, faellt die Zusicherung darunter auf.
IMMICH_LIEST_MIT_POST = {"_search_metadata_all_pages"}


def _immich_schreibsenken() -> set:
    """ImmichClient-Methoden, die eine veraendernde HTTP-Methode benutzen."""
    baum = _baum("services/immich_client.py")
    klasse = next(n for n in baum.body
                  if isinstance(n, ast.ClassDef) and n.name == "ImmichClient")
    aus = set()
    for m in klasse.body:
        if not isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
               and c.func.attr in {"post", "put", "patch", "delete"}
               for c in ast.walk(m)):
            aus.add(m.name)
    return aus - IMMICH_LIEST_MIT_POST


def test_die_immich_schreibsenken_sind_die_erwarteten():
    """Ein Fehlgriff bei der Ableitung darf nicht still passieren.

    Diese Liste ist die einzige Stelle, an der Teil B einen Schreibvorgang
    nach aussen ueberhaupt sehen kann. Eine neue Methode gehoert entweder
    dazu oder mit Grund nach IMMICH_LIEST_MIT_POST.
    """
    assert _immich_schreibsenken() == {
        "update_person", "create_album", "add_assets_to_album",
        "share_album_with_users",
    }
    assert IMMICH_LIEST_MIT_POST <= set(
        _funktionen(_baum("services/immich_client.py"))), (
        "Eine Ausnahme in IMMICH_LIEST_MIT_POST zeigt auf eine Methode, die es "
        "nicht mehr gibt — dann deckt sie irgendwann etwas Neues."
    )


@pytest.fixture
def aufbau(tmp_path, monkeypatch):
    """Client plus eine Liste, in die JEDER Schreibvorgang seinen Namen legt."""
    from services.config_store import ConfigStore
    from services.immich_client import ImmichClient

    pfad = tmp_path / "accounts.json"
    pfad.write_text(json.dumps({
        "accounts": KONTEN, "managed_albums": [ALBUM],
        "dismissed_match_ids": [], "synced_name_match_ids": [],
        "sync_log": [], "auto_sync": {"enabled": False, "time": "01:00"},
    }), encoding="utf-8")

    # `raising=False` stand hier urspruenglich, und der Blindpruefer hat es
    # als Gefahr benannt: monkeypatch koennte bei einem umbenannten Feld
    # stumm ein NEUES, ungelesenes Attribut anlegen; der Store zeigte dann auf
    # den echten Pfad, und alle Faelle waeren gruen, ohne etwas zu pruefen.
    #
    # Nachgemessen ist die Sorge hier NICHT erreichbar: `Settings` ist ein
    # pydantic-Modell und weist ein unbekanntes Feld selbst ab
    # (`ValueError: "Settings" object has no field ...`), auch mit
    # `raising=False`. `raising=True` steht trotzdem, weil es die schaerfere
    # Vorgabe ist und nichts kostet — aber es traegt hier nichts, und das
    # gehoert dazugesagt, statt eine schoen klingende Zusage stehen zu lassen.
    monkeypatch.setattr(main.settings, "secret", TESTMARKE)
    monkeypatch.setattr(main.settings, "config_path", pfad)

    geschrieben: list[str] = []

    def merke_immich(name):
        echt = getattr(ImmichClient, name)

        async def gemerkt(self, *a, **k):
            geschrieben.append(f"immich.{name}")
            return await echt(self, *a, **k)

        return gemerkt

    def merke_speichern():
        echt = ConfigStore._save

        def gemerkt(self, *a, **k):
            geschrieben.append("store._save")
            return echt(self, *a, **k)

        return gemerkt

    with TestClient(main.app) as client:
        # Erst NACH dem Start instrumentieren: Der Startup selbst schreibt
        # legitim (Wanderung, user_id-Nachtrag) und gehoert nicht zur Anfrage.
        #
        # An der KLASSE, nicht am Modul des Aufrufers: Damit ist es
        # gleichgueltig, wie ein Router die Funktion importiert hat — genau
        # daran ist die vorige Fassung vorbeigelaufen.
        monkeypatch.setattr(ConfigStore, "_save", merke_speichern())
        for name in sorted(_immich_schreibsenken()):
            monkeypatch.setattr(ImmichClient, name, merke_immich(name))

        class Konto:
            async def get_person(self, _pid):
                return {"id": _pid}

        class Pool:
            def get_for_account(self, _acc):
                return Konto()

            def get(self, *_a, **_k):
                return Konto()

            def invalidate(self, *_a, **_k):
                pass

        # Ueber monkeypatch, nicht per Zuweisung: Der App-Zustand ist global
        # und ueberlebt das Lifespan des Testclients. Die vorige Fassung liess
        # die Attrappe fuer alle folgenden Tests stehen (Zweitstimme,
        # gemessen: `same fake object after: True`).
        monkeypatch.setattr(main.app.state, "client_pool", Pool(), raising=False)
        geschrieben.clear()
        yield client, geschrieben, pfad, main.app.state.store


# (Methode, Pfad, Koerper oder None, ERWARTETER error_key, warum)
#
# Der erwartete Schluessel ist KEIN Beiwerk. Ohne ihn hat sich in der ersten
# Fassung dreimal ein Fall als gruen ausgegeben, der etwas ganz anderes
# geprueft hat — und beide Pruefstimmen haben unabhaengig Umbauten gefunden,
# nach denen ALLE Faelle gruen blieben, ohne einen Endpunkt zu erreichen:
# alle Router abgehaengt (jede Antwort ein generisches 404), die Anmeldung
# abweisend (jede Antwort 401), ein neues Pflichtfeld im Koerper (jede
# Antwort ein 422 der Koerperpruefung). Jeder Schluessel unten ist GEMESSEN.
ABLEHNUNGEN = [
    # Der frueheste Weg dieses Endpunkts, und der einzige ohne echtes Immich:
    # `add_account` ruft ZUERST `client.validate()`.
    ("POST", "/api/accounts", {"name": "", "immich_url": "http://beispiel.invalid",
                               "api_key": "x"},
     "err_immich_unreachable", "Immich nicht erreichbar"),
    ("PUT", "/api/accounts/gibt-es-nicht", {"name": "X"},
     "err_account_not_found", "unbekanntes Konto"),
    ("DELETE", "/api/accounts/gibt-es-nicht", None,
     "err_account_not_found", "unbekanntes Konto"),
    ("POST", "/api/accounts/gibt-es-nicht/refresh", None,
     "err_account_not_found", "unbekanntes Konto"),
    ("POST", "/api/sync/names", {"match_id": "gibt-es-nicht", "name": "X"},
     "err_match_not_found", "unbekanntes Match"),
    # DIESER Fall ist mit Bedacht gewaehlt, und die Wahl ist GEMESSEN:
    # Ein Koerper mit `group_id: "gibt-es-nicht"` waere hier wertlos — den
    # faengt die FRUEHE Schranke (#81) gleich am Anfang des Endpunkts ab, also
    # weit vor jedem Schreibvorgang. Er kann nicht zeigen, ob eine SPAETE
    # Ablehnung hinter einem Schreibvorgang steht; genau daran ist eine
    # fruehere Fassung dieser Tabelle gescheitert.
    #
    # Das Aufloesen des Albumnamens ist die SPAETESTE Ablehnung dieses
    # Endpunkts — und genau die, die einmal hinter `sync_names_multi` stand.
    ("POST", "/api/sync/names-multi",
     {"persons": [{"account_id": "konto-1", "person_id": "p1"},
                  {"account_id": "konto-2", "person_id": "p2"}],
      "canonical_name": "Testname", "existing_album_id": "ia-9"},
     "err_album_name_required",
     "Albumname nicht aufloesbar — die SPAETESTE Ablehnung dieses Endpunkts"),
    ("POST", "/api/sync/extend",
     {"managed_album_id": "gibt-es-nicht", "account_id": "konto-1",
      "person_id": "p9"},
     "err_managed_album_not_found", "unbekanntes verwaltetes Album"),
    ("POST", "/api/sync/album",
     {"match_id": "gibt-es-nicht", "owner_account_id": "konto-1",
      "album_name": "X"},
     "err_match_not_found", "unbekanntes Match"),
    ("POST", "/api/sync/album/gibt-es-nicht/refresh", None,
     "err_managed_album_not_found", "unbekanntes verwaltetes Album"),
    ("DELETE", "/api/sync/albums/gibt-es-nicht", None,
     "err_managed_album_not_found", "unbekanntes verwaltetes Album"),
    ("POST", "/api/sync/undo", {"log_entry_id": "gibt-es-nicht"},
     "err_log_entry_not_found", "unbekannter Protokolleintrag"),
    ("PUT", "/api/sync/autosync-config", {"enabled": True, "time": "25:99"},
     "err_invalid_time_format", "unmoegliche Uhrzeit"),
    # Das Feld heisst `token`. Die erste Fassung schickte `secret` und
    # scheiterte an der Koerperpruefung — der echte Ablehnungsweg
    # (Ratenbremse, `invalid_token`) wurde nie erreicht.
    ("POST", "/api/auth/login", {"token": "falsch"},
     "err_invalid_token", "falsches Geheimnis"),
]

# Endpunkte, die KEINEN Ablehnungsweg haben, den man ohne echte Instanz
# ausloesen kann. Sie stehen hier NAMENTLICH, damit "kein Eintrag" nie
# unbemerkt bleibt — und mit dem Grund, warum sie ausgenommen sind.
OHNE_ABLEHNUNG = {
    ("DELETE", "/api/sync/log"): "nimmt keine Eingabe; es gibt nichts abzulehnen",
    ("POST", "/api/auth/logout"): "nimmt keine Eingabe; loescht nur das Keks",
    ("POST", "/api/matches/refresh"): "nimmt keine Eingabe; jede Ablehnung kaeme "
                                      "aus Immich, nicht aus der Anfrage",
    ("POST", "/api/matches/{match_id}/dismiss"):
        "nimmt JEDE Kennung an, antwortet 204 und schreibt — es gibt keinen "
        "Ablehnungsweg, und das ist Absicht (Owner-Entscheid 21.09.2026, "
        "#88): Eine Ablehnung ist eine Aussage ueber zwei PERSONEN, nicht "
        "ueber einen Vorschlag, der gerade angezeigt wird. Begruendung an "
        "`ConfigStore.dismiss_match`.",
}


SCHREIB_VERBEN = {"POST", "PUT", "PATCH", "DELETE"}

_listen_puffer: dict = {}


def _listen_fuer_datei(datei: pathlib.Path):
    """Alles, was Teil A ueber EINE Datei wissen muss — je Datei einmal.

    Die Helfer-Mengen enthalten AUCH importierte Namen, und die
    Modul-Paare loesen `modul.funktion()` ueber den Import auf. Beides
    kommt aus `_projekt_stand()`, also aus einem Graphen ueber alle
    Projektmodule — vorher endete die Analyse an der Dateigrenze (#90).
    """
    if datei not in _listen_puffer:
        stand = _projekt_stand()
        d = stand["dateien"][datei]

        def lokal(huelle):
            aus = {name for name in d["fns"] if (datei, name) in huelle}
            aus |= {lokal_name for lokal_name, ziel in d["namen"].items()
                    if ziel in huelle}
            return aus

        def ueber_module(huelle):
            return {(alias, name)
                    for alias, ziel in d["aliase"].items()
                    for name in stand["dateien"].get(ziel, {}).get("fns", {})
                    if (ziel, name) in huelle}

        _listen_puffer[datei] = (
            stand["schreibt_store"],
            _ablehnende_huelle(_funktionen(_baum("services/config_store.py"))),
            lokal(stand["lehnt"]),
            lokal(stand["schreibt"]),
            d["fehlernamen"],
            ueber_module(stand["lehnt"]),
            ueber_module(stand["schreibt"]),
        )
    return _listen_puffer[datei]


def _funktion_schreibt(fn) -> bool:
    """Erreicht diese Endpunkt-Funktion irgendwo einen Schreibvorgang?"""
    listen = _listen_fuer_datei(pathlib.Path(inspect.getsourcefile(fn)))
    for stmt in ast.walk(_quelle_einer_funktion(fn)):
        if not isinstance(stmt, ast.stmt):
            continue
        if any(art == "schreibt" for _z, art, _t in _ereignisse(stmt, *listen)):
            return True
    return False


def _schreibende_endpunkte() -> set:
    """Aus dem, was die Anwendung nach aussen anbietet.

    NICHT aus `app.routes`: Dort liegen `_IncludedRouter`-Huellen ohne `path`,
    und die erste Fassung bekam deshalb die LEERE MENGE — ein
    Vollstaendigkeitstest, der nie rot werden konnte.
    """
    aus = {(m.upper(), p) for p, ops in main.app.openapi()["paths"].items()
           for m in ops if m.upper() in SCHREIB_VERBEN}

    # Und das Verb ist nicht die Wirkung: Ein Endpunkt, der bei GET schreibt,
    # faellt sonst heraus, und diese Menge waere eine Menge von VERBEN statt
    # von schreibenden Endpunkten (Zweitstimme, gemessen — sie hat einen
    # schreibenden GET eingehaengt und er blieb unbemerkt).
    for pfad, methoden, fn in _montierte_endpunkte():
        if any(m in SCHREIB_VERBEN for m in methoden):
            continue
        if _funktion_schreibt(fn):
            aus |= {(m, pfad) for m in methoden if m != "HEAD"}
    return aus


def _passt(pfad: str, muster: str) -> bool:
    """`/api/accounts/gibt-es-nicht` passt auf `/api/accounts/{account_id}`.

    Platzhalter gelten NUR auf der Musterseite. Sonst gilt ein kuenftiges
    `POST /api/sync/{x}` durch die Zeile `/api/sync/names` als abgedeckt.
    """
    m_teile, p_teile = muster.strip("/").split("/"), pfad.strip("/").split("/")
    if len(m_teile) != len(p_teile):
        return False
    return all(m.startswith("{") or m == p for m, p in zip(m_teile, p_teile))


def test_jeder_schreibende_endpunkt_hat_einen_ablehnungsfall():
    """Ein NEUER Endpunkt ohne Eintrag macht diesen Waechter rot.

    Das ist der Teil, der die Tabelle am Altern hindert: Sie wird gegen das
    geprueft, was die Anwendung wirklich anbietet.
    """
    alle = _schreibende_endpunkte()
    assert alle, (
        "Die Endpunktmenge ist LEER. Damit prueft dieser Test nichts mehr — "
        "genau der Zustand, in dem die erste Fassung gruen war. Sieh nach, ob "
        "`app.openapi()` noch die erwartete Form hat."
    )

    # `_passt` behandelt jeden `{...}`-Abschnitt als GENAU EIN Segment. Ein
    # Starlette-Konverter bricht das: `{id:int}` wuerde auch auf Nicht-Zahlen
    # passen, `{rest:path}` gar nicht mehr auf mehrere Segmente (Zweitstimme,
    # gemessen). Heute benutzt dieses Projekt keinen; taucht einer auf, ist
    # das hier rot statt still falsch.
    mit_konverter = sorted(p for _m, p in alle if ":" in p)
    assert not mit_konverter, (
        "Diese Routen benutzen einen Starlette-Konverter, und `_passt` kann ihn "
        f"nicht abbilden: {mit_konverter}.\n"
        "Entweder den Konverter vermeiden oder `_passt` durch Starlettes "
        "eigenes `route.matches(scope)` ersetzen."
    )

    abgedeckt = set()
    tote_zeilen = []
    for methode, pfad, _koerper, _schluessel, _warum in ABLEHNUNGEN:
        treffer = {(m, muster) for m, muster in alle
                   if m == methode and _passt(pfad, muster)}
        if not treffer:
            tote_zeilen.append(f"ABLEHNUNGEN: {methode} {pfad}")
        abgedeckt |= treffer
    for (methode, muster), _grund in OHNE_ABLEHNUNG.items():
        treffer = {(m, echtes) for m, echtes in alle
                   if m == methode and echtes == muster}
        if not treffer:
            tote_zeilen.append(f"OHNE_ABLEHNUNG: {methode} {muster}")
        abgedeckt |= treffer

    # Die Gegenrichtung, und sie ist der teuer bezahlte Teil: Zwei Zeilen
    # zeigten auf `/api/faces/...`, waehrend der Router `/api/matches` heisst.
    # Eine wurde nie gefahren, die andere war gruen an einem 404.
    assert not tote_zeilen, (
        "Diese Tabellenzeilen treffen keine echte Route — Pfad oder Methode "
        "stimmen nicht:\n  " + "\n  ".join(tote_zeilen)
    )

    fehlend = sorted(alle - abgedeckt)
    assert not fehlend, (
        "Diese schreibenden Endpunkte haben keinen Ablehnungsfall. Trage sie in "
        "ABLEHNUNGEN ein — oder, wenn sie keinen Ablehnungsweg haben, mit "
        f"Begruendung in OHNE_ABLEHNUNG:\n  " + "\n  ".join(f"{m} {p}" for m, p in fehlend)
    )


@pytest.mark.parametrize(
    "methode,pfad,koerper,schluessel,warum", ABLEHNUNGEN,
    ids=lambda v: str(v)[:40],
)
def test_bis_zur_ablehnung_wird_nichts_geschrieben(
        aufbau, methode, pfad, koerper, schluessel, warum):
    client, geschrieben, datei, store = aufbau

    vorher_datei = datei.read_bytes()
    vorher_speicher = json.dumps(store._data, sort_keys=True)

    antwort = client.request(methode, pfad, headers=KOPF,
                             json=koerper if koerper is not None else None)

    assert 400 <= antwort.status_code < 500, (
        f"{methode} {pfad} sollte ablehnen ({warum}), kam mit {antwort.status_code}"
    )
    bekommen = antwort.json().get("error_key") if isinstance(antwort.json(), dict) else None
    assert bekommen == schluessel, (
        f"{methode} {pfad} lehnt ab, aber aus einem ANDEREN Grund als gedacht "
        f"({warum}). Erwartet {schluessel!r}, bekommen {bekommen!r} bei "
        f"{antwort.status_code}.\n"
        "Ohne diese Zusicherung wird der Fall auch an einer Koerperpruefung, "
        "einem generischen 404 oder der Anmeldung gruen — ohne den Endpunkt je "
        "erreicht zu haben."
    )
    assert datei.read_bytes() == vorher_datei, (
        f"{methode} {pfad} hat VOR der Ablehnung die Konfiguration geschrieben ({warum}).\n"
        "Alles, was ablehnen kann, gehoert vor den ersten Schreibvorgang."
    )
    assert json.dumps(store._data, sort_keys=True) == vorher_speicher, (
        f"{methode} {pfad} hat VOR der Ablehnung den Speicher veraendert ({warum}).\n"
        "Auch ohne Schreibvorgang auf die Platte sieht die laufende Anwendung das sofort."
    )
    assert geschrieben == [], (
        f"{methode} {pfad} hat VOR der Ablehnung geschrieben ({warum}): "
        f"{geschrieben}\n"
        "Diese Liste kommt aus den Schreibsenken selbst (`ConfigStore._save` und "
        "den veraendernden `ImmichClient`-Methoden), nicht aus einem Vergleich "
        "von Zustaenden — sie sieht deshalb auch einen Schreibvorgang, der "
        "denselben Inhalt zurueckschreibt."
    )


# ---------------------------------------------------------------------------
# BENANNTE GRENZEN
# ---------------------------------------------------------------------------
#
# Was dieser Waechter NICHT kann. Die Liste ist nicht aus Bescheidenheit
# geschrieben, sondern weil zwei Zusagen im Kopf dieser Datei schon einmal
# weiter reichten als die Messung — und eine zu weite Zusage ausgerechnet
# hier ist der Fehler, der spaeter jemanden trifft.
#
# Jeder Punkt ist von einer Pruefstimme GEMESSEN worden, nicht vermutet, und
# hat ein Issue. Beide Nacharbeitsrunden dieses Slices waren verbraucht
# (Owner-Regel: hoechstens zwei, danach landen und melden).
#
# TEIL A — Kontrollfluss
#   * ERLEDIGT (#89): Zwei Schleifenrunden; `break` und `continue` tragen
#     ihren Schreibvorgang weiter (der Kopf sieht `continue`, hinter der
#     Schleife steht auch `break`, das `else` sieht `break` NICHT); ein
#     `try`, dessen Wege alle die Funktion verlassen, beendet den Pfad.
#     Die erste Fassung dieses Slices meldete das als erledigt, ohne dass es
#     stimmte: `break`/`continue` lagen mit `return`/`raise` in einem Topf
#     und warfen den Schreibvorgang weg. Der Blindpruefer hat es gemessen.
#   * OFFEN: Keine Auswertungsreihenfolge innerhalb eines Ausdrucks — bei
#     `a() or b()` gilt beides als ausgefuehrt. Bei `match` wird nie
#     angenommen, dass die Faelle erschoepfend sind. Beides erzeugt
#     hoechstens FEHLFUNDE, keine Luecken; dafuer gibt es bisher keinen
#     gemessenen Fall im Baum.
#
# TEIL A — Reichweite
#   * ERLEDIGT (#90): Der Aufrufgraph geht ueber MODULGRENZEN, aufgeloest
#     ueber die Importe (nicht ueber blosse Namensgleichheit). Und jede
#     Projektfunktion, die ein Endpunkt ERREICHT, wird selbst analysiert —
#     ohne das bleibt die Luecke offen, wenn der Verstoss IM Helfer liegt:
#     Die Aufrufstelle sieht dann nur "schreibt und lehnt ab" und kann die
#     Reihenfolge darin nicht kennen.
#   * ERLEDIGT: FastAPI-eigene Routen (Swagger, OpenAPI, ReDoc) werden
#     ausgelassen — sie gehoeren uns nicht und polsterten die Mindestzahl.
#   * OFFEN: Per `app.mount(...)` eingehaengte Unter-Anwendungen sieht Teil A
#     nicht; `_montierte_endpunkte` steigt nur ueber `original_router` ab.
#   * OFFEN: Bei Aufrufen auf einem OBJEKT (`store.x()`) zaehlt der
#     METHODENNAME ohne Empfaenger — ein gleichnamiger Aufruf auf einem
#     fremden Objekt zaehlt mit. Bei Modul- und Namensaufrufen nicht mehr:
#     die gehen ueber die Importe.
#
# AUSNAHMELISTEN
#   * ERLEDIGT (#91): ERLAUBT deckt eine ANZAHL je (Ablehnung,
#     Schreibvorgang). Ein zweiter Fund mit demselben Text ist rot, ein
#     ANDERER Schreibvorgang vor derselben Ablehnung ebenfalls, und eine
#     Ausnahme, die mehr deckt als es Funde gibt, auch. Die Logik hat eine
#     eigene Selbstprobe gegen eine feste Vorlage — ohne sie liess sie sich
#     ersatzlos zurueckdrehen, ohne dass ein Test rot wurde.
#   * OFFEN (#91): OHNE_ABLEHNUNG prueft, dass die Zeile eine echte Route
#     trifft, aber nicht, ob die BEGRUENDUNG noch gilt.
#   * OFFEN, und es ist die Stelle, an der diese Datei einmal leise
#     verstummen wird: Die EINZIGE Probe von Teil A am echten Baum sind die
#     zwei ERLAUBT-Eintraege. Baut jemand `delete_account` so um, dass die
#     Existenzpruefung vor dem Loeschen steht, fordert die Fehlermeldung
#     woertlich auf, sie zu entfernen — und danach hat Teil A am echten Baum
#     keinen Fund mehr, der zeigt, dass er ueberhaupt noch etwas sieht. Die
#     Mechanik-Vorlage laeuft weiter gruen, weil sie erfunden ist.
#
# ABLEHNUNGSFORMEN (#92)
#   * `fehler = errors.x(); raise fehler`, `raise _fabrik()` und eine
#     Ablehnung als `JSONResponse` erkennt Teil A nicht. Teil B faengt sie,
#     sofern der Endpunkt einen Tabellenfall hat, der die Stelle erreicht.
#
# TEIL A — grundsaetzlich
#   * Er kennt nur NAMEN. `getattr(store, "clear_log")()` ist unsichtbar.
#     Dafuer ist Teil B da: Der misst die Senke, nicht den Aufrufer.
#
# TEIL B — grundsaetzlich
#   * Je Endpunkt EIN Ablehnungsweg, und zwar der spaeteste, den man ohne
#     echte Immich-Instanz ausloesen kann.
#   * `sync_service` hat zwei private Helfer mit echter Schreibwirkung
#     (`_refresh_managed_album_unlocked`, `_share_album_if_needed`). Teil A
#     zaehlt nur oeffentliche Dienstfunktionen; ihre WIRKUNG sieht Teil B,
#     weil sie durch die Immich-Senken laeuft.
#
# BEIDE
#   * Sie pruefen die REIHENFOLGE, nicht die Umkehrbarkeit. Ob ein
#     Schreibvorgang zurueckgerollt wird, ist eine andere Frage und hier
#     nicht beantwortet.
