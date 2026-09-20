import type { ManagedAlbum } from "../api/client";

/**
 * Gruppierung verwalteter Alben ueber die stabile Gruppenkennung (#78).
 *
 * Bis v1.6.0 lag diese Regel dreifach im Frontend und ein viertes Mal im
 * Backend, jedes Mal als `album_name.trim().toLowerCase()`. Der Name war damit
 * der Schluessel — und ein Umbenennen zerlegte die Gruppe still, waehrend zwei
 * zufaellig gleichnamige Alben zu einer verschmolzen. Hier steht die Regel
 * jetzt einmal; `group_id` traegt die Zugehoerigkeit, `album_name` ist
 * Anzeigetext.
 *
 * Geteilt wird die REGEL, nicht die Form: Die Komponenten bauen ihre eigenen
 * Gruppen-Objekte (AlbumsOverview ohne, ExtendMatch mit `primary_album`), und
 * eine gemeinsame Form haette nur eine Kopie durch einen Zwang ersetzt.
 */

/** Alben nach Gruppenkennung buendeln, in der Reihenfolge des ersten Auftretens. */
export function bucketByGroup(albums: ManagedAlbum[]): ManagedAlbum[][] {
  const map = new Map<string, ManagedAlbum[]>();
  for (const a of albums) {
    if (!map.has(a.group_id)) map.set(a.group_id, []);
    map.get(a.group_id)!.push(a);
  }
  return Array.from(map.values());
}

/**
 * Personen einer Gruppe zusammenfuehren, ohne Doppelte.
 *
 * Der Schluessel traegt Konto UND Person: Zwei Immich-Instanzen koennen
 * dieselbe Personen-Kennung vergeben.
 */
export function mergePersonRefs(group: ManagedAlbum[]): ManagedAlbum["person_refs"] {
  const seen = new Set<string>();
  const refs: ManagedAlbum["person_refs"] = [];
  for (const album of group) {
    for (const ref of album.person_refs) {
      const key = `${ref.account_id}::${ref.person_id}`;
      if (!seen.has(key)) {
        seen.add(key);
        refs.push(ref);
      }
    }
  }
  return refs;
}

/**
 * Gruppenkennung -> alle Personen dieser Gruppe.
 *
 * Grundlage der transitiven Zugehoerigkeit: Sind p1+p2 und p2+p3 in einer
 * Gruppe, gilt auch p1+p3 als versorgt. Gegenstueck zu `enrich_matches`
 * im Backend.
 */
export function personIdsByGroup(albums: ManagedAlbum[]): Map<string, Set<string>> {
  const map = new Map<string, Set<string>>();
  for (const album of albums) {
    let ids = map.get(album.group_id);
    if (!ids) {
      ids = new Set<string>();
      map.set(album.group_id, ids);
    }
    for (const ref of album.person_refs) ids.add(ref.person_id);
  }
  return map;
}

/**
 * Das Album, dessen Gruppe BEIDE Personen eines Matches enthaelt — und die
 * Groesse dieser Gruppe.
 *
 * Lag bis zur Nacharbeit zu #78 als Schleife in MatchSuggestions. Dort war
 * sie von keinem Test erreichbar: Der Rueckbau auf
 * `album_name.trim().toLowerCase()` liess beide Gates gruen (gemessen von
 * zwei Panel-Stimmen). Hier ist sie pruefbar, und in der Komponente bleibt
 * ein Aufruf statt einer Regel.
 *
 * Gewaehlt wird das Album mit den meisten Personen — das ist der Eintrag,
 * dessen Anzeigename die Gruppe am besten beschreibt.
 */
export function createGroupLookup(albums: ManagedAlbum[]) {
  // Die Personenkarte EINMAL bauen, nicht je Zeile. Die erste Fassung dieser
  // Auslagerung rief die Suche innerhalb der Zeilenschleife auf und baute die
  // Karte bei jedem Aufruf neu — aus O(Alben) je Zeichnung wurde
  // O(Vorschlaege x Alben). Vorher lag sie in einem useMemo; dieser Aufruf
  // stellt das wieder her (Blindpruefer 20.09.2026).
  const byGroup = personIdsByGroup(albums);
  return {
    forPair(personIdA: string, personIdB: string) {
      const album = albums
        .filter((a) => {
          const group = byGroup.get(a.group_id);
          return !!group && group.has(personIdA) && group.has(personIdB);
        })
        .sort((a, b) => b.person_refs.length - a.person_refs.length)[0];
      return {
        album,
        groupPersonCount: album ? (byGroup.get(album.group_id)?.size ?? 0) : 0,
      };
    },
  };
}

export function findGroupAlbumForPair(
  albums: ManagedAlbum[],
  personIdA: string,
  personIdB: string
): { album: ManagedAlbum | undefined; groupPersonCount: number } {
  return createGroupLookup(albums).forPair(personIdA, personIdB);
}
