import { describe, expect, it } from "vitest";
import type { LinkedPerson, Match, Person } from "../api/client";
import { isMatchLinked } from "./MatchSuggestions";
import { linkedDisplayNames } from "./PeopleGrid";

const refs = [
  {
    account_id: "account-a",
    person_id: "person-a",
    person_name: "Alex",
    account_name: "Alice",
    account_color: "#111111",
  },
  {
    account_id: "account-b",
    person_id: "person-b",
    person_name: "Alejandro",
    account_name: "Bob",
    account_color: "#222222",
  },
];

const linkedPerson: LinkedPerson = {
  id: "linked-1",
  display_name: "Alex",
  person_refs: refs,
  created_at: "2026-09-10T00:00:00Z",
};

const match = {
  id: "match-1",
  person_a: refs[0],
  person_b: refs[1],
  confidence: 0.9,
  reasons: ["name_similarity"],
  status: "pending",
  has_album: false,
  names_synced: false,
} satisfies Match;

describe("linked people helpers", () => {
  it("recognises when both sides of a suggestion belong to one linked identity", () => {
    expect(isMatchLinked(match, [linkedPerson])).toBe(true);
    expect(
      isMatchLinked({ ...match, person_b: { ...refs[1], person_id: "other" } }, [linkedPerson])
    ).toBe(false);
  });

  it("shows every distinct current profile name", () => {
    const people = refs.map((ref, index) => ({
      id: ref.person_id,
      name: index === 0 ? "Alexander" : ref.person_name,
      thumbnail_path: null,
      asset_count: 10,
      is_hidden: false,
      account_id: ref.account_id,
      account_name: ref.account_name,
      account_color: ref.account_color,
    })) satisfies Person[];

    expect(linkedDisplayNames(linkedPerson, people)).toEqual(["Alexander", "Alejandro"]);
  });
});
