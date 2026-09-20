import { describe, expect, it } from "vitest";
import {
  bucketByGroup,
  findGroupAlbumForPair,
  mergePersonRefs,
  personIdsByGroup,
} from "./albumGroups";
import type { ManagedAlbum } from "../api/client";

function album(id: string, album_name: string, group_id: string, personen: string[]): ManagedAlbum {
  return {
    id,
    match_id: `match-${id}`,
    album_id: `immich-${id}`,
    album_name,
    group_id,
    owner_account_id: "konto-1",
    person_refs: personen.map((p) => ({
      account_id: "konto-1",
      person_id: p,
      person_name: p,
      account_name: "konto-1",
      account_color: "#000",
    })),
    linked_match_ids: [],
    created_at: "2026-01-01T00:00:00+00:00",
    total_assets: 0,
  };
}

describe("bucketByGroup", () => {
  it("haelt eine Gruppe zusammen, auch wenn die Alben verschieden heissen", () => {
    // Der Kern von #78: Umbenennen darf die Gruppe nicht zerlegen.
    const eimer = bucketByGroup([
      album("a1", "Familie", "gruppe-1", ["p1"]),
      album("a2", "Familie 2024", "gruppe-1", ["p2"]),
    ]);

    expect(eimer).toHaveLength(1);
    expect(eimer[0].map((a) => a.id).sort()).toEqual(["a1", "a2"]);
  });

  it("verschmilzt gleichnamige fremde Gruppen nicht", () => {
    const eimer = bucketByGroup([
      album("a1", "Familie", "gruppe-1", ["p1"]),
      album("a2", "Familie", "gruppe-2", ["p2"]),
    ]);

    expect(eimer).toHaveLength(2);
  });

  it("erhaelt die Reihenfolge des ersten Auftretens", () => {
    // Die Anzeige haengt daran: die Komponenten waehlen spaeter aus jedem
    // Eimer ein fuehrendes Album, und eine wechselnde Reihenfolge liesse die
    // Liste bei jedem Neuzeichnen springen.
    const eimer = bucketByGroup([
      album("a1", "Urlaub", "gruppe-2", ["p1"]),
      album("a2", "Familie", "gruppe-1", ["p2"]),
      album("a3", "Urlaub", "gruppe-2", ["p3"]),
    ]);

    expect(eimer.map((g) => g[0].id)).toEqual(["a1", "a2"]);
  });
});

describe("mergePersonRefs", () => {
  it("entdoppelt ueber Konto UND Person", () => {
    const gruppe = [
      album("a1", "Familie", "gruppe-1", ["p1", "p2"]),
      album("a2", "Familie", "gruppe-1", ["p2", "p3"]),
    ];

    expect(mergePersonRefs(gruppe).map((r) => r.person_id)).toEqual(["p1", "p2", "p3"]);
  });

  it("haelt gleiche Person-Kennungen aus verschiedenen Konten auseinander", () => {
    // Zwei Immich-Instanzen koennen dieselbe Personen-Kennung vergeben; der
    // Schluessel muss deshalb beides tragen.
    const a = album("a1", "Familie", "gruppe-1", ["p1"]);
    const b = album("a2", "Familie", "gruppe-1", ["p1"]);
    b.person_refs[0].account_id = "konto-2";

    expect(mergePersonRefs([a, b])).toHaveLength(2);
  });
});

describe("personIdsByGroup", () => {
  it("sammelt alle Personen einer Gruppe ueber Albumgrenzen hinweg", () => {
    const karte = personIdsByGroup([
      album("a1", "Familie", "gruppe-1", ["p1", "p2"]),
      album("a2", "Anders benannt", "gruppe-1", ["p2", "p3"]),
      album("a3", "Familie", "gruppe-2", ["p9"]),
    ]);

    expect([...(karte.get("gruppe-1") ?? [])].sort()).toEqual(["p1", "p2", "p3"]);
    expect([...(karte.get("gruppe-2") ?? [])]).toEqual(["p9"]);
  });
});

describe("findGroupAlbumForPair", () => {
  it("findet das Album ueber die Gruppe, auch bei verschiedenen Namen", () => {
    const { album: gefunden, groupPersonCount } = findGroupAlbumForPair(
      [
        album("a1", "Familie", "gruppe-1", ["p1", "p2"]),
        album("a2", "Anders benannt", "gruppe-1", ["p2", "p3"]),
      ],
      "p1",
      "p3"
    );

    expect(gefunden?.id).toBe("a1");
    expect(groupPersonCount).toBe(3);
  });

  it("verbindet zwei gleichnamige, aber fremde Gruppen nicht", () => {
    // Sonst gilt ein Paar als versorgt, fuer das kein Album existiert — und
    // der Vorschlag verschwindet still.
    const { album: gefunden, groupPersonCount } = findGroupAlbumForPair(
      [
        album("a1", "Familie", "gruppe-1", ["p1", "p2"]),
        album("a2", "Familie", "gruppe-2", ["p2", "p3"]),
      ],
      "p1",
      "p3"
    );

    expect(gefunden).toBeUndefined();
    expect(groupPersonCount).toBe(0);
  });
});
